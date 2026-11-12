`timescale 1ns/1ps
// Complete 4px AXIS path: luminance -> Gaussian -> previous-frame histogram
// -> selectable Sobel/dark mask/erosion/dilation. Every stage honours ready.
// cfg bit0 true RGB bypass;1 Gaussian bypass;2 histogram bypass;
// bits5:3 post mode0..4;13:6 threshold. Configuration is accepted once at SOF.
module hci01_preprocess #(parameter WIDTH=1920,HEIGHT=1080,BINS=64)(
 input wire clk,rst_n,input wire [127:0] s_data,input wire s_valid,s_sof,s_last,
 input wire [13:0] cfg,output wire s_ready,input wire m_ready,
 output wire [127:0] m_data,output wire m_valid,m_sof,m_last,m_eof,
 output wire [13:0] m_config,output wire [31:0] errors,
 output reg [31:0] frames,output wire lut_valid);
 wire [31:0] gray,gauss,hist,post;
 wire gv,gs,gl,gr,av,asf,al,ae,ar,hv,hs,hl,he,hr;
 wire [13:0] gc,ac,hc;
 wire [31:0] gauss_errors,hist_errors,post_errors,gauss_frames,hist_frames,post_frames;
 reg in_frame,input_done;
 reg [13:0] frame_config;
 reg [10:0] input_col;reg [11:0] input_row;
 reg [31:0] wrapper_errors;
 reg [127:0] bypass_data;reg bypass_valid,bypass_sof,bypass_last,bypass_eof;
 reg [13:0] bypass_config;
 wire [13:0] selected_config=in_frame?frame_config:cfg;
 wire rgb_bypass=selected_config[0];
 wire gray_ready,post_valid,post_sof,post_last,post_eof;
 wire [13:0] post_config;
 wire output_bypass=frame_config[0];
 wire bypass_advance=!bypass_valid||(output_bypass&&m_ready);
 assign s_ready=!input_done&&(rgb_bypass?bypass_advance:gray_ready);
 wire take=s_valid&&s_ready;
 wire [10:0] col=s_sof?11'd0:input_col;
 wire [11:0] row=s_sof?12'd0:input_row;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   in_frame<=0;input_done<=0;frame_config<=0;input_col<=0;input_row<=0;
   bypass_valid<=0;bypass_data<=0;bypass_sof<=0;bypass_last<=0;bypass_eof<=0;bypass_config<=0;wrapper_errors<=0;frames<=0;
  end else begin
   if(bypass_advance)begin
    bypass_valid<=take&&rgb_bypass;bypass_sof<=take&&rgb_bypass&&s_sof;
    bypass_last<=take&&rgb_bypass&&s_last;bypass_eof<=take&&rgb_bypass&&s_last&&row==HEIGHT-1;
    if(take&&rgb_bypass)begin bypass_data<=s_data;bypass_config<=selected_config;end
   end
   if(take)begin
    if(s_sof)begin if(in_frame)wrapper_errors[4]<=1;frame_config<=selected_config;in_frame<=1;end
    else if(!in_frame)wrapper_errors[5]<=1;
    if(s_last!=(col==WIDTH/4-1))wrapper_errors[6]<=1;
    if(s_last)begin input_col<=0;input_row<=row+1'b1;if(row==HEIGHT-1)input_done<=1;end
    else begin input_col<=col+1'b1;input_row<=row;end
   end
   if(m_valid&&m_ready&&m_eof)begin in_frame<=0;input_done<=0;frames<=frames+1'b1;end
  end
 end
 hci01_gray_rgbx_quad u_gray(.clk(clk),.rst_n(rst_n),.s_data(s_data),.s_valid(s_valid&&!input_done&&!rgb_bypass),.s_sof(s_sof),.s_last(s_last),
  .s_ready(gray_ready),.cfg(selected_config),.m_ready(gr),.m_data(gray),.m_valid(gv),.m_sof(gs),.m_last(gl),.m_config(gc));
 hci01_spatial_quad #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.STAGE(0)) u_gauss(
  .clk(clk),.rst_n(rst_n),.s_data(gray),.s_valid(gv),.s_sof(gs),.s_last(gl),.s_config(gc),.s_ready(gr),.m_ready(ar),
  .m_data(gauss),.m_valid(av),.m_sof(asf),.m_last(al),.m_eof(ae),.m_config(ac),.errors(gauss_errors),.frames(gauss_frames));
 hci01_histeq_quad #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.BINS(BINS)) u_hist(
  .clk(clk),.rst_n(rst_n),.s_data(gauss),.s_valid(av),.s_sof(asf),.s_last(al),.s_eof(ae),.s_config(ac),
  .invalidate_lut((in_frame&&frame_config[0])||(take&&s_sof&&selected_config[0])),.s_ready(ar),.m_ready(hr),
  .m_data(hist),.m_valid(hv),.m_sof(hs),.m_last(hl),.m_eof(he),.m_config(hc),.errors(hist_errors),.frames(hist_frames),.lut_valid(lut_valid));
 hci01_spatial_quad #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.STAGE(1)) u_post(
  .clk(clk),.rst_n(rst_n),.s_data(hist),.s_valid(hv),.s_sof(hs),.s_last(hl),.s_config(hc),.s_ready(hr),.m_ready(!output_bypass&&m_ready),
  .m_data(post),.m_valid(post_valid),.m_sof(post_sof),.m_last(post_last),.m_eof(post_eof),.m_config(post_config),.errors(post_errors),.frames(post_frames));
 genvar j;
 generate for(j=0;j<4;j=j+1)begin:rgb_output
  assign m_data[j*32+:32]=output_bypass?bypass_data[j*32+:32]:{8'd0,post[j*8+:8],post[j*8+:8],post[j*8+:8]};
 end endgenerate
 assign m_valid=output_bypass?bypass_valid:post_valid;
 assign m_sof=output_bypass?bypass_sof:post_sof;
 assign m_last=output_bypass?bypass_last:post_last;
 assign m_eof=output_bypass?bypass_eof:post_eof;
 assign m_config=output_bypass?bypass_config:post_config;
 assign errors=gauss_errors|hist_errors|post_errors|wrapper_errors;
endmodule
