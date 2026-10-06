// Digital bypasses only. They do NOT model D-PHY, delay taps or byte alignment.
`timescale 1ns/1ps
module csi_rx_phy #(parameter MIPI_LAN=4,DEVICE="PH1A")(
 input I_debug_button,I_ref_clock,I_clk_hs_rx_p,I_reset_n,
 input [MIPI_LAN-1:0] I_hs_data_p,
 input I_enable,I_wait_for_sync,I_packet_done,
 input I_override_enable,input [5:0] I_override_tap,
 output O_hs_div_clk,O_reset_out,
 output [MIPI_LAN-1:0] O_rx_byte_data_align_vaild,
 output [8*MIPI_LAN-1:0] O_rx_byte_data_align,
 output O_delay_value,O_auto_delay_done,
 output [7:0] O_dbg_delay,output [5:0] O_dbg_best_len,
 output [31:0] O_dbg_raw_bytes,output O_sampler_reset_n);
 reg [31:0] sim_bytes=0;
 reg [3:0] sim_lane_valid=0;
 reg sim_cal_done=0;
 reg sim_sampler_reset_n=0;
 wire manual_active=I_override_enable===1'b1;
 assign O_hs_div_clk=I_clk_hs_rx_p;
 assign O_reset_out=I_reset_n;
 assign O_rx_byte_data_align_vaild=sim_lane_valid;
 assign O_rx_byte_data_align=sim_bytes;
 assign O_dbg_raw_bytes=sim_bytes;
 assign O_sampler_reset_n=sim_sampler_reset_n;
 assign O_delay_value=manual_active ? I_override_tap[0] : 1'b0;
 assign O_auto_delay_done=manual_active | sim_cal_done;
 assign O_dbg_delay={1'b0,manual_active,manual_active?I_override_tap:6'd0};
 assign O_dbg_best_len=0;
endmodule
module csi_rx_word_align #(parameter MIPI_LAN=4)(
 input I_word_clock,I_reset_n,I_enable,I_packet_done,I_wait_for_sync,
 output O_packet_done_out,input [8*MIPI_LAN-1:0] I_word_in,
 input [MIPI_LAN-1:0] I_valid_in,
 output [8*MIPI_LAN-1:0] O_word_out,output O_valid_out);
 assign O_word_out=I_word_in;
 assign O_valid_out=I_enable && I_reset_n && (&I_valid_in);
 assign O_packet_done_out=I_packet_done;
endmodule
module csi_rx_word_gear_box #(parameter MIPI_LAN=4)(
 input I_word_clock,I_reset_n,I_enable,
 input [MIPI_LAN*8-1:0] I_lane_data,input I_lane_data_valid,
 output [31:0] O_word_out,output O_valid_out);
 assign O_word_out=I_lane_data;
 assign O_valid_out=I_lane_data_valid && I_reset_n && I_enable;
endmodule
module csi_rx_10bit_unpack(
 input I_clock,I_reset_n,I_enable,I_line_in,input [31:0] I_data_in,
 input I_din_valid,input [2:0] I_din_bytes,input I_din_last,
 output [39:0] O_data_out,output O_dout_valid,O_dout_last,O_unpack_error);
 assign O_data_out=0;
 assign O_dout_valid=0;
 assign O_dout_last=0;
 assign O_unpack_error=0;
endmodule
module csi_rx_vid2stream(
 input I_data_clk,I_reset_n,I_enable,I_frame_start,I_dout_unpack_last,
 output [31:0] O_fifo_overflows,output O_overflow_pulse,
 input I_packet_done,I_packet_line,I_packet_frame,
 input [39:0] I_data_unpack,input I_dout_unpack_valid,
 input m_axis_video_aclk,m_axis_video_aresetn,m_axis_video_tready,
 output m_axis_video_tuser,m_axis_video_tlast,m_axis_video_tvalid,
 output [39:0] m_axis_video_tdata);
 assign O_fifo_overflows=0;
 assign O_overflow_pulse=0;
 assign m_axis_video_tuser=0;
 assign m_axis_video_tlast=0;
 assign m_axis_video_tvalid=0;
 assign m_axis_video_tdata=0;
endmodule
