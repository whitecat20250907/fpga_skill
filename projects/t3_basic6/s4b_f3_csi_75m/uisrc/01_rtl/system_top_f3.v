`timescale 1ns/1ps
// IMX415 -> vendor CSI RX/ISP -> YUYV -> on-chip CDC -> CSI-2 TX -> RK3576.
// F1 -> F2 gray/Gauss/histEq -> F3 four-lane LZ77 -> F4 CSI-2 container.
// The compressed F3 wire format is developed in a separate next stage.
module system_top_f3 (
    input  wire       I_sysclk_25m,
    output wire       O_clk_24m,
    output wire       O_clk_rst,
    output wire       O_cam_scl,
    inout  wire       IO_cam_sda,
    input  wire       I_clk_hs_p,
    input  wire [3:0] I_data_hs_p,
    input  wire [3:0] I_data_lp_p,
    input  wire [3:0] I_data_lp_n,
    input  wire       I_dsi_en,
    output wire       O_mipi_dsi_hs_clk_p,
    output wire [3:0] O_mipi_dsi_hs_data_p,
    output wire       O_mipi_dsi_lp_clk_p,
    output wire       O_mipi_dsi_lp_clk_n,
    output wire [3:0] O_mipi_dsi_lp_data_p,
    output wire [3:0] O_mipi_dsi_lp_data_n
);
    wire clk_24m, clk_70m, sys_lock;
    wire unused_pclk1, unused_pclk5;
    ui_pll X_ui_pll (
        .refclk(I_sysclk_25m), .reset(1'b0), .lock(sys_lock),
        .clk0_out(clk_24m), .clk1_out(unused_pclk1),
        .clk2_out(unused_pclk5), .clk3_out(clk_70m)
    );
    PH1_LOGIC_ODDR X_cam_clk (
        .q(O_clk_24m), .clk(clk_24m), .d0(1'b1), .d1(1'b0), .rst(1'b0)
    );
    assign O_clk_rst = 1'b1;
    wire cfg_done, ae_cfg_done;
    ui_cfg_imx415 #(.CLK_DIV(24_000_000/100_000-1)) X_ui_cfg_imx415 (
        .I_clk(clk_24m), .I_rst_n(sys_lock),
        .I_ae_req(1'b0), .I_ae_data(8'd0),
        .O_cam_scl(O_cam_scl), .IO_cam_sda(IO_cam_sda),
        .O_cfg_done(cfg_done), .O_ae_cfg_done(ae_cfg_done)
    );

    wire rx_clk, rx_valid;
    wire [31:0] rx_data;
    wire [3:0] lane_error;
    mipi_dphy_rx_over_lvds_wrapper #(
        .DEVICE("PH1"), .LANE_NUM(4)
    ) X_mipi_dphy_rx_over_lvds_wrapper (
        .I_lp_clk(clk_70m), .I_rst(~sys_lock),
        .I_mipi_clk_p(I_clk_hs_p),
        .I_mipi_data_hs_p(I_data_hs_p),
        .I_mipi_data_lp_p(I_data_lp_p),
        .I_mipi_data_lp_n(I_data_lp_n),
        .I_lane_hs_invert(4'b0000), .I_lane_lp_invert(4'b0000),
        .O_hs_rx_clk(rx_clk), .O_hs_rx_valid(rx_valid),
        .O_hs_rx_data(rx_data), .O_lp_rx_lane0_p(),
        .O_lp_rx_lane0_n(), .O_lane_error(lane_error)
    );
    wire csi_sof, csi_eof, csi_valid;
    wire [31:0] csi_data;
    ui_csi_unpacket_4lane X_ui_csi_unpacket_4lane (
        .I_clk(rx_clk), .I_rst_n(sys_lock),
        .I_hs_valid(rx_valid), .I_hs_data(rx_data),
        .O_csi_frame_start(csi_sof), .O_csi_frame_end(csi_eof),
        .O_csi_valid(csi_valid), .O_csi_data(csi_data)
    );
    wire raw_sof, raw_eof, raw_valid;
    wire [39:0] raw_data;
    ui_raw10_unpacket_4lane X_ui_raw10_unpacket_4lane (
        .I_clk(rx_clk), .I_rst_n(sys_lock),
        .I_csi_frame_start(csi_sof), .I_csi_frame_end(csi_eof),
        .I_csi_valid(csi_valid), .I_csi_data(csi_data),
        .O_raw10_frame_start(raw_sof), .O_raw10_frame_end(raw_eof),
        .O_raw10_valid(raw_valid), .O_raw10_data(raw_data)
    );
    wire [39:0] axis_raw;
    wire axis_valid, axis_last, axis_sof;
    ui_image_correction #(.DATA_WIDTH(40), .TDEST_WIDTH(10))
      X_ui_image_correction (
        .I_clk(rx_clk), .I_rst_n(sys_lock),
        .I_raw_data(raw_data), .I_raw_valid(raw_valid),
        .I_raw_frame_start(raw_sof), .I_raw_frame_end(raw_eof),
        .O_raw_tdata(axis_raw), .O_raw_tlast(axis_last),
        .O_raw_tvalid(axis_valid), .O_raw_tuser(axis_sof)
    );
    wire [127:0] isp_rgbx;
    wire isp_valid, isp_sof, isp_last, isp_ready;
    ui_isp_top X_ui_isp_top (
        .I_clk(rx_clk), .I_rst_n(sys_lock),
        .I_tlast(axis_last), .I_tuser(axis_sof),
        .I_tdata(axis_raw), .I_tvalid(axis_valid), .I_tdest(),
        .O_tready(isp_ready), .O_tdata(isp_rgbx),
        .O_tlast(isp_last), .O_tuser(isp_sof),
        .O_tvalid(isp_valid), .I_tready()
    );
    wire yuyv_valid, yuyv_sof, yuyv_last;
    wire [63:0] yuyv_data;
    rgb_to_yuv422_quad u_rgb2yuv_quad (
        .clk(rx_clk), .rst_n(sys_lock),
        .i_de(isp_valid), .i_user_sof(isp_sof),
        .i_last(isp_last), .i_data(isp_rgbx),
        .o_de(yuyv_valid), .o_user_sof(yuyv_sof),
        .o_last(yuyv_last), .o_data(yuyv_data)
    );

    wire dsi_pll_lock, unused_25m;
    wire byte_clk, hs_x2, hs_x4, hs_x4_q, lp_clk;
    pll u_ui_pll_dsi (
        .refclk(I_sysclk_25m), .reset(1'b0),
        .lock(dsi_pll_lock), .clk0_out(unused_25m),
        .clk1_out(byte_clk), .clk2_out(hs_x2),
        .clk3_out(hs_x4), .clk4_out(hs_x4_q),
        .clk5_out(lp_clk)
    );
    reg [2:0] en_sync = 3'b000;
    always @(posedge byte_clk or negedge dsi_pll_lock)
        if (!dsi_pll_lock) en_sync <= 3'b000;
        else en_sync <= {en_sync[1:0], I_dsi_en};
    wire tx_enable = en_sync[2];
    reg [7:0] rst_sync = 8'd0;
    always @(posedge byte_clk or negedge dsi_pll_lock)
        if (!dsi_pll_lock) rst_sync <= 8'd0;
        else rst_sync <= {rst_sync[6:0], tx_enable};
    wire tx_rst_n = rst_sync[7];
    wire tx_valid, tx_ready, tx_sof, tx_last, overflow;
    wire [31:0] tx_data;
    wire gauss_valid, gauss_sof, gauss_last, gauss_overlap;
    wire [63:0] gauss_data;
    gauss3x3_yuyv_quad #(.WIDTH(1920), .HEIGHT(1080),
                         .BOTTOM_WAIT(1024)) u_gauss (
        .clk(rx_clk), .rst_n(sys_lock & tx_rst_n),
        .s_valid(yuyv_valid), .s_data(yuyv_data),
        .s_sof(yuyv_sof), .s_last(yuyv_last),
        .m_valid(gauss_valid), .m_data(gauss_data),
        .m_sof(gauss_sof), .m_last(gauss_last),
        .input_overlap(gauss_overlap)
    );
    wire eq_valid, eq_sof, eq_last, eq_overlap;
    wire [63:0] eq_data;
    histeq_yuyv_quad #(.WIDTH(1920), .HEIGHT(1080),
                      .HIST_SHIFT(5),.BINS(64)) u_histeq (
        .clk(rx_clk), .rst_n(sys_lock & tx_rst_n),
        .s_valid(gauss_valid), .s_data(gauss_data),
        .s_sof(gauss_sof), .s_last(gauss_last),
        .m_valid(eq_valid), .m_data(eq_data),
        .m_sof(eq_sof), .m_last(eq_last),
        .blank_overlap(eq_overlap)
    );
    wire comp_valid,comp_sof,comp_last,comp_overlap;
    wire [63:0] comp_data;
    lz4_line_packetizer #(.WIDTH(1920),.HEIGHT(1080),
                          .QUANT_BITS(4)) u_compress (
        .clk(rx_clk),.rst_n(sys_lock & tx_rst_n),
        .s_valid(eq_valid),.s_data(eq_data),
        .s_sof(eq_sof),.s_last(eq_last),
        .sensor_sof(csi_sof),
        .link_error({lane_error,overflow,gauss_overlap,eq_overlap}),
        .m_valid(comp_valid),.m_data(comp_data),
        .m_sof(comp_sof),.m_last(comp_last),
        .line_overlap(comp_overlap)
    );
    yuyv_quad_async_bridge #(.ADDR_BITS(10)) u_bridge (
        .src_clk(rx_clk), .dst_clk(byte_clk),
        .rst_n(sys_lock & tx_rst_n),
        .s_valid(comp_valid), .s_data(comp_data),
        .s_sof(comp_sof), .s_last(comp_last), .overflow(overflow),
        .m_valid(tx_valid), .m_ready(tx_ready),
        .m_data(tx_data), .m_sof(tx_sof), .m_last(tx_last)
    );
    wire hs_en, hs_last;
    wire [31:0] hs_data;
    csi2_frame_tx #(
        .DT(6'h1E), .VC(2'd0), .H_ACTIVE(1280), .V_ACTIVE(1080),
        .BPP_NUM(2), .BPP_DEN(1),
        .GAP_LINE(32'd200), .GAP_FRAME(32'd4000)
    ) u_csi2_frame_tx (
        .clk(byte_clk), .rst_n(tx_rst_n), .enable(tx_enable),
        .s_tvalid(tx_valid), .s_tready(tx_ready),
        .s_tdata(tx_data), .s_tuser_sof(tx_sof), .s_tlast(tx_last),
        .hs_en(hs_en), .hs_data(hs_data), .hs_last(hs_last),
        .frame_cnt(), .packet_cnt()
    );
    mipi_dphy_tx_wrapper #(
        .LANE_NUM(4), .HS_TX_FIFO_TYPE("DRAM"),
        .LP_TX_FIFO_TYPE("DRAM"), .LP_TX_MAX_DATA_LENGTH(8),
        .CLK_LANE_MODE("INTERRUPT"),
        .T_DATA_LPX(10), .T_DATA_HS_PREPARE(7), .T_DATA_HS_ZERO(30),
        .T_DATA_HS_TRAIL(20), .T_CLK_LPX(10), .T_CLK_PREPARE(10),
        .T_CLK_ZERO(10), .T_CLK_PRE(10), .T_CLK_POST(10),
        .T_CLK_TRAIL(10)
    ) u_dphy_tx (
        .I_hs_clk(byte_clk), .I_hs_clk_x2(hs_x2),
        .I_hs_clk_x4(hs_x4), .I_hs_clk_x4_90d(hs_x4_q),
        .I_lpdt_clk(lp_clk), .I_rst(~tx_rst_n),
        .I_hs_tx_valid(hs_en), .I_hs_tx_data(hs_data),
        .I_hs_tx_last(hs_last), .O_hs_tx_ready(),
        .I_lp_tx_valid(1'b0), .I_lp_tx_data(8'h00),
        .I_lp_tx_last(1'b0), .O_lp_tx_ready(),
        .O_clk_hs_p(O_mipi_dsi_hs_clk_p),
        .O_data_hs_p(O_mipi_dsi_hs_data_p),
        .O_clk_lp_p(O_mipi_dsi_lp_clk_p),
        .O_clk_lp_n(O_mipi_dsi_lp_clk_n),
        .O_data_lp_p(O_mipi_dsi_lp_data_p),
        .O_data_lp_n(O_mipi_dsi_lp_data_n)
    );
endmodule
