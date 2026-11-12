/*===========================================*\
Filename        : imx415_pcie_top.v
Project name    : Phase 11 �� IMX415 1080p60fps Camera via PCIe (AXI4-Stream)
Description     : Top module for PH1A90SEG324-2.
                  Camera-only design, no TPG.
                  Supports runtime resolution switching via REG_CAM_MODE:
                    0=1080p@60, 1=4K@30 , 2=720p.
ע�⣬pcie gen2 x1 ��֧��4k30��Ĭ��ʹ��1080p@60
\*===========================================*/
`timescale 1ns/1ps


module imx415_pcie_top #(
    parameter LINK_WIDTH    = 1,
    parameter DEVICE_FAMILY = "PH1A",
    parameter USER_CLK_FREQ = 125,
    parameter DATA_WIDTH    = 128,
    parameter KEEP_WIDTH    = DATA_WIDTH/8,
    parameter H2C_CHNL_NUM  = 1,
    parameter C2H_CHNL_NUM  = 2,
    parameter USR_IRQ_NUM   = 16,
    parameter MIPI_LAN      = 4,
    // Explicit 1080P build: 512 four-pixel words per CNR line.
    // The retained F167 candidate supports 4K with address width 10.
    parameter CNR_LINE_ADDR_WIDTH = 9
)(
    // ���� System ����
    input   wire                    sys_clk,        // 25 MHz

    // ���� PCIe ����
    input   wire                    refclk_p,
    input   wire                    refclk_n,
    output  wire   [LINK_WIDTH-1:0] txp,
    output  wire   [LINK_WIDTH-1:0] txn,
    input   wire   [LINK_WIDTH-1:0] rxp,
    input   wire   [LINK_WIDTH-1:0] rxn,
    input   wire                    pcie_mperst,

    // ���� MIPI Reference Clock (100MHz LVDS differential, T13/T14) ����
    input   wire                    mipi_ref_clk_p,         // 100MHz LVDS P (T13)

    // ���� IMX415 MIPI CSI-2 ����
    input   wire                    mipi_clk_hs_rx_p,       // MIPI clock lane (P)
    input   wire   [MIPI_LAN-1:0]  mipi_data_hs_p,         // MIPI data lanes (P)

    // ���� IMX415 I2C ����
    output  wire                    cam_scl,
    inout   wire                    cam_sda,

    // ���� IMX415 MCLK ����
    output  wire                    cam_mclk,               // 27MHz forwarded to sensor INCK

    // ���� IMX415 XCLR (hardware reset, active-low on sensor) ����
    output  wire                    cam_xclr,               // Drive high to release reset

    // ���� Debug UART ����
    output  wire                    uart_tx,                // 115200 8N1 debug output (U11)
    input   wire                    uart_rx,                // 115200 8N1 debug input  (V11)
    output wire O_clk_hs_p,O_clk_lp_p,O_clk_lp_n,
    output wire[3:0]O_data_hs_p,O_data_lp_p,O_data_lp_n
);
// Experimental clock forwarding: retain the original HS200_90 PLL source,
// omit the encrypted clock serializer output, keep all data/LP PHY unchanged.
wire dsi_unused_serial_clock;


// ====================================================================
// Compile-time feature enable (same as Phase 8)
// ====================================================================
`ifdef  MSI_EN
localparam IRQ_LGCY_EN = 0; localparam IRQ_MSI_EN = 1; localparam IRQ_MSIX_EN = 0;
`elsif   MSIX_EN
localparam IRQ_LGCY_EN = 0; localparam IRQ_MSI_EN = 0; localparam IRQ_MSIX_EN = 1;
`else
localparam IRQ_LGCY_EN = 1; localparam IRQ_MSI_EN = 0; localparam IRQ_MSIX_EN = 0;
`endif
`ifdef  AXI4MM_BUS_EN          localparam AXI4MM_BUS_EN    = 1; `else localparam AXI4MM_BUS_EN    = 0; `endif
`ifdef  AXI4ST_BUS_EN          localparam AXI4ST_BUS_EN    = 1; `else localparam AXI4ST_BUS_EN    = 0; `endif
`ifdef  DSC_BYPASS_C2H_CHL0_EN localparam DSC_BYPASS_C2H0  = 1; `else localparam DSC_BYPASS_C2H0  = 0; `endif
`ifdef  DSC_BYPASS_C2H_CHL1_EN localparam DSC_BYPASS_C2H1  = 2; `else localparam DSC_BYPASS_C2H1  = 0; `endif
`ifdef  DSC_BYPASS_C2H_CHL2_EN localparam DSC_BYPASS_C2H2  = 4; `else localparam DSC_BYPASS_C2H2  = 0; `endif
`ifdef  DSC_BYPASS_C2H_CHL3_EN localparam DSC_BYPASS_C2H3  = 8; `else localparam DSC_BYPASS_C2H3  = 0; `endif
`ifdef  DSC_BYPASS_H2C_CHL0_EN localparam DSC_BYPASS_H2C0  = 1; `else localparam DSC_BYPASS_H2C0  = 0; `endif
`ifdef  DSC_BYPASS_H2C_CHL1_EN localparam DSC_BYPASS_H2C1  = 2; `else localparam DSC_BYPASS_H2C1  = 0; `endif
`ifdef  DSC_BYPASS_H2C_CHL2_EN localparam DSC_BYPASS_H2C2  = 4; `else localparam DSC_BYPASS_H2C2  = 0; `endif
`ifdef  DSC_BYPASS_H2C_CHL3_EN localparam DSC_BYPASS_H2C3  = 8; `else localparam DSC_BYPASS_H2C3  = 0; `endif
localparam [3:0]    H2C_DSC_BYP_MAP = DSC_BYPASS_H2C0 | DSC_BYPASS_H2C1 | DSC_BYPASS_H2C2 | DSC_BYPASS_H2C3;
localparam [3:0]    C2H_DSC_BYP_MAP = DSC_BYPASS_C2H0 | DSC_BYPASS_C2H1 | DSC_BYPASS_C2H2 | DSC_BYPASS_C2H3;
localparam          DESC_BYP_EN     = (C2H_DSC_BYP_MAP || H2C_DSC_BYP_MAP) ? 1'b1 : 1'b0;

// ====================================================================
// Internal wires
// ====================================================================

`ifdef AXI4ST_BUS_EN
    wire    [C2H_CHNL_NUM-1:0]             s0_axis_c2h_tready;
    wire    [DATA_WIDTH*C2H_CHNL_NUM-1:0]  s0_axis_c2h_tdata;
    wire    [KEEP_WIDTH*C2H_CHNL_NUM-1:0]  s0_axis_c2h_tkeep;
    wire    [KEEP_WIDTH*C2H_CHNL_NUM-1:0]  s0_axis_c2h_tuser;
    wire    [C2H_CHNL_NUM-1:0]             s0_axis_c2h_tlast;
    wire    [C2H_CHNL_NUM-1:0]             s0_axis_c2h_tvalid;

    wire    [H2C_CHNL_NUM-1:0]             m0_axis_h2c_tready;
    wire    [H2C_CHNL_NUM-1:0]             app_h2c_tready;
    wire    [DATA_WIDTH*H2C_CHNL_NUM-1:0]  m0_axis_h2c_tdata;
    wire    [KEEP_WIDTH*H2C_CHNL_NUM-1:0]  m0_axis_h2c_tkeep;
    wire    [KEEP_WIDTH*H2C_CHNL_NUM-1:0]  m0_axis_h2c_tuser;
    wire    [H2C_CHNL_NUM-1:0]             m0_axis_h2c_tlast;
    wire    [H2C_CHNL_NUM-1:0]             m0_axis_h2c_tvalid;

    wire    [C2H_CHNL_NUM-1:0]             app_c2h_tready;
    wire    [DATA_WIDTH*C2H_CHNL_NUM-1:0]  app_c2h_tdata;
    wire    [KEEP_WIDTH*C2H_CHNL_NUM-1:0]  app_c2h_tkeep;
    wire    [KEEP_WIDTH*C2H_CHNL_NUM-1:0]  app_c2h_tuser;
    wire    [C2H_CHNL_NUM-1:0]             app_c2h_tlast;
    wire    [C2H_CHNL_NUM-1:0]             app_c2h_tvalid;

    // Camera output (128-bit AXI-Stream)
    wire    [DATA_WIDTH-1:0]                cam_tdata;
    wire                                    cam_tvalid;
    wire                                    cam_tready;
    wire                                    cam_tlast;
    wire                                    cam_frame_last;
    wire                                    cam_sof;
    wire                                    cam_eof;
`endif

`ifdef AXI4L_MBUS_EN
    wire    [31:0]                          m_axil_awaddr;
    wire    [2:0]                           m_axil_awprot;
    wire                                    m_axil_awvalid;
    wire                                    m_axil_awready;
    wire    [31:0]                          m_axil_wdata;
    wire    [3:0]                           m_axil_wstrb;
    wire                                    m_axil_wvalid;
    wire                                    m_axil_wready;
    wire                                    m_axil_bvalid;
    wire    [1:0]                           m_axil_bresp;
    wire                                    m_axil_bready;
    wire    [31:0]                          m_axil_araddr;
    wire    [2:0]                           m_axil_arprot;
    wire                                    m_axil_arvalid;
    wire                                    m_axil_arready;
    wire    [31:0]                          m_axil_rdata;
    wire app_bar_write_valid,app_bar_read_valid;
    wire [31:0] app_bar_write_address,app_bar_write_data,app_bar_read_address;
    wire [3:0] app_bar_write_strobe;
    wire    [1:0]                           m_axil_rresp;
    wire                                    m_axil_rvalid;
    wire                                    m_axil_rready;
    wire    [31:0]                          app_axil_rdata;
`ifndef AXI4ST_BUS_EN
    assign m_axil_rdata = app_axil_rdata;
`endif
`endif

`ifdef USR_IRQ_EN
    wire    [USR_IRQ_NUM-1:0]               usr_irq_req;
    wire    [USR_IRQ_NUM-1:0]               usr_irq_ack;
    wire                                    msi_enable;
    wire    [4:0]                           msi_vector_width;
`endif

`ifdef DSC_BYPASS_C2H_CHL0_EN
    wire c2h_dsc_byp_ready_0, c2h_dsc_byp_load_0;
    wire [63:0] c2h_dsc_byp_src_addr_0, c2h_dsc_byp_dst_addr_0;
    wire [27:0] c2h_dsc_byp_len_0;
    wire [15:0] c2h_dsc_byp_ctl_0;
`endif
`ifdef DSC_BYPASS_H2C_CHL0_EN
    wire h2c_dsc_byp_ready_0, h2c_dsc_byp_load_0;
    wire [63:0] h2c_dsc_byp_src_addr_0, h2c_dsc_byp_dst_addr_0;
    wire [27:0] h2c_dsc_byp_len_0;
    wire [15:0] h2c_dsc_byp_ctl_0;
