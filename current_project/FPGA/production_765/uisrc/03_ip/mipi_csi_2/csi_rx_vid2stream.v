`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 2025/07/18 17:00:36
// Design Name: 
// Module Name: csi_rx_vid2stream
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////
module csi_rx_vid2stream(
    input wire I_data_clk, I_reset_n, I_enable,
    input wire I_packet_done, I_packet_line, I_packet_frame,
    input wire I_frame_start,
    input wire [39:0] I_data_unpack,
    input wire I_dout_unpack_valid, I_dout_unpack_last,
    input wire m_axis_video_aclk, m_axis_video_aresetn,
    input wire m_axis_video_tready,
    output wire m_axis_video_tuser, m_axis_video_tlast, m_axis_video_tvalid,
    output wire [39:0] m_axis_video_tdata,
    output reg [31:0] O_fifo_overflows,
    output reg O_overflow_pulse
);
// Preserve explicit RAW10 end-of-line through the asynchronous pixel FIFO.
// RAW10's natural 4/5 duty cycle must NEVER be interpreted as a line ending.
wire [41:0] rdata;
wire full, empty;
reg frame_start_pending;
reg frame_level_d;
wire frame_start=I_frame_start || (I_packet_frame && !frame_level_d);
wire write_beat=I_enable && I_dout_unpack_valid && !full;
always @(posedge I_data_clk or negedge I_reset_n) begin
    if(!I_reset_n) begin
        frame_start_pending<=0; frame_level_d<=0;
        O_fifo_overflows<=0; O_overflow_pulse<=0;
    end else begin
        frame_level_d<=I_packet_frame;
        O_overflow_pulse<=0;
        if(!I_enable) frame_start_pending<=0;
        else if(frame_start) frame_start_pending<=1;
        else if(write_beat) frame_start_pending<=0;
        if(I_enable && I_dout_unpack_valid && full) begin
            O_fifo_overflows<=O_fifo_overflows+1'b1;
            O_overflow_pulse<=1;
        end
    end
end
assign m_axis_video_tvalid = m_axis_video_aresetn && !empty;
assign m_axis_video_tuser = m_axis_video_tvalid && rdata[0];
assign m_axis_video_tlast = m_axis_video_tvalid && rdata[1];
assign m_axis_video_tdata = rdata[41:2];
mipi_sfifo #(
    .DATA_WIDTH_W(42), .DATA_WIDTH_R(42),
    .ADDR_WIDTH_W(13), .ADDR_WIDTH_R(13),
    .AL_FULL_NUM(4096), .AL_EMPTY_NUM(2),
    .SHOW_AHEAD_EN(1'b1), .OUTREG_EN("NOREG")
) hs_data_fifo (
    .rst(!I_reset_n || !m_axis_video_aresetn),
    .clkw(I_data_clk), .we(write_beat),
    .di({I_data_unpack,I_dout_unpack_last,frame_start_pending || frame_start}),
    .full_flag(full), .afull(), .aempty(), .valid(),
    .clkr(m_axis_video_aclk), .re(m_axis_video_tready && m_axis_video_tvalid),
    .dout(rdata), .empty_flag(empty), .rdusedw(), .wrusedw()
);
endmodule
