`timescale 1ns/1ps
`default_nettype none
// Display-only 2x reconstruction of actual pose pixels. Sample centers are
// odd physical coordinates; even coordinates interpolate the preceding and
// current logical samples. No geometry, source timestamp or action changes.
module twin_pose_smooth(
 input wire clk,rst,input wire [8:0] ahead_x,
 input wire [9:0] x,y,input wire valid,
 input wire [5:0] pixel,input wire [4:0] valid_mask,
 input wire [23:0] background,
 output reg applies,output reg [23:0] rgb
);
 reg [5:0] previous_line[0:511];
 reg [5:0] above,left,above_left;
 always @(posedge clk)begin
  above<=previous_line[ahead_x];
  // Read only on the first physical row; commit on the second row's odd
  // sample. This avoids same-address read/write dependence where used.
  if(valid && !rst && x[0] && y[0])previous_line[x[9:1]]<=pixel;
  if(rst || !valid)begin left<=0;above_left<=0;end
  else begin left<=pixel;above_left<=above;end
 end
 function [23:0] average;
  input [23:0] a,b;reg [8:0] r,g,bl;
  begin r={1'b0,a[23:16]}+{1'b0,b[23:16]};g={1'b0,a[15:8]}+{1'b0,b[15:8]};bl={1'b0,a[7:0]}+{1'b0,b[7:0]};average={r[8:1],g[8:1],bl[8:1]};end
 endfunction
 function [23:0] color;
  input [5:0] p;input [2:0] group_id;input [23:0] bg;
  begin
   color=bg;
   if(p[5:3]==group_id && valid_mask[group_id-1'b1])begin
    if(group_id<3)case(p[2:0])
     0:color=24'h3f3430;1:color=24'h55433a;2:color=24'h80604b;3:color=24'ha27960;
     4:color=24'hc09576;5:color=24'hd8ad8b;6:color=24'hecc5a4;7:color=24'hffe2c5;
    endcase
    else case(p[2:0])
     0:color=24'h20363c;1:color=24'h29464d;2:color=24'h375c65;3:color=24'h4e7e86;
     4:color=24'h639da6;5:color=24'h7cc9d2;6:color=24'ha8dce1;7:color=24'hd8f0ef;
    endcase
   end
  end
 endfunction
 reg [2:0] group_id;reg [9:0] xmin,ymin;
 reg [23:0] bottom_row,top_row,cur_color,left_color,top_color,corner_color;
 always @*begin
  applies=0;group_id=1;xmin=48;ymin=140;rgb=background;
  if(x>=48 && x<=283 && y>=140 && y<=449)begin applies=1;group_id=1;end
  else if(x>=306 && x<=541 && y>=140 && y<=449)begin applies=1;group_id=2;xmin=306;end
  else if(x>=628 && x<=733 && y>=148 && y<=279)begin applies=1;group_id=3;xmin=628;ymin=148;end
  cur_color=color(pixel,group_id,background);
  left_color=x>xmin?color(left,group_id,background):background;
  top_color=y>ymin?color(above,group_id,background):background;
  corner_color=x>xmin && y>ymin?color(above_left,group_id,background):background;
  bottom_row=x[0]?cur_color:average(left_color,cur_color);
  top_row=x[0]?top_color:average(corner_color,top_color);
  if(applies)rgb=y[0]?bottom_row:average(top_row,bottom_row);
 end
endmodule
`default_nettype wire
