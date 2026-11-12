`timescale 1ns/1ps
`default_nettype none
module twin_feature_plane #(parameter EXTERNAL_ARRIVAL=0)(
 input wire clk,input wire rst,input wire [31:0] now_ms,input wire vblank,
 input wire rx_valid,input wire [7:0] rx_data,output wire rx_ready,
 input wire [17:0] video_addr,output reg [5:0] video_pixel,
 output wire front_ready,output wire [4:0] front_valid_mask,output wire front_fixture,
 output wire [79:0] front_source_ages,output wire [31:0] front_arrival_ms,
 output wire [63:0] front_hand_ns,front_face_ns,front_epoch,front_sequence,
 output wire [31:0] front_capture_sequence,front_eye_metrics,
 output wire [1:0] front_actor_slot,output wire [31:0] front_actor_track_id,front_ui_status,front_display_generation,
 output wire [7:0] front_confidence,front_trajectory_points,front_association_flags,
 output wire busy,output wire [31:0] published_scenes,rejected_primitives,
 output wire [31:0] accepted_packets,crc_errors,format_errors,sequence_errors,
 input wire [31:0] rx_ingress_ms
);
 wire valid,release_scene,fixture,changed;
 wire [7:0] vc,ec,tc;wire [4:0] mask,invalidate;
 wire [79:0] ages;wire [159:0] offsets;wire [63:0] hand_ns,face_ns,epoch,seq;
 wire [31:0] capture,eyes,arrival;
 wire [1:0] actor_slot;wire [31:0] actor_track_id,ui_status,display_generation;
 wire [7:0] classification_confidence,trajectory_points,association_flags;
 wire [6:0] va,ea;wire [5:0] ta;
 wire [50:0] vd;wire [17:0] ed;wire [25:0] td;wire [5:0] raw_video_pixel;
 twin_scene_rx #(.EXTERNAL_ARRIVAL(EXTERNAL_ARRIVAL)) u_rx(
  .clk(clk),.rst(rst),.now_ms(now_ms),.rx_valid(rx_valid),.rx_data(rx_data),.rx_ready(rx_ready),.rx_ingress_ms(rx_ingress_ms),
  .scene_release(release_scene),.scene_valid(valid),.vertex_count(vc),.edge_count(ec),.triangle_count(tc),
  .valid_mask(mask),.fixture(fixture),.source_ages(ages),.group_offsets(offsets),
  .source_hand_ns(hand_ns),.source_face_ns(face_ns),.session_epoch(epoch),.scene_sequence(seq),
  .source_capture_sequence(capture),.eye_metrics(eyes),.arrival_ms(arrival),
  .actor_slot(actor_slot),.actor_track_id(actor_track_id),.ui_status(ui_status),.display_generation(display_generation),
  .classification_confidence(classification_confidence),.trajectory_points(trajectory_points),.association_flags(association_flags),
  .invalidate_mask(invalidate),.epoch_changed(changed),.vertex_addr(va),.vertex_data(vd),
  .edge_addr(ea),.edge_data(ed),.triangle_addr(ta),.triangle_data(td),
  .accepted_packets(accepted_packets),.crc_errors(crc_errors),.format_errors(format_errors),.sequence_errors(sequence_errors));
 twin_raster u_raster(
  .clk(clk),.rst(rst),.now_ms(now_ms),.vblank(vblank),.scene_valid(valid),.scene_release(release_scene),
  .vertex_count(vc),.edge_count(ec),.triangle_count(tc),.valid_mask(mask),.fixture(fixture),
  .source_ages(ages),.group_offsets(offsets),.source_hand_ns(hand_ns),.source_face_ns(face_ns),
  .session_epoch(epoch),.scene_sequence(seq),.source_capture_sequence(capture),.eye_metrics(eyes),.arrival_ms(arrival),
  .actor_slot(actor_slot),.actor_track_id(actor_track_id),.ui_status(ui_status),.display_generation(display_generation),
  .classification_confidence(classification_confidence),.trajectory_points(trajectory_points),.association_flags(association_flags),
  .invalidate_mask(invalidate),.epoch_changed(changed),.vertex_addr(va),.vertex_data(vd),
  .edge_addr(ea),.edge_data(ed),.triangle_addr(ta),.triangle_data(td),.video_addr(video_addr),.video_pixel(raw_video_pixel),
  .front_ready(front_ready),.front_valid_mask(front_valid_mask),.front_fixture(front_fixture),
  .front_source_ages(front_source_ages),.front_arrival_ms(front_arrival_ms),.front_hand_ns(front_hand_ns),.front_face_ns(front_face_ns),
  .front_epoch(front_epoch),.front_sequence(front_sequence),.front_capture_sequence(front_capture_sequence),.front_eye_metrics(front_eye_metrics),
  .front_actor_slot(front_actor_slot),.front_actor_track_id(front_actor_track_id),.front_ui_status(front_ui_status),.front_display_generation(front_display_generation),
  .front_confidence(front_confidence),.front_trajectory_points(front_trajectory_points),.front_association_flags(front_association_flags),
  .busy(busy),.published_scenes(published_scenes),.rejected_primitives(rejected_primitives));
 // Second cycle: fail closed for missing/stale groups. Callers cannot bypass
 // the freshness gate by displaying the framebuffer memory directly.
 always @(posedge clk)begin
  if(rst)video_pixel<=0;
  else if(front_ready && raw_video_pixel[5:3]>=1 && raw_video_pixel[5:3]<=5 && front_valid_mask[raw_video_pixel[5:3]-1'b1])video_pixel<=raw_video_pixel;
  else video_pixel<=0;
 end
endmodule
`default_nettype wire
