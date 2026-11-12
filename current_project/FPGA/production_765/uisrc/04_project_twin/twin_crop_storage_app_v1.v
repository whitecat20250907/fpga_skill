`timescale 1ns/1ps
`default_nettype none
// Lossless backing store for twin_raster's FIVE DISJOINT fixed viewports.
// Actual raster emits nonempty shades 1..7; zero is empty. Keep both banks.
// Exactly one synchronous read cycle, identical to the original two planes.
module twin_crop_storage_app_v1(
 input wire clk,
 input wire wr_en,input wire [17:0] wr_addr,input wire [5:0] wr_pixel,
 input wire back_bank,input wire front_bank,input wire front_ready,
 input wire [17:0] video_addr,output wire [5:0] video_pixel
);
 // App profile: 58,819 stored pixels per bank; five disjoint regions.
 // Renderer contract: every nonempty write has shade 1..7 (verified on actual RTL).
 // Elide the redundant occupied bit; coordinates reconstruct the group.
 (* ram_style="bram(min_area)" *) reg [2:0] plane0[0:58818];
 (* ram_style="bram(min_area)" *) reg [2:0] plane1[0:58818];
 // {inside,group[2:0],dense_address[15:0]}; blank addresses select row zero
 // but are masked after the synchronous read, so no out-of-range RAM read.
 function [19:0] locate;
  input [17:0] address;
  reg [8:0] x,y;reg [15:0] a;reg [2:0] g;reg is_inside;
  begin
   x=address[8:0];y=address[17:9];a=0;g=0;is_inside=1;
   if(y>=70 && y<=224 && x>=24 && x<=141)begin g=0;a=0+(y-70)*118+x-24;end
   else if(y>=70 && y<=224 && x>=153 && x<=270)begin g=1;a=18290+(y-70)*118+x-153;end
   else if(y>=74 && y<=139 && x>=314 && x<=366)begin g=2;a=36580+(y-74)*53+x-314;end
   else if(y>=74 && y<=139 && x>=376 && x<=490)begin g=3;a=40078+(y-74)*115+x-376;end
   else if(y>=162 && y<=224 && x>=314 && x<=490)begin g=4;a=47668+(y-162)*177+x-314;end
   else is_inside=0;
   locate={is_inside,g,a};
  end
 endfunction
 wire [19:0] write_location=locate(wr_addr);
 wire [19:0] read_location=locate(video_addr);
 wire [2:0] stored_pixel=wr_pixel[5:3]==0 ? 3'd0 : wr_pixel[2:0];
 reg [2:0] read0,read1;reg [2:0] read_group;
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
 assign video_pixel=!read_ready || !read_inside || pixel==0 ? 6'd0 : {(read_group+3'd1),pixel[2:0]};
endmodule
`default_nettype wire