`endif

    wire [7:0] c2h_sts_0, h2c_sts_0, c2h_sts_1, h2c_sts_1;
    wire [7:0] c2h_sts_2, h2c_sts_2, c2h_sts_3, h2c_sts_3;

    wire        sys_clk_g;
    wire        app_auxclk;
    wire        user_clk;
    wire        user_rst_n;
    wire        core_clk;
    wire        pll_lock;
    wire        user_link_up;

// ====================================================================
// Internal Power-On Reset
// ====================================================================
    reg  [9:0]  int_por_cnt = 10'd0;
    wire        int_por_done = &int_por_cnt;
    reg         int_por_done_r = 1'b0;

    always @(posedge sys_clk_g) begin
        if (!int_por_done)
            int_por_cnt <= int_por_cnt + 1'b1;
        int_por_done_r <= int_por_done;
    end

// ====================================================================
// Global Clock Buffer
// ====================================================================
PH1_LOGIC_BUFG u_sys_clk_bufg (
    .i  (sys_clk    ),
    .o  (sys_clk_g  )
);

// ====================================================================
// MIPI Reference Clock: 100MHz LVDS differential input (T13/T14)
// TD auto-infers LVDS input buffer from IOSTANDARD=LVDS18 constraint.
// Route through BUFG for global clock tree.
// ====================================================================
    wire mipi_ref_clk_bufg;
PH1_LOGIC_BUFG u_mipi_ref_clk_bufg (
    .i  (mipi_ref_clk_p ),
    .o  (mipi_ref_clk_bufg)
);

// ====================================================================
// Camera PLL: 100MHz LVDS -> 150MHz (cam_pclk) + 100MHz (cam_100m) + 24MHz (cam_24m)
// cam_pclk  = mipi_ref_clock for MIPI PHY (150MHz required for Eye-Scan)
// cam_100m  = reserved
// cam_24m   = I2C and startup sequencing; native 27MHz PLL supplies MCLK
// ====================================================================
    wire cam_pclk, cam_100m, cam_24m, ui_pll_lock;
ui_pll u_ui_pll (
    .refclk     (mipi_ref_clk_bufg  ),
    .reset      (1'b0              ),
    .lock       (ui_pll_lock        ),
    .clk0_out   (cam_pclk           ),
    .clk1_out   (cam_100m           ),
    .clk2_out   (cam_24m            )
);

// ====================================================================
// PLL: 25MHz -> 125MHz (core_clk) + 25MHz (app_auxclk)
// ====================================================================
sgdma_pll u_sgdma_pll(
    .refclk     (sys_clk_g          ),
    .reset      (!int_por_done_r    ),
    .lock       (pll_lock           ),
    .clk0_out   (core_clk           ),
    .clk1_out   (app_auxclk         )
);

// ====================================================================
// PERST# + PLL stable
// ====================================================================
    reg  [21:0] pll_lock_cnt;
    wire        pll_lock_stable_comb = (pll_lock_cnt == 22'h3FFFFF);

    always @(posedge core_clk or negedge pll_lock) begin
        if (!pll_lock)
            pll_lock_cnt <= 22'd0;
        else if (!pll_lock_stable_comb)
            pll_lock_cnt <= pll_lock_cnt + 1'b1;
    end

    reg pll_lock_stable;
    always @(posedge core_clk or negedge pll_lock) begin
        if (!pll_lock)
            pll_lock_stable <= 1'b0;
        else
            pll_lock_stable <= pll_lock_stable_comb;
    end

    wire tl_power_on_rstn = pcie_mperst & pll_lock_stable;

    // debug_button removed (no physical button on AFC03 board)
    // Tie high = "not pressed" (same as PULLUP idle state)
    wire debug_button_w = 1'b1;

    // Sensor register table is the 27 MHz / 891 Mbps profile. The old
    // 24 MHz toggle produced 12 MHz and ~26.67 fps instead of nominal 60.
    // Native PH1 PLL candidate: 25 MHz PFD, 1350 MHz VCO, /50 = 27 MHz.
    // Clock forwarding and I2C release follow the explicit startup sequence.
    wire cam_27m, cam_pll27_lock, cam_clock_cfg_reset_n;
    wire [15:0] cam_clock_startup_status;
    cam_pll27 u_cam_pll27 (.refclk(sys_clk_g),.reset(!int_por_done_r),
        .lock(cam_pll27_lock),.clk25_feedback(),.clk27_out(cam_27m));
    camera_clock_startup u_camera_clock_startup (
        .clock24(cam_24m),.clock27(cam_27m),
        .pll27_lock_raw(cam_pll27_lock),.ui_lock_raw(ui_pll_lock),
        .system_reset_n(user_rst_n),.sensor_xclr(cam_xclr),
        .sensor_mclk(cam_mclk),.config_reset_n(cam_clock_cfg_reset_n),
        .status(cam_clock_startup_status));
    wire [31:0] cam_clock_measured_edges,cam_clock_window_index;
    wire cam_clock_measure_valid,cam_clock_frequency_ok,cam_clock_lock_s;
    (* async_reg="true" *) reg [2:0] cam_monitor_reset27;
    wire cam_monitor_async_reset_n=cam_pll27_lock & user_rst_n;
    always @(posedge cam_27m or negedge cam_monitor_async_reset_n) begin
        if(!cam_monitor_async_reset_n) cam_monitor_reset27<=3'b000;
        else cam_monitor_reset27<={cam_monitor_reset27[1:0],1'b1};
    end
    cam_clock27_monitor #(.REF_HZ(125000000)) u_cam_clock_monitor (
        .clk_ref(user_clk),.ref_reset_n(user_rst_n),.clk_test(cam_27m),
        .test_reset_n(cam_monitor_reset27[2]),.pll_lock(cam_pll27_lock),
        .measured_edges(cam_clock_measured_edges),
        .window_index(cam_clock_window_index),
        .measurement_valid(cam_clock_measure_valid),
        .frequency_ok(cam_clock_frequency_ok),.lock_in_ref(cam_clock_lock_s));
    // Only these individual flags cross domains. No asynchronous binary FSM
    // state is presented as an atomic multibit read to the host.
    (* async_reg="true" *) reg [1:0] cam_xclr_sync,cam_cfg_ready_sync;
    always @(posedge user_clk or negedge user_rst_n) begin
        if(!user_rst_n) begin cam_xclr_sync<=0;cam_cfg_ready_sync<=0;end
        else begin
            cam_xclr_sync<={cam_xclr_sync[0],cam_xclr};
            cam_cfg_ready_sync<={cam_cfg_ready_sync[0],cam_clock_cfg_reset_n};
        end
    end

// ====================================================================
// SGDMA Subsystem (identical to Phase 8)
// ====================================================================
sgdma_subsys #(
    .USER_CLK_FREQ  (USER_CLK_FREQ),
    .DEVICE_FAMILY  (DEVICE_FAMILY),
    .LINK_WIDTH     (LINK_WIDTH),
    .DATA_WIDTH     (DATA_WIDTH),
    .H2C_CHNL_NUM  (H2C_CHNL_NUM),
    .C2H_CHNL_NUM  (C2H_CHNL_NUM),
    .USR_IRQ_NUM    (USR_IRQ_NUM),
    .LGCY_EN        (IRQ_LGCY_EN),
    .MSI_EN         (IRQ_MSI_EN),
    .MSIX_EN        (IRQ_MSIX_EN),
    .AXI4MM_BUS_EN  (AXI4MM_BUS_EN),
    .AXI4ST_BUS_EN  (AXI4ST_BUS_EN),
    .H2C_DSC_BYP_MAP(H2C_DSC_BYP_MAP),
    .C2H_DSC_BYP_MAP(C2H_DSC_BYP_MAP)
) u_sgdma_subsys(
    .app_auxclk             (app_auxclk),
    .tl_power_on_rstn       (tl_power_on_rstn),
    .tl_clk_user            (core_clk),
    .pll_lock               (pll_lock),
    .ref_pad_clk_p          (refclk_p),
    .ref_pad_clk_n          (refclk_n),
    .pcie_tx_p              (txp),
    .pcie_tx_n              (txn),
    .pcie_rx_p              (rxp),
    .pcie_rx_n              (rxn),
    .c2h_sts_0              (c2h_sts_0),
    .h2c_sts_0              (h2c_sts_0),
    .c2h_sts_1              (c2h_sts_1),
    .h2c_sts_1              (h2c_sts_1),
    .c2h_sts_2              (c2h_sts_2),
    .h2c_sts_2              (h2c_sts_2),
    .c2h_sts_3              (c2h_sts_3),
    .h2c_sts_3              (h2c_sts_3),
`ifdef AXI4ST_BUS_EN
    .s0_axis_c2h_tready     (s0_axis_c2h_tready),
    .s0_axis_c2h_tdata      (s0_axis_c2h_tdata),
    .s0_axis_c2h_tkeep      (s0_axis_c2h_tkeep),
    .s0_axis_c2h_tuser      (s0_axis_c2h_tuser),
    .s0_axis_c2h_tlast      (s0_axis_c2h_tlast),
    .s0_axis_c2h_tvalid     (s0_axis_c2h_tvalid),
    .m0_axis_h2c_tready     (m0_axis_h2c_tready),
    .m0_axis_h2c_tdata      (m0_axis_h2c_tdata),
    .m0_axis_h2c_tkeep      (m0_axis_h2c_tkeep),
    .m0_axis_h2c_tuser      (m0_axis_h2c_tuser),
    .m0_axis_h2c_tlast      (m0_axis_h2c_tlast),
    .m0_axis_h2c_tvalid     (m0_axis_h2c_tvalid),
`endif
`ifdef AXI4L_MBUS_EN
    .m_axil_awaddr          (m_axil_awaddr),
    .m_axil_awprot          (m_axil_awprot),
    .m_axil_awvalid         (m_axil_awvalid),
    .m_axil_awready         (m_axil_awready),
    .m_axil_wdata           (m_axil_wdata),
    .m_axil_wstrb           (m_axil_wstrb),
    .m_axil_wvalid          (m_axil_wvalid),
    .m_axil_wready          (m_axil_wready),
    .m_axil_bvalid          (m_axil_bvalid),
    .m_axil_bresp           (m_axil_bresp),
    .m_axil_bready          (m_axil_bready),
    .m_axil_araddr          (m_axil_araddr),
    .m_axil_arprot          (m_axil_arprot),
    .m_axil_arvalid         (m_axil_arvalid),
    .m_axil_arready         (m_axil_arready),
    .m_axil_rdata           (m_axil_rdata),
    .m_axil_rresp           (m_axil_rresp),
    .m_axil_rvalid          (m_axil_rvalid),
    .m_axil_rready          (m_axil_rready),
`endif
`ifdef DSC_BYPASS_C2H_CHL0_EN
    .c2h_dsc_byp_ready_0_o (c2h_dsc_byp_ready_0),
    .c2h_dsc_byp_load_0_i  (c2h_dsc_byp_load_0),
    .c2h_dsc_byp_src_addr_0_i(c2h_dsc_byp_src_addr_0),
    .c2h_dsc_byp_dst_addr_0_i(c2h_dsc_byp_dst_addr_0),
    .c2h_dsc_byp_len_0_i   (c2h_dsc_byp_len_0),
    .c2h_dsc_byp_ctl_0_i   (c2h_dsc_byp_ctl_0),
`endif
`ifdef DSC_BYPASS_H2C_CHL0_EN
    .h2c_dsc_byp_ready_0_o (h2c_dsc_byp_ready_0),
    .h2c_dsc_byp_load_0_i  (h2c_dsc_byp_load_0),
    .h2c_dsc_byp_src_addr_0_i(h2c_dsc_byp_src_addr_0),
    .h2c_dsc_byp_dst_addr_0_i(h2c_dsc_byp_dst_addr_0),
    .h2c_dsc_byp_len_0_i   (h2c_dsc_byp_len_0),
    .h2c_dsc_byp_ctl_0_i   (h2c_dsc_byp_ctl_0),
`endif
`ifdef USR_IRQ_EN
    .usr_irq_req            (usr_irq_req),
    .usr_irq_ack            (usr_irq_ack),
    .msi_enable             (msi_enable),
    .msi_vector_width       (msi_vector_width),
