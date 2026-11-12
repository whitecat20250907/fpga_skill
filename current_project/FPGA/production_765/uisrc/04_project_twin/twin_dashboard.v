`timescale 1ns/1ps
`default_nettype none
// Application compositor. Geometry comes only from the existing HFT2 plane.
// No generated body, RGB framebuffer, inference or autonomous interaction.
// Exactly three pixel-clock cycles from input timing to output timing/RGB.
module twin_dashboard #(
 parameter TEXT_FILE="twin_text.mem",parameter FONT_FILE="twin_font.mem",parameter EXTERNAL_ARRIVAL=0
)(
 input wire clk,input wire rst,input wire [31:0] now_ms,
 input wire i_vs,input wire i_hs,input wire i_de,
 input wire csr_valid,input wire [31:0] csr_eye,input wire [31:0] csr_generation,
 input wire [31:0] csr_heat_context,csr_heat_sample,
 input wire[31:0]csr_pip,input wire[7:0]view_pixel,
 input wire view_pixel_valid,view_front_valid,input wire[1:0]view_mode,
 output wire view_read,output wire[6:0]view_x,view_y,
 input wire [31:0] csr_menu,csr_menu_lo,csr_menu_hi,csr_calibration,csr_phase,csr_errors,csr_hits,csr_quality,
 output wire [31:0] scene_generation,
 input wire rx_valid,input wire [7:0] rx_data,input wire [31:0] rx_ingress_ms,output wire rx_ready,
 output wire o_vs,output wire o_hs,output wire o_de,output reg [23:0] o_rgb,
 output reg [31:0] source_frames,
 output wire [31:0] accepted_packets,crc_errors,format_errors,sequence_errors,
 output wire [31:0] published_scenes,rejected_primitives,
 output wire [4:0] feature_valid_mask,output wire feature_front_ready
);
 localparam [23:0] BG=24'h101318,CARD=24'h181d24,CARD_INNER=24'h14191f,
  BORDER=24'h343e49,TEXT=24'hedf0f3,MUTED=24'hadb7c2,TEAL=24'h7cc9d2,AMBER=24'he5b878;
 wire view_panel=csr_valid&&csr_pip[0];
 function[7:0] view_label;
  input[1:0]kind;input integer col;input live;
  begin
   view_label=32;
   if(!live)begin case(col)0:view_label=87;1:view_label=65;2:view_label=73;3:view_label=84;endcase end
   else case(kind)
    0:case(col)0:view_label=82;1:view_label=71;2:view_label=66;endcase
    1:case(col)0:view_label=70;1:view_label=65;2:view_label=67;3:view_label=69;endcase
    2:case(col)0:view_label=80;1:view_label=65;2:view_label=76;3:view_label=77;endcase
   endcase
  end
 endfunction
 reg [9:0] x,y;reg de_old,vs_old;
 wire vblank=i_vs&&!vs_old;
 wire [17:0] video_addr=y<600?{y[9:1],x[9:1]}:18'd0;
 wire [5:0] feature_pixel;wire [4:0] valid_mask;
 wire front_ready,fixture,busy;
 assign feature_valid_mask=valid_mask;assign feature_front_ready=front_ready;
 wire [79:0] ages;wire [31:0] arrival,capture,eyes;
 wire [63:0] hand_ns,face_ns,epoch,seq;
 wire [1:0] actor_slot;wire [31:0] actor_track_id,ui_status,display_generation;
 wire [7:0] confidence,trajectory_points,association_flags;
 assign scene_generation=display_generation;
 reg [31:0] csr_seen,csr_arrival;
 always @(posedge clk)begin
  if(rst)begin csr_seen<=0;csr_arrival<=0;end
  else if(csr_valid && csr_generation!=csr_seen)begin csr_seen<=csr_generation;csr_arrival<=now_ms;end
 end
 wire lock_point=csr_valid && csr_eye[21] && (now_ms-csr_arrival<350);
 wire [9:0] lock_x=csr_eye[9:0],lock_y=csr_eye[19:10];
 twin_feature_plane #(.EXTERNAL_ARRIVAL(EXTERNAL_ARRIVAL)) u_plane(
  .clk(clk),.rst(rst),.now_ms(now_ms),.vblank(vblank),.rx_valid(rx_valid),.rx_data(rx_data),.rx_ready(rx_ready),.rx_ingress_ms(rx_ingress_ms),
  .video_addr(video_addr),.video_pixel(feature_pixel),.front_ready(front_ready),.front_valid_mask(valid_mask),.front_fixture(fixture),
  .front_source_ages(ages),.front_arrival_ms(arrival),.front_hand_ns(hand_ns),.front_face_ns(face_ns),.front_epoch(epoch),.front_sequence(seq),
  .front_capture_sequence(capture),.front_eye_metrics(eyes),.busy(busy),.published_scenes(published_scenes),.rejected_primitives(rejected_primitives),
  .accepted_packets(accepted_packets),.crc_errors(crc_errors),.format_errors(format_errors),.sequence_errors(sequence_errors),
  .front_actor_slot(actor_slot),.front_actor_track_id(actor_track_id),.front_ui_status(ui_status),.front_display_generation(display_generation),
  .front_confidence(confidence),.front_trajectory_points(trajectory_points),.front_association_flags(association_flags));
 reg [31:0] shown_scenes,shown_capture,shown_track,shown_status,shown_generation;
 reg [1:0] shown_actor;reg [7:0] shown_confidence,shown_points,shown_association;
 reg shown_ready,shown_fixture;reg [4:0] shown_mask;
 reg [9:0] shown_age[0:4];integer a;reg [32:0] age_sum;
 reg latch_hud;reg [15:0] shown_trace_age;
 always @(posedge clk)begin
  if(rst)begin
   x<=0;y<=0;de_old<=0;vs_old<=0;source_frames<=0;latch_hud<=0;shown_trace_age<=0;
   shown_scenes<=0;shown_capture<=32'hffffffff;shown_ready<=0;shown_fixture<=0;shown_mask<=0;
   shown_actor<=1;shown_track<=32'hffffffff;shown_status<=0;shown_generation<=0;
   shown_confidence<=0;shown_points<=0;shown_association<=0;
   for(a=0;a<5;a=a+1)shown_age[a]<=999;
  end else begin
   de_old<=i_de;vs_old<=i_vs;latch_hud<=vblank;
   if(!i_de)x<=0;else x<=x+1'b1;
   if(i_vs)y<=0;else if(de_old&&!i_de)y<=y+1'b1;
   if(vblank)source_frames<=source_frames+1'b1;
   // Raster and its metadata publish together at vblank. Latch one cycle
   // later while blanked, never splice another actor into an active frame.
   if(latch_hud)begin
    shown_scenes<=published_scenes;shown_capture<=capture;shown_ready<=front_ready;shown_fixture<=fixture;
    shown_actor<=front_ready?actor_slot:2'd1;shown_track<=actor_track_id;shown_status<=ui_status;shown_generation<=display_generation;
    shown_confidence<=confidence;shown_points<=trajectory_points;shown_association<=association_flags;
    if(published_scenes!=shown_scenes)shown_mask<=valid_mask;
    for(a=0;a<5;a=a+1)begin
     age_sum={17'd0,ages[a*16 +:16]}+{1'b0,(now_ms-arrival)};
     shown_age[a]<=age_sum>999?10'd999:age_sum[9:0];
     if(a==4)shown_trace_age<=age_sum>65535?16'hffff:age_sum[15:0];
    end
   end
  end
 end
 wire [4:0] visible_mask=shown_mask&valid_mask;
 wire registered=shown_ready&&visible_mask[2]&&shown_track!=32'hffffffff&&shown_association[0];
 wire real_projection=shown_ready&&visible_mask[3]&&shown_status[15]&&shown_status[14]&&shown_status[13];
 wire accepted_result=shown_ready&&visible_mask[4]&&shown_status[12]&&shown_status[3:0]==3&&shown_status[11:8]<8;
 reg [7:0] text_map[0:2431];initial $readmemh(TEXT_FILE,text_map);
 `include "dashboard_labels.vh"
 // Short stair-stepped circular corners: only compares/adds, no DSP squares.
 function rounded;
  input [9:0] xx,yy;input integer x0,y0,x1,y1;
  integer dx,dy,margin;
  begin
   rounded=0;dx=0;dy=0;margin=0;
   if(xx>=x0 && xx<x1 && yy>=y0 && yy<y1)begin
    dx=xx-x0;if(x1-1-xx<dx)dx=x1-1-xx;
    dy=yy-y0;if(y1-1-yy<dy)dy=y1-1-yy;
    case(dy)0:margin=6;1:margin=4;2:margin=2;3:margin=1;default:margin=0;endcase
    rounded=dx>=margin;
   end
  end
 endfunction
 function [23:0] pose_color;
  input [5:0] p;
  begin
   if(p[5:3]==1 || p[5:3]==2)begin
    case(p[2:0])
     0:pose_color=24'h3f3430;1:pose_color=24'h55433a;2:pose_color=24'h80604b;3:pose_color=24'ha27960;
     4:pose_color=24'hc09576;5:pose_color=24'hd8ad8b;6:pose_color=24'hecc5a4;7:pose_color=24'hffe2c5;
    endcase
   end else begin
    case(p[2:0])
     0:pose_color=24'h20363c;1:pose_color=24'h29464d;2:pose_color=24'h375c65;3:pose_color=24'h4e7e86;
     4:pose_color=24'h639da6;5:pose_color=TEAL;6:pose_color=24'ha8dce1;7:pose_color=24'hd8f0ef;
    endcase
   end
  end
 endfunction
 function [23:0] mix_aa;
  input [23:0] background,foreground;input [1:0] alpha;
  reg [9:0] rr,gg,bb;
  begin
   rr=0;gg=0;bb=0;
   case(alpha)
    0:mix_aa=background;
    1:begin rr=background[23:16]*3+foreground[23:16];gg=background[15:8]*3+foreground[15:8];bb=background[7:0]*3+foreground[7:0];mix_aa={rr[9:2],gg[9:2],bb[9:2]};end
    2:begin rr=background[23:16]+foreground[23:16]*3;gg=background[15:8]+foreground[15:8]*3;bb=background[7:0]+foreground[7:0]*3;mix_aa={rr[9:2],gg[9:2],bb[9:2]};end
    default:mix_aa=foreground;
   endcase
  end
 endfunction
 wire strip_visible;wire [23:0] strip_background,strip_ink;wire [7:0] strip_code;wire [3:0] strip_x,strip_y;
 twin_status_strip u_status_strip(.x(x),.y(y),
  .fresh(csr_valid && csr_generation==shown_generation && (now_ms-csr_arrival<350)),
  .menu(csr_menu),.menu_lo(csr_menu_lo),.menu_hi(csr_menu_hi),.calibration(csr_calibration),
  .phase(csr_phase),.errors(csr_errors),.hits(csr_hits),.quality(csr_quality),
  .visible(strip_visible),.background(strip_background),.ink(strip_ink),.code(strip_code),.glyph_x(strip_x),.glyph_y(strip_y));
 reg [23:0] base,ink;reg [7:0] code;reg [3:0] font_y,font_x;
 reg [5:0] msg;reg [5:0] pos;integer chip,origin,percent;
 reg active_chip;reg [9:0] text_col,text_row;integer eye_dx,eye_dy,eye_lid;
 always @*begin
  base=BG;ink=TEXT;code=32;font_y=y[3:0];font_x=x[3:0];msg=0;pos=0;chip=0;origin=0;percent=0;active_chip=0;
  text_col={4'd0,x[9:4]};text_row={4'd0,y[9:4]};eye_dx=0;eye_dy=0;eye_lid=0;
  if(y>=72 && y<600)code=text_map[{y[9:4],x[9:4]}];
  if(y>=64 && y<80)begin code=text_map[{y[9:4],x[9:4]}];ink=MUTED;end
  if(y<72)begin
   base=24'h14191f;
   if(y>=24 && y<56 && x>=32 && x<160)begin
    code=text_map[(x-32)>>5];font_y=(y-24)>>1;font_x=(x-32)>>1;
   end
   if(rounded(x,y,656,24,784,64))base=shown_actor==1?24'h203c43:24'h202730;
   if(rounded(x,y,800,24,928,64))base=shown_actor==2?24'h203c43:24'h202730;
   if(y>=32 && y<48 && ((x>=672 && x<768)||(x>=816 && x<912)))begin
    code=text_map[{y[9:4],x[9:4]}];ink=TEXT;
   end
   if(x>=960 && x<968 && y>=32 && y<56)base=registered?TEAL:MUTED;
  end
  if(rounded(x,y,32,80,176,102))base=24'h24333a;
  if(rounded(x,y,32,112,560,472))base=BORDER;
  if(rounded(x,y,33,113,559,471))base=CARD;
  if(rounded(x,y,608,112,1000,304))base=BORDER;
  if(rounded(x,y,609,113,999,303))base=CARD;
  if(rounded(x,y,608,320,1000,472))base=BORDER;
  if(rounded(x,y,609,321,999,471))base=CARD;
  if(x>=48 && x<284 && y>=140 && y<448)base=CARD_INNER;
  if(x>=306 && x<542 && y>=140 && y<448)base=CARD_INNER;
  if(x==294 && y>=148 && y<438)base=24'h343e49;
  if(x>=628 && x<734 && y>=148 && y<280)base=CARD_INNER;
  // Static single-eye / small-screen legend, not measured landmarks. Actual
  // calibrated gaze geometry is received as g3: eye(390,106) -> screen point
  // inside logical x420..484/y82..134. Uncalibrated packets carry no g3.
  if(x>=752 && x<982 && y>=148 && y<280)begin
   base=CARD_INNER;
   if(x>=832 && x<=981 && y>=160 && y<=275)begin
    if(x==832 || x==981 || y==160 || y==275)base=lock_point?AMBER:real_projection?24'h3f8b87:24'h35515d;
    if((x==906 && y>=168 && y<268)||(y==218 && x>=840 && x<974))base=24'h1c303d;
   end
   eye_dx=x>=780?x-780:780-x;eye_dy=y>=212?y-212:212-y;
   if(x>=756 && x<=804)begin
    eye_lid=eye_dx<8?12:(eye_dx<16?9:(eye_dx<22?5:1));
    if(eye_dy==eye_lid || eye_dy==eye_lid+1)base=MUTED;
    if(eye_dx<=5 && eye_dy<=6)base=24'h547d86;
    if(eye_dx<=2 && eye_dy<=3)base=TEXT;
   end
   if(!real_projection && !lock_point && x>=808 && x<832 && y==212 && x[2:0]<4)base=MUTED;
   if(!real_projection && !lock_point && x>=827 && x<=831 && (y==212-(831-x) || y==212+(831-x)))base=MUTED;
  end
  if(lock_point && x>=840 && x<=972 && y>=164 && y<=270)begin
   if((x+5>=lock_x && x<=lock_x+5 && (y==lock_y-4 || y==lock_y+4)) ||
      (y+4>=lock_y && y<=lock_y+4 && (x==lock_x-5 || x==lock_x+5)))base=AMBER;
  end
  if(x>=628 && x<982 && y>=324 && y<448)base=CARD_INNER;
  if(y>=576)begin base=24'h14181e;ink=MUTED;end
  // Eight result chips always name the supported classes. Only a source-
  // accepted RESULT highlights a chip or exposes its real confidence.
  for(chip=0;chip<8;chip=chip+1)begin
   origin=32+chip*120;active_chip=accepted_result&&shown_status[11:8]==chip;
   if(rounded(x,y,origin,496,origin+112,568))base=active_chip?24'h4c7f86:24'h202730;
   if(rounded(x,y,origin+1,497,origin+111,567))base=active_chip?24'h203c43:CARD;
   if(x>=origin+12 && x<origin+100 && y>=558 && y<561)begin
    base=24'h2c3c48;
    if(active_chip && x-origin-12<(shown_confidence*88)/255)base=TEAL;
   end
   if(y[9:4]==34 && x>=origin+24 && x<origin+88)begin
    // Chip origins alternate half a text cell. Use local glyph coordinates,
    // otherwise a percentage would change code halfway through a glyph.
    font_x=(x-origin-24)&15;code=8'd32;ink=active_chip?TEAL:MUTED;
    if(x>=origin+40 && x<origin+72)code=8'd45;
    percent=(shown_confidence*100)/255;
    if(active_chip)begin
     if(x<origin+40)code=percent==100?8'd49:8'd32;
     else if(x<origin+56)code=percent>=10?8'd48+(percent/10)%10:8'd32;
     else if(x<origin+72)code=8'd48+percent%10;
     else code=8'd37;
    end
   end
  end
  // Dynamic text rows use the same single AA ROM as all static labels.
  if(text_row==5 && text_col>=3 && text_col<11)begin
   msg=!shown_ready?4:(shown_status[17:16]==1?5:(shown_status[17:16]==2?6:4));pos=text_col-3;code=label_char(msg,pos);ink=TEAL;
  end
  if(text_row==5 && text_col>=48 && text_col<62)begin
   msg=!shown_ready?1:(shown_fixture?40:2);pos=text_col-48;code=label_char(msg,pos);ink=shown_fixture?AMBER:(registered?TEAL:MUTED);
  end
  if(text_row==7 && text_col>=25 && text_col<33)begin
   msg=7;
   if(shown_ready && (visible_mask[0]||visible_mask[1]))begin
    case(shown_status[7:4])0:msg=15;1:msg=8;2:msg=9;3:msg=10;4:msg=11;5:msg=12;6:msg=13;default:msg=15;endcase
   end
   pos=text_col-25;code=label_char(msg,pos);ink=AMBER;
  end
  if(text_row==18 && text_col>=39 && text_col<46)begin
   msg=visible_mask[2]?22:25;pos=text_col-39;code=label_char(msg,pos);ink=MUTED;
  end
  if(text_row==18 && text_col>=47 && text_col<62)begin
   msg=lock_point?49:(real_projection?50:51);pos=text_col-47;code=label_char(msg,pos);ink=lock_point?AMBER:(real_projection?TEAL:MUTED);
  end
  if(text_row==28 && ((text_col>=7 && text_col<16)||(text_col>=23 && text_col<33)))begin
   if(text_col<16)begin pos=text_col-7;msg=!shown_ready?7:(visible_mask[0]?26:25);end
   else begin pos=text_col-23;msg=!shown_ready?7:(visible_mask[1]?26:25);end
   code=label_char(msg,pos);ink=msg==26?TEAL:MUTED;
  end
  if(text_row==28 && text_col>=48 && text_col<62)begin
   msg=7;
   if(shown_ready && visible_mask[4])begin
    case(shown_status[3:0])0:msg=21;1:msg=17;2:msg=18;3:msg=shown_status[12]?19:20;4:msg=20;5:msg=16;default:msg=15;endcase
   end
   pos=text_col-48;code=label_char(msg,pos);ink=msg==19?TEAL:MUTED;
  end
  // Optional input inspector occupies the existing trajectory card only.
  // No layout moves, no synthetic image, all other viewports retain priority.
  if(view_panel&&x>=609&&x<999&&y>=321&&y<471)begin
   base=CARD;code=32;ink=MUTED;
   if(x>=847&&x<=976&&y>=327&&y<=456)base=BORDER;
   if(x>=848&&x<976&&y>=328&&y<456)base=CARD_INNER;
   if(x>=640&&x<736&&y>=344&&y<360)begin
    code=view_label(view_mode,(x-640)>>4,view_front_valid);font_x=x-640;font_y=y-344;ink=TEAL;
   end
   if(x>=640&&x<752&&y>=376&&y<392&&view_front_valid)begin
    font_x=x-640;font_y=y-376;
    // Dimensions of the actual source tensor, not the display thumbnail.
    case((x-640)>>4)
     0:code=view_mode==0?54:49;
     1:code=view_mode==0?52:(view_mode==1?50:57);
     2:code=view_mode==0?48:(view_mode==1?56:50);
     3:code=120;
     4:code=view_mode==0?51:49;
     5:code=view_mode==0?54:(view_mode==1?50:57);
     6:code=view_mode==0?48:(view_mode==1?56:50);
    endcase
   end
  end
  if(strip_visible)begin base=strip_background;ink=strip_ink;code=strip_code;font_x=strip_x;font_y=strip_y;end
 end
 reg [2:0] vs_pipe,hs_pipe,de_pipe;
 reg [7:0] char_code;reg [3:0] row_d1,bit_d1,bit_d2;
 wire [31:0] font_row;wire [1:0] alpha=font_row[(15-bit_d2)*2 +:2];
 reg [23:0] base_d1,base_d2,ink_d1,ink_d2;reg [23:0] pixel_base;
 reg [9:0] x_d1,x_d2,y_d1,y_d2;
 // RAM read starts at stage1, returns at stage2, and joins the existing
 // stage3 RGB register. Sync and feature rendering keep their three cycles.
 assign view_x=x_d1-10'd848;assign view_y=y_d1-10'd328;
 assign view_read=view_panel&&de_pipe[0]&&x_d1>=848&&x_d1<976&&y_d1>=328&&y_d1<456;
 wire view_area_d2=view_panel&&x_d2>=609&&x_d2<999&&y_d2>=321&&y_d2<471;
 wire [7:0] heat_level;wire heat_visible;
 reg [31:0] heat_generation;
 wire heat_snapshot=csr_valid && csr_generation==display_generation && csr_generation!=heat_generation;
 always @(posedge clk)if(rst)heat_generation<=0;else if(heat_snapshot)heat_generation<=csr_generation;
 twin_gaze_heatmap u_heatmap(.clk(clk),.rst(rst),.blank(i_vs),.now_ms(now_ms),
  .snapshot_valid(heat_snapshot),
  .context_id(csr_heat_context),.sample_word(csr_heat_sample),.x(x),.y(y),
  .level(heat_level),.visible(heat_visible));
 wire smooth_applies;wire [23:0] smooth_rgb;
 twin_pose_smooth u_pose_smooth(.clk(clk),.rst(rst),.ahead_x(x_d1[9:1]),
  .x(x_d2),.y(y_d2),.valid(de_pipe[1]),.pixel(feature_pixel),
  .valid_mask(valid_mask),.background(base_d2),.applies(smooth_applies),.rgb(smooth_rgb));
 twin_aa_glyph_rom #(.FONT_FILE(FONT_FILE)) u_glyph_rom(.clk(clk),.address({char_code,row_d1}),.data(font_row));
 assign o_vs=vs_pipe[2];assign o_hs=hs_pipe[2];assign o_de=de_pipe[2];
 // Fade only presentation of retained trail pixels. Existing source expiry,
 // accepted-result state, execution and cancellation remain authoritative.
 reg [2:0] trace_level;reg [9:0] fade_r,fade_g,fade_b;
 always @*begin
  if(shown_status[3:0]==3 || shown_status[3:0]==4)
   trace_level=shown_trace_age<500?4:shown_trace_age<700?3:shown_trace_age<900?2:1;
  else trace_level=shown_trace_age<150?4:shown_trace_age<225?3:shown_trace_age<300?2:1;
 end
 always @*begin
  pixel_base=base_d2;fade_r=0;fade_g=0;fade_b=0;
  if(heat_visible && base_d2==CARD_INNER)begin
   case(heat_level)
    1:pixel_base=24'h172a30;2:pixel_base=24'h1b3b42;3:pixel_base=24'h24545a;
    4:pixel_base=24'h396b68;5:pixel_base=24'h657b66;6:pixel_base=24'h9a9369;
    7:pixel_base=24'hc5a575;default:pixel_base=base_d2;
   endcase
  end
  if(feature_pixel[5:3]>=1 && feature_pixel[5:3]<=5 && valid_mask[feature_pixel[5:3]-1'b1])pixel_base=pose_color(feature_pixel);
  if(smooth_applies)pixel_base=smooth_rgb;
  if(feature_pixel[5:3]==5 && valid_mask[4])begin
   fade_r={2'd0,pixel_base[23:16]}*trace_level+{2'd0,base_d2[23:16]}*(4-trace_level);
   fade_g={2'd0,pixel_base[15:8]}*trace_level+{2'd0,base_d2[15:8]}*(4-trace_level);
   fade_b={2'd0,pixel_base[7:0]}*trace_level+{2'd0,base_d2[7:0]}*(4-trace_level);
   pixel_base={fade_r[9:2],fade_g[9:2],fade_b[9:2]};
  end
  if(view_area_d2)pixel_base=base_d2;
  if(view_area_d2&&view_pixel_valid)pixel_base={view_pixel,view_pixel,view_pixel};
 end
 always @(posedge clk)begin
  if(rst)begin
   vs_pipe<=0;hs_pipe<=0;de_pipe<=0;char_code<=32;row_d1<=0;bit_d1<=0;bit_d2<=0;
   base_d1<=0;base_d2<=0;ink_d1<=0;ink_d2<=0;o_rgb<=0;x_d1<=0;x_d2<=0;y_d1<=0;y_d2<=0;
  end else begin
   vs_pipe<={vs_pipe[1:0],i_vs};hs_pipe<={hs_pipe[1:0],i_hs};de_pipe<={de_pipe[1:0],i_de};
   char_code<=code;row_d1<=font_y;bit_d1<=font_x;bit_d2<=bit_d1;
   x_d1<=x;x_d2<=x_d1;y_d1<=y;y_d2<=y_d1;
   base_d1<=base;base_d2<=base_d1;ink_d1<=ink;ink_d2<=ink_d1;
   o_rgb<=de_pipe[1]?mix_aa(pixel_base,ink_d2,alpha):24'd0;
  end
 end
endmodule
`default_nettype wire
