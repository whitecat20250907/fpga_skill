/*****************************************************************
Company : MiLianKe Electronic Technology Co., Ltd.
WebSite:https://www.milianke.com
TechWeb:https://www.uisrc.com
tmall-shop:https://milianke.tmall.com
jd-shop:https://milianke.jd.com
taobao-shop: https://milianke.taobao.com
Description: 
The reference demo provided by Milianke is only used for learning. 
We cannot ensure that the demo itself is free of bugs, so users 
should be responsible for the technical problems and consequences
caused by the use of their own products.
@Author      :   XiaoQingquan 
@Time        :   2024/10 
version:     :   
@Description :   在原基�?�上删去了一些赘余的代码，并且优化了时序，加�?BRAM IP核，
                 让从除法器出来的每一�?数据都可以�?�上相应的像素数�?进�?��?�益，使
                 得它的适用行更加广泛了�?
*****************************************************************/
// Based on the Milianke Gray World AWB interface; vendor originals are retained.
// Four RGB pixels per accepted beat. Q16 gains are latched only at SOF.
`timescale 1ns/1ps
module ui_awb #(
    parameter IMG_HEIGHT=1080, parameter IMG_WIDTH=1920,
    parameter MIN_NEUTRAL_PIXELS=1024
)(
    input I_clk, input I_rst_n,
    input [12:0] I_img_width, input [12:0] I_img_height,
    input I_tlast, input I_tuser, input [95:0] I_tdata,
    input I_tvalid, output I_tready,
    output O_tlast, output O_tuser, output [95:0] O_tdata,
    output O_tvalid, input O_tready
);
    reg [31:0] sum_r,sum_g,sum_b;
    reg [23:0] neutral_count;
    // Exclude black, clipped and strongly coloured pixels from Gray World.
    // Without enough neutral pixels retain the previously latched gains.
    function neutral_pixel;
        input [23:0] rgb;
        reg [7:0] hi,lo;
        reg [9:0] three_lo,two_hi;
        begin
            hi=rgb[23:16]>rgb[15:8]?rgb[23:16]:rgb[15:8];
            if(rgb[7:0]>hi)hi=rgb[7:0];
            lo=rgb[23:16]<rgb[15:8]?rgb[23:16]:rgb[15:8];
            if(rgb[7:0]<lo)lo=rgb[7:0];
            three_lo={2'b0,lo}+{1'b0,lo,1'b0};
            two_hi={1'b0,hi,1'b0};
            neutral_pixel=lo>=8 && hi<=240 && three_lo>=two_hi;
        end
    endfunction
    wire [3:0] neutral;
    genvar n;
    generate for(n=0;n<4;n=n+1)begin: neutral_select
        assign neutral[n]=neutral_pixel(I_tdata[n*24+:24]);
    end endgenerate
    // Observation-only pipeline. AXIS output latency/ready is unchanged.
    // A: accept raw pixels and their neutral decisions together.
    // B: sum four selected pixels; then accumulate the complete frame.
    reg stats_a_valid,stats_a_sof,stats_a_final;
    reg [95:0] stats_a_data;
    reg [3:0] stats_a_neutral;
    reg stats_b_valid,stats_b_sof,stats_b_final;
    reg [10:0] stats_b_r,stats_b_g,stats_b_b;
    reg [2:0] stats_b_count;
    wire [2:0] beat_neutral={2'b0,stats_a_neutral[0]}+{2'b0,stats_a_neutral[1]}+{2'b0,stats_a_neutral[2]}+{2'b0,stats_a_neutral[3]};
    wire [23:0] next_neutral=(stats_b_sof?24'd0:neutral_count)+stats_b_count;
    reg [12:0] line_index;
    reg [17:0] active_r,active_b,pending_r,pending_b;
    reg pending_valid;
    reg div_start;
    reg [31:0] div_r,div_b,div_g;
    wire [47:0] quotient_r,quotient_b;
    wire done_r,done_b;
    reg out_valid,out_last,out_sof;
    reg [25:0] product_r[0:3],product_b[0:3];
    reg [7:0] value_g[0:3];
    wire step = !out_valid || O_tready;
    wire fire = I_tvalid && step;
    wire final_line = I_tuser ? (I_img_height==1) : (line_index==I_img_height-1'b1);
    wire [10:0] beat_r = (stats_a_neutral[0] ? {3'b0,stats_a_data[16+:8]} : 11'd0)+(stats_a_neutral[1] ? {3'b0,stats_a_data[40+:8]} : 11'd0)+(stats_a_neutral[2] ? {3'b0,stats_a_data[64+:8]} : 11'd0)+(stats_a_neutral[3] ? {3'b0,stats_a_data[88+:8]} : 11'd0);
    wire [10:0] beat_g = (stats_a_neutral[0] ? {3'b0,stats_a_data[8+:8]} : 11'd0)+(stats_a_neutral[1] ? {3'b0,stats_a_data[32+:8]} : 11'd0)+(stats_a_neutral[2] ? {3'b0,stats_a_data[56+:8]} : 11'd0)+(stats_a_neutral[3] ? {3'b0,stats_a_data[80+:8]} : 11'd0);
    wire [10:0] beat_b = (stats_a_neutral[0] ? {3'b0,stats_a_data[0+:8]} : 11'd0)+(stats_a_neutral[1] ? {3'b0,stats_a_data[24+:8]} : 11'd0)+(stats_a_neutral[2] ? {3'b0,stats_a_data[48+:8]} : 11'd0)+(stats_a_neutral[3] ? {3'b0,stats_a_data[72+:8]} : 11'd0);
    wire [31:0] next_r = (stats_b_sof ? 32'd0 : sum_r) + stats_b_r;
    wire [31:0] next_g = (stats_b_sof ? 32'd0 : sum_g) + stats_b_g;
    wire [31:0] next_b = (stats_b_sof ? 32'd0 : sum_b) + stats_b_b;
    wire [17:0] use_r = I_tuser && pending_valid ? pending_r : active_r;
    wire [17:0] use_b = I_tuser && pending_valid ? pending_b : active_b;
    assign I_tready=step;
    assign O_tvalid=out_valid;
    assign O_tlast=out_last;
    assign O_tuser=out_sof;

    function [17:0] clamp_gain;
        input [47:0] q;
        begin
            if(q<48'h08000) clamp_gain=18'h08000;
            else if(q>48'h20000) clamp_gain=18'h20000;
            else clamp_gain=q[17:0];
        end
    endfunction
    genvar p;
    generate for(p=0;p<4;p=p+1) begin: pixel
        assign O_tdata[p*24+16+:8]=|product_r[p][25:24] ? 8'hff : product_r[p][23:16];
        assign O_tdata[p*24+8+:8]=value_g[p];
        assign O_tdata[p*24+:8]=|product_b[p][25:24] ? 8'hff : product_b[p][23:16];
    end endgenerate
    divider div_gen_G_R_r1(.clk(I_clk),.rst(!I_rst_n),.start(div_start),
        .denominator(div_r),.numerator({div_g,16'b0}),.quotient(quotient_r),.done(done_r));
    divider divide_G_B_r1(.clk(I_clk),.rst(!I_rst_n),.start(div_start),
        .denominator(div_b),.numerator({div_g,16'b0}),.quotient(quotient_b),.done(done_b));

    integer j;
    always @(posedge I_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin
            sum_r<=0;sum_g<=0;sum_b<=0;line_index<=0;neutral_count<=0;
            active_r<=18'h10000;active_b<=18'h10000;
            pending_r<=18'h10000;pending_b<=18'h10000;pending_valid<=0;
            div_start<=0;div_r<=1;div_b<=1;div_g<=1;
            stats_a_valid<=0;stats_a_sof<=0;stats_a_final<=0;stats_a_data<=0;stats_a_neutral<=0;
            stats_b_valid<=0;stats_b_sof<=0;stats_b_final<=0;stats_b_r<=0;stats_b_g<=0;stats_b_b<=0;stats_b_count<=0;
            out_valid<=0;out_last<=0;out_sof<=0;
            for(j=0;j<4;j=j+1) begin product_r[j]<=0;product_b[j]<=0;value_g[j]<=0;end
        end else begin
            div_start<=0;
            stats_a_valid<=fire;
            if(fire) begin
                stats_a_data<=I_tdata;stats_a_neutral<=neutral;
                stats_a_sof<=I_tuser;stats_a_final<=I_tlast && final_line;
            end
            stats_b_valid<=stats_a_valid;
            if(stats_a_valid) begin
                stats_b_r<=beat_r;stats_b_g<=beat_g;stats_b_b<=beat_b;stats_b_count<=beat_neutral;
                stats_b_sof<=stats_a_sof;stats_b_final<=stats_a_final;
            end
            if(stats_b_valid) begin
                sum_r<=next_r;sum_g<=next_g;sum_b<=next_b;neutral_count<=next_neutral;
                // Every eligible pixel has three positive channels; the
                // nonzero sample-count threshold guarantees nonzero sums.
                if(stats_b_final && next_neutral>=MIN_NEUTRAL_PIXELS) begin
                    div_r<=next_r;div_b<=next_b;div_g<=next_g;div_start<=1;
                end
            end
            if(done_r && done_b) begin
                pending_r<=clamp_gain(quotient_r);pending_b<=clamp_gain(quotient_b);pending_valid<=1;
            end
            if(step) begin
                out_valid<=I_tvalid;
                out_last<=I_tvalid && I_tlast;
                out_sof<=I_tvalid && I_tuser;
                if(I_tvalid) begin
                    for(j=0;j<4;j=j+1) begin
                        product_r[j]<=use_r*I_tdata[j*24+16+:8];
                        product_b[j]<=use_b*I_tdata[j*24+:8];
                        value_g[j]<=I_tdata[j*24+8+:8];
                    end
                end
            end
            if(fire) begin
                if(I_tuser) begin
                    active_r<=use_r;active_b<=use_b;line_index<=I_tlast?13'd1:13'd0;
                end else if(I_tlast) line_index<=line_index+1'b1;
            end
        end
    end
endmodule
