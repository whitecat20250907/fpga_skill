`timescale 1ns/1ps
// One production fork: actual accepted ROI quads and real result pulses.
// A link restart discards old RAM control and waits for the next accepted ISP
// SOF. Old in-flight feature reports are rejected by their real source FID.
module hci03_link_pipeline(
 input wire src_clk,dst_clk,link_async_n,isp_sof_accepted,input wire [31:0] isp_frame_id,
 input wire [2:0] crop_valid,crop_sof,crop_last,crop_eof,
 input wire [383:0] crop_rgb,input wire [95:0] crop_gray,input wire [8:0] crop_count,
 input wire [47:0] crop_x,crop_y,crop_origin_x,crop_origin_y,crop_width,crop_height,
 input wire [31:0] crop_frame_id,crop_sequence,input wire [63:0] crop_time_us,input wire [7:0] crop_flags,
 input wire [1:0] feature_valid,input wire [1535:0] feature_result,
 input wire [63:0] feature_received,feature_skipped,feature_deadline,
 input wire hs_ready,output wire hs_en,hs_last,output wire [31:0] hs_data,
 output wire [1663:0] source_stats,output wire [511:0] destination_stats
);
 (* ASYNC_REG="TRUE" *)reg [1:0] source_reset_sync,destination_reset_sync;
 always @(posedge src_clk or negedge link_async_n)if(!link_async_n)source_reset_sync<=0;else source_reset_sync<={source_reset_sync[0],1'b1};
 always @(posedge dst_clk or negedge link_async_n)if(!link_async_n)destination_reset_sync<=0;else destination_reset_sync<={destination_reset_sync[0],1'b1};
 wire src_rst_n=source_reset_sync[1],dst_rst_n=destination_reset_sync[1];
 // The actual single eye engine/FIFO is ordered. After its first new-epoch
 // report, no pre-epoch report can arrive later from that same engine.
 // Do not compare an indefinite run against one fixed signed32-bit FID.
 reg armed;reg [1:0] eye_epoch_seen;reg [31:0] first_frame_id,old_feature_reports;
 wire signed [31:0] left_age=feature_result[63:32]-first_frame_id,right_age=feature_result[831:800]-first_frame_id;
 wire [1:0] fv={armed&&(eye_epoch_seen[1]||right_age>=0),armed&&(eye_epoch_seen[0]||left_age>=0)}&feature_valid;
 always @(posedge src_clk or negedge src_rst_n)begin
  if(!src_rst_n)begin eye_epoch_seen<=0;armed<=0;first_frame_id<=0;old_feature_reports<=0;end
  else begin
   if(!armed&&isp_sof_accepted)begin armed<=1;first_frame_id<=isp_frame_id;end
   eye_epoch_seen<=eye_epoch_seen|fv;
   old_feature_reports<=old_feature_reports+(feature_valid[0]&&!fv[0])+(feature_valid[1]&&!fv[1]);
  end
 end
 wire [191:0] data;wire [2:0] valid,first,last,ready;wire [63:0] md;wire mv,mf,ml,mr;
 wire [95:0] received_rows,encoded_rows,sent_rows,dropped_rows,last_dropped_frame_id,row_errors,merge_packets;
 wire [5:0] row_occupancy,row_high_water;wire [31:0] packets,merge_errors;wire [63:0] raw_bytes,payload_bytes,wire_bytes;
 hci03_roi_transport u_roi_transport(.clk(src_clk),.rst_n(src_rst_n),.s_valid(crop_valid&{3{armed}}),.s_sof(crop_sof),.s_last(crop_last),.s_eof(crop_eof),
  .s_data(crop_rgb),.s_gray(crop_gray),.s_count(crop_count),.s_x(crop_x),.s_y(crop_y),.s_origin_x(crop_origin_x),.s_origin_y(crop_origin_y),
  .s_width(crop_width),.s_height(crop_height),.s_frame_id(crop_frame_id),.s_config_sequence(crop_sequence),.s_time_us(crop_time_us),.s_flags(crop_flags),
  .m_data(data[63:0]),.m_valid(valid[0]),.m_first(first[0]),.m_last(last[0]),.m_ready(ready[0]),
  .received_rows(received_rows),.encoded_rows(encoded_rows),.sent_rows(sent_rows),.dropped_rows(dropped_rows),.last_dropped_frame_id(last_dropped_frame_id),.errors(row_errors),
  .occupancy(row_occupancy),.high_water(row_high_water),.packets(packets),.raw_bytes(raw_bytes),.payload_bytes(payload_bytes),.wire_bytes(wire_bytes));
 wire [63:0] er_received,er_queued,er_sent,er_dropped,er_dropfid,er_errors;wire [7:0] er_occupancy,er_peak;
 genvar k;generate for(k=0;k<2;k=k+1)begin:eyes
  hci03_eye_packet #(.EYE(k))u_packets(.clk(src_clk),.rst_n(src_rst_n),.s_valid(fv[k]),.s_result(feature_result[k*768+:768]),
   .engine_received(feature_received[k*32+:32]),.engine_skipped(feature_skipped[k*32+:32]),.engine_deadline(feature_deadline[k*32+:32]),
   .m_data(data[(k+1)*64+:64]),.m_valid(valid[k+1]),.m_first(first[k+1]),.m_last(last[k+1]),.m_ready(ready[k+1]),
   .received(er_received[k*32+:32]),.queued(er_queued[k*32+:32]),.sent(er_sent[k*32+:32]),.dropped(er_dropped[k*32+:32]),.last_dropped_frame_id(er_dropfid[k*32+:32]),.errors(er_errors[k*32+:32]),
   .occupancy(er_occupancy[k*4+:4]),.high_water(er_peak[k*4+:4]));
 end endgenerate
 hci03_packet_merge3 u_merge(.clk(src_clk),.rst_n(src_rst_n),.s_data(data),.s_valid(valid),.s_first(first),.s_last(last),.s_ready(ready),
  .m_data(md),.m_valid(mv),.m_first(mf),.m_last(ml),.m_ready(mr),.packets(merge_packets),.errors(merge_errors));
 wire [31:0] bd;wire bv,bf,bl,br;wire [15:0] packet_bytes;
 wire [31:0] bridge_accepted,bridge_committed,bridge_wait,bridge_source_errors,bridge_delivered,bridge_destination_errors;wire [10:0] bridge_peak;
 hci03_packet_async_bridge u_bridge(.src_clk(src_clk),.dst_clk(dst_clk),.rst_n(link_async_n),.s_data(md),.s_valid(mv),.s_first(mf),.s_last(ml),.s_ready(mr),
  .m_data(bd),.m_valid(bv),.m_first(bf),.m_last(bl),.m_ready(br),.m_packet_bytes(packet_bytes),.accepted_words(bridge_accepted),.committed_packets(bridge_committed),
  .source_wait_clocks(bridge_wait),.source_errors(bridge_source_errors),.delivered_packets(bridge_delivered),.destination_errors(bridge_destination_errors),.high_water(bridge_peak));
 wire [31:0] cd;wire cv,cs,cl,cr;wire [31:0] carrier_frames,chunks,empty_chunks,carrier_errors,tx_frames,tx_packets,tx_errors;wire [63:0] input_bytes,container_bytes;
 hci03_csi_carrier u_carrier(.clk(dst_clk),.rst_n(dst_rst_n),.s_data(bd),.s_valid(bv),.s_first(bf),.s_ready(br),.m_data(cd),.m_valid(cv),.m_sof(cs),.m_last(cl),.m_ready(cr),
  .carrier_frames(carrier_frames),.chunks(chunks),.empty_chunks(empty_chunks),.errors(carrier_errors),.input_bytes(input_bytes),.container_bytes(container_bytes));
 hci03_csi2_frame_tx #(.H_ACTIVE(720),.V_ACTIVE(128),.GAP_LINE(200),.GAP_FRAME(4000))u_csi_tx(
  .clk(dst_clk),.rst_n(dst_rst_n),.enable(dst_rst_n),.hs_ready(hs_ready),.s_tdata(cd),.s_tvalid(cv),.s_tuser_sof(cs),.s_tlast(cl),.s_tready(cr),
  .hs_en(hs_en),.hs_data(hs_data),.hs_last(hs_last),.frame_cnt(tx_frames),.packet_cnt(tx_packets),.stream_errors(tx_errors));
 assign source_stats={{31'd0,armed},32'd0,old_feature_reports,{21'd0,bridge_peak},bridge_source_errors,bridge_wait,bridge_committed,bridge_accepted,
  merge_errors,merge_packets,{16'd0,er_peak,er_occupancy},er_errors,er_dropfid,er_dropped,er_sent,er_queued,er_received,
  {20'd0,row_high_water,row_occupancy},row_errors,last_dropped_frame_id,dropped_rows,sent_rows,encoded_rows,received_rows,
  wire_bytes,payload_bytes,raw_bytes,packets,first_frame_id};
 assign destination_stats={32'd0,32'd0,{31'd0,dst_rst_n},tx_errors,tx_packets,tx_frames,bridge_destination_errors,bridge_delivered,
  container_bytes,input_bytes,carrier_errors,empty_chunks,chunks,carrier_frames};
endmodule
