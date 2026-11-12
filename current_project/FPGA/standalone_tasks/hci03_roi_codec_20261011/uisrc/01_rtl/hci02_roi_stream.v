`timescale 1ns/1ps
// Three independently selected post-ISP ROIs. RGB is retained for the face;
// every ROI pixel also carries exact luminance for the eye measurement path.
// Config and a supplied source timestamp are captured ONLY on accepted SOF.
// Output serialises only selected pixels, including overlapping windows.
module hci02_roi_stream #(
 parameter WIDTH=1920,HEIGHT=1080,
 parameter MAX_EYE_WIDTH=256,MAX_EYE_HEIGHT=128,
 parameter MAX_FACE_WIDTH=448,MAX_FACE_HEIGHT=448,USE_SOURCE_FRAME_ID=0
)(
 input wire clk,rst_n,
 input wire [127:0] s_data,input wire s_valid,s_sof,s_last,
 output wire s_ready,
 // Each64bit descriptor: x16,y16,width16,height16, all little bit order.
 input wire [191:0] cfg_windows,input wire [2:0] cfg_enable,
 input wire [31:0] cfg_sequence,input wire [15:0] cfg_ttl,
 input wire cfg_valid,input wire [63:0] source_time_us,input wire [31:0] source_frame_id,
 input wire m_ready,output wire m_valid,
 output wire [31:0] m_data,output wire [7:0] m_gray,
 output wire [1:0] m_roi,
 output wire [15:0] m_x,m_y,m_origin_x,m_origin_y,m_width,m_height,
 output wire m_sof,m_last,m_eof,
 output wire [31:0] m_frame_id,m_config_sequence,
 output wire [63:0] m_time_us,output wire [7:0] m_flags,
 output wire [191:0] frame_windows,output wire [2:0] frame_enable,output wire [15:0] frame_ttl,
 output reg [31:0] frames,invalid_frames,stale_frames,errors
);
 reg [15:0] input_x,input_y;
 reg in_frame,seen_cfg;
 reg [191:0] active_windows;
 reg [2:0] active_enable;
 reg [31:0] active_sequence,config_age;
 reg [63:0] frame_time;
 reg [31:0] frame_tag_id;reg [15:0] active_ttl;
 reg [127:0] held_data;
 reg [15:0] held_x,held_y;
 reg [11:0] pending;
 wire take=s_valid&&s_ready;
 assign s_ready=pending==0;
 wire [15:0] accepted_x=s_sof?16'd0:input_x;
 wire [15:0] accepted_y=s_sof?16'd0:input_y;
 wire new_config=!seen_cfg||cfg_sequence!=active_sequence;
 wire [31:0] next_age=new_config?32'd0:(&config_age?config_age:config_age+1'b1);
 function geometry_ok;
  input [191:0] windows;input [2:0] enable;
  integer j;reg [15:0] x,y,w,h;reg ok;
  begin
   ok=1;
   for(j=0;j<3;j=j+1)begin
    x=windows[j*64+:16];y=windows[j*64+16+:16];
    w=windows[j*64+32+:16];h=windows[j*64+48+:16];
    if(enable[j]&&(w==0||h==0||{1'b0,x}+{1'b0,w}>WIDTH||{1'b0,y}+{1'b0,h}>HEIGHT||
       w>(j==2?MAX_FACE_WIDTH:MAX_EYE_WIDTH)||h>(j==2?MAX_FACE_HEIGHT:MAX_EYE_HEIGHT)))ok=0;
   end
   geometry_ok=ok;
  end
 endfunction
 wire geometry=geometry_ok(cfg_windows,cfg_enable);
 wire fresh=cfg_valid&&cfg_ttl!=0&&cfg_ttl<=4095&&next_age<cfg_ttl;
 wire [2:0] selected_enable=s_sof?((fresh&&geometry)?cfg_enable:3'd0):active_enable;
 wire [191:0] selected_windows=s_sof?cfg_windows:active_windows;
 reg [11:0] selected_pixels;
 integer r,k;reg [15:0] cx,cy,cw,ch;
 always @*begin
  selected_pixels=0;
  for(r=0;r<3;r=r+1)begin
   cx=selected_windows[r*64+:16];cy=selected_windows[r*64+16+:16];
   cw=selected_windows[r*64+32+:16];ch=selected_windows[r*64+48+:16];
   for(k=0;k<4;k=k+1)
    selected_pixels[r*4+k]=selected_enable[r]&&(in_frame||s_sof)&&
     ({1'b0,accepted_x}+k>={1'b0,cx})&&({1'b0,accepted_x}+k<{1'b0,cx}+{1'b0,cw})&&
     accepted_y>=cy&&({1'b0,accepted_y}<{1'b0,cy}+{1'b0,ch});
  end
 end
 reg [3:0] selection;reg found;integer j;
 always @*begin
  selection=0;found=0;
  for(j=0;j<12;j=j+1)if(pending[j]&&!found)begin selection=j;found=1;end
 end
 wire [1:0] selected_roi=selection[3:2];
 wire [63:0] descriptor=active_windows[selected_roi*64+:64];
 assign m_valid=|pending;
 assign m_roi=selected_roi;
 assign m_data=held_data[selection[1:0]*32+:32];
 wire [15:0] luminance=16'd77*m_data[7:0]+16'd150*m_data[15:8]+16'd29*m_data[23:16]+16'd128;
 assign m_gray=luminance[15:8];
 assign m_origin_x=descriptor[15:0];assign m_origin_y=descriptor[31:16];
 assign m_width=descriptor[47:32];assign m_height=descriptor[63:48];
 assign m_x=held_x+selection[1:0]-m_origin_x;
 assign m_y=held_y-m_origin_y;
 assign m_sof=m_x==0&&m_y==0;
 assign m_last=m_x==m_width-1'b1;
 assign m_eof=m_last&&m_y==m_height-1'b1;
 assign m_frame_id=frame_tag_id;assign m_config_sequence=active_sequence;
 assign m_time_us=frame_time;assign m_flags={4'd0,1'b1,active_enable};
 assign frame_windows=active_windows;assign frame_enable=active_enable;assign frame_ttl=active_ttl;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   input_x<=0;input_y<=0;in_frame<=0;seen_cfg<=0;active_windows<=0;
   active_enable<=0;active_sequence<=0;config_age<=0;frame_time<=0;frame_tag_id<=0;active_ttl<=0;
   held_data<=0;held_x<=0;held_y<=0;pending<=0;
   frames<=0;invalid_frames<=0;stale_frames<=0;errors<=0;
  end else begin
   if(m_valid&&m_ready)pending[selection]<=0;
   if(take)begin
    held_data<=s_data;held_x<=accepted_x;held_y<=accepted_y;pending<=selected_pixels;
    if(s_sof)begin
     if(in_frame)errors[1]<=1;
     frames<=frames+1'b1;in_frame<=1;active_windows<=cfg_windows;
     active_enable<=selected_enable;active_sequence<=cfg_sequence;config_age<=next_age;
     frame_time<=source_time_us;frame_tag_id<=USE_SOURCE_FRAME_ID?source_frame_id:frames+1'b1;active_ttl<=cfg_ttl;seen_cfg<=1;
     if(!cfg_valid||!geometry||cfg_enable==0||cfg_ttl==0||cfg_ttl>4095)invalid_frames<=invalid_frames+1'b1;
     else if(!fresh)stale_frames<=stale_frames+1'b1;
     if(cfg_valid&&!geometry)errors[3]<=1;
    end else if(!in_frame)errors[2]<=1;
    if(s_last!=(accepted_x==WIDTH-4))errors[0]<=1;
    if(s_last)begin
     input_x<=0;input_y<=accepted_y+1'b1;
     if(accepted_y==HEIGHT-1)in_frame<=0;
    end else begin input_x<=accepted_x+4;input_y<=accepted_y;end
   end
  end
 end
 // synthesis translate_off
 initial if(WIDTH<4||WIDTH%4!=0||WIDTH>4096||HEIGHT<1||HEIGHT>4095)$fatal(1,"Unsupported ROI source geometry");
 // synthesis translate_on
endmodule
