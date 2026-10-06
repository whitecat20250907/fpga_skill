`timescale 1ns/1ps
// Compatibility adapter for the original demo06 encrypted PHY. It keeps the
// original pin/PHY configuration and runs the elastic ISP on its stable clock.
module ui06_csi_frontend #(
 parameter CROP_WIDTH=1920, CROP_HEIGHT=1080,
 parameter CROP_SKIP_ROWS=1
)(
 input I_hs_clk,I_reset_n,I_hs_valid,input [31:0] I_hs_data,
 input I_video_clk,I_video_reset_n,
 output [39:0] O_tdata,output O_tvalid,O_tuser,O_tlast,input I_tready,
 output [31:0] O_raw_packets,O_crc_errors,O_ecc_errors,O_wc_errors,
 output [31:0] O_timeout_errors,O_fifo_overflows,output O_error_pulse
);
// The preserved hs_rx_wrapper emits lane0 byte at [31:24]. New cores consume
// lane0/protocol-first byte at [7:0]. This is a byte swap, NOT a pixel reversal.
wire [31:0] protocol_data={I_hs_data[7:0],I_hs_data[15:8],I_hs_data[23:16],I_hs_data[31:24]};
(* async_reg="true" *) reg [1:0] hs_reset=0,video_reset=0;
always @(posedge I_hs_clk or negedge I_reset_n)
 if(!I_reset_n) hs_reset<=0;else hs_reset<={hs_reset[0],1'b1};
always @(posedge I_video_clk or negedge I_video_reset_n)
 if(!I_video_reset_n) video_reset<=0;else video_reset<={video_reset[0],1'b1};
wire hs_rstn=hs_reset[1], video_rstn=video_reset[1];
wire done,sync_wait,frame_start,in_frame,in_line,packet_error;
wire [31:0] payload;
wire payload_valid,payload_last;
wire [2:0] payload_bytes;
csi_rx_packet_handler #(.WAIT_VALID_LOW(1)) parser(
 .I_clock(I_hs_clk),.I_reset_n(hs_rstn),.I_enable(1'b1),.I_count_enable(1'b1),
 .I_data(protocol_data),.I_data_valid(I_hs_valid),
 .O_packet_done(done),.O_sync_wait(sync_wait),.O_payload_out(payload),
 .O_payload_valid(payload_valid),.O_payload_bytes(payload_bytes),.O_payload_last(payload_last),
 .O_vsync_out(frame_start),.O_in_frame(in_frame),.O_in_line(in_line),.O_packet_error(packet_error),
 .O_raw_packets(O_raw_packets),.O_crc_errors(O_crc_errors),.O_ecc_errors(O_ecc_errors),
 .O_wc_errors(O_wc_errors),.O_timeout_errors(O_timeout_errors)
);
wire [39:0] raw;
wire raw_valid,raw_last,unpack_error;
csi_rx_10bit_unpack unpack(
 .I_clock(I_hs_clk),.I_reset_n(hs_rstn),.I_enable(1'b1),
 .I_line_in(in_line), .I_data_in(payload),.I_din_valid(payload_valid),.I_din_bytes(payload_bytes),
 .I_din_last(payload_last),.O_data_out(raw),.O_dout_valid(raw_valid),.O_dout_last(raw_last),
 .O_unpack_error(unpack_error)
);
wire [39:0] stream_data;
wire stream_valid,stream_sof,stream_last,stream_ready,overflow;
csi_rx_vid2stream fifo(
 .I_data_clk(I_hs_clk),.I_reset_n(hs_rstn),.I_enable(1'b1),
 .I_packet_done(done),.I_packet_line(in_line),.I_packet_frame(in_frame),.I_frame_start(frame_start),
 .I_data_unpack(raw),.I_dout_unpack_valid(raw_valid),.I_dout_unpack_last(raw_last),
 .m_axis_video_aclk(I_video_clk),.m_axis_video_aresetn(video_rstn),
 .m_axis_video_tready(stream_ready),.m_axis_video_tuser(stream_sof),
 .m_axis_video_tlast(stream_last),.m_axis_video_tvalid(stream_valid),.m_axis_video_tdata(stream_data),
 .O_fifo_overflows(O_fifo_overflows),.O_overflow_pulse(overflow)
);
assign O_error_pulse=packet_error||overflow||unpack_error;
// Legacy demo crop: skip raw row0/group0, select exactly 1920x1080. The sensor
// must supply >=1924 pixels/1081 RAW rows; verify real WC/rows/Bayer on board.
// The shared crop's bounds are exclusive. Horizontal start is one group.
localparam [14:0] V_START=CROP_SKIP_ROWS-1, V_END=CROP_SKIP_ROWS+CROP_HEIGHT;
localparam [14:0] H_END=CROP_WIDTH/4+1;
image_correction crop(
 .I_clk(I_video_clk),.I_rst_n(video_rstn),
 .I_v_start(V_START),.I_v_end(V_END),.I_h_end(H_END),
 .I_raw_tdata(stream_data),.I_raw_tdest(10'd0),.I_raw_tlast(stream_last),
 .I_raw_tvalid(stream_valid),.I_raw_tuser(stream_sof),.I_raw_tready(stream_ready),
 .O_raw_tdata(O_tdata),.O_raw_tlast(O_tlast),.O_raw_tdest(),.O_raw_tvalid(O_tvalid),
 .O_raw_tuser(O_tuser),.O_raw_tready(I_tready)
);
endmodule
