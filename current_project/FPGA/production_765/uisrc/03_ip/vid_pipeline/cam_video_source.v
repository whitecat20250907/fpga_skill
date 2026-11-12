// =============================================================================
// cam_video_source.v �� IMX415 Camera Video Source (drop-in replacement for tpg_gen)
// =============================================================================
// Pipeline:
//   mipi_csi_rx (40b @ user_clk via internal sfifo CDC)
//     �� image_correction (crop to active region)
//       �� ui_BLC (black level correction, offset=50)
//         �� ui_top_demosaic (RAW10 Bayer �� 128b RGB)
//           �� data128_96 �� ui_awb (Gray World AWB) �� data96_128
//             �� FIFO (rate decoupling)
//               �� pack4_rgb24_to_512 (128b��512b, 4 pixels/clk, backpressure)
//
// Output interface: 128-bit AXI-Stream + sof/eof/frame_count.
// Matched to x1 Gen2 PCIe DATA_WIDTH=128.
// No DDR buffering �� pure streaming with frame-drop on DMA backpressure.
// =============================================================================
`timescale 1ns / 1ps

module cam_video_source #(
    parameter MIPI_LAN     = 4,
    parameter DEVICE       = "PH2",
    parameter BAYER_MODE   = "RGGB",
    parameter CNR_LINE_ADDR_WIDTH = 10
)(
    // System clock (PCIe user_clk, ~250-300MHz)
    input  wire          user_clk,
    input  wire          user_rst_n,
    input  wire          enable,
 input wire[1:0]view_select,
 output wire view_fire,view_sof,view_eol,view_eof,
 output wire[95:0]view_rgb,output wire[2:0]view_count,
 output wire[31:0]view_id,output wire[63:0]view_tick,
    input wire model_enable,
    output wire model_valid,input wire model_ready,output wire [127:0] model_data,
    output wire model_sof,model_eol,model_eof,output wire [31:0] model_id,output wire [63:0] model_tick,
    output wire [31:0] model_source_frames,model_complete_frames,model_abort_frames,model_overflows,
    output wire model_error,

    // Runtime resolution parameters (from BAR registers)
    input  wire [1:0]    cfg_bayer_mode,    // 0RGGB/1BGGR/2GRBG/3GBRG; user_clk domain
    input  wire [12:0]   cfg_img_width,      // Active image width  (e.g. 1920, 3840, 1280)
    input  wire [12:0]   cfg_img_height,     // Active image height (e.g. 1080, 2160, 720)
    input  wire [14:0]   cfg_crop_v_start,   // Crop: first valid line (exclusive >)
    input  wire [14:0]   cfg_crop_v_end,     // Crop: last  valid line (exclusive <)
    input  wire [14:0]   cfg_crop_h_end,     // Crop: h beats per line (exclusive <)

    // MIPI CSI-2 physical interface
    input  wire          mipi_ref_clock,     // PHY reference clock
    input  wire          mipi_clk_hs_rx_p,   // MIPI clock lane (P)
    input  wire [MIPI_LAN-1:0] mipi_data_hs_p, // MIPI data lanes (P)

    // Frame control
    input  wire          frame_request,      // Tie to 1 for camera mode

    // AXI-Stream 128-bit output (matched to x1 Gen2 DATA_WIDTH=128)
    output wire [127:0]  m_tdata,
    output wire          m_tvalid,
    input  wire          m_tready,
    output wire          m_tlast,
    output wire          m_frame_last,
    output wire          sof,
    output wire          eof,
    output wire [31:0]   frame_count_out,
    output wire [1:0]    active_bayer_mode,
    input wire [1:0] cfg_cnr_pattern,
    input wire [2:0] cfg_probe_stage, // Set only while capture disabled; soft-reset before STREAMON.
    input wire [2:0] cfg_linear_gate,
    output wire [2:0] linear_gate_active,linear_hist_gate,
    output wire [31:0] linear_hist_sequence,
    output wire [159:0] linear_histogram,
    input wire roi_bar_write_valid,roi_bar_read_valid,
    input wire [31:0] roi_bar_write_address,roi_bar_write_data,roi_bar_read_address,
    input wire [3:0] roi_bar_write_strobe,
    output wire roi_bar_select,output wire [31:0] roi_bar_data,
    output wire [1:0] cnr_active_pattern,
    output wire [31:0] cnr_status,cnr_input_beats,cnr_output_beats,
    output wire [31:0] cnr_input_frames,cnr_output_frames,cnr_h_fallback,cnr_v_fallback,

    // Status / debug
    input  wire          debug_button,       // Board debug button (MIPI delay)
    output wire          mipi_div_clk_out,   // Divided HS clock (debug)
    output wire          auto_delay_done,    // MIPI PHY auto delay calibration done
    output wire          mipi_tvalid_out,    // MIPI receiver raw tvalid (for debug)
    output wire [7:0]    dbg_mipi,           // MIPI �ڲ��������ߣ�hs_div_clk ��
    output wire [7:0]    dbg_delay,          // delay �������ߣ�hs_div_clk ��
    // Shadow command lives in user_clk; held-bus CDC is inside mipi_csi_rx.
    input wire [6:0] phy_control_shadow, // bit6 override enable, bits5:0 tap
    output wire [15:0] phy_raw_nibbles_out,
    output wire phy_pclk_out,
    output wire [31:0] phy_raw_bytes_out,
    output wire [223:0] phy_diag0, phy_diag1, // [223:192] source byte-clock cycles
    output wire [31:0] phy_diag0_status, phy_diag1_status,
    output wire [31:0] phy_diag0_clock_delta, phy_diag1_clock_delta,
    output wire [223:0] csi_snapshot,
    output wire [31:0] csi_snapshot_status,
    output wire [31:0] csi_clock_delta,
    output wire [5:0]    dbg_best_len        // eye-scan ������䳤��
);

    // ================================================================
    // Internal wires
    // ================================================================

    // mipi_csi_rx �� image_correction
    wire ccm_tready;
    wire fifo_full;
    wire [39:0]  mipi_tdata;
    wire         mipi_tvalid;
    assign       mipi_tvalid_out = mipi_tvalid;
    wire         mipi_tlast;
    wire         mipi_tuser;
    wire         mipi_tready;

    // image_correction �� ui_BLC
    wire [39:0]  crop_tdata;
    wire [9:0]   crop_tdest;
    wire         crop_tvalid;
    wire         crop_tlast;
    wire         crop_tuser;
    wire         crop_tready;

    // ui_BLC �� ui_top_demosaic
    wire [39:0]  blc_tdata;
    wire [9:0]   blc_tdest;
    wire         blc_tvalid;
    wire         blc_tlast;
    wire         blc_tuser;
    wire         blc_tready;

    // ui_top_demosaic �� AWB chain �� FIFO �� pack4_rgb24_to_512
    wire [119:0] demo_tdata;
    wire         demo_tvalid;
    wire         demo_tlast;
    wire         demo_tuser;
    wire         demo_tready;

    // AWB internal signals
    wire [95:0]  demo_debug8_96;    // diagnostic projection only; native demosaic120 is not consumed by this debug96 view
    wire [119:0] awb_tdata;         // AWB native120 output
    wire         awb_tvalid;
    wire         awb_tlast;
    wire         awb_tuser;
    wire         awb_tready;

    // Image Cut output (edge pixel zeroing)
    wire [119:0] cut_tdata;
    wire         cut_tvalid;
    wire         cut_tlast;
    wire         cut_tuser;
    wire         cut_tready;

    // Gamma correction output
    wire [95:0]  gamma_tdata;
    wire         gamma_tvalid;
    wire         gamma_tlast;
    wire         gamma_tuser;
    wire         gamma_tready;

    // Contrast adjustment output
    wire [95:0]  contrast_tdata;
    wire         contrast_tvalid;
    wire         contrast_tlast;
    wire         contrast_tuser;
    wire         contrast_tready;

    // Brightness adjustment output
    wire [95:0]  bright_tdata;
    wire         bright_tvalid;
    wire         bright_tlast;
    wire         bright_tuser;
    wire         bright_tready;

    // Saturation adjustment output
    wire [95:0]  sat_tdata;
    wire         sat_tvalid;
    wire         sat_tlast;
    wire         sat_tuser;
    wire         sat_tready;
    wire [127:0] sat_tdata_128;     // Saturation 96b �� 128b (restore padding)

    // FIFO output �� pack4_rgb24_to_512
    wire [127:0] fifo_tdata;
    wire         fifo_tvalid;
    wire         fifo_tlast;
    wire         fifo_tuser;
    wire         fifo_tready;

    // ---- Pipeline diagnostic sticky flags (injected into frame_count upper byte) ----
    reg mipi_tuser_ever, mipi_tlast_ever;
    reg crop_tuser_ever, crop_tlast_ever;
    reg demo_tuser_ever, demo_tlast_ever;
    reg awb_tuser_ever,  awb_tlast_ever;
    reg pack_sof_ever,   pack_eof_ever;
    always @(posedge user_clk or negedge user_rst_n) begin
        if (!user_rst_n) begin
            mipi_tuser_ever <= 1'b0; mipi_tlast_ever <= 1'b0;
            crop_tuser_ever <= 1'b0; crop_tlast_ever <= 1'b0;
            demo_tuser_ever <= 1'b0; demo_tlast_ever <= 1'b0;
            awb_tuser_ever  <= 1'b0; awb_tlast_ever  <= 1'b0;
            pack_sof_ever   <= 1'b0; pack_eof_ever   <= 1'b0;
        end else begin
            if (mipi_tuser)  mipi_tuser_ever <= 1'b1;
            if (mipi_tlast)  mipi_tlast_ever <= 1'b1;
            if (crop_tuser)  crop_tuser_ever <= 1'b1;
            if (crop_tlast)  crop_tlast_ever <= 1'b1;
            if (demo_tuser)  demo_tuser_ever <= 1'b1;
            if (demo_tlast)  demo_tlast_ever <= 1'b1;
            if (awb_tuser)   awb_tuser_ever  <= 1'b1;
            if (awb_tlast)   awb_tlast_ever  <= 1'b1;
            if (sof)         pack_sof_ever   <= 1'b1;
            if (eof)         pack_eof_ever   <= 1'b1;
        end
    end
    wire [31:0] raw_frame_count;

    // ================================================================
    // 1. MIPI CSI-2 Receiver
    //    CDC: internal sfifo bridges hs_rx_clk �� m_axis_video_aclk (user_clk)
    // ================================================================
    wire [191:0] csi_stats;
    wire [191:0] phy_diag0_byte, phy_diag1_byte;
    // Both diagnostic buses originate in BYTE clock, not UI clock. Each
    // snapshot has a coherent hold/ack transfer and its own reset synchronizers.
    // Default PERIOD is destination user_clk cycles (12.5M = 100ms at 125MHz).
    csi_stats_snapshot u_phy_diag0_snapshot (
        .src_clk(mipi_div_clk_out), .dst_clk(user_clk), .rst_n(user_rst_n),
        .src_stats(phy_diag0_byte), .snapshot(phy_diag0),
        .status(phy_diag0_status), .clock_delta(phy_diag0_clock_delta));
    csi_stats_snapshot u_phy_diag1_snapshot (
        .src_clk(mipi_div_clk_out), .dst_clk(user_clk), .rst_n(user_rst_n),
        .src_stats(phy_diag1_byte), .snapshot(phy_diag1),
        .status(phy_diag1_status), .clock_delta(phy_diag1_clock_delta));
    csi_stats_snapshot u_csi_snapshot (.src_clk(mipi_div_clk_out),
        .dst_clk(user_clk),.rst_n(user_rst_n),.src_stats(csi_stats),
        .snapshot(csi_snapshot),.status(csi_snapshot_status),
        .clock_delta(csi_clock_delta));
    mipi_csi_rx #(
        .MIPI_LAN   (MIPI_LAN),
        .DEVICE     (DEVICE)
    ) u_mipi_csi_rx (
        .I_debug_button         (debug_button),
        .I_phy_control_shadow   (phy_control_shadow),
        .O_phy_raw_nibbles      (phy_raw_nibbles_out),
        .O_phy_pclk             (phy_pclk_out),
        .O_phy_raw_bytes        (phy_raw_bytes_out),
        .O_phy_diag0            (phy_diag0_byte),
        .O_phy_diag1            (phy_diag1_byte),
        .I_ref_clock            (mipi_ref_clock),
        .I_clk_hs_rx_p          (mipi_clk_hs_rx_p),
        .I_reset_n              (user_rst_n),
        .I_hs_data_p            (mipi_data_hs_p),
        .I_enable               (enable),
        .O_hs_div_clk           (mipi_div_clk_out),
        // Output clock domain = user_clk (key CDC point!)
        .m_axis_video_aclk      (user_clk),
        .m_axis_video_aresetn   (user_rst_n),
        .m_axis_video_tready    (mipi_tready),
        .m_axis_video_tuser     (mipi_tuser),
        .m_axis_video_tlast     (mipi_tlast),
        .m_axis_video_tvalid    (mipi_tvalid),
        .m_axis_video_tdata     (mipi_tdata),
        .O_auto_delay_done      (auto_delay_done),
        .O_dbg_mipi             (dbg_mipi),
        .O_dbg_delay            (dbg_delay),
        .O_csi_raw_packets      (csi_stats[31:0]),
        .O_csi_crc_errors       (csi_stats[63:32]),
        .O_csi_ecc_errors       (csi_stats[95:64]),
        .O_csi_wc_errors        (csi_stats[127:96]),
        .O_csi_timeout_errors   (csi_stats[159:128]),
        .O_csi_fifo_overflows   (csi_stats[191:160]),
        .O_csi_error_pulse      (),
        .O_dbg_best_len         (dbg_best_len)
    );

    // ================================================================
    // 2. Image Correction (spatial crop to IMG_WIDTH �� IMG_HEIGHT)
    // ================================================================
    image_correction #(
        .DATA_WIDTH     (40),
        .TDEST_WIDTH    (10)
    ) u_image_correction (
        .I_clk          (user_clk),
        .I_rst_n        (user_rst_n),
        // Runtime crop parameters
        .I_v_start      (cfg_crop_v_start),
        .I_v_end        (cfg_crop_v_end),
        .I_h_end        (cfg_crop_h_end),
        // Input from MIPI Rx
        .I_raw_tdata    (mipi_tdata),
        .I_raw_tdest    (10'd0),
        .I_raw_tlast    (mipi_tlast),
        .I_raw_tvalid   (mipi_tvalid),
        .I_raw_tuser    (mipi_tuser),
        .I_raw_tready   (mipi_tready),
        // Output to BLC
        .O_raw_tdata    (crop_tdata),
        .O_raw_tdest    (crop_tdest),
        .O_raw_tlast    (crop_tlast),
        .O_raw_tvalid   (crop_tvalid),
        .O_raw_tuser    (crop_tuser),
        .O_raw_tready   (crop_tready)
    );

    // Atomic source-frame selection before the elastic BLC stage. A shadow
    // write during this frame takes effect only at its next accepted crop SOF.
    localparam [1:0] DEFAULT_BAYER = (BAYER_MODE=="RGGB") ? 2'd0 :
        (BAYER_MODE=="BGGR") ? 2'd1 : (BAYER_MODE=="GRBG") ? 2'd2 : 2'd3;
    reg [1:0] frame_bayer_mode;
    assign active_bayer_mode=frame_bayer_mode;
    always @(posedge user_clk or negedge user_rst_n)
        if(!user_rst_n) frame_bayer_mode <= DEFAULT_BAYER;
        else if(crop_tvalid && crop_tready && crop_tuser) begin
            case(cfg_bayer_mode)
                2'd0,2'd1,2'd2,2'd3: frame_bayer_mode <= cfg_bayer_mode;
                default: frame_bayer_mode <= DEFAULT_BAYER;
            endcase
        end

    // ================================================================
    // 3. Black Level Correction (BLC)
    // ================================================================
    wire [7:0] probe_ready48;
    wire blc_input_ready48,demo_input_ready48,ccm_input_ready48,awb_input_ready48;
    wire cut_input_ready48,contrast_input_ready48,cnr_input_ready48;
    assign crop_tready=(cfg_probe_stage==1)?probe_ready48[1]:blc_input_ready48;
    assign blc_tready=(cfg_probe_stage==2)?probe_ready48[2]:demo_input_ready48;
    assign demo_tready=(cfg_probe_stage==3)?probe_ready48[3]:ccm_input_ready48;
    assign ccm_tready=(cfg_probe_stage==4)?probe_ready48[4]:awb_input_ready48;
    assign awb_tready=(cfg_probe_stage==5)?probe_ready48[5]:cut_input_ready48;
    assign gamma_tready=(cfg_probe_stage==6)?probe_ready48[6]:contrast_input_ready48;
    assign sat_tready=(cfg_probe_stage==7)?probe_ready48[7]:cnr_input_ready48;

    ui_BLC #(
        .Black_level_offset_r0  (10'd50),
        .Black_level_offset_r1  (10'd50),
        .Black_level_offset_r2  (10'd50),
        .Black_level_offset_r3  (10'd50)
    ) u_blc (
        .I_clk      (user_clk),
        .I_rst_n    (user_rst_n),
        // Input from image_correction
        .I_tdata    (crop_tdata),
        .I_tdest    (crop_tdest),
        .I_tlast    (crop_tlast),
        .I_tvalid   (crop_tvalid && cfg_probe_stage!=1),
        .I_tuser    (crop_tuser),
        .I_tready   (blc_input_ready48),
        // Output to demosaic
        .O_tdata    (blc_tdata),
        .O_tdest    (blc_tdest),
        .O_tlast    (blc_tlast),
        .O_tvalid   (blc_tvalid),
        .O_tuser    (blc_tuser),
        .O_tready   (blc_tready)
    );

    // ================================================================
    // 4. Demosaic (RAW10 Bayer �� 128-bit RGB)
    //    128b = 4 pixels �� {8'b0, R[7:0], G[7:0], B[7:0]}
    //    Uses 3 BRAM line buffers (ui_ram_demosaic �� 2 + ui_ram_zhenghe �� 1)
    // ================================================================
    ui_top_demosaic #(
        .data_complete_delay    (50),
        .BAYER_MODE             (BAYER_MODE)
    ) u_demosaic (
        .I_clk              (user_clk),
        .I_rst_n            (user_rst_n),
        // Runtime resolution
        .I_bayer_mode       (frame_bayer_mode),
        .I_img_width        (cfg_img_width),
        .I_img_height       (cfg_img_height),
        // Input from BLC
        .I_axi4s_tdata      (blc_tdata),
        .I_axi4s_tdest      (blc_tdest),
        .I_axi4s_tlast      (blc_tlast),
        .I_axi4s_tvalid     (blc_tvalid && cfg_probe_stage!=2),
        .I_axi4s_tuser      (blc_tuser),
        .I_axi4s_tready     (demo_input_ready48),
        // Output to AWB chain
        .O_tdata            (demo_tdata),
        .O_tvalid           (demo_tvalid),
        .O_tlast            (demo_tlast),
        .O_tuser            (demo_tuser),
        .O_tready           (demo_tready)
    );

    // ================================================================
    // 4a. Auto White Balance (AWB) �� Gray World algorithm
    //     Pipeline: demosaic(128b) �� data128_96 �� AWB(96b) �� data96_128 �� (128b)
    //     Uses divider IP (50-cycle latency) + signal_delay BRAM for data sync.
    //     Gain updated every 4 frames. G channel = reference, R/B adjusted.
    // ================================================================

    // Precision51 native linear RGB10: four packed 30-bit pixels. Only
    // diagnostic taps3/4/5 project [9:2] to RGB8 for the existing RGB3 wire ABI.
    // The actual CCM/AWB/image-cut path never consumes these debug views.
    // AWB core (Gray World, 96-bit 4-pixel parallel)
    // Physical linear RGB colour correction before neutral-only AWB.
    wire [119:0] ccm_tdata;
    wire ccm_tlast, ccm_tuser, ccm_tvalid;
    ui_ccm32 u_ccm (
        .cfg_gate_shadow(cfg_linear_gate),.active_gate(linear_gate_active),
        .hist_gate(linear_hist_gate),.hist_sequence(linear_hist_sequence),.hist_previous(linear_histogram),
        .I_clk(user_clk), .I_rst_n(user_rst_n),
        .I_tdata(demo_tdata), .I_tlast(demo_tlast), .I_tuser(demo_tuser),
        .I_tvalid(demo_tvalid && cfg_probe_stage!=3), .I_tready(ccm_input_ready48),
        .O_tdata(ccm_tdata), .O_tlast(ccm_tlast), .O_tuser(ccm_tuser),
        .O_tvalid(ccm_tvalid), .O_tready(ccm_tready)
    );

    roi_stats_bar u_roi_stats(
        .clk(user_clk),.rst_n(user_rst_n),.fire(ccm_tvalid&&ccm_tready),
        .sof(ccm_tuser),.eol(ccm_tlast),.rgb(ccm_tdata),.width(cfg_img_width),.height(cfg_img_height),
        .write_valid(roi_bar_write_valid),.write_address(roi_bar_write_address),.write_data(roi_bar_write_data),
        .write_strobe(roi_bar_write_strobe),.read_valid(roi_bar_read_valid),.read_address(roi_bar_read_address),
        .read_select(roi_bar_select),.read_data(roi_bar_data));

    ui_awb #(
        .IMG_HEIGHT (2160),
        .IMG_WIDTH  (3840)
    ) u_awb (
        .I_clk      (user_clk),
        .I_rst_n    (user_rst_n),
        .I_img_width (cfg_img_width),
        .I_img_height(cfg_img_height),
        .I_tlast    (ccm_tlast),
        .I_tuser    (ccm_tuser),
        .I_tdata    (ccm_tdata),
        .I_tvalid   (ccm_tvalid && cfg_probe_stage!=4),
        .I_tready   (awb_input_ready48),
        .O_tlast    (awb_tlast),
        .O_tuser    (awb_tuser),
        .O_tdata    (awb_tdata),
        .O_tvalid   (awb_tvalid),
        .O_tready   (awb_tready)
    );

    // ================================================================
    // 4b. Image Cut �� zero out edge pixels to remove demosaic boundary artifacts
    //     SKIP_COLS_left=1 �� zeros first 4 pixels (1 beat at 4-pixel parallel)
    // ================================================================
    ui_image_cut #(
        .IMG_WIDTH      (3840),
        .IMG_HEIGHT     (2160),
        .DATA_WIDTH     (120),
        .SKIP_ROWS_top  (0),
        .SKIP_ROWS_bottom(0),
        .SKIP_COLS_left (1),
        .SKIP_COLS_right(0)
    ) u_image_cut (
        .I_clk      (user_clk),
        .I_rst_n    (user_rst_n),
        .I_img_width (cfg_img_width),
        .I_img_height(cfg_img_height),
        .I_tlast    (awb_tlast),
        .I_tuser    (awb_tuser),
        .I_tdata    (awb_tdata),
        .I_tvalid   (awb_tvalid && cfg_probe_stage!=5),
        .I_tready   (cut_input_ready48),
        .O_tlast    (cut_tlast),
        .O_tuser    (cut_tuser),
        .O_tdata    (cut_tdata),
        .O_tvalid   (cut_tvalid),
        .O_tready   (cut_tready)
    );

    // ================================================================
    // 4c. Gamma Correction (�� = 2.2)
    //     LUT-based per-channel correction, 4-pixel parallel
    // ================================================================
    ui_gamma #(
        .GAMMA_10x  (26)
    ) u_gamma (
        .I_clk      (user_clk),
        .I_rst_n    (user_rst_n),
        .I_tlast    (cut_tlast),
        .I_tuser    (cut_tuser),
        .I_tdata    (cut_tdata),
        .I_tvalid   (cut_tvalid),
        .I_tready   (cut_tready),
        .O_tlast    (gamma_tlast),
        .O_tuser    (gamma_tuser),
        .O_tdata    (gamma_tdata),
        .O_tvalid   (gamma_tvalid),
        .O_tready   (gamma_tready)
    );

    // ================================================================
    // 4d. Contrast Adjustment (level=140, 128=no change)
    // ================================================================
    ui_Contrast_adj #(
        .contrast_level (128)
    ) u_contrast (
        .I_clk      (user_clk),
        .I_rst_n    (user_rst_n),
        .I_tlast    (gamma_tlast),
        .I_tuser    (gamma_tuser),
        .I_tdata    (gamma_tdata),
        .I_tvalid   (gamma_tvalid && cfg_probe_stage!=6),
        .I_tready   (contrast_input_ready48),
        .O_tlast    (contrast_tlast),
        .O_tuser    (contrast_tuser),
        .O_tdata    (contrast_tdata),
        .O_tvalid   (contrast_tvalid),
        .O_tready   (contrast_tready)
    );

    // ================================================================
    // 4e. Brightness Adjustment (+5 offset)
    // ================================================================
    ui_Brightness_adj #(
        .BRIGHTNESS_ADD   (0),
        .BRIGHTNESS_MINUS (0)
    ) u_brightness (
        .I_clk      (user_clk),
        .I_rst_n    (user_rst_n),
        .I_tlast    (contrast_tlast),
        .I_tuser    (contrast_tuser),
        .I_tdata    (contrast_tdata),
        .I_tvalid   (contrast_tvalid),
        .I_tready   (contrast_tready),
        .O_tlast    (bright_tlast),
        .O_tuser    (bright_tuser),
        .O_tdata    (bright_tdata),
        .O_tvalid   (bright_tvalid),
        .O_tready   (bright_tready)
    );

    // ================================================================
    // 4f. Saturation Adjustment (level=130, 128=no change)
    // ================================================================
    ui_Saturation_adj #(
        .ADJUST_VAL (0)
    ) u_saturation (
        .I_clk      (user_clk),
        .I_rst_n    (user_rst_n),
        .I_tlast    (bright_tlast),
        .I_tuser    (bright_tuser),
        .I_tdata    (bright_tdata),
        .I_tvalid   (bright_tvalid),
        .I_tready   (bright_tready),
        .O_tlast    (sat_tlast),
        .O_tuser    (sat_tuser),
        .O_tdata    (sat_tdata),
        .O_tvalid   (sat_tvalid),
        .O_tready   (sat_tready)
    );

    // 96b �� 128b: restore per-pixel 8-bit padding for downstream pack4
    // CHR5 candidate42: source RGB noise treatment, bounded streaming storage.
    wire [95:0] cnr_data;
    wire cnr_valid,cnr_last,cnr_user;
    ui_chroma_rank42 #(.LINE_ADDR_WIDTH(CNR_LINE_ADDR_WIDTH)) u_chroma_rank42(
        .clk(user_clk),.rst_n(user_rst_n),.width(cfg_img_width),.height(cfg_img_height),
        .data(sat_tdata),.valid(sat_tvalid && cfg_probe_stage!=7),.last(sat_tlast),.user(sat_tuser),.ready(cnr_input_ready48),
        .out_data(cnr_data),.out_valid(cnr_valid),.out_last(cnr_last),.out_user(cnr_user),
        .out_ready(probe_ready48[0]),.status(cnr_status),.input_beats(cnr_input_beats),
        .output_beats(cnr_output_beats),.input_frames(cnr_input_frames),
        .output_frames(cnr_output_frames),.horizontal_fallback(cnr_h_fallback),
        .vertical_fallback(cnr_v_fallback),.pattern_shadow(cfg_cnr_pattern),.active_mode(cnr_active_pattern));
    wire [95:0] ccm_debug8_96,awb_debug8_96;
    genvar debug_pixel51;
    generate for(debug_pixel51=0;debug_pixel51<4;debug_pixel51=debug_pixel51+1) begin: linear_debug_projection51
        assign demo_debug8_96[24*debug_pixel51+:24]={demo_tdata[30*debug_pixel51+22+:8],demo_tdata[30*debug_pixel51+12+:8],demo_tdata[30*debug_pixel51+2+:8]};
        assign ccm_debug8_96[24*debug_pixel51+:24]={ccm_tdata[30*debug_pixel51+22+:8],ccm_tdata[30*debug_pixel51+12+:8],ccm_tdata[30*debug_pixel51+2+:8]};
        assign awb_debug8_96[24*debug_pixel51+:24]={awb_tdata[30*debug_pixel51+22+:8],awb_tdata[30*debug_pixel51+12+:8],awb_tdata[30*debug_pixel51+2+:8]};
    end endgenerate
    wire [95:0] probe_data48;
    wire probe_valid48,probe_last48,probe_user48;
    ui_isp_probe48 u_isp_probe48(
        .clk(user_clk),.rst_n(user_rst_n),.stage(cfg_probe_stage),
        .raw_crop(crop_tdata),.raw_blc(blc_tdata),
        .rgb_processed(cnr_data),.rgb_demo(demo_debug8_96),.rgb_ccm(ccm_debug8_96),
        .rgb_awb(awb_debug8_96),.rgb_gamma(gamma_tdata),.rgb_pre_cnr(sat_tdata),
        .valid({sat_tvalid,gamma_tvalid,awb_tvalid,ccm_tvalid,demo_tvalid,blc_tvalid,crop_tvalid,cnr_valid}),
        .last({sat_tlast,gamma_tlast,awb_tlast,ccm_tlast,demo_tlast,blc_tlast,crop_tlast,cnr_last}),
        .user({sat_tuser,gamma_tuser,awb_tuser,ccm_tuser,demo_tuser,blc_tuser,crop_tuser,cnr_user}),
        .ready(probe_ready48),.out_data(probe_data48),.out_valid(probe_valid48),
        .out_last(probe_last48),.out_user(probe_user48),.out_ready(~fifo_full));
    rgb_area3_camera_branch u_model_area3(.view_select(view_select),.view_fire(view_fire),.view_sof(view_sof),.view_eol(view_eol),.view_eof(view_eof),
 .view_rgb(view_rgb),.view_count(view_count),.view_id(view_id),.view_tick(view_tick),

        .clk(user_clk),.rst_n(user_rst_n),.enable(model_enable),
        .supported(cfg_img_width==1920 && cfg_img_height==1080 && cfg_probe_stage==0),
        .tap_fire(probe_valid48 && !fifo_full),.tap_sof(probe_user48),.tap_eol(probe_last48),.tap_isp(probe_data48),
        .m_valid(model_valid),.m_ready(model_ready),.m_data(model_data),.m_sof(model_sof),.m_eol(model_eol),.m_eof(model_eof),
        .m_id(model_id),.m_tick(model_tick),.source_frames(model_source_frames),.complete_frames(model_complete_frames),
        .abort_frames(model_abort_frames),.overflows(model_overflows),.error(model_error));
    ui_data96_128 u_data96_128 (
        .I_tdata    (probe_data48),
        .O_tdata    (sat_tdata_128)
    );

    // ================================================================
    // 4b. Rate-decoupling FIFO (AWB �� pack4)
    //     Demosaic outputs 480 beats/line at 1 beat/clk.
    //     pack4 processes 4 pixels/clk (same as demosaic output rate).
    //     FIFO absorbs bursts when downstream stalls (DMA descriptor).
    // ================================================================
    wire fifo_empty;
    wire [129:0] fifo_rd_data;

    // sat_tready is driven by the CHR5 input handshake.
    assign fifo_tdata   = fifo_rd_data[127:0];
    assign fifo_tlast   = fifo_rd_data[128];
    assign fifo_tuser   = fifo_rd_data[129];
    assign fifo_tvalid  = ~fifo_empty;

    sync_fifo_130 #(
        .ADDR_WIDTH (10)       // 1024 entries, enough for 960-beat 4K line burst
    ) u_demo_fifo (
        .clk      (user_clk),
        .rst_n    (user_rst_n),
        .wr_data  ({probe_user48, probe_last48, sat_tdata_128}),
        .wr_en    (probe_valid48 & ~fifo_full),
        .full     (fifo_full),
        .rd_data  (fifo_rd_data),
        .rd_en    (fifo_tready & ~fifo_empty),
        .empty    (fifo_empty)
    );

    // ================================================================
    // 5. pack4_rgb24_to_128 �� 4-pixel parallel RGB24 packer (128b��128b)
    //    Strips per-pixel padding and tight-packs RGB24 for 128b DMA.
    //    4 inputs (48B) �� 3 outputs (48B), LCM(12,16)=48.
    // ================================================================
    pack4_rgb24_to_128 u_pack4 (
        .cfg_img_height (cfg_img_height),
        .clk            (user_clk),
        .rst_n          (user_rst_n),
        .enable         (enable),
        // Input from FIFO (128b AXI-Stream)
        .s_tdata        (fifo_tdata),
        .s_tvalid       (fifo_tvalid),
        .s_tready       (fifo_tready),
        .s_tlast        (fifo_tlast),
        .s_tuser        (fifo_tuser),
        // 512-bit AXI-Stream output
        .m_tdata        (m_tdata),
        .m_tvalid       (m_tvalid),
        .m_tready       (m_tready),
        .m_tlast        (m_tlast),
        .m_frame_last   (m_frame_last),
        .sof            (sof),
        .eof            (eof),
        .frame_count_out(raw_frame_count)
    );

    // Inject diagnostic sticky flags into frame_count_out[31:24]
    // F[31]: mipi_tuser_ever  F[30]: mipi_tlast_ever
    // F[29]: crop_tuser_ever  F[28]: crop_tlast_ever
    // F[27]: demo_tuser_ever  F[26]: demo_tlast_ever
    // F[25]: awb_tuser_ever   F[24]: awb_tlast_ever
    // F[23:0]: actual frame count
    assign frame_count_out = {
        mipi_tuser_ever, mipi_tlast_ever,
        crop_tuser_ever, crop_tlast_ever,
        demo_tuser_ever, demo_tlast_ever,
        awb_tuser_ever,  awb_tlast_ever,
        raw_frame_count[23:0]
    };

endmodule

// Physical linear RGB colour matrix, signed Q10, four pixels per accepted beat.
// Four registered arithmetic stages freeze together under output backpressure.
module ui_ccm32 #(parameter LOW_LINEAR_GATE=0) (
    input wire [2:0] cfg_gate_shadow,
    output reg [2:0] active_gate,hist_gate,
    output reg [31:0] hist_sequence,
    output wire [159:0] hist_previous,
    input I_clk, I_rst_n, I_tlast, I_tuser, I_tvalid,
    input [119:0] I_tdata,
    output I_tready,
    output reg O_tlast, O_tuser, O_tvalid,
    output reg [119:0] O_tdata,
    input O_tready
);
    localparam signed [15:0] C00 =  16'sd5117;
    localparam signed [15:0] C01 = - 16'sd824;
    localparam signed [15:0] C02 =  16'sd71;
    localparam signed [15:0] C10 = - 16'sd1555;
    localparam signed [15:0] C11 =  16'sd2747;
    localparam signed [15:0] C12 = - 16'sd957;
    localparam signed [15:0] C20 =  16'sd205;
    localparam signed [15:0] C21 = - 16'sd816;
    localparam signed [15:0] C22 =  16'sd4305;
    // Precision51 defaults to0. Runtime0 bypasses the inherited
    // linear floor; nonzero gates and histogram bins retain legacy RGB8 brightness
    // units by observation-only [9:2] projection. Matrix samples remain RGB10.
    // Frame commit is at the accepted CCM input SOF, in the same user_clk.
    wire ce = !O_tvalid || O_tready;
    assign I_tready = ce;
    localparam [2:0] DEFAULT_GATE=LOW_LINEAR_GATE?3'd1:3'd0;
    reg [2:0] requested_gate;
    always @* begin
        case(cfg_gate_shadow)
          3'd0,3'd1,3'd2,3'd3,3'd4,3'd5,3'd6,3'd7:requested_gate=cfg_gate_shadow;
          default:requested_gate=DEFAULT_GATE;
        endcase
    end
    wire [2:0] use_gate=(I_tvalid&&I_tuser)?requested_gate:active_gate;
    wire [119:0] linear_pixels;
    wire [3:0] bin_flags[0:4];
    reg [31:0] histogram[0:4],previous[0:4];
    reg statistics_started;
    assign hist_previous={previous[4],previous[3],previous[2],previous[1],previous[0]};
    function [2:0] pop4;
      input [3:0] q;
      begin pop4={2'd0,q[0]}+{2'd0,q[1]}+{2'd0,q[2]}+{2'd0,q[3]};end
    endfunction
    genvar gate_p;
    generate for(gate_p=0;gate_p<4;gate_p=gate_p+1) begin: joint_linear_floor
        wire [7:0] r=I_tdata[30*gate_p+22+:8];
        wire [7:0] g=I_tdata[30*gate_p+12+:8];
        wire [7:0] b=I_tdata[30*gate_p+2+:8];
        wire dark=(use_gate!=0)&&(r<=use_gate)&&(g<=use_gate)&&(b<=use_gate);
        assign linear_pixels[30*gate_p+:30]=dark?30'd0:I_tdata[30*gate_p+:30];
        wire [7:0] max_rg=(r>g)?r:g;
        wire [7:0] maximum=(max_rg>b)?max_rg:b;
        assign bin_flags[0][gate_p]=(maximum==0);
        assign bin_flags[1][gate_p]=(maximum==1);
        assign bin_flags[2][gate_p]=(maximum==2);
        assign bin_flags[3][gate_p]=(maximum==3);
        assign bin_flags[4][gate_p]=(maximum>=4);
    end endgenerate
    // Telemetry only: register bin counts before the 32-bit accumulators.
    // This removes the demosaic -> max/bin/popcount -> histogram critical path.
    // The image matrix and its four-stage handshake are unchanged.
    reg stat_valid,stat_sof;
    reg [2:0] stat_gate,statistics_gate;
    reg [2:0] bin_count[0:4];
    integer stat_bin;
    always @(posedge I_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin
            active_gate<=DEFAULT_GATE;hist_gate<=DEFAULT_GATE;hist_sequence<=0;statistics_started<=0;
            stat_valid<=0;stat_sof<=0;stat_gate<=DEFAULT_GATE;statistics_gate<=DEFAULT_GATE;
            for(stat_bin=0;stat_bin<5;stat_bin=stat_bin+1)begin histogram[stat_bin]<=0;previous[stat_bin]<=0;bin_count[stat_bin]<=0;end
        end else begin
            stat_valid<=I_tvalid&&ce;stat_sof<=I_tuser;stat_gate<=use_gate;
            if(I_tvalid&&ce)begin
                if(I_tuser)active_gate<=requested_gate;
                for(stat_bin=0;stat_bin<5;stat_bin=stat_bin+1)bin_count[stat_bin]<=pop4(bin_flags[stat_bin]);
            end
            if(stat_valid)begin
                if(stat_sof)begin
                    statistics_started<=1;statistics_gate<=stat_gate;
                    if(statistics_started)begin
                        hist_sequence<=hist_sequence+1'b1;hist_gate<=statistics_gate;
                        for(stat_bin=0;stat_bin<5;stat_bin=stat_bin+1)previous[stat_bin]<=histogram[stat_bin];
                    end
                    for(stat_bin=0;stat_bin<5;stat_bin=stat_bin+1)histogram[stat_bin]<=bin_count[stat_bin];
                end else if(statistics_started)
                    for(stat_bin=0;stat_bin<5;stat_bin=stat_bin+1)histogram[stat_bin]<=histogram[stat_bin]+bin_count[stat_bin];
            end
        end
    end
    reg [2:0] vp, up, lp;
    reg signed [26:0] product [0:35];
    reg signed [27:0] pair_sum [0:11];
    reg signed [26:0] third_product [0:11];
    reg signed [28:0] total [0:11];
    function [9:0] clamp;
        input signed [28:0] q;
        reg signed [29:0] rounded;
        begin
            rounded = {q[28],q} + 30'sd512;
            if (rounded < 0) clamp = 0;
            else if (rounded >= 30'sd1047552) clamp = 1023;
            else clamp = rounded[19:10];
        end
    endfunction
    integer p, k;
    always @(posedge I_clk or negedge I_rst_n) begin
        if (!I_rst_n) begin
            vp<=0; up<=0; lp<=0; O_tvalid<=0; O_tuser<=0; O_tlast<=0; O_tdata<=0;
            for(k=0;k<36;k=k+1) product[k]<=0;
            for(k=0;k<12;k=k+1) begin pair_sum[k]<=0;third_product[k]<=0;total[k]<=0;end
        end else if (ce) begin
            vp<={vp[1:0],I_tvalid}; up<={up[1:0],I_tvalid&&I_tuser}; lp<={lp[1:0],I_tvalid&&I_tlast};
            O_tvalid<=vp[2]; O_tuser<=up[2]; O_tlast<=lp[2];
            for(p=0;p<4;p=p+1) begin
                product[9*p+0] <= $signed({1'b0,linear_pixels[30*p+20+:10]}) * C00;
                product[9*p+1] <= $signed({1'b0,linear_pixels[30*p+10+:10]}) * C01;
                product[9*p+2] <= $signed({1'b0,linear_pixels[30*p+ 0+:10]}) * C02;
                product[9*p+3] <= $signed({1'b0,linear_pixels[30*p+20+:10]}) * C10;
                product[9*p+4] <= $signed({1'b0,linear_pixels[30*p+10+:10]}) * C11;
                product[9*p+5] <= $signed({1'b0,linear_pixels[30*p+ 0+:10]}) * C12;
                product[9*p+6] <= $signed({1'b0,linear_pixels[30*p+20+:10]}) * C20;
                product[9*p+7] <= $signed({1'b0,linear_pixels[30*p+10+:10]}) * C21;
                product[9*p+8] <= $signed({1'b0,linear_pixels[30*p+ 0+:10]}) * C22;
                O_tdata[30*p+20+:10]<=clamp(total[3*p+0]);
                O_tdata[30*p+10+:10]<=clamp(total[3*p+1]);
                O_tdata[30*p+ 0+:10]<=clamp(total[3*p+2]);
            end
            for(k=0;k<12;k=k+1) begin
                pair_sum[k] <= {product[3*k][26],product[3*k]} + {product[3*k+1][26],product[3*k+1]};
                third_product[k] <= product[3*k+2];
                total[k] <= {pair_sum[k][27],pair_sum[k]} + {{2{third_product[k][26]}},third_product[k]};
            end
        end
    end
endmodule
