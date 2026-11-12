`timescale 1ns/1ps
`default_nettype none
// Lossless backing store for twin_raster's FIVE DISJOINT fixed viewports.
// Keep all four shade codes and both banks. The group is a property of XY.
// Exactly one synchronous read cycle, identical to the original two planes.
module twin_crop_storage_v1(
 input wire clk,
 input wire wr_en,input wire [17:0] wr_addr,input wire [4:0] wr_pixel,
 input wire back_bank,input wire front_bank,input wire front_ready,
 input wire [17:0] video_addr,output wire [4:0] video_pixel
);
 // 2 * 119*114 + 159*110 + 2 * 185*28 = 54,982 stored pixels.
 // {occupied,shade[1:0]} preserves empty separately from shade zero.
 (* ram_style="bram(min_area)" *) reg [2:0] plane0[0:54981];
 (* ram_style="bram(min_area)" *) reg [2:0] plane1[0:54981];
 // {inside,group[2:0],dense_address[15:0]}; blank addresses select row zero
 // but are masked after the synchronous read, so no out-of-range RAM read.
 function [19:0] locate;
  input [17:0] address;
  reg [8:0] x,y;reg [15:0] a;reg [2:0] g;reg is_inside;
  begin
   x=address[8:0];y=address[17:9];a=0;g=0;is_inside=1;
   if(y>=90 && y<=203 && x>=28 && x<=146)begin g=0;a=(y-90)*119+x-28;end
   else if(y>=90 && y<=203 && x>=162 && x<=280)begin g=1;a=13566+(y-90)*119+x-162;end
   else if(y>=90 && y<=199 && x>=326 && x<=484)begin g=2;a=27132+(y-90)*159+x-326;end
   else if(y>=244 && y<=271 && x>=36 && x<=220)begin g=3;a=44622+(y-244)*185+x-36;end
   else if(y>=244 && y<=271 && x>=292 && x<=476)begin g=4;a=49802+(y-244)*185+x-292;end
   else is_inside=0;
   locate={is_inside,g,a};
  end
 endfunction
 wire [19:0] write_location=locate(wr_addr);
 wire [19:0] read_location=locate(video_addr);
 wire [2:0] stored_pixel=wr_pixel[4:2]==0 ? 3'b000 : {1'b1,wr_pixel[1:0]};
 reg [2:0] read0,read1,read_group;
 reg read_bank,read_ready,read_inside;
 always @(posedge clk)begin
  if(wr_en && write_location[19])begin
   if(back_bank)plane1[write_location[15:0]]<=stored_pixel;
   else plane0[write_location[15:0]]<=stored_pixel;
  end
  read0<=plane0[read_location[15:0]];
  read1<=plane1[read_location[15:0]];
  read_group<=read_location[18:16];read_inside<=read_location[19];
  read_bank<=front_bank;read_ready<=front_ready;
 end
 wire [2:0] pixel=read_bank ? read1 : read0;
 assign video_pixel=!read_ready || !read_inside || !pixel[2] ? 5'd0 : {(read_group+3'd1),pixel[1:0]};
endmodule
`default_nettype wire
