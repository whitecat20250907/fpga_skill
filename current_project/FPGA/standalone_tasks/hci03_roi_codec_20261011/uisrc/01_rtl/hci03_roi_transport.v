`timescale 1ns/1ps
// Actual accepted three-ROI crop. Codec overload is bounded and explicit;
// this fork cannot stall sensor/full-video or the eye measurement consumers.
module hci03_roi_transport(
 input wire clk,rst_n,input wire [2:0] s_valid,s_sof,s_last,s_eof,
 input wire [383:0] s_data,input wire [95:0] s_gray,input wire [8:0] s_count,
 input wire [47:0] s_x,s_y,s_origin_x,s_origin_y,s_width,s_height,
 input wire [31:0] s_frame_id,s_config_sequence,input wire [63:0] s_time_us,input wire [7:0] s_flags,
 output wire [63:0] m_data,output wire m_valid,m_first,m_last,input wire m_ready,
 output wire [95:0] received_rows,encoded_rows,sent_rows,dropped_rows,last_dropped_frame_id,errors,
 output wire [5:0] occupancy,high_water,output wire [31:0] packets,
 output wire [63:0] raw_bytes,payload_bytes,wire_bytes
);
 wire [2:0] ready,valid,bank,release_valid,release_bank;wire [767:0] metadata;wire [95:0] crc;
 wire [35:0] modes;wire [323:0] lengths,read_addr;wire [575:0] pairs;wire [1:0] active;
 genvar k;generate for(k=0;k<3;k=k+1)begin:roi
  if(k<2)begin:eye
   assign modes[k*12+4+:8]=0;assign lengths[k*108+36+:72]=0;assign pairs[k*192+64+:128]=0;
  end
  hci03_row_codec #(.CHANNELS(k==2?3:1),.MAX_WIDTH(k==2?448:256))u_rows(
   .clk(clk),.rst_n(rst_n),.s_valid(s_valid[k]),.s_sof(s_sof[k]),.s_last(s_last[k]),.s_eof(s_eof[k]),
   .s_data(s_data[k*128+:128]),.s_gray(s_gray[k*32+:32]),.s_count(s_count[k*3+:3]),
   .s_x(s_x[k*16+:16]),.s_y(s_y[k*16+:16]),.s_origin_x(s_origin_x[k*16+:16]),.s_origin_y(s_origin_y[k*16+:16]),
   .s_width(s_width[k*16+:16]),.s_height(s_height[k*16+:16]),.s_frame_id(s_frame_id),.s_config_sequence(s_config_sequence),.s_time_us(s_time_us),.s_flags(s_flags),
   .s_ready(),.m_ready(ready[k]),.m_valid(valid[k]),.m_bank(bank[k]),.m_metadata(metadata[k*256+:256]),.m_raw_crc32(crc[k*32+:32]),
   .m_lane_modes(modes[k*12+:(k==2?12:4)]),.m_lane_lengths(lengths[k*108+:(k==2?108:36)]),
   .read_addr(read_addr[k*108+:(k==2?108:36)]),.read_pairs(pairs[k*192+:(k==2?192:64)]),
   .release_valid(release_valid[k]),.release_bank(release_bank[k]),
   .received_rows(received_rows[k*32+:32]),.encoded_rows(encoded_rows[k*32+:32]),.sent_rows(sent_rows[k*32+:32]),
   .dropped_rows(dropped_rows[k*32+:32]),.last_dropped_frame_id(last_dropped_frame_id[k*32+:32]),.errors(errors[k*32+:32]),
   .occupancy(occupancy[k*2+:2]),.high_water(high_water[k*2+:2]));
 end endgenerate
 hci03_row_packetizer u_packets(.clk(clk),.rst_n(rst_n),.row_valid(valid),.row_bank(bank),.row_ready(ready),
  .row_metadata(metadata),.row_crc(crc),.row_modes(modes),.row_lengths(lengths),.read_addr(read_addr),.read_pairs(pairs),
  .release_valid(release_valid),.release_bank(release_bank),.m_data(m_data),.m_valid(m_valid),.m_first(m_first),.m_last(m_last),.m_ready(m_ready),
  .packets(packets),.raw_bytes(raw_bytes),.payload_bytes(payload_bytes),.wire_bytes(wire_bytes),.active_roi(active));
endmodule
