`timescale 1ns/1ps
// Functional clock-divider stub only: native PH1 LCLK has no installed model.
// The sampler, IDELAY, GSR, reset chains and byte aligner are production RTL.
module rx_clk_gen #(parameter DEVICE="PH1A")(
    input I_mipi_clk_p,I_rst,output O_clk,O_clk_x2,O_clk_x4);
    assign O_clk=tb_csi_reset8.bclk;
    assign O_clk_x2=tb_csi_reset8.pclk;
    assign O_clk_x4=tb_csi_reset8.sclk;
endmodule

module tb_csi_reset8;
    reg [2:0] phase=0;
    integer p_offset=0,b_offset=0;
    wire [2:0] p_phase=phase+p_offset,b_phase=phase+b_offset;
    wire sclk=phase[0],pclk=p_phase[1],bclk=b_phase[2];
    reg running=1,refclk=0;
    always #1.122 if(running)phase=phase+1'b1;
    always #3.333 refclk=~refclk;
    reg reset_n=0,enable=1,wait_sync=1,packet_done=0;
    reg override_enable=0;
    reg [5:0] override_tap=0;
    reg [3:0] serial=0;
    wire [31:0] raw,aligned;
    wire [3:0] valid;
    wire byte_reset_n,sampler_reset_n,cal_done;
    wire [7:0] dbg_delay;
    wire [5:0] best_len;
    csi_rx_phy #(.MIPI_LAN(4),.DEVICE("PH1A")) dut(
        .I_debug_button(1'b1),.I_override_enable(override_enable),.I_override_tap(override_tap),
        .I_ref_clock(refclk),.I_clk_hs_rx_p(sclk),.I_reset_n(reset_n),
        .I_hs_data_p(serial),.I_enable(enable),.I_wait_for_sync(wait_sync),
        .I_packet_done(packet_done),.O_hs_div_clk(),.O_reset_out(byte_reset_n),
        .O_rx_byte_data_align_vaild(valid),.O_rx_byte_data_align(aligned),
        .O_delay_value(),.O_auto_delay_done(cal_done),.O_dbg_delay(dbg_delay),
        .O_dbg_best_len(best_len),.O_dbg_raw_bytes(raw),.O_sampler_reset_n(sampler_reset_n));
    // Scale only the loss timeout for a bounded clock-stop test. The production
    // 15M reference-cycle / 100ms blanking tolerance is unchanged in RTL.
    defparam dut.u_csi_rx_clock_det.LOSS_CYCLES=300;
    reg test_done=0,checking=0,pause_packet=0;
    integer received=0,packets=0,lane_bytes=0,reset_checks=0,override_checks=0;
    integer release_edges=0,k,clock_pauses=0,aborted_packets=0;
    reg [3:0] expected;
    function automatic [7:0] golden(input integer lane,input integer index);
        if(index==0)golden=8'hb8;
        else golden=(8'h20+lane*17+(index-1)*5);
    endfunction
    // Check the actual common reset chain, not merely each lane's output data.
    always @(posedge sclk or negedge dut.w_clock_present_n)begin
        if(!dut.w_clock_present_n)release_edges=0;
        else if(release_edges<3)release_edges=release_edges+1;
        #0.03;
        if(sampler_reset_n !== (release_edges==3))
            $fatal(1,"HS reset release wrong edge=%0d rst=%b",release_edges,sampler_reset_n);
        if(dut.gen_channel_wrapper[0].u_csi_rx_hs_data_phy.gen_ph1a.u_iddrx2.rst!==~sampler_reset_n ||
           dut.gen_channel_wrapper[1].u_csi_rx_hs_data_phy.gen_ph1a.u_iddrx2.rst!==~sampler_reset_n ||
           dut.gen_channel_wrapper[2].u_csi_rx_hs_data_phy.gen_ph1a.u_iddrx2.rst!==~sampler_reset_n ||
           dut.gen_channel_wrapper[3].u_csi_rx_hs_data_phy.gen_ph1a.u_iddrx2.rst!==~sampler_reset_n)
            $fatal(1,"PAD reset is not shared");
        reset_checks=reset_checks+1;
    end
    always @(posedge bclk)begin
        #0.10;
        if(checking && valid!=0)begin
            if(valid!==4'hf)$fatal(1,"Lane phase separated valid=%b",valid);
            for(k=0;k<4;k=k+1)begin
                if(aligned[k*8+:8]!==golden(k,received))
                    $fatal(1,"Absolute serial golden mismatch packet=%0d px=%0d lane=%0d expected=%h got=%h raw=%h p=%0d b=%0d",packets,received,k,golden(k,received),aligned[k*8+:8],raw,p_offset,b_offset);
                lane_bytes=lane_bytes+1;
            end
            wait_sync=0;
            received=received+1;
            if(received==25)checking=0;
        end
    end
    task automatic flush_zero;
        begin
            serial=0;checking=0;packet_done=1;wait_sync=1;
            repeat(3)@(negedge bclk);packet_done=0;
            repeat(64)@(negedge bclk);
            if(raw!==0||valid!==0)$fatal(1,"Zero flush retains stale byte raw=%h valid=%b",raw,valid);
        end
    endtask
    task automatic send_byte(input integer idx);
        integer bitidx,lane;
        begin
            for(bitidx=0;bitidx<8;bitidx=bitidx+1)begin
                @(sclk);#0.2;
                for(lane=0;lane<4;lane=lane+1)serial[lane]=(golden(lane,idx)>>bitidx)&1;
            end
        end
    endtask
    task automatic send_packet;
        integer idx,guard;
        begin
            flush_zero();received=0;checking=1;
            for(idx=0;idx<25;idx=idx+1)begin
                send_byte(idx);
                if(pause_packet && idx==10)begin
                    // Freeze all related clocks with a nonzero packet in flight.
                    // The reference clock continues. This pause is much shorter
                    // than production blanking tolerance and must not drop data.
                    #0.17;running=0;#50;running=1;clock_pauses=clock_pauses+1;
                end
            end
            @(sclk);#0.2;serial=0;
            guard=0;
            while(checking && guard<32)begin @(negedge bclk);guard=guard+1;end
            if(received!=25)$fatal(1,"Sync/payload incomplete received=%0d",received);
            packets=packets+1;flush_zero();
        end
    endtask
    task automatic short_reset(input real offset);
        begin
            @(negedge bclk);#(offset);reset_n=0;#0.06;
            if(sampler_reset_n!==0||byte_reset_n!==0||valid!==0)$fatal(1,"Short reset did not assert immediately");
            #0.19;reset_n=1;
            wait(byte_reset_n===1);repeat(4)@(negedge bclk);
        end
    endtask
    task automatic control_tests;
        begin
            force dut.w_auto_delay_value=6'd13;
            force dut.w_auto_delay_vaild=1'b0;
            force dut.w_auto_delay_done=1'b0;
            force dut.w_auto_delay_best_len=6'd0;
            @(negedge bclk);override_enable=1;override_tap=6'd35;#0.01;
            if(dbg_delay!==8'hc3||cal_done!==1||best_len!==0)$fatal(1,"Override enable/mask/real best_len wrong");
            @(posedge bclk);#0.1;if(dbg_delay!==8'h43)$fatal(1,"Override load not single beat");
            repeat(5)@(negedge bclk);
            if(dbg_delay!==8'h43)$fatal(1,"Stable override fabricated reload");
            override_tap=6'd7;#0.01;if(dbg_delay!==8'hc7)$fatal(1,"Changed tap not loaded");
            @(posedge bclk);#0.1;if(dbg_delay!==8'h47)$fatal(1,"Tap change reload remained asserted");
            @(negedge bclk);override_enable=0;#0.01;
            if(dbg_delay!==8'h8d||cal_done!==0)$fatal(1,"Override falling failed auto current tap reload");
            @(posedge bclk);#0.1;if(dbg_delay!==8'h0d)$fatal(1,"Auto restore load not single beat");
            @(negedge bclk);override_enable=1'bx;#0.01;
            if(dbg_delay!==8'h0d||cal_done!==0)$fatal(1,"Unconnected enable failed automatic fallback");
            override_enable=0;
            override_checks=override_checks+8;
            release dut.w_auto_delay_value;release dut.w_auto_delay_vaild;
            release dut.w_auto_delay_done;release dut.w_auto_delay_best_len;
        end
    endtask
    integer p,b,j;
    initial begin
        #80;reset_n=1;wait(byte_reset_n===1);control_tests();
        // Auto scan is not an analog eye model. Hold tap zero to check the
        // native delay/sample and absolute, lane-coded serialized bytes.
        override_enable=1;override_tap=0;
        for(p=0;p<2;p=p+1)for(b=0;b<4;b=b+1)begin
            reset_n=0;#5;running=0;phase=0;p_offset=p*2;b_offset=b*2;
            #4;running=1;#2;reset_n=1;wait(byte_reset_n===1);
            send_packet();
            for(j=0;j<8;j=j+1)begin short_reset(j*1.122+0.13);send_packet();end
            // Stop clocks before reset: assertion and release must not invent
            // HS edges; the sampler must remain reset until clocks restart.
            @(negedge bclk);#0.17;running=0;#1.07;reset_n=0;#0.06;
            if(sampler_reset_n!==0||valid!==0)$fatal(1,"Stopped reset failed assertion");
            #0.19;reset_n=1;#25;
            if(sampler_reset_n!==0||byte_reset_n!==0)$fatal(1,"Stopped clock fabricated reset release");
            running=1;wait(byte_reset_n===1);send_packet();
        end
        // Reference-domain loss detector must assert without source clocks.
        @(negedge bclk);#0.17;running=0;#2200;
        if(sampler_reset_n!==0||byte_reset_n!==0)$fatal(1,"Loss detector left sampler out of reset");
        running=1;wait(byte_reset_n===1);send_packet();
        // A reset during a qualified packet must suppress all four valid flags
        // without clock assistance. Then a fresh sync begins a complete packet.
        flush_zero();received=0;checking=1;
        for(j=0;j<10;j=j+1)send_byte(j);
        #0.17;checking=0;reset_n=0;#0.06;
        if(sampler_reset_n!==0||valid!==0)$fatal(1,"In-packet reset retained PAD/protocol valid");
        serial=0;#0.19;reset_n=1;wait(byte_reset_n===1);aborted_packets=1;
        send_packet();
        // Reapplying a persistent mailbox override after reset must load once.
        short_reset(0.13);
        if(dbg_delay[6]!==1||dbg_delay[5:0]!==0)$fatal(1,"Mailbox override lost through reset");
        pause_packet=1;send_packet();pause_packet=0;
        if(packets!=83||lane_bytes<8300||override_checks!=8||reset_checks<1000||clock_pauses!=1||aborted_packets!=1)$fatal(1,"Insufficient coverage");
        test_done=1;
        $display("PASS CSI_RESET8 absolute serial golden: packets=%0d lane_bytes=%0d phase_pairs=8 short_resets=66 stopped_resets=8 clock_loss=1 in_packet_abort=%0d in_packet_clock_pause=%0d reset_checks=%0d override_checks=%0d",packets,lane_bytes,aborted_packets,clock_pauses,reset_checks,override_checks);
        $finish;
    end
    initial begin #1000000;$fatal(1,"Test timed out");end
endmodule
