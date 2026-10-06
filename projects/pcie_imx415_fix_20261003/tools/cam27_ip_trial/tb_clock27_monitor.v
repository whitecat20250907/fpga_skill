`timescale 1ns/1ps
module tb_clock27_monitor;
    reg clk_ref=0, clk_test=0;
    reg ref_reset_n=0, test_reset_n=0, pll_lock=0, test_enable=1;
    real half_period=18.5185185185;
    always #20 clk_ref=~clk_ref;
    always begin
        #(half_period);
        if (test_enable) clk_test=~clk_test;
        else clk_test=0;
    end
    wire [31:0] measured_edges, window_index;
    wire measurement_valid, frequency_ok, lock_in_ref;
    cam_clock27_monitor #(.WINDOW_US(100)) dut (
        .clk_ref(clk_ref), .ref_reset_n(ref_reset_n),
        .clk_test(clk_test), .test_reset_n(test_reset_n), .pll_lock(pll_lock),
        .measured_edges(measured_edges), .window_index(window_index),
        .measurement_valid(measurement_valid), .frequency_ok(frequency_ok), .lock_in_ref(lock_in_ref)
    );
    reg done=0;
    task next_window;
        begin @(posedge measurement_valid); #1; end
    endtask
    integer i;
    initial begin
        #160; ref_reset_n=1; test_reset_n=1; pll_lock=1;
        for (i=0;i<8;i=i+1) begin
            next_window;
            if (!frequency_ok || measured_edges < 2698 || measured_edges > 2702)
                $fatal(1,"27MHz window %0d count=%0d ok=%b",i,measured_edges,frequency_ok);
        end
        pll_lock=0;
        next_window; next_window;
        if (frequency_ok || lock_in_ref) $fatal(1,"unlocked clock accepted");
        pll_lock=1;
        next_window; next_window;
        if (!frequency_ok) $fatal(1,"lock restored but stable 27MHz rejected");
        half_period=41.6666666667;
        next_window; next_window;
        for (i=0;i<5;i=i+1) begin
            next_window;
            if (frequency_ok || measured_edges < 1198 || measured_edges > 1202)
                $fatal(1,"12MHz not detected: count=%0d ok=%b",measured_edges,frequency_ok);
        end
        test_enable=0;
        next_window; next_window;
        next_window;
        if (frequency_ok || measured_edges != 0) $fatal(1,"stopped clock accepted");
        half_period=18.5185185185; test_enable=1;
        next_window; next_window;
        for (i=0;i<5;i=i+1) begin
            next_window;
            if (!frequency_ok) $fatal(1,"27MHz restoration failed");
        end
        done=1;
        $display("PASS monitor: 27MHz, loss-of-lock, 12MHz, stopped-clock, restore; windows=%0d",window_index);
        $finish;
    end
    initial begin #6000000; $fatal(1,"monitor timeout"); end
endmodule