`endif
    .user_link_up           (user_link_up),
    .user_clk               (user_clk),
    .user_rst_n             (user_rst_n)
);

// ====================================================================
// Video Source Pipeline
// ====================================================================
`ifdef AXI4ST_BUS_EN

    // ���� Config Registers (Camera) ����
    reg         reg_enable;
    reg         reg_image_loopback; // BAR 0xA4 bit0: H2C FIFO -> C2H, camera stopped
    reg         reg_soft_reset;
    reg [6:0]   reg_phy_control; // E0: bit6 manual override, tap bits5:0
    wire [223:0] phy_diag0, phy_diag1;
    wire [31:0] phy_diag0_status, phy_diag1_status;
    reg [1:0]   reg_bayer_mode;     // BAR D8 shadow: 0 RGGB, 1 BGGR, 2 GRBG, 3 GBRG
    wire [1:0]  cam_active_bayer_mode;
    wire [31:0] cnr_status,cnr_input_beats,cnr_output_beats,cnr_input_frames,cnr_output_frames,cnr_h_fallback,cnr_v_fallback; // BAR DC: accepted cropped-frame mode
    reg [1:0] cnr_pattern_shadow;
    reg [2:0] linear_gate_shadow;
    reg [2:0] isp_probe_stage48;
    reg [31:0] isp_probe_rejected48;
    wire [2:0] linear_gate_active,linear_hist_gate;
    wire [31:0] linear_hist_sequence;
    wire [159:0] linear_histogram;
    wire roi_bar_select;wire[31:0]roi_bar_data;
    wire [1:0] cnr_active_pattern;
    wire vid_sys_rst_n,cam_sys_rst_n,cam_enable;
    reg model_enable;reg [63:0] model_epoch;
    wire frame_credit_pending, frame_packet_in_flight, frame_accepting;
    wire model_packet_busy,model_credit_pending;
    wire preview_admission_allowed,model_admission_allowed;
    model_preview_admission model_preview_schedule(
      .clk(user_clk),.rst_n(vid_sys_rst_n),.model_enable(model_enable),
      .source_sof(cam_tvalid && cam_sof),.preview_busy(frame_packet_in_flight),.model_busy(model_packet_busy),
      .preview_allowed(preview_admission_allowed),.model_allowed(model_admission_allowed));

    wire model_credit=app_bar_write_valid && app_bar_write_address[19:0]==20'h001A0 && app_bar_write_strobe[0] && app_bar_write_data[0];
    wire[1:0]view_select;wire view_fire,view_sof,view_eol,view_eof;
    wire[95:0]view_rgb;wire[2:0]view_count;wire[31:0]view_id;wire[63:0]view_tick;
    wire model_valid,model_ready,model_sof,model_eol,model_eof,model_error;
    wire [127:0] model_data;wire [31:0] model_id;wire [63:0] model_tick;
    wire [31:0] model_source_frames,model_complete_frames,model_abort_frames,model_overflows;
