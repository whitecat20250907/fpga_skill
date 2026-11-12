`timescale 1ns/1ps
`default_nettype none
// Passive view of accepted RGB3 pixels. No ready output, and no model writes.
// mode 0: 640x360 -> 128x72, 1: face128 unchanged, 2: palm192 -> 96x96.
// Thumbnail decimation is DISPLAY ONLY. The inference tensor is untouched.
// Four byte lanes permit every accepted 4-pixel beat without a write queue.
module hmi_input_viewer(
 input wire src_clk,ui_clk,rst_n,input wire enable,input wire[1:0]mode,
 input wire fire,sof,eol,eof,input wire[2:0]count,input wire[95:0]rgb,
 input wire[31:0]frame_id,input wire[63:0]frame_tick,epoch,
 input wire ui_blank,input wire[31:0]ui_ms,
 input wire read_enable,input wire[6:0]read_x,read_y,
 output wire[7:0]pixel,output reg pixel_valid,
 output wire front_valid,output reg[1:0]front_mode,
 output reg[7:0]front_width,front_height,
 output reg[31:0]front_id,output reg[63:0]front_tick,front_epoch,
 output reg[31:0]completed,dropped,malformed
);
 (* async_reg="true" *) reg[2:0]src_up=0,ui_up=0;
 always @(posedge src_clk or negedge rst_n) if(!rst_n)src_up<=0;else src_up<={src_up[1:0],1'b1};
 always @(posedge ui_clk or negedge rst_n) if(!rst_n)ui_up<=0;else ui_up<={ui_up[1:0],1'b1};
 wire sr=src_up[2],ur=ui_up[2];
 // Passive two-stage display pipeline. All identity/geometry accompanies
 // its accepted pixels. There is still no ready output or inference delay.
 reg source_active,r_fire,p_fire,r_sof,r_eol,r_eof,p_sof,p_eol,p_eof;
 reg[2:0]r_count,p_count;reg[1:0]r_mode,p_mode;
 reg[95:0]r_rgb;reg[31:0]r_frame_id,p_frame_id;
 reg[63:0]r_frame_tick,p_frame_tick,r_epoch,p_epoch;
 reg[7:0]gray[0:3];wire[15:0]luma_pipe[0:3];
 always @(posedge src_clk or negedge sr)begin
  if(!sr)begin source_active<=0;r_fire<=0;p_fire<=0;end
  else begin source_active<=enable;r_fire<=fire&&source_active;p_fire<=r_fire&&source_active;end
 end
 always @(posedge src_clk)begin
  if(fire&&source_active)begin
   r_sof<=sof;r_eol<=eol;r_eof<=eof;r_count<=count;r_mode<=mode;r_rgb<=rgb;
   r_frame_id<=frame_id;r_frame_tick<=frame_tick;r_epoch<=epoch;
  end
  if(r_fire)begin
   p_sof<=r_sof;p_eol<=r_eol;p_eof<=r_eof;p_count<=r_count;p_mode<=r_mode;
   p_frame_id<=r_frame_id;p_frame_tick<=r_frame_tick;p_epoch<=r_epoch;
  end
 end
 genvar shade;
 generate for(shade=0;shade<4;shade=shade+1)begin: luma_stage
  assign luma_pipe[shade]=r_rgb[shade*24+:8]*16'd77+r_rgb[shade*24+8+:8]*16'd150+
      r_rgb[shade*24+16+:8]*16'd29+16'd128;
  always @(posedge src_clk)if(r_fire)gray[shade]<=luma_pipe[shade][15:8];
 end endgenerate
 reg request,ack,write_bank,front_bank,have_front,pending,active;
 (* async_reg="true" *) reg[1:0]ack_sync,request_sync,enabled_sync;
 always @(posedge src_clk or negedge sr) if(!sr)ack_sync<=0;else ack_sync<={ack_sync[0],ack};
 always @(posedge ui_clk or negedge ur) begin
  if(!ur)begin request_sync<=0;enabled_sync<=0;end
  else begin request_sync<={request_sync[0],request};enabled_sync<={enabled_sync[0],source_active};end
 end
 reg[1:0]held_mode;reg[31:0]held_id;reg[63:0]held_tick,held_epoch;
 reg[9:0]ix,iy;reg[6:0]ox,oy;reg[2:0]xphase,yphase;
 wire begin_frame=p_fire&&p_sof&&source_active&&!pending&&p_mode<3;
 wire taking=p_fire&&source_active&&!pending&&(active||begin_frame);
 wire[1:0]cm=begin_frame?p_mode:held_mode;
 wire[9:0]cx=begin_frame?0:ix,cy=begin_frame?0:iy;
 wire[6:0]dx=begin_frame?0:ox,dy=begin_frame?0:oy;
 wire[2:0]xp=begin_frame?0:xphase,yp=begin_frame?0:yphase;
 wire[9:0]width=cm==0?640:(cm==1?128:192),height=cm==0?360:(cm==1?128:192);
 wire[2:0]stride=cm==0?5:(cm==1?1:2);
 wire boundary_ok=p_count>=1&&p_count<=4&&cx+p_count<=width&&
  p_eol==(cx+p_count==width)&&p_eof==(p_eol&&cy==height-1)&&
  (begin_frame||(p_frame_id==held_id&&p_frame_tick==held_tick&&p_epoch==held_epoch&&p_mode==held_mode));
 reg[3:0]we;reg[11:0]wa[0:3];reg[7:0]wd[0:3];
 integer k,j,phase,next_x,out_count;
 always @* begin
  we=0;phase=xp;next_x=dx;out_count=0;
  for(j=0;j<4;j=j+1)begin wa[j]=0;wd[j]=0;end
  for(k=0;k<4;k=k+1)if(k<p_count)begin
   if(phase==0)begin
    // Address/data need not be zero when WE is low. Keeping permission out
    // of these muxes removes the packet-error -> address/data timing cone.
    wa[next_x%4]={dy,5'b0}+(next_x/4);wd[next_x%4]=gray[k];
    if(taking&&boundary_ok&&yp==0)we[next_x%4]=1;
    next_x=next_x+1;out_count=out_count+1;
   end
   phase=phase+1;if(phase==stride)phase=0;
  end
 end
 wire[12:0]read_addr={front_bank,read_y,read_x[6:2]};
 wire[31:0]lane_pixels;reg[1:0]read_lane;
 genvar lane;
 generate for(lane=0;lane<4;lane=lane+1)begin: storage
  (* ram_style="bram" *) reg[7:0]mem[0:8191];reg[7:0]q;
  always @(posedge src_clk)if(sr&&we[lane])mem[{write_bank,wa[lane]}]<=wd[lane];
  always @(posedge ui_clk)q<=mem[read_addr];
  assign lane_pixels[lane*8+:8]=q;
 end endgenerate
 assign pixel=lane_pixels[read_lane*8+:8];
 reg[31:0]arrival_ms;
 assign front_valid=have_front&&enabled_sync[1]&&(ui_ms-arrival_ms<500);
 always @(posedge ui_clk or negedge ur)begin
  if(!ur)begin ack<=0;front_bank<=0;have_front<=0;front_mode<=0;front_width<=0;front_height<=0;
   front_id<=0;front_tick<=0;front_epoch<=0;arrival_ms<=0;read_lane<=0;pixel_valid<=0;end
  else begin
   read_lane<=read_x[1:0];pixel_valid<=read_enable&&front_valid&&read_x<front_width&&read_y<front_height&&!ui_blank;
   if(!enabled_sync[1])have_front<=0;
   // Source holds both bank and metadata until this vblank ACK crosses back.
   if(ui_blank&&request_sync[1]!=ack)begin
    front_bank<=write_bank;front_mode<=held_mode;front_id<=held_id;front_tick<=held_tick;front_epoch<=held_epoch;
    front_width<=held_mode==2?96:128;front_height<=held_mode==0?72:(held_mode==1?128:96);
    arrival_ms<=ui_ms;have_front<=enabled_sync[1];ack<=request_sync[1];
   end
  end
 end
 always @(posedge src_clk or negedge sr)begin
  if(!sr)begin request<=0;write_bank<=0;pending<=0;active<=0;held_mode<=0;held_id<=0;held_tick<=0;held_epoch<=0;
   ix<=0;iy<=0;ox<=0;oy<=0;xphase<=0;yphase<=0;completed<=0;dropped<=0;malformed<=0;end
  else begin
   if(pending&&ack_sync[1]==request)begin pending<=0;write_bank<=!write_bank;end
   if(!source_active)active<=0;
   if(p_fire&&p_sof)begin
    if(!begin_frame)begin dropped<=dropped+1'b1;active<=0;end
    else begin
     if(active)malformed<=malformed+1'b1;
     held_mode<=p_mode;held_id<=p_frame_id;held_tick<=p_frame_tick;held_epoch<=p_epoch;
    end
   end
   if(taking)begin
    if(!boundary_ok)begin active<=0;malformed<=malformed+1'b1;end
    else begin
     active<=!p_eof;
     if(p_eol)begin
      ix<=0;ox<=0;xphase<=0;iy<=cy+1'b1;
      yphase<=yp==stride-1?0:yp+1'b1;oy<=dy+(yp==0?1'b1:1'b0);
     end else begin ix<=cx+p_count;ox<=next_x; xphase<=phase;iy<=cy;oy<=dy;yphase<=yp;end
     if(p_eof)begin request<=!request;pending<=1;completed<=completed+1'b1;end
    end
   end
  end
 end
endmodule
`default_nettype wire
