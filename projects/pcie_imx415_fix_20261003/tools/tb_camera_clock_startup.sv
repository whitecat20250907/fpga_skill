`timescale 1ns/1ps
// Ideal digital clocks only; no primitive/PLL, PCB, power-rail or sensor model.
module tb_camera_clock_startup;
    localparam real HALF24=1000000000.0/24000000.0/2.0;
    localparam real HALF27=1000000000.0/27000000.0/2.0;
    localparam real TOLERANCE_NS=0.003;
    reg clock24=0,clock27=0,run24=1,run27=1;
    initial forever begin #(HALF24);if(run24)clock24=~clock24;else clock24=0;end
    initial begin #4.137;forever begin #(HALF27);if(run27)clock27=~clock27;else clock27=0;end end
    reg pll27_lock_raw=0,ui_lock_raw=0,system_reset_n=0;
    wire sensor_xclr,sensor_mclk,config_reset_n;
    wire [15:0] status;
    camera_clock_startup dut(.clock24(clock24),.clock27(clock27),
        .pll27_lock_raw(pll27_lock_raw),.ui_lock_raw(ui_lock_raw),.system_reset_n(system_reset_n),
        .sensor_xclr(sensor_xclr),.sensor_mclk(sensor_mclk),.config_reset_n(config_reset_n),.status(status));
    reg test_done=0;
    realtime qualified_at=0,xclr_low_at=0,xclr_high_at=0;
    realtime first_mclk_at=0,ack_stable_at=0,high_at=0,low_at=0;
    realtime source_rise_at=0,source_fall_at=0;
    integer startup_epochs=0,full_highs=0,full_lows=0,reset_truncations=0;
    reg have_first_mclk=0,have_high=0,have_low=0;
    function automatic real magnitude(input real value);
        begin magnitude=value<0?-value:value;end
    endfunction
    always @(posedge clock27)source_rise_at=$realtime;
    always @(negedge clock27)source_fall_at=$realtime;
    always @(posedge status[1])qualified_at=$realtime;
    always @(posedge status[5])ack_stable_at=$realtime;
    always @(negedge sensor_xclr)begin
        xclr_low_at=$realtime;have_first_mclk=0;have_low=0;
    end
    always @(posedge sensor_xclr)begin
        xclr_high_at=$realtime;
        if($realtime-qualified_at<10000.0-TOLERANCE_NS)
            $fatal(1,"XCLR low after qualified locks too short %0.3f ns",$realtime-qualified_at);
        if($realtime-xclr_low_at<10000.0-TOLERANCE_NS)
            $fatal(1,"Actual XCLR low pulse too short");
        if(sensor_mclk!==0 || config_reset_n!==0)
            $fatal(1,"Clock/config active at XCLR release");
    end
    always @(posedge sensor_mclk)begin
        // The source and derived-clock monitors share this simulation time;
        // defer only to the inactive region so the source timestamp is current.
        #0;
        if(sensor_xclr!==1)$fatal(1,"MCLK rising while XCLR low");
        if(magnitude($realtime-source_rise_at)>TOLERANCE_NS)
            $fatal(1,"MCLK enabled mid-high instead of a complete source edge");
        if(!have_first_mclk)begin
            have_first_mclk=1;first_mclk_at=$realtime;
            if($realtime-xclr_high_at<2000.0-TOLERANCE_NS)
                $fatal(1,"XCLR high to first INCK too short %0.3f ns",$realtime-xclr_high_at);
        end else if(have_low)begin
            if(magnitude(($realtime-low_at)-HALF27)>TOLERANCE_NS)
                $fatal(1,"Normal MCLK low pulse not full width %0.3f ns",$realtime-low_at);
            full_lows=full_lows+1;
        end
        have_high=1;high_at=$realtime;
    end
    always @(negedge sensor_mclk)begin
        #0;
        if(have_high)begin
            if(magnitude(($realtime-high_at)-HALF27)>TOLERANCE_NS)begin
                if(sensor_xclr!==0)$fatal(1,"Runt/truncated MCLK while XCLR is high: %0.3f ns",$realtime-high_at);
                reset_truncations=reset_truncations+1;
            end else begin
                if(magnitude($realtime-source_fall_at)>TOLERANCE_NS)
                    $fatal(1,"Normal MCLK falling edge not the source falling edge");
                full_highs=full_highs+1;
            end
            have_high=0;
        end
        have_low=sensor_xclr;low_at=$realtime;
    end
    always @(posedge config_reset_n)begin
        if(sensor_xclr!==1 || status[5]!==1 || !have_first_mclk)
            $fatal(1,"I2C config released without reset/forwarded-clock acknowledgment");
        if($realtime-first_mclk_at<50000.0-TOLERANCE_NS)
            $fatal(1,"INCK to I2C-enable interval too short %0.3f ns",$realtime-first_mclk_at);
        if($realtime-ack_stable_at<50000.0-TOLERANCE_NS)
            $fatal(1,"Stable ACK to I2C-enable interval too short %0.3f ns",$realtime-ack_stable_at);
        startup_epochs=startup_epochs+1;
        $display("PASS startup epoch=%0d qualified-XCLR=%0.3fns XCLR-INCK=%0.3fns INCK-I2C=%0.3fns ACK-I2C=%0.3fns",startup_epochs,xclr_high_at-qualified_at,first_mclk_at-xclr_high_at,$realtime-first_mclk_at,$realtime-ack_stable_at);
    end
    task automatic expect_async_reset;
        begin
            #0.010;
            if(sensor_xclr!==0 || sensor_mclk!==0 || config_reset_n!==0)
                $fatal(1,"Reset/lock loss did not asynchronously clear XCLR first, MCLK and I2C");
        end
    endtask
    task automatic wait_running;
        begin
            wait(config_reset_n===1);#0.010;
            if(status[10:8]!==3'd5)$fatal(1,"Config released outside RUN state");
            repeat(16)@(posedge sensor_mclk);
        end
    endtask
    initial begin
        #75.913;ui_lock_raw=1;
        #19.777;pll27_lock_raw=1;system_reset_n=1;
        // This brief lock pulse is not long enough for synchronization/stability.
        #99.331;pll27_lock_raw=0;expect_async_reset();
        #777.117;pll27_lock_raw=1;
        wait_running();
        // Lose PLL lock in the middle of a forwarded HIGH pulse. The truncated
        // pulse is allowed only after XCLR went low, not by raw combinational gate.
        @(posedge sensor_mclk);#5.333;pll27_lock_raw=0;expect_async_reset();
        #7717.193;pll27_lock_raw=1;wait_running();
        // UI lock loss must assert reset even when its 24 MHz control clock has
        // stopped. Restoration must not release anything until that clock returns.
        @(negedge clock24);run24=0;
        #7.777;ui_lock_raw=0;expect_async_reset();
        #15000.271;ui_lock_raw=1;
        #10000.113;
        if(sensor_xclr!==0 || sensor_mclk!==0 || config_reset_n!==0)
            $fatal(1,"Reset release occurred without control-clock edges");
        run24=1;wait_running();
        // System reset with both PLL clocks/locks continuing, at another phase.
        @(posedge sensor_mclk);#11.791;system_reset_n=0;expect_async_reset();
        #13013.219;system_reset_n=1;wait_running();
        // A falsely HIGH raw lock with no 27 MHz clock cannot produce ACK or
        // release I2C during initial startup. This is not an analog PLL model.
        @(negedge sensor_mclk);#1.137;system_reset_n=0;expect_async_reset();run27=0;
        #1717.731;system_reset_n=1;
        #80000.151;
        if(sensor_mclk!==0 || config_reset_n!==0 || status[4]!==0 || status[10:8]!==3'd3)
            $fatal(1,"Missing 27 MHz clock falsely acknowledged/released configuration");
        $display("PASS missing startup source clock: no gate ACK and I2C remains in reset");
        #3.191;run27=1;wait_running();
        if(startup_epochs!=5 || full_highs<100 || full_lows<100 || reset_truncations<2)
            $fatal(1,"Coverage insufficient epochs=%0d highs=%0d lows=%0d async_stops=%0d",startup_epochs,full_highs,full_lows,reset_truncations);
        test_done=1;
        $display("PASS camera startup digital selfcheck epochs=%0d full_high=%0d full_low=%0d reset_only_truncations=%0d",startup_epochs,full_highs,full_lows,reset_truncations);
        $finish;
    end
    initial begin #1000000;$fatal(1,"Camera startup digital selfcheck timed out");end
endmodule
