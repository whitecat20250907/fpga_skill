`timescale 1ns/1ps
// Three simultaneous post-ISP crops, up to four compacted pixels per ROI per
// clock. Each lane has independent ready/valid retirement; a source beat is
// accepted only when all three elastic lanes can be replaced. No pixel is
// serialised or duplicated in time merely because it belongs to several ROIs.
module hci02_roi_quad #(
 parameter WIDTH=1920,HEIGHT=1080,MAX_EYE_WIDTH=256,MAX_EYE_HEIGHT=128,
 parameter MAX_FACE_WIDTH=448,MAX_FACE_HEIGHT=448
)(
 input wire clk,rst_n,input wire [127:0] s_data,input wire s_valid,s_sof,s_last,
 output wire s_ready,input wire [191:0] cfg_windows,input wire [2:0] cfg_enable,
 input wire [31:0] cfg_sequence,input wire [15:0] cfg_ttl,input wire cfg_valid,
 input wire [31:0] source_frame_id,input wire [63:0] source_time_us,
 input wire [2:0] m_ready,output reg [2:0] m_valid,m_sof,m_last,m_eof,
 output reg [383:0] m_data,output reg [95:0] m_gray,output reg [8:0] m_count,
 output reg [47:0] m_x,m_y,output wire [47:0] m_origin_x,m_origin_y,m_width,m_height,
 output wire [31:0] m_frame_id,m_config_sequence,output wire [63:0] m_time_us,
 output wire [7:0] m_flags,output wire [191:0] frame_windows,
 output wire [2:0] frame_enable,output wire [15:0] frame_ttl,
 output reg [31:0] frames,invalid_frames,stale_frames,errors
);
 reg [15:0] input_x,input_y,active_ttl;
 reg in_frame,seen_cfg;reg [191:0] active_windows;reg [2:0] active_enable;
 reg [31:0] active_sequence,config_age,frame_id;reg [63:0] frame_time;
 wire [2:0] advance=~m_valid|m_ready;
 assign s_ready=&advance;wire take=s_valid&&s_ready;
 wire [15:0] accepted_x=s_sof?0:input_x,accepted_y=s_sof?0:input_y;
 wire new_config=!seen_cfg||cfg_sequence!=active_sequence;
 wire [31:0] next_age=new_config?0:(&config_age?config_age:config_age+1'b1);
 function geometry_ok;
  input [191:0] windows;input [2:0] enable;
  integer j;reg [15:0] x,y,w,h;reg ok;
  begin ok=1;
   for(j=0;j<3;j=j+1)begin
    x=windows[j*64+:16];y=windows[j*64+16+:16];w=windows[j*64+32+:16];h=windows[j*64+48+:16];
    if(enable[j]&&(w==0||h==0||{1'b0,x}+{1'b0,w}>WIDTH||{1'b0,y}+{1'b0,h}>HEIGHT||
     w>(j==2?MAX_FACE_WIDTH:MAX_EYE_WIDTH)||h>(j==2?MAX_FACE_HEIGHT:MAX_EYE_HEIGHT)))ok=0;
   end
   geometry_ok=ok;
  end
 endfunction
 function [7:0] luminance;
  input [31:0] rgb;reg [15:0] q;
  begin q=16'd77*rgb[7:0]+16'd150*rgb[15:8]+16'd29*rgb[23:16]+16'd128;luminance=q[15:8];end
 endfunction
 wire geometry=geometry_ok(cfg_windows,cfg_enable);
 wire fresh=cfg_valid&&cfg_ttl!=0&&cfg_ttl<=4095&&next_age<cfg_ttl;
 wire [2:0] selected_enable=s_sof?((fresh&&geometry)?cfg_enable:3'd0):active_enable;
 wire [191:0] selected_windows=s_sof?cfg_windows:active_windows;
 reg [383:0] next_data;reg [95:0] next_gray;reg [8:0] next_count;
 reg [47:0] next_x,next_y;reg [2:0] next_sof,next_last,next_eof;
 integer r,k,n;reg [15:0] x,y,w,h,lx,ly;
 always @*begin
  next_data=0;next_gray=0;next_count=0;next_x=0;next_y=0;next_sof=0;next_last=0;next_eof=0;
  for(r=0;r<3;r=r+1)begin
   x=selected_windows[r*64+:16];y=selected_windows[r*64+16+:16];
   w=selected_windows[r*64+32+:16];h=selected_windows[r*64+48+:16];n=0;lx=0;ly=0;
   for(k=0;k<4;k=k+1)begin
    if(selected_enable[r]&&(in_frame||s_sof)&&{1'b0,accepted_x}+k>={1'b0,x}&&
     {1'b0,accepted_x}+k<{1'b0,x}+{1'b0,w}&&accepted_y>=y&&{1'b0,accepted_y}<{1'b0,y}+{1'b0,h})begin
     if(n==0)begin lx=accepted_x+k-x;ly=accepted_y-y;end
     next_data[r*128+n*32+:32]=s_data[k*32+:32];
     next_gray[r*32+n*8+:8]=luminance(s_data[k*32+:32]);n=n+1;
    end
   end
   next_count[r*3+:3]=n;next_x[r*16+:16]=lx;next_y[r*16+:16]=ly;
   next_sof[r]=n!=0&&lx==0&&ly==0;next_last[r]=n!=0&&lx+n==w;next_eof[r]=next_last[r]&&ly==h-1;
  end
 end
 genvar q;generate for(q=0;q<3;q=q+1)begin:metadata
  assign m_origin_x[q*16+:16]=active_windows[q*64+:16];assign m_origin_y[q*16+:16]=active_windows[q*64+16+:16];
  assign m_width[q*16+:16]=active_windows[q*64+32+:16];assign m_height[q*16+:16]=active_windows[q*64+48+:16];
 end endgenerate
 assign m_frame_id=frame_id;assign m_config_sequence=active_sequence;assign m_time_us=frame_time;
 assign m_flags={4'd0,1'b1,active_enable};assign frame_windows=active_windows;assign frame_enable=active_enable;assign frame_ttl=active_ttl;
 integer j;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   input_x<=0;input_y<=0;active_ttl<=0;in_frame<=0;seen_cfg<=0;active_windows<=0;active_enable<=0;
   active_sequence<=0;config_age<=0;frame_id<=0;frame_time<=0;m_valid<=0;m_sof<=0;m_last<=0;m_eof<=0;
   m_data<=0;m_gray<=0;m_count<=0;m_x<=0;m_y<=0;frames<=0;invalid_frames<=0;stale_frames<=0;errors<=0;
  end else begin
   for(j=0;j<3;j=j+1)if(advance[j])begin
    m_valid[j]<=take&&next_count[j*3+:3]!=0;
    m_sof[j]<=take&&next_sof[j];m_last[j]<=take&&next_last[j];m_eof[j]<=take&&next_eof[j];
    if(take)begin m_data[j*128+:128]<=next_data[j*128+:128];m_gray[j*32+:32]<=next_gray[j*32+:32];
     m_count[j*3+:3]<=next_count[j*3+:3];m_x[j*16+:16]<=next_x[j*16+:16];m_y[j*16+:16]<=next_y[j*16+:16];end
   end
   if(take)begin
    if(s_sof)begin
     if(in_frame)errors[1]<=1;
     frames<=frames+1'b1;in_frame<=1;seen_cfg<=1;active_windows<=cfg_windows;active_enable<=selected_enable;
     active_sequence<=cfg_sequence;config_age<=next_age;active_ttl<=cfg_ttl;frame_id<=source_frame_id;frame_time<=source_time_us;
     if(!cfg_valid||!geometry||cfg_enable==0||cfg_ttl==0||cfg_ttl>4095)invalid_frames<=invalid_frames+1'b1;
     else if(!fresh)stale_frames<=stale_frames+1'b1;
     if(cfg_valid&&!geometry)errors[3]<=1;
    end else if(!in_frame)errors[2]<=1;
    if(s_last!=(accepted_x==WIDTH-4))errors[0]<=1;
    if(s_last)begin input_x<=0;input_y<=accepted_y+1'b1;if(accepted_y==HEIGHT-1)in_frame<=0;end
    else begin input_x<=accepted_x+4;input_y<=accepted_y;end
   end
  end
 end
 // synthesis translate_off
 initial if(WIDTH<4||WIDTH%4!=0||WIDTH>4096||HEIGHT<1||HEIGHT>4095)$fatal(1,"Unsupported quad ROI source geometry");
 // synthesis translate_on
endmodule
