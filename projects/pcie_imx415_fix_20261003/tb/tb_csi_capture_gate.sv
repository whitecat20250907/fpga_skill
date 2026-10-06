`timescale 1ns/1ps
module tb_csi_capture_gate;
    reg clk=0, video_clk=0, reset_n=0;
    always #4.5 clk=~clk;
    always #3.4 video_clk=~video_clk;
    wire valid,user,last;
    wire [39:0] data;
    wire [31:0] raw_packets,crc_errors,ecc_errors,wc_errors,timeouts,overflows;
    mipi_csi_rx #(.MIPI_LAN(4),.DEVICE("PH1A")) rx(
        .I_debug_button(1'b1),.I_ref_clock(clk),.I_clk_hs_rx_p(clk),
        .I_reset_n(reset_n),.I_hs_data_p(4'b0),.I_enable(1'b1),
        .O_hs_div_clk(),.m_axis_video_aclk(video_clk),
        .m_axis_video_aresetn(reset_n),.m_axis_video_tready(1'b1),
        .m_axis_video_tuser(user),.m_axis_video_tlast(last),
        .m_axis_video_tvalid(valid),.m_axis_video_tdata(data),
        .O_auto_delay_done(),.O_dbg_mipi(),.O_dbg_delay(),.O_dbg_best_len(),
        .O_csi_raw_packets(raw_packets),.O_csi_crc_errors(crc_errors),
        .O_csi_ecc_errors(ecc_errors),.O_csi_wc_errors(wc_errors),
        .O_csi_timeout_errors(timeouts),.O_csi_fifo_overflows(overflows),
        .O_csi_error_pulse());
    reg [23:0] hdata;
    wire [7:0] hecc;
    csi_rx_hdr_ecc header_encode(.data(hdata),.ecc(hecc));
    reg crc_init=0,crc_en=0;
    reg [7:0] crc_data;
    wire [15:0] checksum;
    crc16_8b golden_crc(.clk(clk),.rst(!reset_n),.init(crc_init),
        .din(crc_data),.din_en(crc_en),.crc(checksum));
    reg [39:0] golden[0:3];
    integer received=0,lasts=0,sofs=0;
    always @(posedge video_clk) if(reset_n && valid) begin
        if(received>=4) $fatal(1,"Gate emitted extra data or pre-calibration pixels");
        if(data!==golden[received] || last!==(received%2==1) || user!==(received==0))
            $fatal(1,"Calibrated frame mismatch %0d data=%h/%h last=%b user=%b",received,data,golden[received],last,user);
        received=received+1; if(last) lasts=lasts+1; if(user) sofs=sofs+1;
    end
    task automatic idle(input integer n);
        begin
            @(negedge clk); rx.u_csi_rx_phy.sim_valid=0;
            repeat(n) @(negedge clk);
        end
    endtask
    task automatic word(input [31:0] value);
        begin
            @(negedge clk); rx.u_csi_rx_phy.sim_data=value;
            rx.u_csi_rx_phy.sim_valid=4'hf;
        end
    endtask
    task automatic header(input [5:0] dt,input integer wc);
        begin
            wait(rx.w_sync_wait); word(32'hb8b8b8b8);
            hdata={wc[15:0],2'b00,dt}; #0.1;
            word({hecc,hdata});
        end
    endtask
    task automatic short_packet(input [5:0] dt);
        begin header(dt,0); idle(20); end
    endtask
    reg [7:0] pbytes[0:15];
    task automatic raw_line(input integer base,input integer golden_index);
        integer g,p,n,j;
        reg [9:0] pixel[0:3];
        reg [31:0] w;
        begin
            for(g=0;g<2;g=g+1) begin
                for(p=0;p<4;p=p+1) pixel[p]=base+g*4+p;
                pbytes[g*5]=pixel[0][9:2];pbytes[g*5+1]=pixel[1][9:2];
                pbytes[g*5+2]=pixel[2][9:2];pbytes[g*5+3]=pixel[3][9:2];
                pbytes[g*5+4]={pixel[3][1:0],pixel[2][1:0],pixel[1][1:0],pixel[0][1:0]};
                if(golden_index>=0) golden[golden_index+g]={pixel[3],pixel[2],pixel[1],pixel[0]};
            end
            @(negedge clk);crc_init=1;
            @(negedge clk);crc_init=0;crc_en=1;
            for(n=0;n<10;n=n+1) begin crc_data=pbytes[n];@(negedge clk);end
            crc_en=0;pbytes[10]=checksum[7:0];pbytes[11]=checksum[15:8];
            header(6'h2b,10);
            for(n=0;n<12;n=n+4) begin
                w=0;for(j=0;j<4;j=j+1)w[j*8+:8]=pbytes[n+j];word(w);
            end
            idle(25);
        end
    endtask
    initial begin
        #40;@(negedge clk);reset_n=1;idle(20);
        short_packet(0);raw_line(10,-1);
        if(!rx.w_in_frame) $fatal(1,"Parser was disabled during calibration feedback");
        rx.u_csi_rx_phy.sim_done=1;idle(10);
        raw_line(30,-1);short_packet(1);
        if(received!=0 || raw_packets!=0) $fatal(1,"Calibration gate admitted partial current frame");
        $display("PASS parser remained active before calibration; output waits for NEW FS after done");
        short_packet(0);raw_line(100,0);raw_line(200,2);short_packet(1);
        wait(received==4);idle(10);
        if(raw_packets!=2 || crc_errors || ecc_errors || wc_errors || timeouts || overflows || sofs!=1 || lasts!=2)
            $fatal(1,"Capture gate/stats inconsistent raw=%0d crc=%0d ecc=%0d",raw_packets,crc_errors,ecc_errors);
        $display("PASS real wordalign+gearbox+parser+unpack+sfifo capture gate: 4 groups,1 SOF,2 TLAST,2 CRC-good lines");
        $finish;
    end
    initial begin #1000000;$fatal(1,"Capture gate test timeout");end
endmodule

// This PHY shell substitutes only electrical sampling/calibration. The real
// complete digital chain starts at byte_align output, INCLUDING the B8 sync
// byte which word_align intentionally skips before the header.
module csi_rx_phy #(parameter MIPI_LAN=4,parameter DEVICE="PH1A")(
    input I_debug_button,I_ref_clock,I_clk_hs_rx_p,I_reset_n,I_enable,
    input [MIPI_LAN-1:0] I_hs_data_p,
    input I_wait_for_sync,I_packet_done,
    output O_hs_div_clk,O_reset_out,
    output [MIPI_LAN-1:0] O_rx_byte_data_align_vaild,
    output [8*MIPI_LAN-1:0] O_rx_byte_data_align,
    output O_delay_value,O_auto_delay_done,
    output [7:0] O_dbg_delay,output [5:0] O_dbg_best_len);
    reg [31:0] sim_data=0;
    reg [3:0] sim_valid=0;
    reg sim_done=0;
    assign O_hs_div_clk=I_ref_clock;
    assign O_reset_out=I_reset_n;
    assign O_rx_byte_data_align_vaild=sim_valid;
    assign O_rx_byte_data_align=sim_data;
    assign O_delay_value=0;
    assign O_auto_delay_done=sim_done;
    assign O_dbg_delay=8'h10;
    assign O_dbg_best_len=32;
endmodule
