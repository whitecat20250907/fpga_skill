`timescale 1ns/1ps
module tb_sampler_reset;
    reg [2:0] phase=0;
    reg running=1;
    wire sclk=phase[0],pclk=phase[1],bclk=phase[2];
    // Preserves a genuine 4:2:1 relationship; stops freeze all phases.
    always #1.122 if(running)phase=phase+1'b1;
    reg reset_n=0;
    reg [3:0] serial=0;
    reg random_bits=0;
    integer seed=32'h13579bdf;
    always @(sclk)begin
        #0.20;
        if(random_bits)serial=$random(seed);
        else serial=0;
    end
    wire [31:0] candidate_bytes,reference_bytes;
    wire [3:0] candidate_valid,reference_valid;
    wire [31:0] candidate_aligned,reference_aligned;
    genvar lane;
    generate for(lane=0;lane<4;lane=lane+1)begin: lanes
        csi_rx_hs_data_phy #(.DEVICE("PH1A")) candidate(
            .I_rxclk(bclk),.I_rxclk_div_x2(pclk),.I_rxclk_div_x4(sclk),
            .I_reset_n(reset_n),.I_hs_data_p(serial[lane]),
            .I_delay_value(6'd0),.I_delay_vaild(1'b0),
            .O_rx_data(candidate_bytes[lane*8+:8]),.O_delay_data_val());
        csi_rx_hs_data_phy_reference #(.DEVICE("PH1A")) reference(
            .I_rxclk(bclk),.I_rxclk_div_x2(pclk),.I_rxclk_div_x4(sclk),
            .I_reset_n(reset_n),.I_hs_data_p(serial[lane]),
            .I_delay_value(6'd0),.I_delay_vaild(1'b0),
            .O_rx_data(reference_bytes[lane*8+:8]),.O_delay_data_val());
        csi_rx_byte_align ca(.I_clock(bclk),.I_reset_n(reset_n),.I_enable(1'b1),
            .I_lan_data_in(candidate_bytes[lane*8+:8]),.I_wait_for_sync(1'b1),
            .I_packet_done(1'b0),.O_data_out_vaild(candidate_valid[lane]),
            .O_data_out(candidate_aligned[lane*8+:8]));
        csi_rx_byte_align ra(.I_clock(bclk),.I_reset_n(reset_n),.I_enable(1'b1),
            .I_lan_data_in(reference_bytes[lane*8+:8]),.I_wait_for_sync(1'b1),
            .I_packet_done(1'b0),.O_data_out_vaild(reference_valid[lane]),
            .O_data_out(reference_aligned[lane*8+:8]));
    end endgenerate
    integer age=0,compared=0,resets=0,stops=0,nonzero_compared=0,aligned_compared=0,k;
    reg test_done=0;
    always @(posedge bclk or negedge reset_n)begin
        if(!reset_n)age=0;
        else begin
            age=age+1;
            #0.1;
            // Reset-free sampling does not promise blank raw bytes. Its bounded
            // contents must converge to the unchanged actual vendor primitive.
            if(age>=8)begin
                if(candidate_bytes!==reference_bytes)
                    $fatal(1,"Sampler byte/pixel ordering changed age=%0d candidate=%h reference=%h",age,candidate_bytes,reference_bytes);
                compared=compared+1;
                if(candidate_bytes!=0)nonzero_compared=nonzero_compared+1;
            end
            // The byte-align contract defines its byte only when lane valid.
            // A rejected transient sync can leave different inactive offsets;
            // this is explicitly excluded from the qualified-byte comparison.
            if(age>=64)begin
                if(candidate_valid!==reference_valid)
                    $fatal(1,"Post-settle actual byte-align valid differed age=%0d cv=%b rv=%b",age,candidate_valid,reference_valid);
                for(k=0;k<4;k=k+1)if(candidate_valid[k])begin
                    if(candidate_aligned[k*8+:8]!==reference_aligned[k*8+:8])
                        $fatal(1,"Qualified lane byte changed age=%0d lane=%0d",age,k);
                    aligned_compared=aligned_compared+1;
                end
            end
        end
    end
    task automatic flush_zero;
        begin
            random_bits=0;
            repeat(64)@(negedge bclk);
            #0.1;
            if(candidate_bytes!==0 || reference_bytes!==0 || candidate_valid!==0 || reference_valid!==0)
                $fatal(1,"Stale sampled/sync state survived 64 zero byte clocks candidate=%h valid=%b",candidate_bytes,candidate_valid);
            if(candidate_aligned!==reference_aligned)
                $fatal(1,"Post-flush byte align differs");
        end
    endtask
    task automatic pulse_reset(input real phase_delay,input real width);
        begin
            @(negedge bclk);#(phase_delay);reset_n=0;resets=resets+1;
            #0.02;
            if(candidate_valid!==0 || reference_valid!==0)
                $fatal(1,"Protocol valid not asynchronously reset");
            #(width);reset_n=1;
        end
    endtask
    integer j;
    initial begin
        #80;reset_n=1;flush_zero();
        random_bits=1;repeat(1000)@(negedge bclk);
        // Release at all eight bit phases with a sub-byte-clock reset pulse.
        for(j=0;j<8;j=j+1)begin
            pulse_reset(j*1.122+0.13,0.25);
            random_bits=1;repeat(96)@(negedge bclk);
            flush_zero();random_bits=1;
        end
        // Reset with every clock stopped. No clock may be needed to suppress
        // protocol valid; sampling resumes and is overwritten after restart.
        for(j=0;j<4;j=j+1)begin
            random_bits=1;repeat(24)@(negedge bclk);
            #0.17;running=0;stops=stops+1;
            #1.07;reset_n=0;resets=resets+1;
            #0.02;
            if(candidate_valid!==0 || reference_valid!==0)$fatal(1,"Stopped-clock reset left valid");
            #0.33;reset_n=1;
            #15.0;
            if(candidate_valid!==0 || reference_valid!==0)$fatal(1,"Stopped-clock reset release fabricated valid");
            running=1;flush_zero();
        end
        // Clock pause without reset preserves the actual pipeline history.
        random_bits=1;repeat(128)@(negedge bclk);
        #0.17;running=0;stops=stops+1;#30;running=1;
        repeat(1024)@(negedge bclk);flush_zero();
        if(compared<3000 || nonzero_compared<2500 || resets!=12 || stops!=5)
            $fatal(1,"Insufficient reset-free sampler coverage compared=%0d nonzero=%0d",compared,nonzero_compared);
        test_done=1;
        $display("PASS actual PH1 IDDRx2 reset-free/reference byte equality 4lanes compared=%0d nonzero=%0d resets=%0d stops=%0d aligned=%0d; byte-align reset/zero-flush",compared,nonzero_compared,resets,stops,aligned_compared);
        $finish;
    end
    initial begin #100000;$fatal(1,"Sampler test timeout");end
endmodule
