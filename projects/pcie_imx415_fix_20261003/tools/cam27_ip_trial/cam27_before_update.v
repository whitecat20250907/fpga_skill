// Verilog netlist created by Tang Dynasty vRelease_2026.1_SP2
// Sun Oct  4 23:17:06 2026

`timescale 1ns / 1ps
module cam27_trial  // cam27_trial_seed.v(26)
  (
  refclk,
  reset,
  clk0_out,
  clk1_out,
  clk2_out,
  lock
  );

  input refclk;  // cam27_trial_seed.v(35)
  input reset;  // cam27_trial_seed.v(36)
  output clk0_out;  // cam27_trial_seed.v(38)
  output clk1_out;  // cam27_trial_seed.v(39)
  output clk2_out;  // cam27_trial_seed.v(40)
  output lock;  // cam27_trial_seed.v(37)

  wire clk0_buf;  // cam27_trial_seed.v(42)
  wire ui_pll_open0;  // cam27_trial_seed.v(106)
  wire ui_pll_open1;  // cam27_trial_seed.v(115)
  wire ui_pll_open10;  // cam27_trial_seed.v(117)
  wire ui_pll_open11;  // cam27_trial_seed.v(120)
  wire ui_pll_open12;  // cam27_trial_seed.v(120)
  wire ui_pll_open13;  // cam27_trial_seed.v(120)
  wire ui_pll_open14;  // cam27_trial_seed.v(119)
  wire ui_pll_open15;  // cam27_trial_seed.v(120)
  wire ui_pll_open16;  // cam27_trial_seed.v(119)
  wire ui_pll_open17;  // cam27_trial_seed.v(120)
  wire ui_pll_open18;  // cam27_trial_seed.v(119)
  wire ui_pll_open19;  // cam27_trial_seed.v(120)
  wire ui_pll_open2;  // cam27_trial_seed.v(116)
  wire ui_pll_open20;  // cam27_trial_seed.v(119)
  wire ui_pll_open21;  // cam27_trial_seed.v(120)
  wire ui_pll_open22;  // cam27_trial_seed.v(119)
  wire ui_pll_open23;  // cam27_trial_seed.v(120)
  wire ui_pll_open3;  // cam27_trial_seed.v(117)
  wire ui_pll_open4;  // cam27_trial_seed.v(117)
  wire ui_pll_open5;  // cam27_trial_seed.v(117)
  wire ui_pll_open6;  // cam27_trial_seed.v(117)
  wire ui_pll_open7;  // cam27_trial_seed.v(117)
  wire ui_pll_open8;  // cam27_trial_seed.v(117)
  wire ui_pll_open9;  // cam27_trial_seed.v(117)

  PH1_LOGIC_BUFG bufg_feedback (
    .i(clk0_buf),
    .o(clk0_out));  // cam27_trial_seed.v(44)
  PH1_PHY_PLL #(
    .CLKC0_CPHASE(3),
    .CLKC0_CPHASE_DIV2(0),
    .CLKC0_DIV(4),
    .CLKC0_DIV2_ENABLE("DISABLE"),
    .CLKC0_DUTY50("ENABLE"),
    .CLKC0_DUTY_INT(2),
    .CLKC0_ENABLE("ENABLE"),
    .CLKC0_FPHASE(0),
    .CLKC0_FPHASE_RSTSEL(0),
    .CLKC0_USR_RST("ENABLE"),
    .CLKC1_CPHASE(39),
    .CLKC1_CPHASE_DIV2(0),
    .CLKC1_DIV(40),
    .CLKC1_DIV2_ENABLE("DISABLE"),
    .CLKC1_DUTY50("ENABLE"),
    .CLKC1_DUTY_INT(20),
    .CLKC1_ENABLE("ENABLE"),
    .CLKC1_FPHASE(0),
    .CLKC1_FPHASE_RSTSEL(0),
    .CLKC1_USR_RST("ENABLE"),
    .CLKC2_CPHASE(49),
    .CLKC2_CPHASE_DIV2(0),
    .CLKC2_DIV(50),
    .CLKC2_DIV2_ENABLE("DISABLE"),
    .CLKC2_DUTY50("ENABLE"),
    .CLKC2_DUTY_INT(25),
    .CLKC2_ENABLE("DISABLE"),
    .CLKC2_FPHASE(0),
    .CLKC2_FPHASE_RSTSEL(0),
    .CLKC3_CPHASE(0),
    .CLKC3_CPHASE_DIV2(0),
    .CLKC3_DIV(1),
    .CLKC3_DIV2_ENABLE("DISABLE"),
    .CLKC3_DUTY50("ENABLE"),
    .CLKC3_DUTY_INT(1),
    .CLKC3_ENABLE("DISABLE"),
    .CLKC3_FPHASE(0),
    .CLKC3_FPHASE_RSTSEL(0),
    .CLKC4_CPHASE(0),
    .CLKC4_CPHASE_DIV2(0),
    .CLKC4_DIV(1),
    .CLKC4_DIV2_ENABLE("DISABLE"),
    .CLKC4_DUTY50("ENABLE"),
    .CLKC4_DUTY_INT(1),
    .CLKC4_ENABLE("DISABLE"),
    .CLKC4_FPHASE(0),
    .CLKC4_FPHASE_RSTSEL(0),
    .CLKC5_CPHASE(0),
    .CLKC5_CPHASE_DIV2(0),
    .CLKC5_DIV(1),
    .CLKC5_DIV2_ENABLE("DISABLE"),
    .CLKC5_DUTY50("ENABLE"),
    .CLKC5_DUTY_INT(1),
    .CLKC5_ENABLE("DISABLE"),
    .CLKC5_FPHASE(0),
    .CLKC5_FPHASE_RSTSEL(0),
    .CLKC6_CPHASE(0),
    .CLKC6_CPHASE_DIV2(0),
    .CLKC6_DIV(1),
    .CLKC6_DIV2_ENABLE("DISABLE"),
    .CLKC6_DUTY50("ENABLE"),
    .CLKC6_DUTY_INT(1),
    .CLKC6_ENABLE("DISABLE"),
    .CLKC6_FPHASE(0),
    .CLKC6_FPHASE_RSTSEL(0),
    .CLK_MAIN_ENABLE("DISABLE"),
    .DERIVE_PLL_CLOCKS("DISABLE"),
    .DITHER_ENABLE("DISABLE"),
    .DIVOUT_MUXC0("DIV"),
    .DIVOUT_MUXC1("DIV"),
    .DIVOUT_MUXC2("DIV"),
    .DIVOUT_MUXC3("DIV"),
    .DIVOUT_MUXC4("DIV"),
    .DIVOUT_MUXC5("DIV"),
    .DIVOUT_MUXC6("DIV"),
    .DYN_CPHASE_CLKC0_DIV2_EN("DISABLE"),
    .DYN_CPHASE_CLKC0_DIV_EN("DISABLE"),
    .DYN_CPHASE_CLKC1_DIV2_EN("DISABLE"),
    .DYN_CPHASE_CLKC1_DIV_EN("DISABLE"),
    .DYN_CPHASE_CLKC2_DIV2_EN("DISABLE"),
    .DYN_CPHASE_CLKC2_DIV_EN("DISABLE"),
    .DYN_CPHASE_CLKC3_DIV2_EN("DISABLE"),
    .DYN_CPHASE_CLKC3_DIV_EN("DISABLE"),
    .DYN_CPHASE_CLKC4_DIV2_EN("DISABLE"),
    .DYN_CPHASE_CLKC4_DIV_EN("DISABLE"),
    .DYN_CPHASE_CLKC5_DIV2_EN("DISABLE"),
    .DYN_CPHASE_CLKC5_DIV_EN("DISABLE"),
    .DYN_CPHASE_CLKC6_DIV2_EN("DISABLE"),
    .DYN_CPHASE_CLKC6_DIV_EN("DISABLE"),
    .DYN_FPHASE_EN("DISABLE"),
    .DYN_PHASE_PATH_SEL("DISABLE"),
    .EXT_USR_FREQ_EN("DISABLE"),
    .FBCLK_DIV(27),
    .FBKCLK("CLKC0_EXT"),
    .FBKCLK_INT("VCO_PHASE0"),
    .FEEDBK_MODE("NORMAL"),
    .FIN("100.000000"),
    .FRAC_ENABLE("DISABLE"),
    .FREQ_OFFSET(0),
    .GEN_BASIC_CLOCK("DISABLE"),
    .GMC_GAIN(0),
    .HIGH_SPEED_EN("DISABLE"),
    .ICP_CUR(0),
    .INTPI(0),
    .LPF_CAP(0),
    .LPF_RES(0),
    .MAIN_MUXC("MAIN"),
    .MPHASE_ENABLE("DISABLE"),
    .PD_DIG("DISABLE"),
    .PHASE_PATH_SEL(0),
    .PLL_FEED_TYPE("EXTERNAL"),
    .PLL_USR_RST("ENABLE"),
    .PREDIV_MUXC0("VCO"),
    .PREDIV_MUXC1("VCO"),
    .PREDIV_MUXC2("VCO"),
    .PREDIV_MUXC3("VCO"),
    .PREDIV_MUXC4("VCO"),
    .PREDIV_MUXC5("VCO"),
    .PREDIV_MUXC6("VCO"),
    .REFCLK_DET_BYP("DISABLE"),
    .REFCLK_DIV(10),
    .REFCLK_OUT_ENABLE("DISABLE"),
    .REFCLK_USR_RST("DISABLE"),
    .SDM_FRAC(0),
    .SSC_AMP(0.000000),
    .SSC_ENABLE("DISABLE"),
    .SSC_FREQ_DIV(0),
    .SSC_MODE("CENTER"),
    .SSC_RNGE(0),
    .WORK_MODE("USER"))
    pll_inst (
    .clkc_en(8'b00000011),
    .clkc_rst(2'b00),
    .cps_step(2'b00),
    .drp_addr(8'b00000000),
    .drp_clk(1'b0),
    .drp_rd(1'b0),
    .drp_rstn(1'b1),
    .drp_sel(1'b0),
    .drp_wdata(8'b00000000),
    .drp_wr(1'b0),
    .ext_freq_mod_clk(1'b0),
    .ext_freq_mod_en(1'b0),
    .ext_freq_mod_val(17'b00000000000000000),
    .fbclk(clk0_out),
    .pllpd(1'b0),
    .pllreset(reset),
    .psclk(1'b0),
    .psclksel(3'b000),
    .psdown(1'b0),
    .psstep(1'b0),
    .refclk(refclk),
    .refclk_rst(1'b0),
    .ssc_en(1'b0),
    .wakeup(1'b0),
    .clkc({ui_pll_open22,ui_pll_open20,ui_pll_open18,ui_pll_open16,ui_pll_open14,clk2_out,clk1_out,clk0_buf}),
    .clkcb({ui_pll_open23,ui_pll_open21,ui_pll_open19,ui_pll_open17,ui_pll_open15,ui_pll_open13,ui_pll_open12,ui_pll_open11}),
    .drp_err(ui_pll_open1),
    .drp_rdata({ui_pll_open10,ui_pll_open9,ui_pll_open8,ui_pll_open7,ui_pll_open6,ui_pll_open5,ui_pll_open4,ui_pll_open3}),
    .drp_rdy(ui_pll_open2),
    .lock(lock),
    .psdone(ui_pll_open0));  // cam27_trial_seed.v(95)

  // synthesis translate_off
  glbl glbl();
  always @(*) begin
    glbl.gsr <= PH1_PHY_GSR.gsr;
    glbl.gsrn <= PH1_PHY_GSR.gsrn;
    glbl.done_gwe <= PH1_PHY_GSR.done_gwe;
    glbl.usr_gsrn_en <= PH1_PHY_GSR.usr_gsrn_en;
  end
  // synthesis translate_on

endmodule 

