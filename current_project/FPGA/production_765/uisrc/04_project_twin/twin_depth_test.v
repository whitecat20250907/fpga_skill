`timescale 1ns/1ps
`default_nettype none
// One in-flight scene's depth, only for the three 3D viewports.
// Lower unsigned depth is nearer; equal depth preserves later edge/detail writes.
// Clear every stored 3D pixel before drawing a new scene. Reset flushes the
// pipeline, not the RAM. The caller must drain busy before publishing/switching bank.
module twin_depth_test(
 input wire clk,input wire rst,
 input wire in_valid,input wire in_clear,input wire in_test,
 input wire [17:0] in_address,input wire [5:0] in_pixel,
 input wire [9:0] in_depth,
 output reg out_valid,output reg [17:0] out_address,
 output reg [5:0] out_pixel,output wire busy
);
 function [16:0] locate3d;
  input [17:0] address;
  reg [8:0] x,y;reg [15:0] dense;reg is_inside;
  begin
   x=address[8:0];y=address[17:9];dense=0;is_inside=1;
   if(y>=70 && y<=224 && x>=24 && x<=141)dense=(y-70)*118+x-24;
   else if(y>=70 && y<=224 && x>=153 && x<=270)dense=18290+(y-70)*118+x-153;
   else if(y>=74 && y<=139 && x>=314 && x<=366)dense=36580+(y-74)*53+x-314;
   else is_inside=0;
   locate3d={is_inside,dense};
  end
 endfunction
 wire [16:0] location=locate3d(in_address);
 (* ram_style="bram(min_area)" *) reg [9:0] depth[0:40077];
 reg [9:0] read_depth;
 reg s_valid,s_clear,s_test,s_inside;
 reg [15:0] s_dense;reg [17:0] s_address;
 reg [5:0] s_pixel;reg [9:0] s_depth;
 // Read-before-write RAM may return the old value on consecutive same-address
 // fragments. Explicit forwarding is independent of the physical RAM mode.
 reg last_write;reg [15:0] last_address;reg [9:0] last_depth;
 wire [9:0] effective_depth=last_write && last_address==s_dense ? last_depth : read_depth;
 wire accept_fragment=s_clear || !s_test || !s_inside || s_depth<=effective_depth;
 wire write_depth=s_valid && s_inside && (s_clear || (s_test && accept_fragment));
 wire [9:0] new_depth=s_clear ? 10'h3ff : s_depth;
 always @(posedge clk)begin
  read_depth<=depth[location[15:0]];
  if(!rst && write_depth)depth[s_dense]<=new_depth;
 end
 always @(posedge clk)begin
  if(rst)begin
   s_valid<=0;s_clear<=0;s_test<=0;s_inside<=0;s_dense<=0;
   s_address<=0;s_pixel<=0;s_depth<=0;
   out_valid<=0;out_address<=0;out_pixel<=0;
   last_write<=0;last_address<=0;last_depth<=0;
  end else begin
   s_valid<=in_valid;s_clear<=in_clear;s_test<=in_test;s_inside<=location[16];
   s_dense<=location[15:0];s_address<=in_address;s_pixel<=in_pixel;s_depth<=in_depth;
   out_valid<=s_valid && accept_fragment;
   out_address<=s_address;out_pixel<=s_pixel;
   last_write<=write_depth;last_address<=s_dense;last_depth<=new_depth;
  end
 end
 assign busy=s_valid || out_valid;
endmodule
`default_nettype wire
