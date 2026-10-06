`timescale 1ns/1ps
// F5 bring-up monitor. Replaces the first 64 bytes of each YUYV frame with
// a little-endian header. This makes physical FPGA counters observable at RK
// without any new pins or changing the working 1920x1080 CSI-2 transport.
// It is a diagnostic wire format, not yet the compressed-frame format.
module camera_meta_overlay (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        s_valid,
    input  wire [63:0] s_data,
    input  wire        s_sof,
    input  wire        s_last,
    input  wire [3:0]  lane_error,
    input  wire        bridge_overflow,
    output wire        m_valid,
    output wire [63:0] m_data,
    output wire        m_sof,
    output wire        m_last
);
    reg [63:0] ticks;
    reg [63:0] sof_tick;
    reg [63:0] last_line_tick;
    reg [63:0] snap_sof_tick;
    reg [63:0] snap_period;
    reg [63:0] snap_frame_span;
    reg [31:0] frame_id;
    reg [31:0] snap_frame_id;
    reg [31:0] rows;
    reg [31:0] words;
    reg [31:0] snap_rows;
    reg [31:0] snap_words;
    reg [31:0] snap_flags;
    reg [3:0] lane_error_sticky;
    reg [9:0] col;
    reg first_frame;
    reg [63:0] header_word;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ticks <= 0;
            sof_tick <= 0;
            last_line_tick <= 0;
            snap_sof_tick <= 0;
            snap_period <= 0;
            snap_frame_span <= 0;
            frame_id <= 0;
            snap_frame_id <= 0;
            rows <= 0;
            words <= 0;
            snap_rows <= 0;
            snap_words <= 0;
            snap_flags <= 0;
            lane_error_sticky <= 0;
            col <= 0;
            first_frame <= 1'b1;
        end else begin
            ticks <= ticks + 1'b1;
            lane_error_sticky <= lane_error_sticky | lane_error;
            if (s_valid) begin
                if (s_sof) begin
                    snap_frame_id <= frame_id + 1'b1;
                    frame_id <= frame_id + 1'b1;
                    snap_sof_tick <= ticks;
                    snap_period <= first_frame ? 64'd0 : ticks - sof_tick;
                    snap_frame_span <= first_frame ? 64'd0 : last_line_tick - sof_tick;
                    snap_rows <= rows;
                    snap_words <= words;
                    snap_flags <= {22'd0, bridge_overflow, 5'd0,
                                   lane_error_sticky | lane_error};
                    first_frame <= 1'b0;
                    sof_tick <= ticks;
                    rows <= s_last ? 32'd1 : 32'd0;
                    words <= 32'd1;
                    col <= s_last ? 10'd0 : 10'd1;
                end else begin
                    words <= words + 1'b1;
                    col <= s_last ? 10'd0 : col + 1'b1;
                    if (s_last) rows <= rows + 1'b1;
                end
                if (s_last) last_line_tick <= ticks;
            end
        end
    end

    // Bytes on the RK side are in increasing bit order within each qword.
    // Offset 0 magic, 4 version, 8 frame_id, 12 flags, 16 SOF ticks,
    // 24 previous SOF period, 32 previous frame span, 40 rows, 44 words,
    // 48 nominal RX clock Hz, 52 header size, 56/60 reserved.
    always @* begin
        case (col)
            10'd0: header_word = {32'd1, 32'h41475046}; // "FPGA", v1
            10'd1: header_word = {snap_flags, snap_frame_id};
            10'd2: header_word = snap_sof_tick;
            10'd3: header_word = snap_period;
            10'd4: header_word = snap_frame_span;
            10'd5: header_word = {snap_words, snap_rows};
            10'd6: header_word = {32'd64, 32'd111375000};
            default: header_word = 64'd0;
        endcase
    end
    assign m_valid = s_valid;
    assign m_sof = s_sof;
    assign m_last = s_last;
    assign m_data = (s_valid && (s_sof || (rows == 0 && col < 10'd8)))
                  ? header_word : s_data;
endmodule
