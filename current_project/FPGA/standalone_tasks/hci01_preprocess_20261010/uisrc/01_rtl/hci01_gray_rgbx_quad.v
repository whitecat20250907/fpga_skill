`timescale 1ns/1ps
// 4 RGBX pixels/accepted beat. RGB byte order follows the real ISP: R at bit0.
// Each frame carries its accepted configuration through every elastic stage.
module hci01_gray_rgbx_quad(
 input wire clk,rst_n,input wire [127:0] s_data,
 input wire s_valid,s_sof,s_last,output wire s_ready,
 input wire [13:0] cfg,input wire m_ready,
 output reg [31:0] m_data,output reg m_valid,m_sof,m_last,
 output reg [13:0] m_config);
 reg [13:0] active_config;
 wire advance=!m_valid||m_ready;
 assign s_ready=advance;
 wire [13:0] this_config=s_sof?cfg:active_config;
 function [7:0] luminance;
  input [23:0] rgb;
  reg [15:0] sum;
  begin
   sum=16'd77*rgb[7:0]+16'd150*rgb[15:8]+16'd29*rgb[23:16]+16'd128;
   luminance=sum[15:8];
  end
 endfunction
 integer k;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin m_valid<=0;m_sof<=0;m_last<=0;m_data<=0;m_config<=0;active_config<=0;end
  else if(advance)begin
   m_valid<=s_valid;m_sof<=s_valid&&s_sof;m_last<=s_valid&&s_last;
   if(s_valid)begin
    if(s_sof)active_config<=cfg;
    m_config<=this_config;
    // True RGB passthrough is handled by the whole wrapper before this stage.
    for(k=0;k<4;k=k+1)m_data[k*8+:8]<=luminance(s_data[k*32+:24]);
   end
  end
 end
endmodule
