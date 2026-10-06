`timescale 1ns/1ps
// F3/F4: four parallel delta + offset-one LZ77 engines, one 1920-pixel row.
// The output is a 1280-pixel YUYV *byte container*: 32-byte header,
// 1920-byte striped payload and zero padding. RK treats the bytes as a
// transport format, not as displayable YUYV. Four lanes each supply two
// bytes per cycle. One row uses 320 clocks after compression completes.
// QUANT_BITS=4 makes this a near-lossless, maximum-error-15 mode.
module lz4_line_packetizer #(
    parameter WIDTH=1920,
    parameter HEIGHT=1080,
    parameter QUANT_BITS=4
)(
    input wire clk,rst_n,
    input wire s_valid,
    input wire [63:0] s_data,
    input wire s_sof,s_last,
    input wire sensor_sof,
    input wire [6:0] link_error,
    output wire m_valid,
    output reg [63:0] m_data,
    output wire m_sof,m_last,
    output reg line_overlap
);
    localparam N=WIDTH/4;
    localparam IDLE=2'd0,WAIT=2'd1,SEND=2'd2;
    reg [1:0] state;
    reg [8:0] col;
    reg [10:0] row,row_out;
    reg [31:0] frame_id,frame_out;
    reg start;
    reg [8:0] word_ptr;
    reg [3:0] done_seen,modes;
    reg [8:0] length0,length1,length2,length3;
    reg [31:0] crc,row_crc;
    reg [63:0] ticks,frame_sof_tick,last_sof_tick,packet_start_tick;
    reg [31:0] prev_period_ticks,overlap_count;
    reg have_sensor_sof;
    wire [7:0] y0=s_data[7:0], y1=s_data[23:16];
    wire [7:0] y2=s_data[39:32],y3=s_data[55:48];
    wire [7:0] q0=(y0>>QUANT_BITS)<<QUANT_BITS;
    wire [7:0] q1=(y1>>QUANT_BITS)<<QUANT_BITS;
    wire [7:0] q2=(y2>>QUANT_BITS)<<QUANT_BITS;
    wire [7:0] q3=(y3>>QUANT_BITS)<<QUANT_BITS;
    function [31:0] crc_byte;
        input [31:0] old_crc;
        input [7:0] value;
        reg [31:0] v;
        integer bitn;
        begin
            v=old_crc^{24'd0,value};
            for(bitn=0;bitn<8;bitn=bitn+1)
                v=v[0] ? (v>>1)^32'hEDB88320 : (v>>1);
            crc_byte=v;
        end
    endfunction
    wire [31:0] crc_next=crc_byte(crc_byte(crc_byte(crc_byte(crc,q0),q1),q2),q3);
    wire [8:0] pair_addr=(word_ptr-9'd4)<<1;
    wire [8:0] pair_addr_next=pair_addr+1'b1;
    wire [7:0] a0[0:3],a1[0:3];
    wire [3:0] busy,done,done_bank,done_mode;
    wire [8:0] done_length[0:3];
    genvar lane;
    generate for(lane=0;lane<4;lane=lane+1) begin:ENG
        wire [7:0] gray;
        if(lane==0) assign gray=q0;
        if(lane==1) assign gray=q1;
        if(lane==2) assign gray=q2;
        if(lane==3) assign gray=q3;
        lz1_lane_engine #(.N(N)) u_engine (
            .clk(clk),.rst_n(rst_n),
            .cap_valid(s_valid),.cap_gray(gray),.cap_addr(col),
            .cap_line_start(col==0),.cap_bank(1'b0),
            .start(start),.start_bank(1'b0),
            .busy(busy[lane]),.done(done[lane]),
            .done_bank(done_bank[lane]),
            .done_mode(done_mode[lane]),.done_length(done_length[lane]),
            .read_bank(1'b0),.read_mode(modes[lane]),
            .read_addr(pair_addr),.read_data(a0[lane]),
            .read_addr_next(pair_addr_next),.read_data_next(a1[lane])
        );
    end endgenerate
    wire [10:0] packed_bytes={2'b0,length0}+{2'b0,length1}+
                             {2'b0,length2}+{2'b0,length3};
    wire [7:0] flags=8'h01 | (QUANT_BITS<<4);
    assign m_valid=(state==SEND);
    assign m_sof=m_valid && row_out==0 && word_ptr==0;
    assign m_last=m_valid && word_ptr==319;
    always @* begin
        case(word_ptr)
            0: m_data={{5'd0,row_out[10:8]},row_out[7:0],flags,8'd1,
                       8'h52,8'h34,8'h5A,8'h4C}; // "LZ4R", version, flags, row
            1: m_data={{5'd0,packed_bytes[10:8]},packed_bytes[7:0],
                       8'h07,8'h80,frame_out}; // raw bytes 1920
            2: m_data={7'd0,length1,7'd0,length0,
                       {7'd0,modes[3]},{7'd0,modes[2]},
                       {7'd0,modes[1]},{7'd0,modes[0]}};
            3: m_data={row_crc,7'd0,length3,7'd0,length2};
            244: m_data=(row_out==0)
                ? {16'd0,{link_error,line_overlap},8'd1,
                   8'h4B,8'h43,8'h49,8'h54} : 64'd0; // "TICK"
            245: m_data=(row_out==0)
                ? {frame_sof_tick[31:0],frame_out} : 64'd0;
            246: m_data=(row_out==0)
                ? {packet_start_tick[31:0],frame_sof_tick[63:32]} : 64'd0;
            247: m_data=(row_out==0)
                ? {prev_period_ticks,packet_start_tick[63:32]} : 64'd0;
            248: m_data=(row_out==0)
                ? {overlap_count,32'd111375000} : 64'd0;
            default: begin
                if(word_ptr>=4 && word_ptr<244)
                    m_data={
                        (pair_addr_next<length3 ? a1[3]:8'd0),
                        (pair_addr<length3 ? a0[3]:8'd0),
                        (pair_addr_next<length2 ? a1[2]:8'd0),
                        (pair_addr<length2 ? a0[2]:8'd0),
                        (pair_addr_next<length1 ? a1[1]:8'd0),
                        (pair_addr<length1 ? a0[1]:8'd0),
                        (pair_addr_next<length0 ? a1[0]:8'd0),
                        (pair_addr<length0 ? a0[0]:8'd0)};
                else m_data=64'd0;
            end
        endcase
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE;col<=0;row<=0;row_out<=0;
            frame_id<=0;frame_out<=0;
            start<=0;word_ptr<=0;done_seen<=0;modes<=0;
            length0<=0;length1<=0;length2<=0;length3<=0;
            crc<=32'hFFFFFFFF;row_crc<=0;line_overlap<=0;
            ticks<=0;frame_sof_tick<=0;last_sof_tick<=0;
            packet_start_tick<=0;prev_period_ticks<=0;
            overlap_count<=0;have_sensor_sof<=0;
        end else begin
            start<=0;
            ticks<=ticks+1'b1;
            if(sensor_sof) begin
                frame_sof_tick<=ticks;
                if(have_sensor_sof)
                    prev_period_ticks<=ticks-last_sof_tick;
                last_sof_tick<=ticks;
                have_sensor_sof<=1;
            end
            if(s_valid) begin
                // Compression + emission must finish in the camera line blank.
                // A following line arriving early would reuse the single bank.
                if(state!=IDLE && col==0) begin
                    line_overlap<=1;
                    overlap_count<=overlap_count+1'b1;
                end
                crc<=s_last?32'hFFFFFFFF:crc_next;
                if(s_sof) begin frame_id<=frame_id+1'b1;row<=0;end
                if(s_last) begin
                    col<=0;
                    row<=(s_sof?11'd0:row)+1'b1;
                    if(state==IDLE) begin
                        row_out<=s_sof?11'd0:row;
                        frame_out<=frame_id+(s_sof?32'd1:32'd0);
                        row_crc<=~crc_next;
                        done_seen<=0;
                        start<=1;
                        state<=WAIT;
                    end else line_overlap<=1;
                end else col<=col+1'b1;
            end
            if(state==WAIT) begin
                if(done[0]) begin
                    done_seen[0]<=1; modes[0]<=done_mode[0];
                    length0<=done_length[0];
                end
                if(done[1]) begin
                    done_seen[1]<=1; modes[1]<=done_mode[1];
                    length1<=done_length[1];
                end
                if(done[2]) begin
                    done_seen[2]<=1; modes[2]<=done_mode[2];
                    length2<=done_length[2];
                end
                if(done[3]) begin
                    done_seen[3]<=1; modes[3]<=done_mode[3];
                    length3<=done_length[3];
                end
                if(&done_seen) begin word_ptr<=0;state<=SEND;end
            end
            if(state==SEND) begin
                if(word_ptr==0) packet_start_tick<=ticks;
                if(word_ptr==319) state<=IDLE;
                else word_ptr<=word_ptr+1'b1;
            end
        end
    end
endmodule
