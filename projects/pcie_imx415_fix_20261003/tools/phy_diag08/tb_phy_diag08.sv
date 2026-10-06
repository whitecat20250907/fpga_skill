`timescale 1ns/1ps
module tb_phy_diag08;
 reg user_clk=0,byte_clk=0,byte_run=1,reset_n=0;
 always #4 user_clk=~user_clk;
 always #4.489 if(byte_run) byte_clk=~byte_clk; else byte_clk=0;
 reg [6:0] control=0;
 wire [223:0] diag0,diag1,old_snapshot;
 wire [31:0] stat0,stat1;
 reg test_done=0;
 integer checks=0,scoreboard_cycles=0;
 cam_video_source #(.DEVICE("PH1A")) dut(
  .user_clk(user_clk),.user_rst_n(reset_n),.enable(1'b1),
  .cfg_bayer_mode(2'b00),.cfg_img_width(13'd1280),.cfg_img_height(13'd720),
  .cfg_crop_v_start(15'd0),.cfg_crop_v_end(15'd721),.cfg_crop_h_end(15'd321),
  .mipi_ref_clock(user_clk),.mipi_clk_hs_rx_p(byte_clk),.mipi_data_hs_p(4'b0),
  .frame_request(1'b1),.m_tready(1'b1),.debug_button(1'b1),
  .phy_control_shadow(control),.phy_diag0(diag0),.phy_diag1(diag1),
  .phy_diag0_status(stat0),.phy_diag1_status(stat1),.csi_snapshot(old_snapshot),
  .m_tdata(),.m_tvalid(),.m_tlast(),.m_frame_last(),.sof(),.eof(),
  .frame_count_out(),.active_bayer_mode(),.mipi_div_clk_out(),
  .auto_delay_done(),.mipi_tvalid_out(),.dbg_mipi(),.dbg_delay(),
  .phy_diag0_clock_delta(),.phy_diag1_clock_delta(),.csi_snapshot_status(),
  .csi_clock_delta(),.dbg_best_len());
 // Accelerate only testbench request periods; the production candidate keeps
 // PERIOD125000/default12.5M. Use the exact existing snapshot implementation.
 defparam dut.u_mipi_csi_rx.u_phy_control_snapshot.PERIOD=16;
 defparam dut.u_phy_diag0_snapshot.PERIOD=37;
 defparam dut.u_phy_diag1_snapshot.PERIOD=37;
 defparam dut.u_csi_snapshot.PERIOD=37;
 reg [31:0] expected_lanes[0:3];
 reg [31:0] expected_payload=0,expected_words=0,expected_errors=0;
 reg [31:0] expected_current=0,expected_last=0,expected_fs=0;
 reg [7:0] expected_sticky=0;
 integer lane;
 // Exact event scoreboard samples pre-edge protocol outputs like the candidate.
 // This verifies totals/FS rollover even while the auto gate is closed.
 always @(posedge byte_clk or negedge reset_n) begin
  if(!reset_n) begin
   for(lane=0;lane<4;lane=lane+1) expected_lanes[lane]=0;
   expected_payload=0;expected_words=0;expected_errors=0;
   expected_current=0;expected_last=0;expected_fs=0;expected_sticky=0;
  end else begin
   for(lane=0;lane<4;lane=lane+1)
    if(dut.u_mipi_csi_rx.w_rx_byte_data_align_vaild[lane])
     expected_lanes[lane]=expected_lanes[lane]+1;
   if(dut.u_mipi_csi_rx.w_payload_valid) expected_payload=expected_payload+1;
   if(dut.u_mipi_csi_rx.w_word_align_data_vaild) expected_words=expected_words+1;
   if(dut.u_mipi_csi_rx.w_packet_error) expected_errors=expected_errors+1;
   expected_sticky=expected_sticky|{dut.u_mipi_csi_rx.w_packet_error,
    dut.u_mipi_csi_rx.w_vsync_out,dut.u_mipi_csi_rx.w_payload_valid,
    dut.u_mipi_csi_rx.w_word_align_data_vaild,dut.u_mipi_csi_rx.w_rx_byte_data_align_vaild};
   if(dut.u_mipi_csi_rx.w_vsync_out) begin
    expected_fs=expected_fs+1;expected_last=expected_current;
    expected_current=dut.u_mipi_csi_rx.w_payload_valid&&dut.u_mipi_csi_rx.w_payload_last ? 1 : 0;
   end else if(dut.u_mipi_csi_rx.w_payload_valid&&dut.u_mipi_csi_rx.w_payload_last)
    expected_current=expected_current+1;
   #0.2;
   if(dut.u_mipi_csi_rx.O_phy_diag0[127:0]!=={expected_lanes[3],expected_lanes[2],expected_lanes[1],expected_lanes[0]})
    $fatal(1,"lane valid-cycle exact count mismatch");
   if(dut.u_mipi_csi_rx.O_phy_diag0[167:160]!==expected_sticky)
    $fatal(1,"sticky observation mismatch");
   if(dut.u_mipi_csi_rx.O_phy_diag1!=={expected_payload,expected_words,expected_errors,expected_current,expected_last,expected_fs})
    $fatal(1,"ungated protocol exact count/FS rollover mismatch");
   scoreboard_cycles=scoreboard_cycles+1;
  end
 end
 reg [23:0] hdr_data=0;
 wire [7:0] hdr_ecc;
 csi_rx_hdr_ecc encoder(.data(hdr_data),.ecc(hdr_ecc));
 function automatic [15:0] crc_byte(input [15:0] crc,input [7:0] data);
  reg [15:0] v;integer bitno;
  begin v=crc;for(bitno=0;bitno<8;bitno=bitno+1)
   if(v[0]^data[bitno])v=(v>>1)^16'h8408;else v=v>>1;crc_byte=v;end
 endfunction
 task automatic idle(input integer cycles);
  begin @(negedge byte_clk);dut.u_mipi_csi_rx.u_csi_rx_phy.sim_lane_valid=0;
   dut.u_mipi_csi_rx.u_csi_rx_phy.sim_bytes=32'h44332211;
   repeat(cycles)@(negedge byte_clk);end
 endtask
 task automatic word(input [31:0] value);
  begin @(negedge byte_clk);dut.u_mipi_csi_rx.u_csi_rx_phy.sim_bytes=value;
   dut.u_mipi_csi_rx.u_csi_rx_phy.sim_lane_valid=4'hf;end
 endtask
 task automatic header(input [5:0] dt,input integer wc);
  begin wait(dut.u_mipi_csi_rx.w_sync_wait);
   @(negedge byte_clk);hdr_data={wc[15:0],2'b0,dt};#0.1;
   dut.u_mipi_csi_rx.u_csi_rx_phy.sim_bytes={hdr_ecc,hdr_data};
   dut.u_mipi_csi_rx.u_csi_rx_phy.sim_lane_valid=4'hf;end
 endtask
 task automatic raw_line(input bad_crc);
  reg [15:0] crc;
  begin crc=16'hffff;crc=crc_byte(crc,8'h13);crc=crc_byte(crc,8'h27);
   crc=crc_byte(crc,8'h91);crc=crc_byte(crc,8'h3a);crc=crc_byte(crc,8'hc5);
   if(bad_crc)crc=crc^16'h0100;
   header(6'h2b,5);word(32'h3a912713);word({8'h55,crc[15:8],crc[7:0],8'hc5});idle(12);
  end
 endtask
 task automatic command(input [6:0] value);
  begin @(negedge user_clk);control=value;
   wait(dut.u_mipi_csi_rx.phy_control_byte===value);
   checks=checks+1;repeat(4)@(negedge byte_clk);
   if(dut.u_mipi_csi_rx.u_csi_rx_phy.I_override_enable!==value[6] ||
      dut.u_mipi_csi_rx.u_csi_rx_phy.I_override_tap!==value[5:0])
    $fatal(1,"coherent command did not reach PHY inputs");end
 endtask
 initial begin
  #31;reset_n=1;idle(12);
  // Change x4-origin status between byte edges; exactly the third local edge
  // exposes it in the diagnostic flags, never the direct asynchronous input.
  #1.1;dut.u_mipi_csi_rx.u_csi_rx_phy.sim_sampler_reset_n=1;
  @(posedge byte_clk);#0.2;
  if(dut.u_mipi_csi_rx.O_phy_diag0[175]!==0)$fatal(1,"sampler status bypassed first FF");
  @(posedge byte_clk);#0.2;
  if(dut.u_mipi_csi_rx.O_phy_diag0[175]!==0)$fatal(1,"sampler status bypassed second FF");
  @(posedge byte_clk);#0.2;
  if(dut.u_mipi_csi_rx.O_phy_diag0[175]!==1)$fatal(1,"sampler status missing after third FF");
  checks=checks+1;
  command(7'h4d);command(7'h29);command(7'h00);
  // Distinct lane events before calibration; word valid stays low for masks.
  @(negedge byte_clk);dut.u_mipi_csi_rx.u_csi_rx_phy.sim_lane_valid=4'b0101;
  repeat(5)@(negedge byte_clk);idle(4);
  header(0,0);idle(12);raw_line(0);raw_line(1);header(0,0);idle(12);
  if(dut.u_mipi_csi_rx.O_csi_raw_packets!==0 || dut.u_mipi_csi_rx.O_csi_crc_errors!==0)
   $fatal(1,"original calibrated count gate changed");
  if(expected_payload!==4 || expected_errors!==1 || expected_last!==2 || expected_current!==0 || expected_fs!==2)
   $fatal(1,"pre-cal raw observations not exact or falsely CRC-qualified");
  checks=checks+1;
  // Actual snapshots are coherent held buses from byte domain into user domain.
  repeat(150)@(negedge user_clk);
  if(diag1[191:0]!==dut.u_mipi_csi_rx.O_phy_diag1 || diag0[191:0]!==dut.u_mipi_csi_rx.O_phy_diag0)
   $fatal(1,"user-domain held diagnostic snapshots do not equal stable byte-domain data");
  if(diag0[223:192]==0||diag1[223:192]==0||stat0[31:1]==0||stat1[31:1]==0)
   $fatal(1,"snapshot source_cycles/status do not advance");
  checks=checks+1;
  // Byte clock stops: changed source command must not fake an acknowledgement.
  @(negedge byte_clk);byte_run=0;
  @(negedge user_clk);control=7'h5a;
  repeat(60)@(negedge user_clk);
  if(dut.u_mipi_csi_rx.phy_control_byte!==7'h00)$fatal(1,"command changed without byte-clock edges");
  byte_run=1;wait(dut.u_mipi_csi_rx.phy_control_byte===7'h5a);checks=checks+1;
  // Assert reset with byte clock stopped; release waits for actual local edges.
  @(negedge byte_clk);byte_run=0;#0.7;reset_n=0;
  #0.3;
  if(dut.u_mipi_csi_rx.O_phy_diag0[127:0]!==0||dut.u_mipi_csi_rx.O_phy_diag1!==0)
   $fatal(1,"byte counter asynchronous reset did not clear");
  #22;reset_n=1;control=7'h46;repeat(30)@(negedge user_clk);
  if(dut.u_mipi_csi_rx.phy_control_byte!==0)$fatal(1,"destination reset released with no local clock");
  byte_run=1;wait(dut.u_mipi_csi_rx.phy_control_byte===7'h46);checks=checks+1;
  command(7'h00);idle(8);
  if(dut.u_mipi_csi_rx.O_phy_diag1!==0)$fatal(1,"pre-reset events reappeared");
  dut.u_mipi_csi_rx.u_csi_rx_phy.sim_cal_done=1;
  idle(8);header(0,0);idle(12);raw_line(0);idle(12);
  if(dut.u_mipi_csi_rx.O_csi_raw_packets!==1)$fatal(1,"post-cal original packet counting broken");
  checks=checks+1;
  test_done=1;
  $display("PASS PHY_DIAG08_DIGITAL_CDC_AND_EVENTS checks=%0d scoreboard_cycles=%0d (PHY/ISP stubs; no analog timing proof)",checks,scoreboard_cycles);
  $finish;
 end
 initial begin #200000;$fatal(1,"PHY diagnostic selfcheck timeout");end
endmodule
