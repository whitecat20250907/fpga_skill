`timescale 1ns/1ps
// Camera side: four YUYV pixels (64 bits) per valid cycle, no backpressure.
// CSI-2 TX side: two YUYV pixels (32 bits) per ready/valid transfer.
// 1024 x 66-bit elastic FIFO; no external DDR. Only complete lines are
// released to CSI-2 TX, which must never pause inside a long packet.
// The sticky overflow flag must be exposed in final link metadata, because a
// camera cannot be stalled.
module yuyv_quad_async_bridge #(
    parameter ADDR_BITS = 10
)(
    input  wire        src_clk,
    input  wire        dst_clk,
    input  wire        rst_n,
    input  wire        s_valid,
    input  wire [63:0] s_data,
    input  wire        s_sof,
    input  wire        s_last,
    output reg         overflow,
    output wire        m_valid,
    input  wire        m_ready,
    output wire [31:0] m_data,
    output wire        m_sof,
    output wire        m_last
);
    localparam DEPTH = 1 << ADDR_BITS;
    reg [65:0] ram [0:DEPTH-1];
    reg [ADDR_BITS:0] wbin, wgray, cgray, rbin, rgray;
    reg [ADDR_BITS:0] rgray_w1, rgray_w2;
    reg [ADDR_BITS:0] cgray_r1, cgray_r2;
    reg [65:0] hold, ahead;
    reg have, upper, ahead_valid;
    wire full, empty, read_en;
    wire [ADDR_BITS:0] wbin_next = wbin + {{ADDR_BITS{1'b0}}, (s_valid && !full)};
    wire [ADDR_BITS:0] wgray_next = (wbin_next >> 1) ^ wbin_next;
    assign read_en = (!have && !empty) ||
                     (have && !upper && m_ready && !empty);
    wire [ADDR_BITS:0] rbin_next = rbin + {{ADDR_BITS{1'b0}}, read_en};
    wire [ADDR_BITS:0] rgray_next = (rbin_next >> 1) ^ rbin_next;
    assign full = (wgray == {~rgray_w2[ADDR_BITS:ADDR_BITS-1],
                            rgray_w2[ADDR_BITS-2:0]});
    // cgray advances only with an accepted end-of-line word. Thus the read
    // side can start a CSI-2 packet only when its entire payload is buffered.
    assign empty = (rgray == cgray_r2);

    always @(posedge src_clk or negedge rst_n) begin
        if (!rst_n) begin
            wbin <= 0; wgray <= 0; cgray <= 0;
            rgray_w1 <= 0; rgray_w2 <= 0;
            overflow <= 1'b0;
        end else begin
            rgray_w1 <= rgray;
            rgray_w2 <= rgray_w1;
            if (s_valid && !full) begin
                ram[wbin[ADDR_BITS-1:0]] <= {s_last, s_sof, s_data};
                wbin <= wbin_next;
                wgray <= wgray_next;
                if (s_last) cgray <= wgray_next;
            end else if (s_valid) begin
                overflow <= 1'b1;
            end
        end
    end

    always @(posedge dst_clk or negedge rst_n) begin
        if (!rst_n) begin
            rbin <= 0; rgray <= 0; cgray_r1 <= 0; cgray_r2 <= 0;
            hold <= 0; ahead <= 0;
            have <= 1'b0; upper <= 1'b0; ahead_valid <= 1'b0;
        end else begin
            cgray_r1 <= cgray;
            cgray_r2 <= cgray_r1;
            if (!have && !empty) begin
                hold <= ram[rbin[ADDR_BITS-1:0]];
                rbin <= rbin_next;
                rgray <= rgray_next;
                have <= 1'b1;
                upper <= 1'b0;
            end else if (have && m_ready) begin
                if (!upper) begin
                    upper <= 1'b1;
                    // Prefetch during the lower-word handshake. The following
                    // upper-word handshake can swap registers with no bubble.
                    if (!empty) begin
                        ahead <= ram[rbin[ADDR_BITS-1:0]];
                        rbin <= rbin_next;
                        rgray <= rgray_next;
                        ahead_valid <= 1'b1;
                    end
                end else if (ahead_valid) begin
                    hold <= ahead;
                    upper <= 1'b0;
                    ahead_valid <= 1'b0;
                end else begin
                    upper <= 1'b0;
                    have <= 1'b0;
                end
            end
        end
    end

    assign m_valid = have;
    assign m_data = upper ? hold[63:32] : hold[31:0];
    assign m_sof = have && !upper && hold[64];
    assign m_last = have && upper && hold[65];
endmodule
