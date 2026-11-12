`timescale 1ns/1ps
`default_nettype none
// Production data path: actual BAR commit -> timestamped async FIFO -> HFT2
// -> hardware XYZ renderer. UART and a Windows forwarding process are absent.
module twin_pcie_ui #(
 parameter TEXT_FILE="twin_text.mem",parameter FONT_FILE="twin_font.mem",
 parameter integer WORD_ADDR_BITS=9,SNAPSHOT_PERIOD=125000
)(
 input wire view_fire,view_sof,view_eol,view_eof,view_source_enable,
 input wire[95:0]view_rgb,input wire[2:0]view_count,input wire[31:0]view_id,input wire[63:0]view_tick,view_epoch,
 output wire[1:0]view_select,
 input wire bar_clk,input wire ui_clk,input wire rst_n,input wire[31:0]now_ms,
 input wire bar_write_valid,input wire[31:0]bar_write_address,bar_write_data,input wire[3:0]bar_write_strobe,
 input wire bar_read_valid,input wire[31:0]bar_read_address,
 output wire bar_read_select,output wire[31:0]bar_read_data,
 input wire i_vs,input wire i_hs,input wire i_de,
 output wire o_vs,output wire o_hs,output wire o_de,output wire[23:0]o_rgb,
 output wire[31:0]accepted_packets,crc_errors,format_errors,sequence_errors,published_scenes,
 output wire[4:0]feature_valid_mask,output wire feature_front_ready,
 output wire transport_reset,transport_fault
);
 (* async_reg="true" *) reg[2:0]ui_up=0;
 always @(posedge ui_clk or negedge rst_n)
  if(!rst_n)ui_up<=0;else ui_up<={ui_up[1:0],1'b1};
 wire byte_valid,byte_ready;wire[7:0]byte_data;wire[31:0]ingress_ms;
 wire ingress_read_select;wire[31:0]ingress_read_data,words,rejected_writes,generation;
 wire ready,flushing,ingress_bar_rst_n;wire ui_reset=!ui_up[2] || transport_reset;
 // One UI-domain monotonic millisecond clock is supplied by the board top.
 // A stream flush resets the scene, not this clock or the anchor timebase.
 twin_bar_ingress #(.WORD_ADDR_BITS(WORD_ADDR_BITS)) u_ingress(
  .bar_clk(bar_clk),.ui_clk(ui_clk),.rst_n(rst_n),.ui_now_ms(now_ms),
  .bar_write_valid(bar_write_valid),.bar_write_address(bar_write_address),.bar_write_data(bar_write_data),.bar_write_strobe(bar_write_strobe),
  .bar_read_valid(bar_read_valid),.bar_read_address(bar_read_address),.bar_read_select(ingress_read_select),.bar_read_data(ingress_read_data),
  .byte_valid(byte_valid),.byte_data(byte_data),.byte_ingress_ms(ingress_ms),.byte_ready(byte_ready && !ui_reset),
  .stream_reset(transport_reset),.writer_ready(ready),.flushing(flushing),.fault(transport_fault),
  .accepted_words(words),.rejected_writes(rejected_writes),.flush_generation(generation),.local_bar_reset_n(ingress_bar_rst_n));
 wire[31:0]source_frames,rejected_primitives,scene_generation;
 wire[31:0]source_pip;assign view_select=source_pip[2:1];
 wire csr_select,csr_valid,csr_busy;wire[31:0]csr_read,csr_rejected;wire[991:0]csr_front;
 twin_ui_csr u_hmi_csr(.bar_clk(bar_clk),.ui_clk(ui_clk),.rst_n(rst_n),
  .write_valid(bar_write_valid),.write_address(bar_write_address),.write_data(bar_write_data),.write_strobe(bar_write_strobe),
  .read_valid(bar_read_valid),.read_address(bar_read_address),.read_select(csr_select),.read_data(csr_read),
  .ui_blank(i_vs),.scene_generation(scene_generation),.front(csr_front),.source_pip(source_pip),.front_valid(csr_valid),.busy(csr_busy),.rejected(csr_rejected));
 wire view_read,view_pixel_valid,view_front_valid;wire[6:0]view_x,view_y;
 wire[7:0]view_pixel,view_width,view_height;wire[1:0]view_front_mode;
 wire[31:0]view_front_id,view_completed,view_dropped,view_malformed;wire[63:0]view_front_tick,view_front_epoch;
 hmi_input_viewer u_input_viewer(.src_clk(bar_clk),.ui_clk(ui_clk),.rst_n(rst_n&&!transport_reset),
  .enable(source_pip[0]&&view_source_enable),.mode(view_select),
  .fire(view_fire),.sof(view_sof),.eol(view_eol),.eof(view_eof),.count(view_count),.rgb(view_rgb),
  .frame_id(view_id),.frame_tick(view_tick),.epoch(view_epoch),.ui_blank(i_vs),.ui_ms(now_ms),
  .read_enable(view_read),.read_x(view_x),.read_y(view_y),.pixel(view_pixel),.pixel_valid(view_pixel_valid),
  .front_valid(view_front_valid),.front_mode(view_front_mode),.front_width(view_width),.front_height(view_height),
  .front_id(view_front_id),.front_tick(view_front_tick),.front_epoch(view_front_epoch),
  .completed(view_completed),.dropped(view_dropped),.malformed(view_malformed));
 twin_dashboard #(.TEXT_FILE(TEXT_FILE),.FONT_FILE(FONT_FILE),.EXTERNAL_ARRIVAL(1)) u_dashboard(
  .clk(ui_clk),.rst(ui_reset),.now_ms(now_ms),
  .csr_valid(csr_valid),.csr_eye(csr_front[3*32+:32]),
  .csr_pip(csr_front[22*32+:32]),.view_read(view_read),.view_x(view_x),.view_y(view_y),
  .view_pixel(view_pixel),.view_pixel_valid(view_pixel_valid),.view_front_valid(view_front_valid),.view_mode(view_front_mode),
  .csr_heat_context(csr_front[19*32+:32]),.csr_heat_sample(csr_front[23*32+:32]),
  .csr_menu(csr_front[12*32+:32]),.csr_menu_lo(csr_front[13*32+:32]),.csr_menu_hi(csr_front[14*32+:32]),
  .csr_calibration(csr_front[15*32+:32]),.csr_phase(csr_front[24*32+:32]),.csr_errors(csr_front[25*32+:32]),
  .csr_hits(csr_front[26*32+:32]),.csr_quality(csr_front[27*32+:32]),.csr_generation(csr_front[30*32+:32]),.scene_generation(scene_generation),.i_vs(i_vs),.i_hs(i_hs),.i_de(i_de),
  .rx_valid(byte_valid && !ui_reset),.rx_data(byte_data),.rx_ingress_ms(ingress_ms),.rx_ready(byte_ready),
  .o_vs(o_vs),.o_hs(o_hs),.o_de(o_de),.o_rgb(o_rgb),.source_frames(source_frames),
  .accepted_packets(accepted_packets),.crc_errors(crc_errors),.format_errors(format_errors),.sequence_errors(sequence_errors),
  .published_scenes(published_scenes),.rejected_primitives(rejected_primitives),
  .feature_valid_mask(feature_valid_mask),.feature_front_ready(feature_front_ready));
 wire[223:0]snapshot;wire[31:0]snapshot_status,clock_delta;
 csi_stats_snapshot #(.PERIOD(SNAPSHOT_PERIOD)) u_snapshot(.src_clk(ui_clk),.dst_clk(bar_clk),.rst_n(rst_n),
  .src_stats({26'd0,feature_front_ready,feature_valid_mask,published_scenes,accepted_packets,crc_errors,format_errors,sequence_errors}),
  .snapshot(snapshot),.status(snapshot_status),.clock_delta(clock_delta));
 // BAR readback is functional state, so it must not release directly
 // from the UI-domain DSI reset. Keep asynchronous assertion when BAR stops.
 // Reuse the ingress BAR release chain; no duplicate reset pipeline.
 wire snapshot_rst_n=ingress_bar_rst_n;
 reg snapshot_select;reg[31:0]snapshot_data;
 always @(posedge bar_clk or negedge snapshot_rst_n)begin
  if(!snapshot_rst_n)begin snapshot_select<=0;snapshot_data<=0;end
  else if(bar_read_valid)begin
   snapshot_select<=1;
   case(bar_read_address[19:0])
    20'h00c40:snapshot_data<=snapshot_status;
    20'h00c44:snapshot_data<=snapshot[191:160];
    20'h00c48:snapshot_data<=snapshot[159:128];
    20'h00f00:snapshot_data<=32'h31574956; // VIW1, input-viewer ABI
    20'h00f04:snapshot_data<=view_completed;
    20'h00f08:snapshot_data<=view_dropped;
    20'h00f0c:snapshot_data<=view_malformed;
    20'h00f10:snapshot_data<=source_pip;
    20'h00c4c:snapshot_data<=snapshot[127:96];
    20'h00c50:snapshot_data<=snapshot[95:64];
    20'h00c54:snapshot_data<=snapshot[63:32];
    20'h00c58:snapshot_data<=snapshot[31:0];
    20'h00c5c:snapshot_data<=clock_delta;
    default:begin snapshot_select<=0;snapshot_data<=0;end
   endcase
  end
 end
 assign bar_read_select=csr_select || snapshot_select || ingress_read_select;
 assign bar_read_data=csr_select ? csr_read : snapshot_select ? snapshot_data : ingress_read_data;
endmodule
`default_nettype wire
