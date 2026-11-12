// Actual complete RGB frame statistics; no generated substitute image.
module dsi_frame_stats(input clk,rst,input vsync,de,input [23:0] rgb,
 input config_done,output [191:0] stats);
 reg prev_vsync;
 reg [31:0] frames,pixels,red_sum,green_sum,blue_sum;
 reg [31:0] last_pixels,last_red,last_green,last_blue;
 assign stats={31'b0,config_done,frames,last_pixels,last_red,last_green,last_blue};
 always @(posedge clk) begin
  if(rst)begin prev_vsync<=0;frames<=0;pixels<=0;red_sum<=0;green_sum<=0;blue_sum<=0;
   last_pixels<=0;last_red<=0;last_green<=0;last_blue<=0;end
  else begin
   prev_vsync<=vsync;
   if(vsync&&!prev_vsync)begin
    frames<=frames+1'b1;last_pixels<=pixels;last_red<=red_sum;last_green<=green_sum;last_blue<=blue_sum;
    pixels<=0;red_sum<=0;green_sum<=0;blue_sum<=0;
   end else if(de)begin pixels<=pixels+1'b1;red_sum<=red_sum+rgb[23:16];
    green_sum<=green_sum+rgb[15:8];blue_sum<=blue_sum+rgb[7:0];end
  end
 end
endmodule
