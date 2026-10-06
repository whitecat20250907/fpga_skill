`timescale 1ns/1ps
// F2 stages 1+2: YUYV -> gray8, then exact 3x3 [1 2 1]^T[1 2 1]/16.
// Four pixels per clock; two row latency plus one group. Replicate borders.
// Three rotating 480x40-bit line banks avoid read/write collisions. The
// frame's last row is drained during vertical blanking; no external DDR.
module gauss3x3_yuyv_quad #(
    parameter WIDTH = 1920,
    parameter HEIGHT = 1080,
    parameter GROUPS = WIDTH/4
)(
    input wire clk, rst_n,
    input wire s_valid,
    input wire [63:0] s_data,
    input wire s_sof, s_last,
    output reg m_valid,
    output reg [63:0] m_data,
    output reg m_sof, m_last,
    output reg input_overlap
);
    reg [39:0] hbuf0 [0:GROUPS-1];
    reg [39:0] hbuf1 [0:GROUPS-1];
    reg [39:0] hbuf2 [0:GROUPS-1];
    reg [9:0] in_col, bottom_col;
    reg [10:0] in_row, flush_row;
    reg [1:0] bank_select, flush_bank, bottom_bank;
    reg [31:0] prev_group;
    reg [7:0] left_pixel;
    reg flush_pending, bottom_active;

    function [39:0] horiz;
        input [7:0] left;
        input [31:0] center;
        input [7:0] right;
        reg [9:0] h0,h1,h2,h3;
        begin
            h0 = {2'b0,left} + {1'b0,center[7:0],1'b0} + {2'b0,center[15:8]};
            h1 = {2'b0,center[7:0]} + {1'b0,center[15:8],1'b0} + {2'b0,center[23:16]};
            h2 = {2'b0,center[15:8]} + {1'b0,center[23:16],1'b0} + {2'b0,center[31:24]};
            h3 = {2'b0,center[23:16]} + {1'b0,center[31:24],1'b0} + {2'b0,right};
            horiz = {h3,h2,h1,h0};
        end
    endfunction

    function [63:0] gauss_pack;
        input [39:0] upper, center, lower;
        reg [11:0] s0,s1,s2,s3;
        begin
            s0 = upper[9:0] + {center[9:0],1'b0} + lower[9:0] + 12'd8;
            s1 = upper[19:10] + {center[19:10],1'b0} + lower[19:10] + 12'd8;
            s2 = upper[29:20] + {center[29:20],1'b0} + lower[29:20] + 12'd8;
            s3 = upper[39:30] + {center[39:30],1'b0} + lower[39:30] + 12'd8;
            gauss_pack = {8'h80,s3[11:4],8'h80,s2[11:4],
                          8'h80,s1[11:4],8'h80,s0[11:4]};
        end
    endfunction

    wire [31:0] y4 = {s_data[55:48],s_data[39:32],
                      s_data[23:16],s_data[7:0]};
    wire [9:0] this_col = s_sof ? 10'd0 : in_col;
    wire [10:0] this_row = s_sof ? 11'd0 : in_row;
    wire [1:0] this_bank = s_sof ? 2'd0 : bank_select;
    wire flush_now = flush_pending && !s_valid && !bottom_active;
    wire emit_now = flush_now ||
                    (s_valid && !flush_pending && !bottom_active && this_col != 0);
    wire [9:0] emit_col = flush_now ? GROUPS-1 : this_col-1'b1;
    wire [10:0] emit_row = flush_now ? flush_row : this_row;
    wire [1:0] emit_bank = flush_now ? flush_bank : this_bank;
    wire [39:0] h_now = flush_now
        ? horiz(left_pixel, prev_group, prev_group[31:24])
        : horiz(left_pixel, prev_group, y4[7:0]);
    wire [39:0] q0 = hbuf0[emit_col];
    wire [39:0] q1 = hbuf1[emit_col];
    wire [39:0] q2 = hbuf2[emit_col];
    reg [39:0] center_h, top_h;
    always @* begin
        case (emit_bank)
            2'd0: begin center_h=q2; top_h=q1; end
            2'd1: begin center_h=q0; top_h=q2; end
            default: begin center_h=q1; top_h=q0; end
        endcase
        if (emit_row == 1) top_h = center_h;
    end
    wire [39:0] b0 = hbuf0[bottom_col];
    wire [39:0] b1 = hbuf1[bottom_col];
    wire [39:0] b2 = hbuf2[bottom_col];
    reg [39:0] bottom_h, prev_h;
    always @* begin
        case (bottom_bank)
            2'd0: begin bottom_h=b0; prev_h=b2; end
            2'd1: begin bottom_h=b1; prev_h=b0; end
            default: begin bottom_h=b2; prev_h=b1; end
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            in_col<=0; in_row<=0; bank_select<=0;
            prev_group<=0; left_pixel<=0;
            flush_pending<=0; flush_row<=0; flush_bank<=0;
            bottom_active<=0; bottom_col<=0; bottom_bank<=0;
            m_valid<=0; m_data<=0; m_sof<=0; m_last<=0;
            input_overlap<=0;
        end else begin
            m_valid<=0; m_sof<=0; m_last<=0;
            if (s_valid && (flush_pending || bottom_active))
                input_overlap<=1'b1;
            if (emit_now) begin
                case (emit_bank)
                    2'd0: hbuf0[emit_col] <= h_now;
                    2'd1: hbuf1[emit_col] <= h_now;
                    default: hbuf2[emit_col] <= h_now;
                endcase
                if (emit_row != 0) begin
                    m_valid<=1;
                    m_data<=gauss_pack(top_h,center_h,h_now);
                    m_sof<=(emit_row==1 && emit_col==0);
                    m_last<=(emit_col==GROUPS-1);
                end
            end
            if (bottom_active) begin
                m_valid<=1;
                m_data<=gauss_pack(prev_h,bottom_h,bottom_h);
                m_last<=(bottom_col==GROUPS-1);
                if (bottom_col==GROUPS-1) bottom_active<=0;
                else bottom_col<=bottom_col+1'b1;
            end else if (flush_now) begin
                flush_pending<=0;
                if (flush_row==HEIGHT-1) begin
                    bottom_active<=1;
                    bottom_col<=0;
                    bottom_bank<=flush_bank;
                end
            end else if (s_valid && !flush_pending) begin
                if (this_col==0) begin
                    prev_group<=y4;
                    left_pixel<=y4[7:0];
                end else begin
                    left_pixel<=prev_group[31:24];
                    prev_group<=y4;
                end
                if (s_last) begin
                    in_col<=0;
                    in_row<=this_row+1'b1;
                    bank_select<=(this_bank==2) ? 2'd0 : this_bank+1'b1;
                    flush_pending<=1;
                    flush_row<=this_row;
                    flush_bank<=this_bank;
                end else begin
                    in_col<=this_col+1'b1;
                    in_row<=this_row;
                    bank_select<=this_bank;
                end
            end
        end
    end
endmodule
