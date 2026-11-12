`timescale 1ns/1ps
// One nominal25MHz/1us source timebase. Only the Gray code crosses to video;
// both stages are explicit async_reg. It timestamps accepted source events,
// not exposure onset or a physical hand action. No external clock calibration.
module hci02_timebase #(parameter CLOCK_HZ=25000000,DIV=CLOCK_HZ/1000000)(
 input wire source_clk,video_clk,rst_n,
 output reg [63:0] source_time_us,output reg [63:0] video_time_us
);
 (* async_reg="true" *) reg [2:0] source_reset_sync,video_reset_sync;
 always @(posedge source_clk or negedge rst_n)
  if(!rst_n)source_reset_sync<=0;else source_reset_sync<={source_reset_sync[1:0],1'b1};
 always @(posedge video_clk or negedge rst_n)
  if(!rst_n)video_reset_sync<=0;else video_reset_sync<={video_reset_sync[1:0],1'b1};
 reg [$clog2(DIV)-1:0] fraction;
 reg [63:0] source_gray;
 (* async_reg="true" *) reg [63:0] gray_video1,gray_video2;
 wire [63:0] next_us=source_time_us+1'b1;
 function [63:0] gray_decode;
  input [63:0] gray;reg [63:0] b;
  begin b=gray^(gray>>32);b=b^(b>>16);b=b^(b>>8);b=b^(b>>4);b=b^(b>>2);b=b^(b>>1);gray_decode=b;end
 endfunction
 always @(posedge source_clk or negedge source_reset_sync[2])begin
  if(!source_reset_sync[2])begin fraction<=0;source_time_us<=0;source_gray<=0;end
  else if(fraction==DIV-1)begin fraction<=0;source_time_us<=next_us;source_gray<=next_us^(next_us>>1);end
  else fraction<=fraction+1'b1;
 end
 always @(posedge video_clk or negedge video_reset_sync[2])begin
  if(!video_reset_sync[2])begin gray_video1<=0;gray_video2<=0;video_time_us<=0;end
  else begin gray_video1<=source_gray;gray_video2<=gray_video1;video_time_us<=gray_decode(gray_video2);end
 end
 // synthesis translate_off
 initial if(CLOCK_HZ%1000000!=0||DIV<2)$fatal(1,"Timebase needs integer source clocks per microsecond");
 // synthesis translate_on
endmodule
