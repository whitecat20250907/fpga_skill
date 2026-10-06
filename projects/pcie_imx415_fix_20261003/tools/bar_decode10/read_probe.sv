`timescale 1ns/1ps
`include "param_tpg.vh"
`include "param_imx415.vh"

// Only the exact production read fragments are under test. These deterministic
// input fixtures test register/address meaning; they are not camera/PCIe models.
module read_probe # (parameter OLD_DECODE=0) (
    input wire user_clk,user_rst_n,
    input wire [31:0] m_axil_araddr,
    input wire m_axil_arvalid,
    output wire [31:0] m_axil_rdata,
    output wire selected
);
wire user_link_up=1'b1,reg_enable=1'b1,reg_soft_reset=1'b0;
wire [15:0] active_width=16'd1920,active_height=16'd1080;
wire [31:0] cam_frame_count=32'h10203040;
wire [31:0] padded_frame_bytes=32'd6220864,fifo_drop_count=32'h87654321;
wire cam_i2c_done_s=1'b1,cam_sof_seen=1'b1,s0_axis_c2h_tready=1'b1;
wire vid_tvalid=1'b1,cam_enable=1'b1,mipi_clk_present=1'b1;
wire vid_frame_last=1'b0,dbg_tready_ever=1'b1;
wire [31:0] frame_total_beats=32'h01020304,dbg_dma_beat_cnt=32'h55667788;
wire [223:0] cam_ui_snapshot=224'h2d6;
wire [5:0] cam_best_len_sync=6'd12;
wire [1:0] cam_raw_valid_sync=2'b10;
wire cam_delay_done_s=1'b1;
wire [12:0] cam_img_width=13'd1920,cam_img_height=13'd1080;
wire [1:0] reg_cam_mode=2'd0;
wire [31:0] drop_detect_count=32'd3,gate_drop_count=32'd2,gate_pass_count=32'd9;
wire [7:0] reg_ae_gain=8'd100;
wire reg_image_loopback=1'b0;
wire [31:0] csi_snapshot_status=32'h22;
wire [223:0] csi_snapshot={32'h01000006,32'h01000005,32'h01000004,
    32'h01000003,32'h01000002,32'h01000001,32'h01000000};
wire [31:0] csi_clock_delta=32'h00aabbcc;
wire [31:0] cam_clock_measured_edges=32'd270000,cam_clock_window_index=32'd17;
wire [1:0] reg_bayer_mode=2'd3,cam_active_bayer_mode=2'd2;
wire [1:0] cam_cfg_ready_sync=2'b10,cam_xclr_sync=2'b10;
wire cam_clock_frequency_ok=1'b1,cam_clock_lock_s=1'b1;
wire [6:0] reg_phy_control=7'h55;
wire [223:0] phy_diag0={32'h3000abcd,32'hb8d5d5af,32'h3412cdab,
    32'h20100003,32'h20100002,32'h20100001,32'h20100000};
wire [223:0] phy_diag1={32'h30000abc,32'h40100005,32'h40100004,
    32'h40100003,32'h40100002,32'h40100001,32'h40100000};
wire [31:0] phy_diag0_status=32'haa,phy_diag1_status=32'hcc;
// A distinct deterministic fallback proves that a zero/default register does
// not falsely pass when the production mux accidentally chooses application.
wire [31:0] app_axil_rdata=(m_axil_araddr[15:0]==16'h0128)
    ? 32'h13579bdf : (32'ha5a50000 | {16'd0,m_axil_araddr[15:0]});
generate if (OLD_DECODE) begin : old_source
`include "production_read_old.vh"
assign selected=vid_rd_sel_d1;
end else begin : corrected_source
`include "production_read_new.vh"
assign selected=vid_rd_sel_d1;
end endgenerate
endmodule
