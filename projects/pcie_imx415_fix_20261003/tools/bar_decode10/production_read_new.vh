    reg        vid_rd_sel_d1;

    always @(posedge user_clk or negedge user_rst_n) begin
        if (!user_rst_n)
            vid_rd_sel_d1 <= 1'b0;
        else
            vid_rd_sel_d1 <= m_axil_arvalid &&
                             (m_axil_araddr[19:16] == 4'h0) &&
                             (m_axil_araddr[15:0] >= 16'h0040) &&
                             (m_axil_araddr[15:0] <= 16'h011C);
    end

    // Active frame count: always camera
    wire [31:0] active_frame_count = cam_frame_count;

    reg [31:0] vid_reg_rdata_d1;

    always @(posedge user_clk) begin
        case (m_axil_araddr[15:0])
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
                                                       s0_axis_c2h_tready,  // [8]  DMA tready
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

    assign m_axil_rdata = vid_rd_sel_d1 ? vid_reg_rdata_d1 : app_axil_rdata;
