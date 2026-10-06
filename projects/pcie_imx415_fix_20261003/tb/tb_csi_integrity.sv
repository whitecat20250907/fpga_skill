`timescale 1ns/1ps
module tb_csi_integrity;
    reg clk=0, video_clk=0;
    always #2.5 clk=~clk;
    always #3.4 video_clk=~video_clk;
    reg reset_n=0, enable=1, in_valid=0;
    reg [31:0] in_data=0;
    wire packet_done,sync_wait,payload_valid,payload_last,fs,frame,line,packet_error;
    wire [31:0] payload, raw_packets,crc_errors,ecc_errors,wc_errors,timeouts;
    wire [2:0] payload_bytes;
    csi_rx_packet_handler #(.GAP_TIMEOUT(64)) parser(
        .I_clock(clk),.I_reset_n(reset_n),.I_enable(enable),.I_count_enable(1'b1),
        .I_data(in_data),.I_data_valid(in_valid),
        .O_packet_done(packet_done),.O_sync_wait(sync_wait),
        .O_payload_out(payload),.O_payload_valid(payload_valid),
        .O_payload_bytes(payload_bytes),.O_payload_last(payload_last),
        .O_vsync_out(fs),.O_in_frame(frame),.O_in_line(line),
        .O_packet_error(packet_error),.O_raw_packets(raw_packets),
        .O_crc_errors(crc_errors),.O_ecc_errors(ecc_errors),
        .O_wc_errors(wc_errors),.O_timeout_errors(timeouts)
    );
    wire [39:0] unpack;
    wire unpack_valid,unpack_last,unpack_error;
    csi_rx_10bit_unpack unpacker(
        .I_clock(clk),.I_reset_n(reset_n),.I_enable(enable),
        .I_line_in(line),.I_data_in(payload),.I_din_valid(payload_valid),
        .I_din_bytes(payload_bytes),.I_din_last(payload_last),
        .O_data_out(unpack),.O_dout_valid(unpack_valid),
        .O_dout_last(unpack_last),.O_unpack_error(unpack_error)
    );
    reg ready=0, allow_reads=1;
    wire tuser,tlast,tvalid;
    wire [39:0] tdata;
    wire [31:0] overflows;
    wire overflow_pulse;
    csi_rx_vid2stream stream(
        .I_data_clk(clk),.I_reset_n(reset_n),.I_enable(enable),
        .I_packet_done(packet_done),.I_packet_line(line),.I_packet_frame(frame),
        .I_frame_start(fs),.I_data_unpack(unpack),
        .I_dout_unpack_valid(unpack_valid),.I_dout_unpack_last(unpack_last),
        .m_axis_video_aclk(video_clk),.m_axis_video_aresetn(reset_n),
        .m_axis_video_tready(ready),.m_axis_video_tuser(tuser),
        .m_axis_video_tlast(tlast),.m_axis_video_tvalid(tvalid),
        .m_axis_video_tdata(tdata),.O_fifo_overflows(overflows),
        .O_overflow_pulse(overflow_pulse)
    );
    reg [23:0] hdr_data=0;
    wire [7:0] hdr_ecc;
    csi_rx_hdr_ecc header_encoder(.data(hdr_data),.ecc(hdr_ecc));
    reg crc_init=0, crc_en=0;
    reg [7:0] crc_byte=0;
    wire [15:0] ref_crc;
    // Actual vendor DSI checksum RTL, independent from parser's bit-serial
    // function. No PHY/PLL primitive is modeled by this digital protocol test.
    crc16_8b golden_crc(.clk(clk),.rst(!reset_n),.init(crc_init),
        .din(crc_byte),.din_en(crc_en),.crc(ref_crc));

    reg [39:0] expected_data[0:40000];
    reg expected_last[0:40000];
    reg expected_user[0:40000];
    integer expected_n=0,actual_n=0,payload_total=0;
    integer stream_sofs=0,stream_lasts=0;
    reg [7:0] bytes[0:8191];
    reg [7:0] lfsr=8'hd7;
    reg stalled=0;
    reg [41:0] held;
    always @(negedge video_clk) begin
        lfsr={lfsr[6:0],lfsr[7]^lfsr[5]^lfsr[4]^lfsr[3]};
        ready=reset_n && allow_reads && (lfsr[1:0]!=0);
    end
    always @(posedge video_clk) begin
        if(reset_n) begin
            if(stalled && (!tvalid || {tdata,tlast,tuser}!==held))
                $fatal(1,"AXI payload/markers changed while stalled at %0d",actual_n);
            stalled=tvalid && !ready;
            held={tdata,tlast,tuser};
            if(tvalid && ready) begin
                if(actual_n>=expected_n) $fatal(1,"Unexpected pixel group %0d",actual_n);
                if(tdata!==expected_data[actual_n] || tlast!==expected_last[actual_n] || tuser!==expected_user[actual_n])
                    $fatal(1,"Stream mismatch at %0d data=%h exp=%h last=%b/%b user=%b/%b",actual_n,tdata,expected_data[actual_n],tlast,expected_last[actual_n],tuser,expected_user[actual_n]);
                if(tlast) stream_lasts=stream_lasts+1;
                if(tuser) stream_sofs=stream_sofs+1;
                actual_n=actual_n+1;
            end
        end else stalled=0;
    end
    always @(posedge clk) begin
        if(payload_valid) payload_total=payload_total+payload_bytes;
        if(unpack_error) $fatal(1,"RAW10 unpack shape error");
    end
    task automatic idle(input integer cycles);
        begin
            @(negedge clk); in_valid=0; in_data=0;
            repeat(cycles) @(negedge clk);
        end
    endtask
    task automatic word(input reg [31:0] value);
        begin
            @(negedge clk); in_valid=1; in_data=value;
        end
    endtask
    task automatic header(input reg [5:0] dt,input integer count,input reg [1:0] vc,input reg bad_ecc);
        reg [31:0] h;
        begin
            wait(sync_wait); @(negedge clk);
            hdr_data={count[15:0],vc,dt}; #0.1;
            h={hdr_ecc,hdr_data};
            if(bad_ecc) h[24]=!h[24];
            in_valid=1; in_data=h;
        end
    endtask
    task automatic short_packet(input reg [5:0] dt,input integer index);
        begin header(dt,index,0,0); idle(12); end
    endtask
    task automatic send_line(input integer width,input integer row,input integer frame_id,input integer gap_mod,input reg bad_crc,input reg enqueue);
        integer g,p,n,j,wc,start_n,before_payload;
        reg [9:0] pixel[0:3];
        reg [15:0] c;
        reg [31:0] w;
        begin
            wc=(width/4)*5;
            before_payload=payload_total;
            start_n=expected_n;
            // All 10 bits vary independently and encode position/frame/row.
            for(g=0;g<width/4;g=g+1) begin
                for(p=0;p<4;p=p+1)
                    pixel[p]=(g*4+p+row*67+frame_id*149)^((g*13+p*17)<<2);
                bytes[g*5+0]=pixel[0][9:2]; bytes[g*5+1]=pixel[1][9:2];
                bytes[g*5+2]=pixel[2][9:2]; bytes[g*5+3]=pixel[3][9:2];
                bytes[g*5+4]={pixel[3][1:0],pixel[2][1:0],pixel[1][1:0],pixel[0][1:0]};
                if(enqueue) begin
                    expected_data[expected_n]={pixel[3],pixel[2],pixel[1],pixel[0]};
                    expected_last[expected_n]=g==width/4-1;
                    expected_user[expected_n]=row==0 && g==0;
                    expected_n=expected_n+1;
                end
            end
            @(negedge clk); crc_init=1;
            @(negedge clk); crc_init=0; crc_en=1;
            for(n=0;n<wc;n=n+1) begin
                crc_byte=bytes[n]; @(negedge clk);
            end
            crc_en=0; c=ref_crc;
            if(bad_crc) c=c^16'h0100;
            bytes[wc]=c[7:0]; bytes[wc+1]=c[15:8];
            bytes[wc+2]=8'hbf;bytes[wc+3]=8'h51;bytes[wc+4]=8'h2b;
            header(6'h2b,wc,0,0);
            for(n=0;n<wc+2;n=n+4) begin
                w=0;
                for(j=0;j<4;j=j+1) w[j*8+:8]=bytes[n+j];
                word(w);
                if(n+4<wc+2 && gap_mod!=0 && ((n/4)%gap_mod)==gap_mod-1) idle(1+(n%3));
            end
            // Deliberately valid tail words: parser must not emit CRC/padding.
            word(32'hdeadbeef); word(32'hdeadbeef); idle(12);
            if(payload_total-before_payload!=wc)
                $fatal(1,"WC clipping failed width=%0d payload=%0d expected=%0d",width,payload_total-before_payload,wc);
            if(enqueue) begin
                wait(actual_n==expected_n); idle(3);
                $display("PASS RAW line width=%0d WC=%0d groups=%0d gap=%0d CRCbad=%0d",width,wc,expected_n-start_n,gap_mod,bad_crc);
            end
        end
    endtask
    integer n,check_packets;
    initial begin
        #40; @(negedge clk); reset_n=1; idle(20);
        short_packet(0,1);
        send_line(4,0,1,0,0,1);
        send_line(8,1,1,2,0,1);
        send_line(12,2,1,0,0,1);
        send_line(16,3,1,3,0,1);
        send_line(20,4,1,0,0,1);
        short_packet(1,1);
        // The actual IMX415 lines are divisible by five, not necessarily four.
        short_packet(0,2);
        send_line(1944,0,2,0,0,1);
        send_line(1944,1,2,7,0,1);
        send_line(3888,2,2,11,0,1);
        send_line(1920,3,2,0,0,1);
        send_line(1280,4,2,0,0,1);
        short_packet(1,2);
        if(raw_packets!=10 || crc_errors!=0 || wc_errors!=0 || ecc_errors!=0 || timeouts!=0)
            $fatal(1,"Unexpected nominal counters packets=%0d crc=%0d wc=%0d ecc=%0d timeout=%0d",raw_packets,crc_errors,wc_errors,ecc_errors,timeouts);
        check_packets=raw_packets;
        short_packet(0,3);
        // CRC diagnosis is intentionally streaming: data is emitted before CRC
        // verdict. It must be counted, not mislabeled as discarded/corrected.
        send_line(1944,0,3,0,1,1);
        short_packet(1,3);
        if(crc_errors!=1 || raw_packets!=check_packets) $fatal(1,"Bad CRC not counted");
        // Inconsistent RAW10 byte count is not forwarded to the unpacker.
        header(6'h2b,7,0,0); word(32'h11223344); word(32'h55667788); word(32'h00001234); idle(12);
        if(wc_errors!=1) $fatal(1,"Malformed WC not counted");
        header(6'h2b,10,0,1); idle(12);
        if(ecc_errors!=1) $fatal(1,"Bad ECC not counted");
        header(6'h2b,20,0,0); idle(80);
        if(timeouts!=1) $fatal(1,"Missing payload timeout not counted");
        // A non-selected VC must not affect frame state or RAW pixels.
        n=payload_total;
        header(0,42,1,0); idle(12);
        if(frame) $fatal(1,"Other-VC frame start leaked");
        if(payload_total!=n || overflows!=0) $fatal(1,"Unexpected VC data/overflow");
        if(stream_lasts!=11 || stream_sofs!=3) $fatal(1,"Incorrect boundary counts");
        allow_reads=0; idle(12);
        force stream.I_dout_unpack_valid=1'b1;
        force stream.I_dout_unpack_last=1'b0;
        force stream.I_data_unpack=40'h1122334455;
        repeat(9000) @(negedge clk);
        release stream.I_dout_unpack_valid;
        release stream.I_dout_unpack_last;
        release stream.I_data_unpack;
        idle(5);
        if(overflows!=809) $fatal(1,"FIFO drop counter incorrect %0d expected809",overflows);
        $display("PASS FIFO full: 8191 stored groups / 809 explicitly counted rejected groups");
        @(negedge clk); reset_n=0; idle(15);
        reset_n=1; allow_reads=1; idle(20);
        if(overflows!=0 || raw_packets!=0) $fatal(1,"Receiver reset did not clear state/counters");
        short_packet(0,4); send_line(1944,0,4,3,0,1); short_packet(1,4);
        $display("PASS CSI integrity groups=%0d SOF=%0d TLAST=%0d CRC/ECC/WC/timeout counters verified; actual vendor sfifo RAM+CDC and DSI crc16 RTL used",actual_n,stream_sofs,stream_lasts);
        $finish;
    end
    initial begin #5000000; $fatal(1,"CSI integrity simulation timeout"); end
endmodule
