`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 2025/06/17 09:00:03
// Design Name: 
// Module Name: mipi_csi_rx
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////


module mipi_csi_rx#(
    parameter MIPI_LAN  = 4,
    parameter DEVICE    = "EG"
    
)(
input wire                I_debug_button  ,
    // Seven-bit command is asynchronous to BYTE clock but belongs to the
    // m_axis_video_aclk source domain. Never synchronize these bits separately.
    input wire [6:0] I_phy_control_shadow,
    output wire [191:0] O_phy_diag0, O_phy_diag1,   

    input wire                I_ref_clock     ,   
    input wire                I_clk_hs_rx_p   , 
    input wire                I_reset_n       ,    
    input wire [MIPI_LAN-1:0] I_hs_data_p     ,
    input wire                I_enable        ,
    output wire               O_hs_div_clk    ,

    input  wire               m_axis_video_aclk,
    input  wire               m_axis_video_aresetn,
	input  wire               m_axis_video_tready,
    output wire               m_axis_video_tuser,
    output wire               m_axis_video_tlast,
    output wire               m_axis_video_tvalid,
    output wire [39:0]        m_axis_video_tdata,
    output wire               O_auto_delay_done,

    // 调试总线（hs_div_clk 域，需要在顶层 CDC 采样）
    // [3:0] = 各 lane 字节对齐有效
    // [4]   = word 对齐有效
    // [5]   = in_frame（包处理器检测到帧起始）
    // [6]   = payload_valid（包数据输出有效）
    // [7]   = unpack_valid（10-bit 解包有效）
    output wire [7:0]         O_dbg_mipi,
    // delay 调试总线（hs_div_clk 域，需要在顶层 CDC 采样）
    // [5:0] = 当前生效 delay tap
    // [6]   = 手动扫 tap 模式已锁存
    // [7]   = 本拍 delay code load pulse
    output wire [7:0]         O_dbg_delay,
    output wire [5:0]         O_dbg_best_len,
    // Diagnostic counters are in O_hs_div_clk domain: snapshot/handshake at CDC.
    output wire [31:0] O_csi_raw_packets,
    output wire [31:0] O_csi_crc_errors,
    output wire [31:0] O_csi_ecc_errors,
    output wire [31:0] O_csi_wc_errors,
    output wire [31:0] O_csi_timeout_errors,
    output wire [31:0] O_csi_fifo_overflows,
    output wire O_csi_error_pulse
    );

    // synthesis translate_off
    initial if(MIPI_LAN!=4) $fatal(1,"PHY_DIAG08 requires four lanes for fixed diagnostic layout");
    // synthesis translate_on
    wire [MIPI_LAN-1:0]     w_rx_byte_data_align_vaild;
    wire [8*MIPI_LAN-1:0]   w_rx_byte_data_align;
    wire [8*MIPI_LAN-1:0]   w_word_align_data;
    wire                    w_word_align_data_vaild;
    wire [31:0]             w_word_gear_data;
    wire                    w_word_gear_data_vaild;

    wire [31:0]             w_payload_out;
    wire                    w_payload_valid;
    wire                    w_hs_div_clk ;
    wire                    w_reset_out;
    wire [39:0]             w_data_out_unpack;    
    wire                    w_dout_unpack_valid;
    wire                    w_delay_value;
    wire                    w_sync_wait;
    wire                    w_packet_done;
    wire                    w_vsync_out;
    wire                    w_in_frame;
    wire                    w_in_line;

    wire [2:0] w_payload_bytes;
    wire w_payload_last, w_unpack_last, w_packet_error;
    wire w_unpack_error, w_fifo_error;
    reg [1:0] delay_done_sync;
    wire [31:0] phy_raw_bytes;
    wire phy_sampler_reset_n_x4;
    (* async_reg="true" *) reg [2:0] phy_sampler_reset_sync;
    // One status bit crosses from the HSx4 sampler-reset domain. Do not sample
    // the raw x4 signal in the byte-domain diagnostic held bus.
    always @(posedge w_hs_div_clk or negedge w_reset_out)
        if(!w_reset_out) phy_sampler_reset_sync<=3'b000;
        else phy_sampler_reset_sync<={phy_sampler_reset_sync[1:0],phy_sampler_reset_n_x4};
    wire [223:0] phy_cmd_snapshot;
    wire [6:0] phy_control_byte=phy_cmd_snapshot[6:0];
    // Existing module's request timer is in dst_clk. PERIOD125000 means
    // ~1.122ms at 111.375MHz BYTE clock, not 1ms in the 125MHz source domain.
    // Source held bus includes user-domain source_cycles in snapshot[223:192].
    csi_stats_snapshot #(.PERIOD(125000)) u_phy_control_snapshot (
        .src_clk(m_axis_video_aclk), .dst_clk(w_hs_div_clk), .rst_n(I_reset_n),
        .src_stats({185'd0,I_phy_control_shadow}), .snapshot(phy_cmd_snapshot),
        .status(), .clock_delta());
    reg [31:0] phy_lane0_valid_cycles,phy_lane1_valid_cycles;
    reg [31:0] phy_lane2_valid_cycles,phy_lane3_valid_cycles;
    reg [31:0] phy_payload_beats,phy_word_valid_cycles,phy_packet_errors;
    reg [31:0] phy_current_payload_lines,phy_last_frame_payload_lines,phy_frame_starts;
    reg [7:0] phy_sticky_valid;
    // Sticky bit7 error pulse, bit6 FS, bit5 payload-valid, bit4 aligned word,
    // bits3:0 aligned lane-valid. Counts remain active before auto calibration
    // and capture_armed; packet parser I_enable still controls protocol itself.
    wire [7:0] phy_valid_now={w_packet_error,w_vsync_out,w_payload_valid,
        w_word_align_data_vaild,w_rx_byte_data_align_vaild};
    always @(posedge w_hs_div_clk or negedge w_reset_out) begin
        if(!w_reset_out) begin
            phy_lane0_valid_cycles<=0;phy_lane1_valid_cycles<=0;
            phy_lane2_valid_cycles<=0;phy_lane3_valid_cycles<=0;
            phy_payload_beats<=0;phy_word_valid_cycles<=0;phy_packet_errors<=0;
            phy_current_payload_lines<=0;phy_last_frame_payload_lines<=0;
            phy_frame_starts<=0;phy_sticky_valid<=0;
        end else begin
            if(w_rx_byte_data_align_vaild[0]) phy_lane0_valid_cycles<=phy_lane0_valid_cycles+1'b1;
            if(w_rx_byte_data_align_vaild[1]) phy_lane1_valid_cycles<=phy_lane1_valid_cycles+1'b1;
            if(w_rx_byte_data_align_vaild[2]) phy_lane2_valid_cycles<=phy_lane2_valid_cycles+1'b1;
            if(w_rx_byte_data_align_vaild[3]) phy_lane3_valid_cycles<=phy_lane3_valid_cycles+1'b1;
            if(w_payload_valid) phy_payload_beats<=phy_payload_beats+1'b1;
            if(w_word_align_data_vaild) phy_word_valid_cycles<=phy_word_valid_cycles+1'b1;
            if(w_packet_error) phy_packet_errors<=phy_packet_errors+1'b1;
            phy_sticky_valid<=phy_sticky_valid | phy_valid_now;
            // Payload-last means a parsed RAW10 payload boundary, not CRC-good
            // line acceptance. A later CRC error does not erase this observation.
            // If FS and last coincide, last belongs to the new frame here.
            if(w_vsync_out) begin
                phy_frame_starts<=phy_frame_starts+1'b1;
                phy_last_frame_payload_lines<=phy_current_payload_lines;
                phy_current_payload_lines<=w_payload_valid&&w_payload_last ? 32'd1 : 32'd0;
            end else if(w_payload_valid&&w_payload_last)
                phy_current_payload_lines<=phy_current_payload_lines+1'b1;
        end
    end
    // Low-first BAR-friendly layout. lane0 valid-cycles is bits31:0.
    assign O_phy_diag0={{O_dbg_mipi,O_dbg_delay,phy_sampler_reset_sync[2],phy_control_byte,phy_sticky_valid},
        phy_raw_bytes,phy_lane3_valid_cycles,phy_lane2_valid_cycles,
        phy_lane1_valid_cycles,phy_lane0_valid_cycles};
    assign O_phy_diag1={phy_payload_beats,phy_word_valid_cycles,phy_packet_errors,
        phy_current_payload_lines,phy_last_frame_payload_lines,phy_frame_starts};
    always @(posedge w_hs_div_clk or negedge w_reset_out)
        if(!w_reset_out) delay_done_sync<=0;
        else delay_done_sync<={delay_done_sync[0],O_auto_delay_done};
    wire parse_ready=I_enable && delay_done_sync[1];
    reg capture_armed, pixel_frame_start;
    // Calibration must not disable parser feedback used by PHY byte alignment.
    // Only image output is gated; after calibration wait for a NEW complete FS.
    always @(posedge w_hs_div_clk or negedge w_reset_out)
        if(!w_reset_out) begin capture_armed<=0; pixel_frame_start<=0; end
        else begin
            pixel_frame_start<=0;
            if(!parse_ready) capture_armed<=0;
            else if(w_vsync_out) begin capture_armed<=1; pixel_frame_start<=1; end
        end
    wire pixel_enable=parse_ready && capture_armed;
    assign O_csi_error_pulse=pixel_enable && (w_packet_error || w_unpack_error || w_fifo_error);
   assign O_hs_div_clk = w_hs_div_clk;

    assign O_dbg_mipi = {w_dout_unpack_valid,
                         w_payload_valid,
                         w_in_frame,
                         w_word_align_data_vaild,
                         w_rx_byte_data_align_vaild};
 
csi_rx_phy #(
    .MIPI_LAN   (MIPI_LAN),
    .DEVICE     (DEVICE)
)u_csi_rx_phy(

.I_debug_button(I_debug_button),
    .I_override_enable          (phy_control_byte[6]),
    .I_override_tap             (phy_control_byte[5:0]),
    .O_dbg_raw_bytes            (phy_raw_bytes),
    .O_sampler_reset_n          (phy_sampler_reset_n_x4),

    .I_ref_clock                (I_ref_clock),
    .I_clk_hs_rx_p              (I_clk_hs_rx_p              ),
    .I_reset_n                  (I_reset_n                  ),
    .I_hs_data_p                (I_hs_data_p                ),
    .I_enable                   (I_enable                   ),
    .I_wait_for_sync            (w_sync_wait                ),
    .I_packet_done              (w_packet_done              ),
    .O_hs_div_clk               (w_hs_div_clk               ),
    .O_reset_out                (w_reset_out                ),
    .O_rx_byte_data_align_vaild (w_rx_byte_data_align_vaild ),
    .O_rx_byte_data_align       (w_rx_byte_data_align       ),
    .O_delay_value              (w_delay_value),
    .O_auto_delay_done          (O_auto_delay_done),
    .O_dbg_delay                (O_dbg_delay),
    .O_dbg_best_len             (O_dbg_best_len)
);

csi_rx_word_align #(
    .MIPI_LAN(MIPI_LAN)
)u_csi_rx_word_align(
    .I_word_clock      (w_hs_div_clk        ),
    .I_reset_n         (w_reset_out         ),
    .I_enable          (I_enable            ),
    .I_packet_done     (w_packet_done       ),
    .I_wait_for_sync   (w_sync_wait         ),
    .O_packet_done_out (),
    .I_word_in         (w_rx_byte_data_align),
    .I_valid_in        (w_rx_byte_data_align_vaild),
    .O_word_out        (w_word_align_data   ),
    .O_valid_out       (w_word_align_data_vaild)
);

csi_rx_word_gear_box #(
    .MIPI_LAN(MIPI_LAN)
)u_csi_rx_word_gear_box(
    .I_word_clock      (w_hs_div_clk           ),
    .I_reset_n         (w_reset_out            ),
    .I_enable          (I_enable               ),
    .I_lane_data       (w_word_align_data      ),
    .I_lane_data_valid (w_word_align_data_vaild),
    .O_word_out        (w_word_gear_data       ),
    .O_valid_out       (w_word_gear_data_vaild )
);


csi_rx_packet_handler #(
    .MIPI_LAN(MIPI_LAN)
)u_csi_rx_packet_handler(
    .I_clock         (w_hs_div_clk           ),
    .I_reset_n       (w_reset_out            ),
    .I_enable        (I_enable               ),
    .I_count_enable  (pixel_enable),
    .I_data          (w_word_gear_data       ),
    .I_data_valid    (w_word_gear_data_vaild ),
    .O_sync_wait     (w_sync_wait            ),
    .O_packet_done   (w_packet_done          ),
    .O_payload_out   (w_payload_out          ),
    .O_payload_valid (w_payload_valid        ),
    .O_vsync_out     (w_vsync_out            ),
    .O_in_frame      (w_in_frame             ),
    .O_in_line       (w_in_line              ),
    .O_payload_bytes (w_payload_bytes),
    .O_payload_last  (w_payload_last),
    .O_packet_error  (w_packet_error),
    .O_raw_packets   (O_csi_raw_packets),
    .O_crc_errors    (O_csi_crc_errors),
    .O_ecc_errors    (O_csi_ecc_errors),
    .O_wc_errors     (O_csi_wc_errors),
    .O_timeout_errors(O_csi_timeout_errors)
);


csi_rx_10bit_unpack u_csi_rx_10bit_unpack(
    .I_clock        (w_hs_div_clk       ),
    .I_reset_n      (w_reset_out        ),
    .I_enable       (pixel_enable       ),
    .I_line_in      (w_in_line          ),
    .I_data_in      (w_payload_out      ),
    .I_din_valid    (w_payload_valid    ),
    .I_din_bytes    (w_payload_bytes),
    .I_din_last     (w_payload_last),
    .O_data_out     (w_data_out_unpack  ),
    .O_dout_valid   (w_dout_unpack_valid),
    .O_dout_last    (w_unpack_last),
    .O_unpack_error (w_unpack_error)
);

csi_rx_vid2stream u_csi_rx_vid2stream(
    .I_data_clk           (w_hs_div_clk         ),
    .I_reset_n            (w_reset_out          ),
    .I_enable             (pixel_enable         ),
    .I_frame_start        (pixel_frame_start    ),
    .I_dout_unpack_last   (w_unpack_last        ),
    .O_fifo_overflows     (O_csi_fifo_overflows  ),
    .O_overflow_pulse     (w_fifo_error          ),
    .I_packet_done        (w_packet_done        ),
    .I_packet_line        (w_in_line            ),
    .I_packet_frame       (w_in_frame           ),
    .I_data_unpack        (w_data_out_unpack    ),
    .I_dout_unpack_valid  (w_dout_unpack_valid  ),
    .m_axis_video_aclk    (m_axis_video_aclk    ),
    .m_axis_video_aresetn (m_axis_video_aresetn ),
    .m_axis_video_tready  (m_axis_video_tready  ),
    .m_axis_video_tuser   (m_axis_video_tuser   ),
    .m_axis_video_tlast   (m_axis_video_tlast   ),
    .m_axis_video_tvalid  (m_axis_video_tvalid  ),
    .m_axis_video_tdata   (m_axis_video_tdata   )
);

endmodule
