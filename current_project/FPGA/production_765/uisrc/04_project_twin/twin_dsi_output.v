`timescale 1ns/1ps
`default_nettype none
// Qualified DSI source chain, with stable config flags synchronized locally.
module twin_dsi_output(
 input wire sys_clk,clock_reset,output wire monitor_hs,monitor_lock,output wire ui_clk,output wire ui_reset,
 output wire timing_vs,timing_hs,timing_de,
 input wire pixel_vs,pixel_hs,pixel_de,input wire[23:0]pixel_rgb,
 output wire O_clk_hs_p,O_clk_lp_p,O_clk_lp_n,
 output wire[3:0]O_data_hs_p,O_data_lp_p,O_data_lp_n
);
 wire x2,x4,x4_90,lp_clk,locked,config_start,config_done;
 wire internal_reset;
 // The BAR-controlled clock reset may disappear while the PLL output is
 // stopped or between pixel clock edges. Assert immediately; release only
 // after three local edges. All PHY clocks, including LP, are derived from
 // the same PLL, so their recovery/removal remains covered by related-clock
 // STA rather than a false path from the independent PCIe clock.
 // Bootstrap counter has its own local release. A stopped PLL or lock loss
 // asserts reset immediately; its counter cannot release between UI edges.
 wire startup_raw_reset=clock_reset|~locked;
 (* async_reg="true" *) reg [2:0] startup_release;
 always @(posedge ui_clk or posedge startup_raw_reset)
  if(startup_raw_reset)startup_release<=0;
  else startup_release<={startup_release[1:0],1'b1};
 wire startup_reset=~startup_release[2];
 wire raw_reset=clock_reset|startup_reset|internal_reset;
 (* async_reg="true" *) reg [2:0] reset_release;
 always @(posedge ui_clk or posedge raw_reset)
  if(raw_reset)reset_release<=0;
  else reset_release<={reset_release[1:0],1'b1};
 assign ui_reset=~reset_release[2];
 assign monitor_hs=x4_90;
 assign monitor_lock=locked;
 pll u_pll(.refclk(sys_clk),.reset(clock_reset),.lock(locked),.clk0_out(ui_clk),.clk1_out(x2),.clk2_out(x4),.clk3_out(x4_90),.clk4_out(lp_clk));
 reset_gen u_reset(.I_clk(ui_clk),.I_pll_lock(1'b1),.I_rst(startup_reset),.O_rst_n(),.O_rst(internal_reset),.O_config_start(config_start));
 (* async_reg="true" *) reg[1:0]start_lp=0,done_ui=0;
 always @(posedge lp_clk)if(ui_reset)start_lp<=0;else start_lp<={start_lp[0],config_start};
 always @(posedge ui_clk)if(ui_reset)done_ui<=0;else done_ui<={done_ui[0],config_done};
 wire[23:0]unused_tpg;wire vs32,hs32,de32;wire[31:0]rgb32,hs_data;
 wire hs_enable,hs_last,lp_valid,lp_last,lp_ready;wire[7:0]lp_data;
 video_source #(.HTOTAL(1344),.HSA(24),.HBP(136),.HFP(160),.VTOTAL(635),.VSA(2),.VBP(21),.VFP(12))
  u_timing(.I_clk(ui_clk),.I_rst(ui_reset),.I_config_done(done_ui[1]),
  .O_rgb24b_vsync(timing_vs),.O_rgb24b_hsync(timing_hs),.O_rgb24b_de(timing_de),.O_rgb24b_data(unused_tpg));
 rgb_24b_to_32b #(.H_ACTIVE(1024)) u_pack(.I_clk(ui_clk),.I_rst(ui_reset),
  .I_vsync(pixel_vs),.I_hsync(pixel_hs),.I_de(pixel_de),.I_data(pixel_rgb),
  .O_vsync(vs32),.O_hsync(hs32),.O_de(de32),.O_data(rgb32));
 dsi_video_mode_packet #(.H_ACTIVE(1024)) u_packet(.I_clk(ui_clk),.I_rst(ui_reset),
  .I_vsync(vs32),.I_hsync(hs32),.I_de(de32),.I_data(rgb32),.O_hs_en(hs_enable),.O_hs_data(hs_data),.O_hs_last(hs_last));
 display_config_wrapper u_config(.I_clk(lp_clk),.I_rst(ui_reset),.I_config_start(start_lp[1]),.O_config_done(config_done),
  .O_lp_tx_valid(lp_valid),.O_lp_tx_last(lp_last),.O_lp_tx_data(lp_data),.I_lp_tx_ready(lp_ready));
 mipi_dphy_tx_wrapper #(.LANE_NUM(4),.HS_TX_FIFO_TYPE("DRAM"),.LP_TX_FIFO_TYPE("DRAM"),.LP_TX_MAX_DATA_LENGTH(8),
  .CLK_LANE_MODE("CONTINUE"),.T_DATA_LPX(10),.T_DATA_HS_PREPARE(10),.T_DATA_HS_ZERO(20),.T_DATA_HS_TRAIL(20),
  .T_CLK_LPX(10),.T_CLK_PREPARE(10),.T_CLK_ZERO(10),.T_CLK_PRE(10),.T_CLK_POST(10),.T_CLK_TRAIL(10)) u_phy(
  .I_hs_clk(ui_clk),.I_hs_clk_x2(x2),.I_hs_clk_x4(x4),.I_hs_clk_x4_90d(x4_90),.I_rst(ui_reset),
  .I_hs_tx_valid(hs_enable),.I_hs_tx_data(hs_data),.I_hs_tx_last(hs_last),.O_hs_tx_ready(),
  .I_lpdt_clk(lp_clk),.I_lp_tx_valid(lp_valid),.I_lp_tx_data(lp_data),.I_lp_tx_last(lp_last),.O_lp_tx_ready(lp_ready),
  .O_clk_hs_p(O_clk_hs_p),.O_data_hs_p(O_data_hs_p),.O_clk_lp_p(O_clk_lp_p),.O_clk_lp_n(O_clk_lp_n),
  .O_data_lp_p(O_data_lp_p),.O_data_lp_n(O_data_lp_n));
endmodule
`default_nettype wire
