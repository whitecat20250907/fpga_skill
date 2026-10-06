
`timescale 1ns/1ps
module tb_counter_event_equivalence;
    reg clk=0;
    always #2.5 clk=~clk;
    reg reset_n=0,enable=1,count_enable=1,in_valid=0;
    reg [31:0] in_data=0;
    wire [42:0] candidate_control,reference_control;
    wire [159:0] candidate_counts,reference_counts;
    wire candidate_sync,reference_sync;
    wire [31:0] cp,rp;
    wire [2:0] cb,rb;
    wire cd,cv,cl,cf,ci,cil,ce,rd,rv,rl,rf,ri,ril,re;
    wire [31:0] cr,cc,cec,cw,ct,rr,rc,rec,rw,rt;
    csi_rx_packet_handler #(.GAP_TIMEOUT(64)) candidate(
        .I_clock(clk),.I_reset_n(reset_n),.I_enable(enable),.I_count_enable(count_enable),
        .I_data(in_data),.I_data_valid(in_valid),.O_packet_done(cd),.O_sync_wait(candidate_sync),
        .O_payload_out(cp),.O_payload_valid(cv),.O_payload_bytes(cb),.O_payload_last(cl),
        .O_vsync_out(cf),.O_in_frame(ci),.O_in_line(cil),.O_packet_error(ce),
        .O_raw_packets(cr),.O_crc_errors(cc),.O_ecc_errors(cec),.O_wc_errors(cw),.O_timeout_errors(ct));
    csi_rx_packet_handler_reference #(.GAP_TIMEOUT(64)) reference(
        .I_clock(clk),.I_reset_n(reset_n),.I_enable(enable),.I_count_enable(count_enable),
        .I_data(in_data),.I_data_valid(in_valid),.O_packet_done(rd),.O_sync_wait(reference_sync),
        .O_payload_out(rp),.O_payload_valid(rv),.O_payload_bytes(rb),.O_payload_last(rl),
        .O_vsync_out(rf),.O_in_frame(ri),.O_in_line(ril),.O_packet_error(re),
        .O_raw_packets(rr),.O_crc_errors(rc),.O_ecc_errors(rec),.O_wc_errors(rw),.O_timeout_errors(rt));
    assign candidate_control={cp,cb,cd,candidate_sync,cv,cl,cf,ci,cil,ce};
    assign reference_control={rp,rb,rd,reference_sync,rv,rl,rf,ri,ril,re};
    assign candidate_counts={cr,cc,cec,cw,ct};
    assign reference_counts={rr,rc,rec,rw,rt};
    reg [159:0] previous_reference_counts=0;
    integer compared_cycles=0,qualified_cases=0,blocked_cases=0;
    reg test_done=0;
    // The exact golden count is delayed one clock, rather than relaxed.
    // Async reset discards the pending event and clears the delay scoreboard.
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            previous_reference_counts=0;
            #0.2;
            if(candidate_counts!==160'b0 || reference_counts!==160'b0)
                $fatal(1,"Asynchronous counter reset mismatch");
        end else begin
            #0.2;
            if(candidate_control!==reference_control)
                $fatal(1,"Protocol/control changed candidate=%h reference=%h",candidate_control,reference_control);
            if(candidate_counts!==previous_reference_counts)
                $fatal(1,"One-cycle exact counter mismatch candidate=%h golden_delayed=%h",candidate_counts,previous_reference_counts);
            previous_reference_counts=reference_counts;
            compared_cycles=compared_cycles+1;
        end
    end
    reg [23:0] hdr_data=0;
    wire [7:0] hdr_ecc;
    csi_rx_hdr_ecc encoder(.data(hdr_data),.ecc(hdr_ecc));
    function automatic [15:0] stimulus_crc;
        input [15:0] crc;
        input [7:0] data;
        reg [15:0] v;
        integer bitno;
        begin
            v=crc;
            for(bitno=0;bitno<8;bitno=bitno+1)
                if(v[0]^data[bitno])v=(v>>1)^16'h8408;
                else v=v>>1;
            stimulus_crc=v;
        end
    endfunction
    task automatic idle(input integer cycles);
        begin
            @(negedge clk);in_valid=0;in_data=0;
            repeat(cycles)@(negedge clk);
        end
    endtask
    task automatic header(input [5:0] dt,input integer wc,input bad_ecc);
        reg [31:0] h;
        begin
            wait(candidate_sync && reference_sync);
            @(negedge clk);hdr_data={wc[15:0],2'b00,dt};#0.1;
            h={hdr_ecc,hdr_data};if(bad_ecc)h[24]=~h[24];
            in_data=h;in_valid=1;
        end
    endtask
    task automatic word(input [31:0] value);
        begin @(negedge clk);in_data=value;in_valid=1;end
    endtask
    task automatic raw5(input bad_crc);
        reg [15:0] c;
        begin
            header(0,0,0);idle(12);
            c=16'hffff;
            c=stimulus_crc(c,8'h13);c=stimulus_crc(c,8'h27);
            c=stimulus_crc(c,8'h91);c=stimulus_crc(c,8'h3a);c=stimulus_crc(c,8'hc5);
            if(bad_crc)c=c^16'h0100;
            header(6'h2b,5,0);word(32'h3a912713);word({8'h55,c[15:8],c[7:0],8'hc5});
        end
    endtask
    // Returns immediately after the decision clock; live gates reverse before
    // the counter clock. Counts must follow the earlier captured qualification.
    task automatic event_case(input integer kind,input qualified);
        begin
            @(negedge clk);enable=1;count_enable=qualified;in_valid=0;
            case(kind)
                0:raw5(0);
                1:raw5(1);
                2:header(6'h2b,10,1);
                3:header(6'h2b,7,0);
                4:begin
                    header(6'h2b,10,0);
                    @(negedge clk);in_valid=0;
                    repeat(63)@(negedge clk);
                    // The next posedge is the 64th empty body cycle.
                end
            endcase
            @(posedge clk);#0.4;
            @(negedge clk);count_enable=~qualified;enable=0;in_valid=0;
            repeat(4)@(negedge clk);
            enable=1;idle(12);
            if(qualified)qualified_cases=qualified_cases+1;
            else blocked_cases=blocked_cases+1;
        end
    endtask
    integer kind;
    initial begin
        #30;@(negedge clk);reset_n=1;idle(12);
        for(kind=0;kind<5;kind=kind+1)begin
            event_case(kind,1);event_case(kind,0);
        end
        idle(4);
        if(candidate_counts!=={32'd1,32'd1,32'd1,32'd1,32'd1})
            $fatal(1,"Qualified/blocked event totals incorrect: %h",candidate_counts);
        $display("PASS event qualification: five captured-enabled events survive live gates off; five captured-disabled events remain blocked after gates on");
        // Drop a newly registered ECC event by asserting reset between clocks.
        @(negedge clk);enable=1;count_enable=1;
        header(6'h2b,10,1);@(posedge clk);#0.4;reset_n=0;in_valid=0;
        #0.5;
        if(candidate_counts!==160'b0 || reference_counts!==160'b0)
            $fatal(1,"Reset did not clear pending diagnostics");
        repeat(3)@(negedge clk);reset_n=1;idle(12);
        if(candidate_counts!==160'b0)$fatal(1,"Pending pre-reset event reappeared");
        event_case(2,1);idle(4);
        if(candidate_counts!=={32'd0,32'd0,32'd1,32'd0,32'd0})
            $fatal(1,"Post-reset exact totals incorrect");
        test_done=1;
        $display("PASS one-cycle counter/control equivalence cycles=%0d qualified=%0d blocked=%0d reset_pending_event_verified",compared_cycles,qualified_cases,blocked_cases);
        $finish;
    end
    initial begin #100000;$fatal(1,"Counter equivalence simulation timeout");end
endmodule