wire [31:0] model_packets,model_packet_aborts,model_drops;
    always @(posedge user_clk or negedge user_rst_n)begin
      if(!user_rst_n)begin model_enable<=0;model_epoch<=0;end
      else if(app_bar_write_valid)begin
        if(app_bar_write_address[19:0]==20'h0019C && app_bar_write_strobe[0] && !model_packet_busy)model_enable<=app_bar_write_data[0];
        if(app_bar_write_address[19:0]==20'h001A4 && (&app_bar_write_strobe) && !model_enable && !model_packet_busy)model_epoch[31:0]<=app_bar_write_data;
        if(app_bar_write_address[19:0]==20'h001A8 && (&app_bar_write_strobe) && !model_enable && !model_packet_busy)model_epoch[63:32]<=app_bar_write_data;
      end
    end
    model_frame_packet #(.PAYLOAD_SIZE(861824),.FORMAT(32'h31444e42)) model_packet(.clk(user_clk),.rst_n(vid_sys_rst_n),.enable(model_enable && cam_enable),.credit(model_credit),.admit_frame(model_admission_allowed),.epoch(model_epoch),
      .s_valid(model_valid),.s_ready(model_ready),.s_data(model_data),.s_sof(model_sof),.s_eof(model_eof),.s_id(model_id),.s_tick(model_tick),
      .m_valid(s0_axis_c2h_tvalid[1]),.m_ready(s0_axis_c2h_tready[1]),.m_data(s0_axis_c2h_tdata[DATA_WIDTH*2-1:DATA_WIDTH]),.m_last(s0_axis_c2h_tlast[1]),
      .pending(model_credit_pending),.busy(model_packet_busy),.completed(model_packets),.aborted(model_packet_aborts),.dropped(model_drops));
    assign s0_axis_c2h_tkeep[KEEP_WIDTH*2-1:KEEP_WIDTH]={KEEP_WIDTH{1'b1}};
    assign s0_axis_c2h_tuser[KEEP_WIDTH*2-1:KEEP_WIDTH]={KEEP_WIDTH{1'b1}};
    reg [1:0]   reg_cam_mode;       // Camera resolution mode (0=1080p, 1=4K, 2=720p)
    reg [7:0]   reg_ae_gain;        // AE gain value (0-240, default32 = 9.6dB)
    reg[19:0]reg_ae_shr;reg reg_ae_exposure_valid;
    reg         reg_ae_gain_valid; // explicit software override, not mode default

    // ���� Resolution Mode LUT (runtime switchable) ����
    // cam_mode �� { img_width[12:0], img_height[12:0], crop_v_start[14:0], crop_v_end[14:0], crop_h_end[14:0] }
    reg  [12:0] cam_img_width;
    reg  [12:0] cam_img_height;
    reg  [14:0] cam_crop_v_start;
    reg  [14:0] cam_crop_v_end;
    reg  [14:0] cam_crop_h_end;

    always @(*) begin
        case (reg_cam_mode)
            2'd0: begin  // 1080p 2��2 binning
                cam_img_width    = 13'd1920;
                cam_img_height   = 13'd1080;
                cam_crop_v_start = 15'd15; // first row 16, even Bayer phase
                cam_crop_v_end   = 15'd1096; // rows 16..1095: 1080 inside 1097
                cam_crop_h_end   = 15'd481;
            end
            2'd1: begin  // 4K full resolution
                cam_img_width    = 13'd3840;
                cam_img_height   = 13'd2160;
                cam_crop_v_start = 15'd15; // first row 16, even Bayer phase
                cam_crop_v_end   = 15'd2176; // rows 16..2175: 2160 inside 2192
                cam_crop_h_end   = 15'd961;
            end
            2'd2: begin  // 720p
                cam_img_width    = 13'd1280;
                cam_img_height   = 13'd720;
                cam_crop_v_start = 15'd35;
                cam_crop_v_end   = 15'd756;
                cam_crop_h_end   = 15'd321;
            end
            default: begin // fallback to 1080p
                cam_img_width    = 13'd1920;
                cam_img_height   = 13'd1080;
                cam_crop_v_start = 15'd15; // first row 16, even Bayer phase
                cam_crop_v_end   = 15'd1096; // rows 16..1095: 1080 inside 1097
                cam_crop_h_end   = 15'd481;
            end
        endcase
    end

    assign vid_sys_rst_n = user_rst_n & ~reg_soft_reset;
    assign cam_sys_rst_n = vid_sys_rst_n;

    // Enable gating
    assign cam_enable = reg_enable & user_link_up & !reg_image_loopback;

    // Status wires
    wire [223:0] csi_snapshot;
    wire [31:0] csi_snapshot_status,csi_clock_delta;
    wire [31:0] cam_frame_count;
    wire        cam_i2c_done;           // cam_24m domain
    wire [15:0] cam_phy_raw_nibbles;
    wire cam_phy_pclk;
    wire [31:0] cam_phy_raw_bytes;
    wire        cam_mipi_div_clk;       // MIPI HS clock domain
    wire        cam_auto_delay_done;    // MIPI HS �� user_clk CDC
    wire        cam_mipi_tvalid;        // MIPI raw tvalid (debug)
    wire [7:0]  cam_dbg_mipi;           // MIPI debug bus (hs_div_clk)
    wire [7:0]  cam_dbg_delay;          // delay debug bus (hs_div_clk)
    wire [5:0]  cam_dbg_best_len;       // eye-scan best length
    wire        cam_i2c_bus_error;      // I2C bus error
    wire        frame_pulse;

    // ���� CDC: cam_i2c_done (cam_24m �� user_clk) ����
    (* async_reg="true" *) reg [1:0]   cam_i2c_done_sync;
    wire        cam_i2c_done_s = cam_i2c_done_sync[1];
    always @(posedge user_clk or negedge user_rst_n) begin
        if (!user_rst_n)
            cam_i2c_done_sync <= 2'b00;
        else
            cam_i2c_done_sync <= {cam_i2c_done_sync[0], cam_i2c_done};
    end

    // ���� CDC: cam_auto_delay_done (hs_div_clk �� user_clk) ����
    (* async_reg="true" *) reg [1:0]   cam_delay_done_sync;
    wire        cam_delay_done_s = cam_delay_done_sync[1];
    always @(posedge user_clk or negedge user_rst_n) begin
        if (!user_rst_n)
            cam_delay_done_sync <= 2'b00;
        else
            cam_delay_done_sync <= {cam_delay_done_sync[0], cam_auto_delay_done};
    end

    // Coherent calibration-window diagnostic from BYTE to user clock.
    // Best-window length may change while manual sampling reports done.
    // Transfer completion and all six bits together; never sample a live bus.
    wire [6:0] cam_window_status;
    wire cam_window_valid,cam_window_busy;
    wire [5:0] cam_best_len_sync=cam_window_status[6] && cam_delay_done_s
        ? cam_window_status[5:0] : 6'd0;
    cdc_latest_command #(.WIDTH(7),.INITIAL_VALUE(7'd0)) u_cam_window_status (
        .rst_n(cam_sys_rst_n & cam_i2c_done_s),.src_clk(cam_mipi_div_clk),
        .src_load(1'b0),.src_value({cam_auto_delay_done,cam_dbg_best_len}),
        .src_busy(cam_window_busy),.dst_clk(user_clk),.dst_ready(1'b1),
        .dst_valid(cam_window_valid),.dst_value(cam_window_status));

    // ���� Clock detect: cam_mipi_div_clk �� mipi_clk_present (user_clk) ����
    // Coherent snapshot completion and measured HS edges indicate recent
    // activity. A sampled clock toggle was an instantaneous pulse, not a
    // stable "clock present" indication. Expire after 200ms without a new
    // snapshot, including source-clock loss leaving the handshake busy.
    reg [30:0] mipi_snapshot_seen;
    reg [24:0] mipi_snapshot_age;
    wire mipi_clk_present=(csi_snapshot_status[31:1]!=0) &&
        (csi_clock_delta!=0) && (mipi_snapshot_age<25'd25000000);
    always @(posedge user_clk or negedge user_rst_n) begin
        if(!user_rst_n) begin mipi_snapshot_seen<=0;mipi_snapshot_age<=25'd25000000;end
        else if(csi_snapshot_status[31:1]!=mipi_snapshot_seen) begin
            mipi_snapshot_seen<=csi_snapshot_status[31:1];mipi_snapshot_age<=0;
        end else if(mipi_snapshot_age<25'd25000000)
            mipi_snapshot_age<=mipi_snapshot_age+1'b1;
    end
    (* async_reg="true" *) reg [1:0] cam_raw_valid_sync;
    always @(posedge user_clk or negedge user_rst_n) begin
        if(!user_rst_n) cam_raw_valid_sync<=0;
        else cam_raw_valid_sync<={cam_raw_valid_sync[0],cam_mipi_tvalid};
    end

    // BAR0+0x134 bit0: one whole-frame receive credit, posted by driver34.
    wire frame_receive_credit;

    wire [31:0] frame_credit_posts;
    wire [DATA_WIDTH-1:0]   fifo_out_tdata;
    wire                    fifo_out_tvalid;
    wire                    fifo_out_tlast;
    wire                    fifo_in_tready;
    wire [13:0]             fifo_fill_level;  // 0..8192, bounded 128KiB preview burst buffer
    wire [DATA_WIDTH-1:0]   fc_out_tdata;
    wire                    fc_out_tvalid;
    wire                    fc_out_tlast;
    wire                    fc_in_tready;
    wire [31:0]             fc_drop_count;


    // Frame bytes calculation (same as Phase 8)
    // Active resolution: always from camera mode LUT
    wire [15:0] active_width  = {3'd0, cam_img_width};
    wire [15:0] active_height = {3'd0, cam_img_height};

    localparam BYTES_PER_BEAT = DATA_WIDTH / 8;  // 16 for 128-bit

    wire [31:0] line_bytes_w      = {16'd0, active_width} * 32'd3;  // RGB24 = 3 bytes/pixel
    wire [31:0] beats_raw         = line_bytes_w / BYTES_PER_BEAT;
    wire [31:0] beats_mod         = line_bytes_w % BYTES_PER_BEAT;
    wire [15:0] beats_per_line_w  = (beats_mod == 32'd0) ? beats_raw[15:0] : beats_raw[15:0] + 16'd1;
    wire [31:0] frame_total_beats = {16'd0, beats_per_line_w} * {16'd0, active_height};
    wire [31:0] padded_frame_bytes = frame_total_beats * BYTES_PER_BEAT;

    // ���� cam_video_source (IMX415 camera video source, v2 verified) ����
    // Resolution parameters now driven by runtime registers via reg_cam_mode LUT
    cam_video_source #(
        .MIPI_LAN       (MIPI_LAN),
        .DEVICE         ("PH1A"),
        .BAYER_MODE     ("GBRG"),
        .CNR_LINE_ADDR_WIDTH(CNR_LINE_ADDR_WIDTH)
    ) u_cam_video_source (.view_select(view_select),.view_fire(view_fire),.view_sof(view_sof),.view_eol(view_eol),.view_eof(view_eof),
 .view_rgb(view_rgb),.view_count(view_count),.view_id(view_id),.view_tick(view_tick),

        .model_enable(model_enable),.model_valid(model_valid),.model_ready(model_ready),.model_data(model_data),
        .model_sof(model_sof),.model_eol(model_eol),.model_eof(model_eof),.model_id(model_id),.model_tick(model_tick),
        .model_source_frames(model_source_frames),.model_complete_frames(model_complete_frames),.model_abort_frames(model_abort_frames),.model_overflows(model_overflows),.model_error(model_error),
        .user_clk           (user_clk),
        .user_rst_n         (cam_sys_rst_n & cam_i2c_done_s),
        .enable             (cam_enable & cam_i2c_done_s),
        // Runtime resolution parameters
        .phy_control_shadow (reg_phy_control),
        .phy_raw_nibbles_out(cam_phy_raw_nibbles),
        .phy_pclk_out       (cam_phy_pclk),
        .phy_raw_bytes_out  (cam_phy_raw_bytes),
        .phy_diag0          (phy_diag0),
        .phy_diag1          (phy_diag1),
        .phy_diag0_status   (phy_diag0_status),
        .phy_diag1_status   (phy_diag1_status),
        .phy_diag0_clock_delta(),
        .phy_diag1_clock_delta(),
        .cfg_bayer_mode     (reg_bayer_mode),
        .active_bayer_mode  (cam_active_bayer_mode),
        .cfg_cnr_pattern(cnr_pattern_shadow),.cnr_active_pattern(cnr_active_pattern),
        .cfg_probe_stage(isp_probe_stage48),
        .cfg_linear_gate(linear_gate_shadow),.linear_gate_active(linear_gate_active),
        .linear_hist_gate(linear_hist_gate),.linear_hist_sequence(linear_hist_sequence),.linear_histogram(linear_histogram),
        .roi_bar_write_valid(app_bar_write_valid),.roi_bar_write_address(app_bar_write_address),
        .roi_bar_write_data(app_bar_write_data),.roi_bar_write_strobe(app_bar_write_strobe),
        .roi_bar_read_valid(app_bar_read_valid),.roi_bar_read_address(app_bar_read_address),
        .roi_bar_select(roi_bar_select),.roi_bar_data(roi_bar_data),
        .cnr_status(cnr_status),.cnr_input_beats(cnr_input_beats),.cnr_output_beats(cnr_output_beats),
        .cnr_input_frames(cnr_input_frames),.cnr_output_frames(cnr_output_frames),
        .cnr_h_fallback(cnr_h_fallback),.cnr_v_fallback(cnr_v_fallback),
        .cfg_img_width      (cam_img_width),
        .cfg_img_height     (cam_img_height),
        .cfg_crop_v_start   (cam_crop_v_start),
        .cfg_crop_v_end     (cam_crop_v_end),
        .cfg_crop_h_end     (cam_crop_h_end),
        // MIPI CSI-2
        .mipi_ref_clock     (cam_pclk),          // 150MHz from ui_pll C0
        .mipi_clk_hs_rx_p   (mipi_clk_hs_rx_p),
        .mipi_data_hs_p     (mipi_data_hs_p),
        // Process every CSI frame; driver credit controls packet admission, �� FIFO(2048) + frame_completer absorb tready gaps
        .frame_request      (1'b1),
        // 128-bit AXI-Stream output
        .m_tdata            (cam_tdata),
        .m_tvalid           (cam_tvalid),
        .m_tready           (cam_tready),
        .m_tlast            (cam_tlast),
        .m_frame_last       (cam_frame_last),
        .sof                (cam_sof),
        .eof                (cam_eof),
        .frame_count_out    (cam_frame_count),
        // Debug / status
        .debug_button       (debug_button_w),
        .mipi_div_clk_out   (cam_mipi_div_clk),
        .auto_delay_done    (cam_auto_delay_done),
        .mipi_tvalid_out    (cam_mipi_tvalid),
        .dbg_mipi           (cam_dbg_mipi),
        .dbg_delay          (cam_dbg_delay),
        .csi_snapshot       (csi_snapshot),
        .csi_snapshot_status(csi_snapshot_status),
        .csi_clock_delta    (csi_clock_delta),
        .dbg_best_len       (cam_dbg_best_len)
    );

    // ���� Camera �� video pipeline (direct, no MUX) ����
    wire [DATA_WIDTH-1:0]   vid_tdata      = cam_tdata;
    wire                    vid_tvalid     = cam_tvalid;
    wire                    vid_frame_last = cam_frame_last;

    // ���� Frame-level gate: one host receive credit admits one complete frame ����
    // Prevents mixed-frame artifacts when DMA can't keep up (e.g. 1080p@60fps).
    // Decision made at SOF: require credit, ready, empty pipeline and no prior packet; old threshold �� pass; else �� drop silently.
    wire [DATA_WIDTH-1:0]   gated_tdata;
    wire                    gated_tvalid;
    wire                    gated_frame_last;
    wire [31:0]             gate_drop_count;
    wire [31:0]             gate_pass_count;

    vid_frame_gate #(
        .DATA_WIDTH     (DATA_WIDTH),
        .FILL_BITS      (14)
    ) u_frame_gate (
        .clk              (user_clk),
        .rst_n            (vid_sys_rst_n),
        .enable           (cam_enable),
        .receive_credit   (frame_receive_credit),
        .receive_ready    (s0_axis_c2h_tready[0] && preview_admission_allowed),
        .packet_done      (fc_out_tvalid && s0_axis_c2h_tready[0] && fc_out_tlast && !reg_image_loopback),
        .pipeline_empty   (!fifo_out_tvalid && !fc_out_tvalid),
        .credit_pending   (frame_credit_pending),
        .packet_in_flight (frame_packet_in_flight),
        .accepting_frame  (frame_accepting),
        .credit_post_count(frame_credit_posts),
        .s_tdata          (vid_tdata),
        .s_tvalid         (vid_tvalid),
        .s_tready         (),            // always 1, unused
        .s_tlast          (cam_tlast),
        .s_frame_last     (vid_frame_last),
        .s_sof            (cam_sof),
        .m_tdata          (gated_tdata),
        .m_tvalid         (gated_tvalid),
        .m_frame_last     (gated_frame_last),
        .fifo_fill_level  (fifo_fill_level),
        .gate_drop_count  (gate_drop_count),
        .gate_pass_count  (gate_pass_count)
    );

    // ���� Frame drop detection + tlast injection ����
    // Detects mid-frame drops (tvalid low for >DROP_IDLE_THRESH cycles)
    // and injects zero+tlast to cleanly terminate partial FIFO packets.
    wire [DATA_WIDTH-1:0] fifo_s_tdata;
    wire                  fifo_s_tvalid;
    wire                  fifo_s_tlast;
    wire                  vid_frame_drop;
    reg [31:0] preview_overflow_words;
    reg [13:0] preview_fifo_highwater;
    always @(posedge user_clk or negedge vid_sys_rst_n) begin
        if(!vid_sys_rst_n) begin preview_overflow_words<=0;preview_fifo_highwater<=0;end
        else begin
            if(fifo_s_tvalid && !fifo_in_tready)preview_overflow_words<=preview_overflow_words+1'b1;
            if(fifo_fill_level>preview_fifo_highwater)preview_fifo_highwater<=fifo_fill_level;
        end
    end

    vid_drop_detect #(
        .DATA_WIDTH       (DATA_WIDTH),
        .DROP_IDLE_THRESH (50000)        // ~200us @ 250MHz, beyond H-blank (~35us max)
    ) u_drop_detect (
        .clk              (user_clk),
        .rst_n            (vid_sys_rst_n),
        .vid_tdata        (gated_tdata),
        .vid_tvalid       (gated_tvalid),
        .vid_frame_last   (gated_frame_last),
        .downstream_ready (fifo_in_tready),
        .out_tdata        (fifo_s_tdata),
        .out_tvalid       (fifo_s_tvalid),
        .out_tlast        (fifo_s_tlast),
        .drop_pulse       (vid_frame_drop)
    );

    // ���� AXI-Stream FIFO: absorb brief SGDMA tready gaps ����

    axis_stream_fifo #(
        .DATA_WIDTH (DATA_WIDTH),
        .DEPTH      (8192),
        .ADDR_BITS  (13)
    ) u_c2h_fifo (
        .clk        (user_clk),
        .rst_n      (vid_sys_rst_n),
        .s_tdata    (fifo_s_tdata),
        .s_tvalid   (fifo_s_tvalid),
        .s_tready   (fifo_in_tready),
        .s_tlast    (fifo_s_tlast),
        .m_tdata    (fifo_out_tdata),
        .m_tvalid   (fifo_out_tvalid),
        .m_tready   (fc_in_tready),
        .m_tlast    (fifo_out_tlast),
        .fill_level (fifo_fill_level)
    );

    // ���� Frame Guardian: flush dropped frames to maintain SGDMA packet boundary ����

    frame_completer #(
        .DATA_WIDTH     (DATA_WIDTH),
        .TIMEOUT_CYCLES (50000)          // ~200us at 250MHz (backup safety net)
    ) u_frame_completer (
        .clk                 (user_clk),
        .rst_n               (vid_sys_rst_n),
        .s_tdata             (fifo_out_tdata),
        .s_tvalid            (fifo_out_tvalid),
        .s_tready            (fc_in_tready),
        .s_tlast             (fifo_out_tlast),
        .m_tdata             (fc_out_tdata),
        .m_tvalid            (fc_out_tvalid),
        .m_tready            (s0_axis_c2h_tready[0] & !reg_image_loopback),
        .m_tlast             (fc_out_tlast),
        .drop_count          (fc_drop_count)
    );

    // Backpressure: camera always accepted (gate drops entire frames when needed)
    assign cam_tready = 1'b1;

    // ���� C2H routing: Frame Completer output �� SGDMA engine ����
    // Image loop35: direct AXI handshake, with payload and all metadata in
    // one FIFO entry. The registered output holds stable for any RX pause.
    // Camera/credit/ISP path and vendor application remain present.
    wire loop35_sready, loop35_mvalid, loop35_mlast;
    wire [DATA_WIDTH+2*KEEP_WIDTH-1:0] loop35_mdata;
    wire loop35_rst_n = vid_sys_rst_n & reg_image_loopback;
    axis_stream_fifo #(
        .DATA_WIDTH(DATA_WIDTH+2*KEEP_WIDTH), .DEPTH(256), .ADDR_BITS(8)
    ) u_image_loop35_fifo (
        .clk(user_clk), .rst_n(loop35_rst_n),
        .s_tdata({m0_axis_h2c_tdata, m0_axis_h2c_tkeep, m0_axis_h2c_tuser}),
        .s_tvalid(m0_axis_h2c_tvalid[0] & loop35_rst_n),
        .s_tready(loop35_sready), .s_tlast(m0_axis_h2c_tlast[0]),
        .m_tdata(loop35_mdata), .m_tvalid(loop35_mvalid),
        .m_tready(s0_axis_c2h_tready[0] & loop35_rst_n),
        .m_tlast(loop35_mlast), .fill_level()
    );
    assign m0_axis_h2c_tready = reg_image_loopback ?
        (loop35_sready & vid_sys_rst_n) : app_h2c_tready;
    assign s0_axis_c2h_tdata[DATA_WIDTH-1:0] = reg_image_loopback ? loop35_mdata[DATA_WIDTH+2*KEEP_WIDTH-1:2*KEEP_WIDTH] : fc_out_tdata;
    assign s0_axis_c2h_tkeep[KEEP_WIDTH-1:0] = reg_image_loopback ? loop35_mdata[2*KEEP_WIDTH-1:KEEP_WIDTH] : {KEEP_WIDTH{1'b1}};
    assign s0_axis_c2h_tuser[KEEP_WIDTH-1:0] = reg_image_loopback ? loop35_mdata[KEEP_WIDTH-1:0] : {KEEP_WIDTH{1'b1}};
    assign s0_axis_c2h_tlast[0] = reg_image_loopback ? loop35_mlast : fc_out_tlast;
    assign s0_axis_c2h_tvalid[0] = reg_image_loopback ? (loop35_mvalid & vid_sys_rst_n) : fc_out_tvalid;

    // ���� Stall/drop counter (observable via REG_DROP_COUNT) ����
    // Tracks flush-terminated frames. Should be 0 for perfect operation.
    // Non-zero = frames with short SGDMA packet (driver can detect & hold prev).
    wire [31:0] fifo_drop_count = fc_drop_count;

    // ���� Debug counters ����
    reg [31:0] dbg_dma_beat_cnt;
    reg        dbg_tready_ever;
    reg [31:0] drop_detect_count;       // vid_drop_detect trigger count
    wire       dma_beat_fire_dbg = fc_out_tvalid & s0_axis_c2h_tready[0];

    always @(posedge user_clk or negedge vid_sys_rst_n) begin
        if (!vid_sys_rst_n) begin
            dbg_dma_beat_cnt  <= 32'd0;
            dbg_tready_ever   <= 1'b0;
            drop_detect_count <= 32'd0;
        end else begin
            if (dma_beat_fire_dbg)
                dbg_dma_beat_cnt <= dbg_dma_beat_cnt + 1'b1;
            if (s0_axis_c2h_tready[0])
                dbg_tready_ever <= 1'b1;
            if (vid_frame_drop)
                drop_detect_count <= drop_detect_count + 1'b1;
        end
    end

    // Camera SOF detection (for status register)
    reg cam_sof_seen;
    always @(posedge user_clk or negedge vid_sys_rst_n) begin
        if (!vid_sys_rst_n)
            cam_sof_seen <= 1'b0;
        else if (cam_sof)
            cam_sof_seen <= 1'b1;
    end

    assign app_c2h_tready = {C2H_CHNL_NUM{1'b0}}; // private image FIFO owns loop35 C2H
`endif

// ====================================================================
// IMX415 I2C Configuration (runs on cam_24m = 24MHz from ui_pll)
// CLK_DIV = 239 �� 24MHz / (239+1) = 100kHz I2C
// ====================================================================
    // F162: complete configuration words cross through acknowledged mailboxes.
    // Independent mode delivery lets a new mode recover an I2C error even
    // while an unaccepted gain command is held at the camera side.
    // Reject 4K before both the sensor mailbox and local geometry register.
    // Readback retains the current accepted mode; no silent 4K truncation.
    wire cam_mode_wr = wr_pulse && app_bar_write_address[7:0]==`REG_CAM_MODE
        && (CNR_LINE_ADDR_WIDTH>=10 || app_bar_write_data[1:0]!=2'd1);
    wire cam_gain_wr = wr_pulse && app_bar_write_address[7:0]==`REG_AE_GAIN;
    wire [1:0] cam_mode_sync2;
    wire cam_mode_mailbox_valid,cam_mode_mailbox_busy;
    cdc_latest_command #(.WIDTH(2),.INITIAL_VALUE(2'd0)) u_cam_mode_command (
        .rst_n(user_rst_n & cam_clock_cfg_reset_n),.src_clk(user_clk),
        .src_load(cam_mode_wr),
        .src_value(cam_mode_wr ? app_bar_write_data[1:0] : reg_cam_mode),
        .src_busy(cam_mode_mailbox_busy),.dst_clk(cam_24m),.dst_ready(1'b1),
        .dst_valid(cam_mode_mailbox_valid),.dst_value(cam_mode_sync2));

    // Bit8 means software explicitly supplied a gain. At boot it is zero:
    // keep ROM defaults (4K=0x10; 1080P/720P=0x20) until an explicit write.
    wire [29:0] cam_gain_command;wire[19:0]cam_applied_shr;
    wire cam_gain_mailbox_valid,cam_gain_mailbox_busy;
    wire ae_cfg_done_w,ae_write_success;
    reg ae_cfg_done_d1;
    wire ae_cfg_done_fall=~ae_cfg_done_w & ae_cfg_done_d1;
    wire ae_trig_pending=cam_gain_mailbox_valid & cam_gain_command[8];
    cdc_latest_command #(.WIDTH(30),.INITIAL_VALUE(30'h020)) u_cam_gain_command (
        .rst_n(user_rst_n & cam_clock_cfg_reset_n),.src_clk(user_clk),
        .src_load(cam_gain_wr),
        .src_value(cam_gain_wr ? {app_bar_write_data[31],app_bar_write_data[27:8],1'b1,app_bar_write_data[7:0]} :
                                {reg_ae_exposure_valid,reg_ae_shr,reg_ae_gain_valid,reg_ae_gain}),
        .src_busy(cam_gain_mailbox_busy),.dst_clk(cam_24m),
        .dst_ready(!cam_gain_command[8] || ae_cfg_done_fall),
        .dst_valid(cam_gain_mailbox_valid),.dst_value(cam_gain_command));
    reg [7:0] ae_write_cnt;
    always @(posedge cam_24m or negedge cam_clock_cfg_reset_n) begin
        if(!cam_clock_cfg_reset_n) begin ae_cfg_done_d1<=1'b1;ae_write_cnt<=0;end
        else begin
            ae_cfg_done_d1<=ae_cfg_done_w;
            if(ae_write_success) ae_write_cnt<=ae_write_cnt+1'b1;
        end
    end

    // UI metadata is one held-bundle snapshot, never asynchronous counter
    // bits. Its 100ms update is diagnostic, not an I2C command acknowledgment.
    wire [223:0] cam_ui_snapshot;
    csi_stats_snapshot #(.PERIOD(12500000)) u_cam_ui_snapshot (
        .src_clk(cam_24m),.dst_clk(user_clk),
        .rst_n(cam_clock_cfg_reset_n & user_rst_n),
        .src_stats({161'd0,cam_applied_shr,ae_write_cnt,ae_trig_pending,ae_cfg_done_w,cam_i2c_bus_error}),
        .snapshot(cam_ui_snapshot),.status(),.clock_delta());

    ui_cfg_imx415 #(
        .CLK_DIV    (`CAM_I2C_CLK_DIV),.ENABLE_EXPOSURE(1)
    ) u_cam_i2c_cfg (
        .I_clk          (cam_24m),
        .I_rst_n        (cam_clock_cfg_reset_n),
        .I_cam_mode     (cam_mode_sync2),  // CDC-synchronized mode
        .I_ae_req       (ae_trig_pending),  // AE trigger: auto on startup + PCIe write
        .I_ae_data      (cam_gain_command[7:0]),
        .I_ae_exposure_valid(cam_gain_command[29]),.I_ae_shr(cam_gain_command[28:9]),.O_applied_shr(cam_applied_shr),
        .I_ae_override_valid(cam_gain_command[8]),    // CDC-synchronized gain value
        .O_cam_scl      (cam_scl),
        .IO_cam_sda     (cam_sda),
        .O_cfg_done     (cam_i2c_done),
        .O_ae_cfg_done  (ae_cfg_done_w),
        .O_ae_write_success(ae_write_success),
        .O_bus_error    (cam_i2c_bus_error)
    );

// ====================================================================
// User BAR Register Intercept (0x40-0xA0)
// Extended with camera registers at 0x80-0xA0
// ====================================================================
`ifdef AXI4L_MBUS_EN
`ifdef AXI4ST_BUS_EN
    // ���� Write intercept ����
    //37: update only from the actual independently accepted AW/W pair.
    // No high BAR offset aliases and no side effect without low-byte enable.
    wire wr_pulse=app_bar_write_valid &&
                  app_bar_write_address[19:8]==12'd0 && app_bar_write_strobe[0];
    // 11 diagnostic command registers use the BAR-relative low20 address.
    // They do not change the inherited write contract for existing registers.
    reg trace_arm_toggle,trace_armed,trace_trigger_mode,trace_forced;
    reg [11:0] trace_read_index;
    wire [31:0] trace_read_data;
    wire trace_done,trace_busy;
    wire [11:0] trace_head;
    wire [12:0] trace_count;
    wire trace_write=app_bar_write_valid && app_bar_write_address[19:16]==0;
    //47 linear-noise gate: independent low20 decode, byte0 only; default1.
    // Probe mode survives video soft-reset, but cannot change during capture.
    // Host: STREAMOFF -> write/check0x18c -> S_FMT/STREAMON soft reset -> capture.
    always @(posedge user_clk or negedge user_rst_n) begin
        if(!user_rst_n) begin isp_probe_stage48<=0;isp_probe_rejected48<=0;end
        else if(app_bar_write_valid && app_bar_write_address[19:0]==20'h0018c && app_bar_write_strobe[0]) begin
            if(!reg_enable && app_bar_write_data[31:3]==0) isp_probe_stage48<=app_bar_write_data[2:0];
            else isp_probe_rejected48<=isp_probe_rejected48+1'b1;
        end
    end
    always @(posedge user_clk or negedge user_rst_n) begin
        if(!user_rst_n) linear_gate_shadow<=3'd0;
        else if(app_bar_write_valid && app_bar_write_address[19:0]==20'h00168 && app_bar_write_strobe[0])
            linear_gate_shadow<=app_bar_write_data[2:0];
    end
    // Independent full-low20 write decode; 0x160 never aliases legacy CTRL0x60.
    always @(posedge user_clk or negedge user_rst_n) begin
        if(!user_rst_n) cnr_pattern_shadow<=2'd0;
        else if(app_bar_write_valid && app_bar_write_address[19:0]==20'h00160 && app_bar_write_strobe[0])
            cnr_pattern_shadow<=app_bar_write_data[1:0];
    end

    always @(posedge user_clk or negedge user_rst_n) begin
        if(!user_rst_n) begin trace_arm_toggle<=0;trace_armed<=0;trace_read_index<=0;trace_trigger_mode<=0;trace_forced<=0;end
        else if(trace_write) begin
            if(app_bar_write_address[15:0]==16'h0120 && app_bar_write_strobe[0] && app_bar_write_data[0] && !trace_busy) begin
                trace_arm_toggle<=~trace_arm_toggle;trace_armed<=1;trace_trigger_mode<=app_bar_write_data[1];trace_forced<=0;
            end
            if(app_bar_write_address[15:0]==16'h0120 && app_bar_write_strobe[0] && app_bar_write_data[3] && trace_busy) begin
                trace_trigger_mode<=0;trace_forced<=1;
            end
            if(app_bar_write_address[15:0]==16'h0124 && &app_bar_write_strobe[1:0]) trace_read_index<=app_bar_write_data[11:0];
        end
    end
    csi_raw_trace #(.DATA_WIDTH(16)) u_raw_trace (
        .rst_n(user_rst_n),.byte_clk(cam_phy_pclk),.user_clk(user_clk),
        .raw_bytes({16'd0,cam_phy_raw_nibbles}),.arm_toggle(trace_arm_toggle),.armed(trace_armed),
        .trigger_mode(trace_trigger_mode),.error_level(|cam_phy_raw_bytes),
        .read_index(trace_read_index),.read_data(trace_read_data),.done(trace_done),.busy(trace_busy),
        .head(trace_head),.captured_count(trace_count));
    assign frame_receive_credit = trace_write &&
        app_bar_write_address[15:0]==16'h0134 && app_bar_write_strobe[0] && app_bar_write_data[0];
    // wr_pulse above is exactly one committed-byte-enabled transaction.

    always @(posedge user_clk or negedge user_rst_n) begin
        if (!user_rst_n) begin
            reg_enable      <= 1'b0;
            reg_image_loopback <= 1'b0;
            reg_soft_reset  <= 1'b0;
            reg_phy_control <= 7'd0; // automatic tap scan
            reg_bayer_mode  <= 2'd3; // Candidate GBRG; must confirm on HDMI chart
            reg_cam_mode    <= 2'd0;    // Default: 1080p binning
            reg_ae_gain     <= 8'd32;  // Default: 9.6dB (100 �� 0.3dB)
            reg_ae_gain_valid <= 1'b0;reg_ae_shr<=20'd8;reg_ae_exposure_valid<=0;
        end else begin
            if (reg_soft_reset)
                reg_soft_reset <= 1'b0;

            if (wr_pulse) begin
                case (app_bar_write_address[7:0])
                    `REG_CTRL: begin
                        reg_enable     <= app_bar_write_data[0];
                        reg_soft_reset <= app_bar_write_data[1];
                    end
                    8'hA4:           reg_image_loopback <= app_bar_write_data[0];
                    8'hD8:           reg_bayer_mode <= app_bar_write_data[1:0];
                    8'hE0:           reg_phy_control <= app_bar_write_data[6:0];
                    `REG_CAM_MODE:    if(cam_mode_wr)begin reg_cam_mode <= app_bar_write_data[1:0];reg_ae_exposure_valid<=0;reg_ae_shr<=8;end
                    `REG_AE_GAIN: begin
                        reg_ae_gain       <= app_bar_write_data[7:0];
                        reg_ae_gain_valid <= 1'b1;reg_ae_exposure_valid<=app_bar_write_data[31];reg_ae_shr<=app_bar_write_data[27:8];
                    end
                endcase
            end
        end
    end

    // ���� Read intercept (register range 0x40-0xA0) ����
    // Actual RK user interface is BAR0: 1MiB, base 0x21200000.
    // Decode BAR0 offset [19:0]; assigned base [31:20] may be nonzero.
    // Keep offset [19:16] zero and low16 0x0040..0x011C to exclude IRQ 0x0128.
    reg        vid_rd_sel_d1;
    wire twin_bar_select;wire[31:0]twin_bar_data;
    wire isolation_select,isolation_drive;wire[31:0]isolation_data;wire[14:0]dsi_raw_pins;
    wire dsi_clock_select,dsi_clock_enabled,dsi_clock_reset,dsi_monitor_hs,dsi_monitor_lock;wire[31:0]dsi_clock_data;


    always @(posedge user_clk or negedge user_rst_n) begin
        if (!user_rst_n)
            vid_rd_sel_d1 <= 1'b0;
        else if(app_bar_read_valid)
            vid_rd_sel_d1 <= 1'b1 &&
                             (app_bar_read_address[19:16] == 4'h0) &&
                             (((app_bar_read_address[15:0] >= 16'h0040) &&
                               (app_bar_read_address[15:0] <= 16'h011C)) ||
                              app_bar_read_address[15:0]==16'h0120 || app_bar_read_address[15:0]==16'h0124 ||
                              app_bar_read_address[15:0]==16'h0130 ||
                              app_bar_read_address[15:0]==16'h0134 || app_bar_read_address[15:0]==16'h0138 ||
                              (app_bar_read_address[15:0]>=16'h0140 && app_bar_read_address[15:0]<=16'h01DC));
    end

    // Active frame count: always camera
    wire [31:0] active_frame_count = cam_frame_count;

    reg [31:0] vid_reg_rdata_d1;

    always @(posedge user_clk) begin
        if(app_bar_read_valid) case (app_bar_read_address[15:0])
            16'h0120: vid_reg_rdata_d1 <= {3'd0,(trace_done ? trace_count : 13'd0),(trace_done ? trace_head : 12'd0),trace_forced,trace_arm_toggle,trace_busy,trace_done};
            16'h0124: vid_reg_rdata_d1 <= {20'd0,trace_read_index};
            16'h0130: vid_reg_rdata_d1 <= trace_read_data;
            16'h0134: vid_reg_rdata_d1 <= {28'd0,frame_accepting,frame_packet_in_flight,frame_credit_pending,cam_enable};
            16'h0138: vid_reg_rdata_d1 <= frame_credit_posts;
            16'h0140: vid_reg_rdata_d1 <= 32'h43485235;
            16'h0144: vid_reg_rdata_d1 <= cnr_status;
            16'h0148: vid_reg_rdata_d1 <= cnr_input_beats;
            16'h014C: vid_reg_rdata_d1 <= cnr_output_beats;
            16'h0150: vid_reg_rdata_d1 <= cnr_input_frames;
            16'h0154: vid_reg_rdata_d1 <= cnr_output_frames;
            16'h0158: vid_reg_rdata_d1 <= cnr_h_fallback;
            16'h015C: vid_reg_rdata_d1 <= cnr_v_fallback;
            16'h0160: vid_reg_rdata_d1 <= {28'd0,cnr_active_pattern,cnr_pattern_shadow};
            16'h0164: vid_reg_rdata_d1 <= 32'h43525031;
            16'h018C: vid_reg_rdata_d1 <= {28'd0,reg_enable,isp_probe_stage48};
            16'h0190: vid_reg_rdata_d1 <= 32'h49535038; // ISP8 capability; not bit identity
            16'h0194: vid_reg_rdata_d1 <= isp_probe_rejected48;
            16'h01C4: vid_reg_rdata_d1 <= preview_overflow_words;
            16'h01C8: vid_reg_rdata_d1 <= {18'd0,preview_fifo_highwater};
            16'h0198: vid_reg_rdata_d1 <= 32'h31444e42;
            16'h019C: vid_reg_rdata_d1 <= {28'd0,model_error,model_packet_busy,model_credit_pending,model_enable};
            16'h01A0: vid_reg_rdata_d1 <= model_packets;
            16'h01A4: vid_reg_rdata_d1 <= model_epoch[31:0];
            16'h01A8: vid_reg_rdata_d1 <= model_epoch[63:32];
            16'h01AC: vid_reg_rdata_d1 <= model_source_frames;
            16'h01B0: vid_reg_rdata_d1 <= model_complete_frames;
            16'h01B4: vid_reg_rdata_d1 <= model_abort_frames;
            16'h01B8: vid_reg_rdata_d1 <= model_overflows;
            16'h01BC: vid_reg_rdata_d1 <= model_packet_aborts;
            16'h01C0: vid_reg_rdata_d1 <= model_drops;
            16'h01D0: vid_reg_rdata_d1 <= 32'h32454153; // SAE2 gain + SHR group/readback
            16'h01D4: vid_reg_rdata_d1 <= {12'd0,cam_ui_snapshot[30:11]};
            16'h01D8: vid_reg_rdata_d1 <= reg_cam_mode==1 ? 32'd4503 : 32'd2283;
            16'h01DC: vid_reg_rdata_d1 <= {reg_ae_exposure_valid,3'd0,reg_ae_shr,reg_ae_gain};
            16'h01CC: vid_reg_rdata_d1 <= 32'h314d4454; // TDM1 whole-frame scheduling
            16'h0168: vid_reg_rdata_d1 <= {21'd0,linear_hist_gate,1'b0,linear_gate_active,1'b0,linear_gate_shadow};
            16'h016C: vid_reg_rdata_d1 <= 32'h4C494E31;
            16'h0170: vid_reg_rdata_d1 <= 32'h4C494E47;
            16'h0174: vid_reg_rdata_d1 <= linear_hist_sequence;
            16'h0178: vid_reg_rdata_d1 <= linear_histogram[31:0];
            16'h017C: vid_reg_rdata_d1 <= linear_histogram[63:32];
            16'h0180: vid_reg_rdata_d1 <= linear_histogram[95:64];
            16'h0184: vid_reg_rdata_d1 <= linear_histogram[127:96];
            16'h0188: vid_reg_rdata_d1 <= linear_histogram[159:128];
            // ���� Video registers (0x40-0x7C) ����
            `REG_TPG_STATUS:      vid_reg_rdata_d1 <= {30'd0,
                                                       user_link_up, reg_enable};
            `REG_WIDTH:           vid_reg_rdata_d1 <= {16'd0, active_width};
            `REG_HEIGHT:          vid_reg_rdata_d1 <= {16'd0, active_height};
            `REG_PIXEL_FORMAT:    vid_reg_rdata_d1 <= 32'h0000_0001;
            `REG_FRAME_COUNT:     vid_reg_rdata_d1 <= active_frame_count;
            `REG_FPS_CONFIG:      vid_reg_rdata_d1 <= 32'd0;
            `REG_BYTES_PER_FRAME: vid_reg_rdata_d1 <= {16'd0, active_width} *
                                                      {16'd0, active_height} * 32'd3;
            `REG_VERSION:         vid_reg_rdata_d1 <= `PHASE9_VERSION;
            `REG_CTRL:            vid_reg_rdata_d1 <= {30'd0, reg_soft_reset, reg_enable};
            `REG_PADDED_BYTES:    vid_reg_rdata_d1 <= padded_frame_bytes;
            `REG_DROP_COUNT:      vid_reg_rdata_d1 <= fifo_drop_count;
            `REG_PATTERN_SEL:     vid_reg_rdata_d1 <= 32'd0;
            `REG_DELIVERED_COUNT: vid_reg_rdata_d1 <= active_frame_count;
            `REG_DBG_STATE:       vid_reg_rdata_d1 <= {20'd0,
                                                       1'b1,               // [11] source=Camera (always)
                                                       cam_i2c_done_s,      // [10] I2C config done (synced)
                                                       cam_sof_seen,        // [9]  camera SOF detected
                                                       s0_axis_c2h_tready[0],  // [8]  DMA tready
                                                       vid_tvalid,          // [7]  video output valid
                                                       cam_enable,          // [6]  camera path enabled
                                                       1'b0,               // [5]  (was TPG enable)
                                                       mipi_clk_present,    // [4]  MIPI clock alive
                                                       vid_frame_last,      // [3]  frame tlast
                                                       dbg_tready_ever,     // [2]  tready ever asserted
                                                       reg_enable,          // [1]  global enable
                                                       user_link_up};       // [0]  PCIe link up
            `REG_DBG_PIX_CNT:     vid_reg_rdata_d1 <= frame_total_beats;
            `REG_DBG_DMA_BEAT:    vid_reg_rdata_d1 <= dbg_dma_beat_cnt;

            // ���� Camera registers (0x80-0x98) ����
            `REG_SOURCE_SEL:      vid_reg_rdata_d1 <= 32'd1;  // always camera
            `REG_CAM_STATUS:      vid_reg_rdata_d1 <= {cam_ui_snapshot[10:3],          // [31:24] AE I2C write count
                                                       9'd0,
                                                       cam_ui_snapshot[2],     // [14] AE trigger pending
                                                       cam_ui_snapshot[1],       // [13] AE cfg done from FSM
                                                       1'b0,
                                                       cam_best_len_sync,   // [11:6] eye-scan best length
                                                       cam_raw_valid_sync[1],     // [5] MIPI raw tvalid (2FF sampled level)
                                                       cam_delay_done_s,    // [4] auto delay calibration done
                                                       cam_ui_snapshot[0],   // [3] I2C bus error (UI snapshot)
                                                       cam_sof_seen,        // [2] camera frame active
                                                       mipi_clk_present,    // [1] MIPI clock alive (synced)
                                                       cam_i2c_done_s};     // [0] I2C config done (synced)
            `REG_CAM_FRAME_COUNT: vid_reg_rdata_d1 <= cam_frame_count;
            `REG_CAM_ERROR:       vid_reg_rdata_d1 <= {3'd0, cam_img_width,    // [28:16] active camera width
                                                       3'd0, cam_img_height}; // [12:0]  active camera height
            `REG_CAM_MODE:        vid_reg_rdata_d1 <= {30'd0, reg_cam_mode};
            `REG_DROP_DETECT_CNT: vid_reg_rdata_d1 <= drop_detect_count;
            `REG_AE_GAIN:         vid_reg_rdata_d1 <= {24'd0, reg_ae_gain};
            `REG_GATE_DROP_CNT:   vid_reg_rdata_d1 <= gate_drop_count;
            `REG_GATE_PASS_CNT:   vid_reg_rdata_d1 <= gate_pass_count;

            8'hA4:                vid_reg_rdata_d1 <= {31'd0, reg_image_loopback};
            8'hA8:                vid_reg_rdata_d1 <= csi_snapshot_status;
            8'hAC:                vid_reg_rdata_d1 <= csi_snapshot[223:192];
            8'hB0:                vid_reg_rdata_d1 <= csi_snapshot[31:0];
            8'hB4:                vid_reg_rdata_d1 <= csi_snapshot[63:32];
            8'hB8:                vid_reg_rdata_d1 <= csi_snapshot[95:64];
            8'hBC:                vid_reg_rdata_d1 <= csi_snapshot[127:96];
            8'hC0:                vid_reg_rdata_d1 <= csi_snapshot[159:128];
            8'hC4:                vid_reg_rdata_d1 <= csi_snapshot[191:160];
            8'hC8:                vid_reg_rdata_d1 <= csi_clock_delta;
            8'hCC:                vid_reg_rdata_d1 <= cam_clock_measured_edges;
            8'hD0:                vid_reg_rdata_d1 <= cam_clock_window_index;
            8'hD8:                vid_reg_rdata_d1 <= {30'd0,reg_bayer_mode};
            8'hDC:                vid_reg_rdata_d1 <= {30'd0,cam_active_bayer_mode};
            8'hD4:                vid_reg_rdata_d1 <= {27'd0,
                cam_cfg_ready_sync[1],cam_xclr_sync[1],
                (cam_clock_window_index!=0),cam_clock_frequency_ok,
                cam_clock_lock_s};
            16'h00E0:             vid_reg_rdata_d1 <= {25'd0,reg_phy_control};
            16'h00E4:             vid_reg_rdata_d1 <= phy_diag0_status;
            16'h00E8:             vid_reg_rdata_d1 <= phy_diag0[31:0];
            16'h00EC:             vid_reg_rdata_d1 <= phy_diag0[63:32];
            16'h00F0:             vid_reg_rdata_d1 <= phy_diag0[95:64];
            16'h00F4:             vid_reg_rdata_d1 <= phy_diag0[127:96];
            16'h00F8:             vid_reg_rdata_d1 <= phy_diag0[159:128];
            16'h00FC:             vid_reg_rdata_d1 <= phy_diag0[191:160];
            16'h0100:             vid_reg_rdata_d1 <= phy_diag1_status;
            16'h0104:             vid_reg_rdata_d1 <= phy_diag1[31:0];
            16'h0108:             vid_reg_rdata_d1 <= phy_diag1[63:32];
            16'h010C:             vid_reg_rdata_d1 <= phy_diag1[95:64];
            16'h0110:             vid_reg_rdata_d1 <= phy_diag1[127:96];
            16'h0114:             vid_reg_rdata_d1 <= phy_diag1[159:128];
            16'h0118:             vid_reg_rdata_d1 <= phy_diag1[191:160];
            16'h011C:             vid_reg_rdata_d1 <= {24'd0,phy_diag0[175:168]};
            default:              vid_reg_rdata_d1 <= 32'd0;
        endcase
    end

    assign m_axil_rdata = roi_bar_select ? roi_bar_data : dsi_clock_select ? dsi_clock_data : (isolation_select ? isolation_data : (twin_bar_select ? twin_bar_data : (vid_rd_sel_d1 ? vid_reg_rdata_d1 : app_axil_rdata)));
`endif
`endif

// ====================================================================
// SGDMA Application (identical to Phase 8)
// ====================================================================
sgdma_app #(
    .ODATA_WIDTH    (DATA_WIDTH),
    .OKEEP_WIDTH    (KEEP_WIDTH),
    .H2C_CHNL_NUM  (H2C_CHNL_NUM),
    .H2C_DSC_BYP_MAP(H2C_DSC_BYP_MAP),
    .C2H_CHNL_NUM  (C2H_CHNL_NUM),
    .C2H_DSC_BYP_MAP(C2H_DSC_BYP_MAP),
    .DESC_BYP_EN   (DESC_BYP_EN)
) u_sgdma_app(
    .usr_rst_n                  (user_rst_n),
    .loop_reset_n               (vid_sys_rst_n),
    .usr_clk                    (user_clk),
`ifdef AXI4ST_BUS_EN
    .m0_axis_h2c_tready         (app_h2c_tready),
    .m0_axis_h2c_tdata          (m0_axis_h2c_tdata),
    .m0_axis_h2c_tkeep          (m0_axis_h2c_tkeep),
    .m0_axis_h2c_tuser          (m0_axis_h2c_tuser),
    .m0_axis_h2c_tlast          (m0_axis_h2c_tlast),
    .m0_axis_h2c_tvalid         (m0_axis_h2c_tvalid & {H2C_CHNL_NUM{!reg_image_loopback}}),
    .s0_axis_c2h_tready         (app_c2h_tready),
    .s0_axis_c2h_tdata          (app_c2h_tdata),
    .s0_axis_c2h_tkeep          (app_c2h_tkeep),
    .s0_axis_c2h_tuser          (app_c2h_tuser),
    .s0_axis_c2h_tlast          (app_c2h_tlast),
    .s0_axis_c2h_tvalid         (app_c2h_tvalid),
`endif
`ifdef AXI4L_MBUS_EN
    .m_axil_awaddr              (m_axil_awaddr),
    .m_axil_awprot              (m_axil_awprot),
    .m_axil_awvalid             (m_axil_awvalid),
    .m_axil_awready             (m_axil_awready),
    .m_axil_wdata               (m_axil_wdata),
    .m_axil_wstrb               (m_axil_wstrb),
    .m_axil_wvalid              (m_axil_wvalid),
    .m_axil_wready              (m_axil_wready),
    .m_axil_bvalid              (m_axil_bvalid),
    .m_axil_bresp               (m_axil_bresp),
    .m_axil_bready              (m_axil_bready),
    .m_axil_araddr              (m_axil_araddr),
    .m_axil_arprot              (m_axil_arprot),
    .m_axil_arvalid             (m_axil_arvalid),
    .m_axil_arready             (m_axil_arready),
    .bar_write_valid           (app_bar_write_valid),
    .bar_write_address         (app_bar_write_address),
    .bar_write_data            (app_bar_write_data),
    .bar_write_strobe          (app_bar_write_strobe),
    .bar_read_valid            (app_bar_read_valid),
    .bar_read_address          (app_bar_read_address),
    .m_axil_rdata               (app_axil_rdata),
    .m_axil_rresp               (m_axil_rresp),
    .m_axil_rvalid              (m_axil_rvalid),
    .m_axil_rready              (m_axil_rready),
`endif
`ifdef DSC_BYPASS_C2H_CHL0_EN
    .c2h_dsc_byp_ready_0_i     (c2h_dsc_byp_ready_0),
    .c2h_dsc_byp_load_0_o      (c2h_dsc_byp_load_0),
    .c2h_dsc_byp_src_addr_0_o  (c2h_dsc_byp_src_addr_0),
    .c2h_dsc_byp_dst_addr_0_o  (c2h_dsc_byp_dst_addr_0),
    .c2h_dsc_byp_len_0_o       (c2h_dsc_byp_len_0),
    .c2h_dsc_byp_ctl_0_o       (c2h_dsc_byp_ctl_0),
`endif
`ifdef DSC_BYPASS_H2C_CHL0_EN
    .h2c_dsc_byp_ready_0_i     (h2c_dsc_byp_ready_0),
    .h2c_dsc_byp_load_0_o      (h2c_dsc_byp_load_0),
    .h2c_dsc_byp_src_addr_0_o  (h2c_dsc_byp_src_addr_0),
    .h2c_dsc_byp_dst_addr_0_o  (h2c_dsc_byp_dst_addr_0),
    .h2c_dsc_byp_len_0_o       (h2c_dsc_byp_len_0),
    .h2c_dsc_byp_ctl_0_o       (h2c_dsc_byp_ctl_0),
`endif
`ifdef USR_IRQ_EN
    .usr_irq_req                (usr_irq_req),
    .usr_irq_ack                (usr_irq_ack),
    .msi_enable                 (msi_enable),
    .msi_vector_width           (msi_vector_width),
`endif
    .c2h_sts_0                  (c2h_sts_0),
    .h2c_sts_0                  (h2c_sts_0),
    .c2h_sts_1                  (c2h_sts_1),
    .h2c_sts_1                  (h2c_sts_1),
    .c2h_sts_2                  (c2h_sts_2),
    .h2c_sts_2                  (h2c_sts_2),
    .c2h_sts_3                  (c2h_sts_3),
    .h2c_sts_3                  (h2c_sts_3)
);

// ====================================================================
// Debug UART (115200 8N1, periodic status output every 0.5s)
// Clock: app_auxclk (25MHz from sgdma_pll, always available after PLL lock)
// Output format: "S:xx F:xxxxxxxx\r\n"
// Status byte: [0]=pll_lock [1]=pll_lock_stable [2]=link_up [3]=ui_pll_lock
// ====================================================================

    // CDC: pll_lock_stable (core_clk �� app_auxclk, same PLL but different freq)
    (* async_reg="true" *) reg [1:0] dbg_pll_stable_sync;
    always @(posedge app_auxclk)
        dbg_pll_stable_sync <= {dbg_pll_stable_sync[0], pll_lock_stable};

    // CDC: user_link_up (user_clk �� app_auxclk, fully async)
    (* async_reg="true" *) reg [2:0] dbg_link_up_sync;
    always @(posedge app_auxclk or negedge pll_lock) begin
        if (!pll_lock)
            dbg_link_up_sync <= 3'b0;
        else
            dbg_link_up_sync <= {dbg_link_up_sync[1:0], user_link_up};
    end

    (* async_reg="true" *) reg [1:0] dbg_ui_lock_sync;
    always @(posedge app_auxclk or negedge pll_lock) begin
        if(!pll_lock) dbg_ui_lock_sync<=0;
        else dbg_ui_lock_sync<={dbg_ui_lock_sync[0],ui_pll_lock};
    end

    // Assemble status word
    wire [15:0] dbg_uart_status = {12'd0,
                                   dbg_ui_lock_sync[1],              // [3]
                                   dbg_link_up_sync[2],      // [2]
                                   dbg_pll_stable_sync[1],   // [1]
                                   pll_lock};                // [0]

    // Frame count (user_clk domain, sampled without formal CDC �� debug display only)
`ifdef AXI4ST_BUS_EN
    wire [223:0] dbg_uart_snapshot;
    csi_stats_snapshot #(.PERIOD(2500000)) u_dbg_uart_snapshot (
        .src_clk(user_clk),.dst_clk(app_auxclk),.rst_n(pll_lock & user_rst_n),
        .src_stats({160'd0,cam_frame_count}),.snapshot(dbg_uart_snapshot),
        .status(),.clock_delta());
    wire [31:0] dbg_uart_fcount = dbg_uart_snapshot[31:0];
`else
    wire [31:0] dbg_uart_fcount = 32'd0;
`endif

    debug_uart #(
        .CLK_FREQ   (25_000_000),       // app_auxclk = 25MHz
        .BAUD_RATE  (115200)
    ) u_debug_uart (
        .clk         (app_auxclk),
        .rst_n       (pll_lock),
        .tx          (uart_tx),
        .rx          (uart_rx),
        .status      (dbg_uart_status),
        .frame_count (dbg_uart_fcount)
    );


    // Project-feature UI: existing camera/ISP/DMA paths above stay intact.
    wire twin_ui_clk,twin_ui_reset,twin_i_vs,twin_i_hs,twin_i_de,twin_o_vs,twin_o_hs,twin_o_de;
    wire[23:0]twin_rgb;wire[31:0]twin_ms;
    twin_tick_ms u_twin_time(.clk(twin_ui_clk),.rst(twin_ui_reset),.now_ms(twin_ms));
    twin_pcie_ui u_twin_pcie_ui(.view_select(view_select),.view_fire(view_fire),.view_sof(view_sof),.view_eol(view_eol),.view_eof(view_eof),
 .view_rgb(view_rgb),.view_count(view_count),.view_id(view_id),.view_tick(view_tick),

      .view_epoch(model_epoch),.view_source_enable(vid_sys_rst_n&&model_enable&&cam_enable&&!model_error),.bar_clk(user_clk),.ui_clk(twin_ui_clk),.rst_n(user_rst_n && !twin_ui_reset),.now_ms(twin_ms),
      .bar_write_valid(app_bar_write_valid),.bar_write_address(app_bar_write_address),.bar_write_data(app_bar_write_data),.bar_write_strobe(app_bar_write_strobe),
      .bar_read_valid(app_bar_read_valid),.bar_read_address(app_bar_read_address),.bar_read_select(twin_bar_select),.bar_read_data(twin_bar_data),
      .i_vs(twin_i_vs),.i_hs(twin_i_hs),.i_de(twin_i_de),.o_vs(twin_o_vs),.o_hs(twin_o_hs),.o_de(twin_o_de),.o_rgb(twin_rgb),
      .accepted_packets(),.crc_errors(),.format_errors(),.sequence_errors(),.published_scenes(),.feature_valid_mask(),.feature_front_ready(),
      .transport_reset(),.transport_fault());
    twin_dsi_isolation u_dsi_isolation(.clk(user_clk),.rst_n(user_rst_n),
      .write_valid(app_bar_write_valid),.write_address(app_bar_write_address),.write_data(app_bar_write_data),.write_strobe(app_bar_write_strobe),
      .read_valid(app_bar_read_valid),.read_address(app_bar_read_address),.read_select(isolation_select),.read_data(isolation_data),
      .raw_pins(dsi_raw_pins),.pins({O_clk_hs_p,O_clk_lp_p,O_clk_lp_n,O_data_hs_p,O_data_lp_p,O_data_lp_n}),.drive_enabled(isolation_drive));
    twin_dsi_clock_control u_dsi_clock_control(.clk(user_clk),.rst_n(user_rst_n),
      .ui_clk(twin_ui_clk),.hs_clk(dsi_monitor_hs),.pll_locked(dsi_monitor_lock),.ui_reset(twin_ui_reset),
      .write_valid(app_bar_write_valid),.write_address(app_bar_write_address),.write_data(app_bar_write_data),.write_strobe(app_bar_write_strobe),
      .read_valid(app_bar_read_valid),.read_address(app_bar_read_address),.read_select(dsi_clock_select),.read_data(dsi_clock_data),
      .clock_enabled(dsi_clock_enabled),.clock_reset(dsi_clock_reset));
    assign dsi_raw_pins[14]=dsi_monitor_hs;
    twin_dsi_output u_twin_dsi(.sys_clk(sys_clk),.clock_reset(dsi_clock_reset),
      .monitor_hs(dsi_monitor_hs),.monitor_lock(dsi_monitor_lock),.ui_clk(twin_ui_clk),.ui_reset(twin_ui_reset),
      .timing_vs(twin_i_vs),.timing_hs(twin_i_hs),.timing_de(twin_i_de),
      .pixel_vs(twin_o_vs),.pixel_hs(twin_o_hs),.pixel_de(twin_o_de),.pixel_rgb(twin_rgb),
      .O_clk_hs_p(dsi_unused_serial_clock),.O_clk_lp_p(dsi_raw_pins[13]),.O_clk_lp_n(dsi_raw_pins[12]),
      .O_data_hs_p(dsi_raw_pins[11:8]),.O_data_lp_p(dsi_raw_pins[7:4]),.O_data_lp_n(dsi_raw_pins[3:0]));

endmodule
`timescale 1ns/1ps
`default_nettype none
// Diagnostic experiment only. Default all fifteen DSI output pads to high Z.
// Internal PLL/DSI clocks continue unchanged. Do not select as a production UI.
// The board owner changes this only with capture stopped, then tests a fresh
// stream. Active switching is not a qualified DSI link sequencing operation.
module twin_dsi_isolation(
 input wire clk,rst_n,
 input wire write_valid,input wire[31:0]write_address,write_data,input wire[3:0]write_strobe,
 input wire read_valid,input wire[31:0]read_address,
 output reg read_select,output reg[31:0]read_data,
 input wire[14:0]raw_pins,output wire[14:0]pins,
 output reg drive_enabled
);
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)drive_enabled<=0;
  else if(write_valid && write_address[19:0]==20'h00d00 && &write_strobe)begin
   if(write_data==32'h44534900)drive_enabled<=0;
   else if(write_data==32'h44534901)drive_enabled<=1;
  end
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin read_select<=0;read_data<=0;end
  else if(read_valid)begin
   read_select<=read_address[19:0]==20'h00d00;
   read_data<=32'h44534900|{31'd0,drive_enabled};
  end
 end
 assign pins=drive_enabled ? raw_pins : 15'bz;
endmodule
`default_nettype wire

`timescale 1ns/1ps
`default_nettype none
// Scoped diagnostic. Reset only the DSI PLL; never gate a clock with logic.
// The activity counters deliberately ignore clock_enable and ui_reset. They
// must continue to expose a PLL which did NOT actually stop on request.
module twin_dsi_clock_control #(
 parameter integer WINDOW_CYCLES=12500
)(
 input wire clk,rst_n,ui_clk,hs_clk,pll_locked,ui_reset,
 input wire write_valid,input wire[31:0]write_address,write_data,
 input wire[3:0]write_strobe,
 input wire read_valid,input wire[31:0]read_address,
 output reg read_select,output reg[31:0]read_data,
 output reg clock_enabled,output wire clock_reset
);
 assign clock_reset=~clock_enabled;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)clock_enabled<=0;
  else if(write_valid && write_address[19:0]==20'h00d04 && &write_strobe)begin
   if(write_data==32'h44534300)clock_enabled<=0;
   else if(write_data==32'h44534301)clock_enabled<=1;
  end
 end
 (* async_reg="true" *)reg[1:0]ui_release=0,hs_release=0;
 always @(posedge ui_clk or negedge rst_n)
  if(!rst_n)ui_release<=0;else ui_release<={ui_release[0],1'b1};
 always @(posedge hs_clk or negedge rst_n)
  if(!rst_n)hs_release<=0;else hs_release<={hs_release[0],1'b1};
 // Counter reset asserts asynchronously through the release synchronizer,
 // and deasserts only on that counter's own clock edge.
 reg[7:0]ui_div=0,hs_div=0;
 always @(posedge ui_clk or negedge ui_release[1])
  if(!ui_release[1])ui_div<=0;else ui_div<=ui_div+1'b1;
 always @(posedge hs_clk or negedge hs_release[1])
  if(!hs_release[1])hs_div<=0;else hs_div<=hs_div+1'b1;
 // Only one divided-clock bit crosses, and first Q is private to second D.
 (* async_reg="true" *)reg[1:0]ui_sample=0,hs_sample=0,lock_sample=0,reset_sample=0;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin ui_sample<=0;hs_sample<=0;lock_sample<=0;reset_sample<=0;end
  else begin
   ui_sample<={ui_sample[0],ui_div[7]};hs_sample<={hs_sample[0],hs_div[7]};
   lock_sample<={lock_sample[0],pll_locked};reset_sample<={reset_sample[0],ui_reset};
  end
 end
 reg ui_previous=0,hs_previous=0;
 reg[13:0]window_count=0;
 reg[7:0]ui_edges=0,hs_edges=0,ui_measured=0,hs_measured=0;
 reg[31:0]window_index=0;
 reg window_valid=0;
 wire ui_edge=ui_sample[1]^ui_previous;
 wire hs_edge=hs_sample[1]^hs_previous;
 wire[7:0]ui_next=(ui_edges==8'hff)?8'hff:ui_edges+ui_edge;
 wire[7:0]hs_next=(hs_edges==8'hff)?8'hff:hs_edges+hs_edge;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   ui_previous<=0;hs_previous<=0;window_count<=0;ui_edges<=0;hs_edges<=0;
   ui_measured<=0;hs_measured<=0;window_index<=0;window_valid<=0;
  end else begin
   ui_previous<=ui_sample[1];hs_previous<=hs_sample[1];
   if(window_count==WINDOW_CYCLES-1)begin
    window_count<=0;ui_measured<=ui_next;hs_measured<=hs_next;
    ui_edges<=0;hs_edges<=0;window_index<=window_index+1'b1;window_valid<=1;
   end else begin window_count<=window_count+1'b1;ui_edges<=ui_next;hs_edges<=hs_next;end
  end
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin read_select<=0;read_data<=0;end
  else if(read_valid)begin
   case(read_address[19:0])
    20'h00d04:begin read_select<=1;read_data<=32'h44534300|{31'd0,clock_enabled};end
    20'h00d08:begin read_select<=1;read_data<={8'hd5,hs_measured,ui_measured,
                      4'd0,window_valid,reset_sample[1],lock_sample[1],clock_enabled};end
    20'h00d0c:begin read_select<=1;read_data<=window_index;end
    default:begin read_select<=0;read_data<=0;end
   endcase
  end
 end
endmodule
`default_nettype wire
