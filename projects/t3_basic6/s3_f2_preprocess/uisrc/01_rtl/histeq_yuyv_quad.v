`timescale 1ns/1ps
// F2 stage 3: four-bank global histogram equalization, 4 gray pixels/clock.
// Frame N accumulates histogram while using frame N-1's LUT. At frame end a
// 32-cycle integer divider and 256-bin LUT builder run during vertical blank.
// Parameters 1920x1080 use HIST_SHIFT=5, matching golden_vectors.py's
// per-bin right shift before CDF and Q24 reciprocal calculation.
module histeq_yuyv_quad #(
    parameter WIDTH=1920,
    parameter HEIGHT=1080,
    parameter HIST_SHIFT=5
)(
    input wire clk,rst_n,
    input wire s_valid,
    input wire [63:0] s_data,
    input wire s_sof,s_last,
    output wire m_valid,
    output wire [63:0] m_data,
    output wire m_sof,m_last,
    output reg blank_overlap
);
    localparam S_CLEAR=3'd0, S_RUN=3'd1, S_PASS1=3'd2,
               S_DIV=3'd3, S_PASS2=3'd4;
    reg [2:0] state;
    reg [20:0] hist0[0:255],hist1[0:255],hist2[0:255],hist3[0:255];
    reg [7:0] lut[0:255];
    reg lut_ready;
    reg [7:0] bin;
    reg [10:0] row;
    reg [7:0] last_bin0,last_bin1,last_bin2,last_bin3;
    reg [20:0] last_count0,last_count1,last_count2,last_count3;
    reg last_valid;
    reg [22:0] cdf,cdf_min,denom;
    reg found_min;
    reg [31:0] dividend,quotient,inv255;
    reg [32:0] remainder;
    reg [5:0] bitpos;
    wire [7:0] p0=s_data[7:0], p1=s_data[23:16];
    wire [7:0] p2=s_data[39:32],p3=s_data[55:48];
    wire [7:0] o0=lut_ready?lut[p0]:p0;
    wire [7:0] o1=lut_ready?lut[p1]:p1;
    wire [7:0] o2=lut_ready?lut[p2]:p2;
    wire [7:0] o3=lut_ready?lut[p3]:p3;
    assign m_valid=s_valid;
    assign m_sof=s_sof;
    assign m_last=s_last;
    assign m_data={8'h80,o3,8'h80,o2,8'h80,o1,8'h80,o0};

    wire [22:0] bin_count={2'b0,hist0[bin]}+{2'b0,hist1[bin]}+
                          {2'b0,hist2[bin]}+{2'b0,hist3[bin]};
    wire [22:0] cdf_next=cdf+(bin_count>>HIST_SHIFT);
    wire [22:0] min_next=found_min?cdf_min:
                         ((cdf_next!=0)?cdf_next:23'd0);
    wire [22:0] denom_next=cdf_next-min_next;
    wire [22:0] num_next=(cdf_next>cdf_min)?cdf_next-cdf_min:23'd0;
    wire [54:0] product=num_next*inv255;
    wire [30:0] lut_value=product[54:24];
    wire [32:0] div_shift={remainder[31:0],dividend[bitpos]};
    wire div_ge=div_shift>={10'd0,denom};
    wire [32:0] div_remainder_next=div_ge?
                                div_shift-{10'd0,denom}:div_shift;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state<=S_CLEAR; bin<=0; row<=0; lut_ready<=0;
            last_bin0<=0;last_bin1<=0;last_bin2<=0;last_bin3<=0;
            last_count0<=0;last_count1<=0;last_count2<=0;last_count3<=0;
            last_valid<=0; cdf<=0;cdf_min<=0;denom<=0;found_min<=0;
            dividend<=0;quotient<=0;inv255<=0;remainder<=0;bitpos<=0;
            blank_overlap<=0;
        end else begin
            if (s_valid && state!=S_RUN) blank_overlap<=1'b1;
            case (state)
                S_CLEAR: begin
                    hist0[bin]<=0;hist1[bin]<=0;
                    hist2[bin]<=0;hist3[bin]<=0;
                    if (bin==255) begin bin<=0;state<=S_RUN; end
                    else bin<=bin+1'b1;
                end
                S_RUN: if (s_valid) begin
                    last_count0 <= ((last_valid && !s_sof && last_bin0==p0)
                                   ? last_count0 : hist0[p0])+1'b1;
                    last_count1 <= ((last_valid && !s_sof && last_bin1==p1)
                                   ? last_count1 : hist1[p1])+1'b1;
                    last_count2 <= ((last_valid && !s_sof && last_bin2==p2)
                                   ? last_count2 : hist2[p2])+1'b1;
                    last_count3 <= ((last_valid && !s_sof && last_bin3==p3)
                                   ? last_count3 : hist3[p3])+1'b1;
                    hist0[p0] <= ((last_valid && !s_sof && last_bin0==p0)
                                   ? last_count0 : hist0[p0])+1'b1;
                    hist1[p1] <= ((last_valid && !s_sof && last_bin1==p1)
                                   ? last_count1 : hist1[p1])+1'b1;
                    hist2[p2] <= ((last_valid && !s_sof && last_bin2==p2)
                                   ? last_count2 : hist2[p2])+1'b1;
                    hist3[p3] <= ((last_valid && !s_sof && last_bin3==p3)
                                   ? last_count3 : hist3[p3])+1'b1;
                    last_bin0<=p0;last_bin1<=p1;last_bin2<=p2;last_bin3<=p3;
                    last_valid<=1;
                    if (s_last) begin
                        if ((s_sof?11'd0:row)==HEIGHT-1) begin
                            row<=0;bin<=0;cdf<=0;cdf_min<=0;
                            found_min<=0;state<=S_PASS1;
                        end else row<=(s_sof?11'd0:row)+1'b1;
                    end else if (s_sof) row<=0;
                end
                S_PASS1: begin
                    cdf<=cdf_next;
                    if (!found_min && cdf_next!=0) begin
                        cdf_min<=cdf_next;
                        found_min<=1;
                    end
                    if (bin==255) begin
                        denom<=denom_next;
                        dividend<=(32'd255<<24)+(denom_next>>1);
                        quotient<=0;remainder<=0;bitpos<=31;
                        state<=S_DIV;
                    end else bin<=bin+1'b1;
                end
                S_DIV: begin
                    // Degenerate single-level frame: pass through next frame.
                    if (denom==0) begin
                        inv255<=0;cdf<=0;bin<=0;state<=S_PASS2;
                    end else begin
                        remainder<=div_remainder_next;
                        quotient[bitpos]<=div_ge;
                        if (bitpos==0) begin
                            inv255<={quotient[31:1],div_ge};
                            cdf<=0;bin<=0;state<=S_PASS2;
                        end else bitpos<=bitpos-1'b1;
                    end
                end
                S_PASS2: begin
                    cdf<=cdf_next;
                    lut[bin]<=(denom==0)?bin:
                               ((lut_value>255)?8'd255:lut_value[7:0]);
                    hist0[bin]<=0;hist1[bin]<=0;
                    hist2[bin]<=0;hist3[bin]<=0;
                    if (bin==255) begin
                        bin<=0;state<=S_RUN;lut_ready<=1;last_valid<=0;
                    end else bin<=bin+1'b1;
                end
                default: state<=S_CLEAR;
            endcase
        end
    end
endmodule
