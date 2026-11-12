// Passive four-pixel RGB10 tap. No ready output and no image-path modification.
// All ports are in clk. ROI command is latched only on an accepted SOF.
// A new command refreshes a three-frame lease; invalid/expired ROI yields no stats.
`timescale 1ns/1ps
module roi_luma_stats(
 input wire clk,input wire rst_n,input wire fire,input wire sof,input wire eol,
 input wire [119:0] rgb,input wire [12:0] width,height,
 input wire enable,input wire [31:0] command_id,source_frame,
 input wire [12:0] x0,y0,x1,y1,
 output reg [31:0] stats_seq,frame_id,command_used,source_used,
 output reg valid,output reg [31:0] pixels,output reg [63:0] sum,
 output wire [511:0] histogram
);
 reg [12:0] x,y,ax0,ay0,ax1,ay1,aw,ah;
 reg active,good;reg [2:0] lease;reg [31:0] cmd,src,frame;
 reg [31:0] count,hist_acc[0:15],published[0:15];reg [63:0] total;
 integer i,j;reg [12:0] px,py,lx0,ly0,lx1,ly1,w,h;
 reg enabled,shape_ok;reg [2:0] next_lease,n;
 reg [17:0] weighted;
 reg [9:0] p_luma[0:3];reg [3:0] inside_now,p_inside;
 reg [12:0] group_sum;reg [2:0] additions[0:15];reg [31:0] new_count;
 reg [63:0] new_sum;
 reg q_fire,q_sof,q_end,q_enabled,q_good,q_clear;
 reg [2:0] q_n,q_additions[0:15];reg [12:0] q_sum;
 reg [25:0] q_area;reg [31:0] q_frame,q_command,q_source;
 reg p_fire,p_sof,p_end,p_enabled,p_good,p_clear;
 reg [25:0] p_area;reg [31:0] p_frame,p_command,p_source;
 integer a;
 integer lane,bucket;
 // Statistics-only pipeline: all published outputs trail the passive tap by
 // exactly two clocks. The image stream has no dependency on this module.
 always @* begin
  new_count=(q_sof?32'd0:count)+q_n;
  new_sum=(q_sof?64'd0:total)+q_sum;
 end
 genvar g;generate for(g=0;g<16;g=g+1)begin
  assign histogram[g*32+:32]=published[g];
 end endgenerate
 always @* begin
  px=sof?13'd0:x;py=sof?13'd0:y;
  lx0=sof?x0:ax0;ly0=sof?y0:ay0;lx1=sof?x1:ax1;ly1=sof?y1:ay1;
  w=sof?width:aw;h=sof?height:ah;
  next_lease=command_id!=cmd?3'd3:(lease!=0?lease-1'b1:3'd0);
  enabled=sof?(enable&&next_lease!=0&&x0<x1&&y0<y1&&x1<=width&&y1<=height):active;
  shape_ok=(w!=0&&h!=0&&w[1:0]==0&&py<h&&px+4<=w&&eol==(px+4==w));
  inside_now=0;
  for(j=0;j<4;j=j+1)
   inside_now[j]=enabled&&px+j>=lx0&&px+j<lx1&&py>=ly0&&py<ly1;
 end
 // Four constant products end at p_luma. Bucket decode and population counts
 // are a separate register stage, not a multiplier-to-indexed-adder cascade.
 always @* begin
  n={2'b0,p_inside[0]}+{2'b0,p_inside[1]}+{2'b0,p_inside[2]}+{2'b0,p_inside[3]};
  group_sum=({3'b0,p_luma[0]} & {13{p_inside[0]}})+({3'b0,p_luma[1]} & {13{p_inside[1]}})
           +({3'b0,p_luma[2]} & {13{p_inside[2]}})+({3'b0,p_luma[3]} & {13{p_inside[3]}});
  for(bucket=0;bucket<16;bucket=bucket+1)
   additions[bucket]={2'b0,(p_inside[0]&&p_luma[0][9:6]==bucket)}+{2'b0,(p_inside[1]&&p_luma[1][9:6]==bucket)}
               +{2'b0,(p_inside[2]&&p_luma[2][9:6]==bucket)}+{2'b0,(p_inside[3]&&p_luma[3][9:6]==bucket)};
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   x<=0;y<=0;ax0<=0;ay0<=0;ax1<=0;ay1<=0;aw<=0;ah<=0;
   active<=0;good<=0;lease<=0;cmd<=0;src<=0;frame<=0;
   p_fire<=0;p_sof<=0;p_end<=0;p_enabled<=0;p_good<=0;p_clear<=0;
   p_inside<=0;p_area<=0;p_frame<=0;p_command<=0;p_source<=0;
   for(i=0;i<4;i=i+1)p_luma[i]<=0;
  end else begin
   p_fire<=fire;
   if(fire)begin
    p_sof<=sof;p_end<=eol&&py+1==h;p_enabled<=enabled;
    p_good<=(sof?1'b1:good)&&shape_ok;
    p_clear<=sof&&(!enabled||command_id!=cmd);
    p_inside<=inside_now;p_area<=(lx1-lx0)*(ly1-ly0);
    p_frame<=sof?frame+1'b1:frame;p_command<=sof?command_id:cmd;p_source<=sof?source_frame:src;
    for(i=0;i<4;i=i+1)begin
     weighted=18'd54*rgb[i*30+20+:10]+18'd183*rgb[i*30+10+:10]+18'd19*rgb[i*30+:10];
     p_luma[i]<=weighted[17:8];
    end
    if(sof)begin
     ax0<=x0;ay0<=y0;ax1<=x1;ay1<=y1;aw<=width;ah<=height;
     active<=enabled;lease<=next_lease;cmd<=command_id;src<=source_frame;frame<=frame+1'b1;
    end
    good<=(sof?1'b1:good)&&shape_ok;
    x<=eol?13'd0:px+13'd4;y<=eol?py+1'b1:py;
   end
  end
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   q_fire<=0;q_sof<=0;q_end<=0;q_enabled<=0;q_good<=0;q_clear<=0;
   q_n<=0;q_sum<=0;q_area<=0;q_frame<=0;q_command<=0;q_source<=0;
   for(lane=0;lane<16;lane=lane+1)q_additions[lane]<=0;
  end else begin
   q_fire<=p_fire;
   if(p_fire)begin
    q_sof<=p_sof;q_end<=p_end;q_enabled<=p_enabled;q_good<=p_good;q_clear<=p_clear;
    q_n<=n;q_sum<=group_sum;q_area<=p_area;q_frame<=p_frame;q_command<=p_command;q_source<=p_source;
    for(lane=0;lane<16;lane=lane+1)q_additions[lane]<=additions[lane];
   end
  end
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   stats_seq<=0;frame_id<=0;command_used<=0;source_used<=0;valid<=0;
   count<=0;total<=0;pixels<=0;sum<=0;
   for(a=0;a<16;a=a+1)begin hist_acc[a]<=0;published[a]<=0;end
  end else if(q_fire)begin
   if(q_clear)valid<=0;
   count<=new_count;total<=new_sum;
   for(a=0;a<16;a=a+1)hist_acc[a]<=(q_sof?32'd0:hist_acc[a])+q_additions[a];
   if(q_end)begin
    stats_seq<=stats_seq+1'b1;frame_id<=q_frame;
    command_used<=q_command;source_used<=q_source;
    valid<=q_enabled&&q_good&&new_count==q_area;
    pixels<=new_count;sum<=new_sum;
    for(a=0;a<16;a=a+1)published[a]<=(q_sof?32'd0:hist_acc[a])+q_additions[a];
   end
  end
 end
endmodule
