`timescale 1ns/1ps
`default_nettype none
// Two losslessly cropped 512x300 planes (unchanged logical coordinates). XYZ is projected in hardware; geometry is drawn
// into the back plane and published only at vsync. Group tags allow stale or
// lost hands/face/eyes to disappear independently without retaining a pose.
module twin_raster #(
 parameter integer MAX_AGE_MS=350
)(
 input wire clk,input wire rst,input wire [31:0] now_ms,input wire vblank,
 input wire scene_valid,output reg scene_release,
 input wire [7:0] vertex_count,edge_count,triangle_count,
 input wire [4:0] valid_mask,input wire fixture,
 input wire [79:0] source_ages,input wire [159:0] group_offsets,
 input wire [63:0] source_hand_ns,source_face_ns,session_epoch,scene_sequence,
 input wire [31:0] source_capture_sequence,eye_metrics,arrival_ms,
 input wire [1:0] actor_slot,input wire [31:0] actor_track_id,ui_status,display_generation,
 input wire [7:0] classification_confidence,trajectory_points,association_flags,
 input wire [4:0] invalidate_mask,input wire epoch_changed,
 output reg [6:0] vertex_addr,input wire [50:0] vertex_data,
 output reg [6:0] edge_addr,input wire [17:0] edge_data,
 output reg [5:0] triangle_addr,input wire [25:0] triangle_data,
 input wire [17:0] video_addr,output wire [5:0] video_pixel,
 output reg front_ready,output reg [4:0] front_valid_mask,output reg front_fixture,
 output reg [79:0] front_source_ages,output reg [31:0] front_arrival_ms,
 output reg [63:0] front_hand_ns,front_face_ns,front_epoch,front_sequence,
 output reg [31:0] front_capture_sequence,front_eye_metrics,
 output reg [1:0] front_actor_slot,output reg [31:0] front_actor_track_id,front_ui_status,front_display_generation,
 output reg [7:0] front_confidence,front_trajectory_points,front_association_flags,
 output wire busy,output reg [31:0] published_scenes,rejected_primitives
);
 localparam IDLE=0,CLEAR=1,VREQ=2,VWAIT=3,VPROJ0=4,VPROJ1=5,VSTORE=6,
  TREQ=7,TWAIT=8,TLATCH=9,TSETUP=10,TSCAN=11,ENEXT=12,
  EREQ=13,EWAIT=14,ELATCH=15,ESETUP=16,ESTAMP=17,ESTEP=18,
  DNEXT=19,DSTAMP=20,PUBLISH=21,RELEASE=22,TBOUNDS=23,TXDIV=24,TXWAIT=25,TYDIV=26,TYWAIT=27,EZDIV=28,EZWAIT=29,DRAIN=30,LDIV=31,LWAIT=32,LXDIV=33,LXWAIT=34,LYDIV=35,LYWAIT=36,TLOAD_B=37,TLOAD_C=38,ELOAD_B=39,LACC_A=40,LACC_B=41,LACC_C=42;
 reg [5:0] state;
 reg front_bank,back_bank;
 reg [7:0] nv,ne,nt,vertex_index,edge_index,triangle_index,dot_index;
 reg [17:0] clear_address;
 // Clear only the five disjoint stored viewports, one pixel per clock.
 // Their coordinates match compact_storage; geometry and video addressing stay unchanged.
 reg [2:0] clear_group;
 reg [8:0] clear_left,clear_right,clear_bottom;
 reg [17:0] clear_next_group;
 wire [8:0] clear_next_row=clear_address[17:9]+9'd1;
 always @*begin
  clear_left=314;clear_right=490;clear_bottom=224;clear_next_group=0;
  case(clear_group)
   0:begin clear_left=24;clear_right=141;clear_bottom=224;clear_next_group={9'd70,9'd153};end
   1:begin clear_left=153;clear_right=270;clear_bottom=224;clear_next_group={9'd74,9'd314};end
   2:begin clear_left=314;clear_right=366;clear_bottom=139;clear_next_group={9'd74,9'd376};end
   3:begin clear_left=376;clear_right=490;clear_bottom=139;clear_next_group={9'd162,9'd314};end
   default:begin end
  endcase
 end
 reg [4:0] work_valid,work_seen;reg work_fixture;
 reg [79:0] work_ages;reg [159:0] work_offsets;
 reg [63:0] work_hand_ns,work_face_ns,work_epoch,work_sequence;
 reg [31:0] work_capture,work_eyes,work_arrival;
 reg [1:0] work_actor_slot;reg [31:0] work_actor_track_id,work_ui_status,work_display_generation;
 reg [7:0] work_confidence,work_trajectory_points,work_association_flags;
 reg signed [23:0] pz[0:127];
 reg signed [10:0] px[0:127],py[0:127];reg [2:0] pg[0:127];
 reg pv[0:127];reg [1:0] point_style[0:127];
 reg signed [31:0] projection_x,projection_z,projection_y,projection_depth;
 reg signed [15:0] input_y;reg [2:0] input_group;
 wire signed [31:0] vx=$signed(projection_x)>>>12;
 wire signed [31:0] vy=$signed(projection_y)>>>12;
 wire signed [15:0] ox=work_offsets[input_group*32 +:16];
 wire signed [15:0] oy=work_offsets[input_group*32+16 +:16];
 wire signed [31:0] screen_x=vx+$signed(ox),screen_y=vy+$signed(oy);
 function in_viewport;
  input [2:0] group_id;input signed [31:0] x,y;
  begin
   case(group_id)
    0:in_viewport=x>=24 && x<=141 && y>=70 && y<=224;
    1:in_viewport=x>=153 && x<=270 && y>=70 && y<=224;
    2:in_viewport=x>=314 && x<=366 && y>=74 && y<=139;
    3:in_viewport=x>=376 && x<=490 && y>=74 && y<=139;
    4:in_viewport=x>=314 && x<=490 && y>=162 && y<=224;
    default:in_viewport=0;
   endcase
  end
 endfunction
 function signed [10:0] min3;
  input signed [10:0] a,b,c;begin min3=a<b?(a<c?a:c):(b<c?b:c);end
 endfunction
 function signed [10:0] max3;
  input signed [10:0] a,b,c;begin max3=a>b?(a>c?a:c):(b>c?b:c);end
 endfunction
 reg signed [10:0] ax,ay,bx,by,cx,cy;
 reg signed [10:0] xmin,xmax,ymin,ymax,scan_x,scan_y;
 reg signed [24:0] e0,e1,e2,row0,row1,row2;
 reg signed [11:0] step_x0,step_x1,step_x2,step_y0,step_y1,step_y2;
 reg [2:0] draw_group;reg [1:0] draw_shade;
 reg signed [31:0] az,bz,cz,tri_area,tri_nx,tri_ny;
 reg signed [31:0] gradient_x,gradient_y,row_depth,scan_depth;
 reg signed [31:0] line_depth,target_depth,line_depth_step;
 reg [2:0] triangle_shade;
 reg light_pass;reg [6:0] ia,ib,ic;
 reg [10:0] la,lb,lc,face_light;
 // Each scene primitive is serial already. Three vertex attributes are fetched
 // in three clocks rather than replicating whole memories for three ports.
 wire [6:0] depth_addr=state==TLOAD_B ? ib : state==TLOAD_C ? ic :
   state==ELATCH ? edge_data[6:0] : state==ELOAD_B ? edge_data[14:8] :
   state==DNEXT ? dot_index[6:0] : triangle_data[6:0];
 wire signed [23:0] depth_read=pz[depth_addr];
 wire [6:0] sum_addr=state==LACC_A ? ia : state==LACC_B ? ib : state==LACC_C ? ic : vertex_index[6:0];
 reg [17:0] light_sum[0:127];reg [6:0] light_count[0:127];reg [10:0] vertex_light[0:127];
 wire [17:0] sum_read=light_sum[sum_addr];
 wire [6:0] count_read=light_count[sum_addr];
 wire [10:0] light_read=vertex_light[depth_addr];
 reg signed [31:0] light_a,light_nx,light_ny,light_gx,light_gy,light_row,light_scan;
 function [10:0] surface_light;
  input signed [31:0] slope;reg signed [31:0] level;
  begin level=1280-(slope>>>1);surface_light=level<512 ? 11'd512 : level>1792 ? 11'd1792 : level[10:0];end
 endfunction
 function [2:0] quantize_light;
  input signed [31:0] value;reg signed [31:0] level;
  begin level=(value+128)>>>8;quantize_light=level<1 ? 3'd1 : level>7 ? 3'd7 : level[2:0];end
 endfunction
 reg div_start;reg signed [31:0] div_n,div_d;
 wire div_busy,div_done,div_zero,div_overflow;wire signed [31:0] div_q;
 twin_signed_divider u_setup_divider(clk,rst,div_start,div_n,div_d,div_busy,div_done,div_q,div_zero,div_overflow);
 function [9:0] quantize_depth;
  input signed [31:0] q8;reg signed [31:0] value;
  begin value=(q8>>>6)+512;quantize_depth=value<0 ? 10'd0 : value>1022 ? 10'd1022 : value[9:0];end
 endfunction
 function [2:0] diffuse_shade;
  input signed [31:0] slope;
  begin
   if(slope < -256)diffuse_shade=7;else if(slope < -128)diffuse_shade=6;
   else if(slope < 0)diffuse_shade=5;else if(slope < 128)diffuse_shade=4;
   else if(slope < 256)diffuse_shade=3;else diffuse_shade=2;
  end
 endfunction
 reg signed [10:0] line_x,line_y,target_x,target_y;
 reg signed [11:0] dx,dy,step_sx,step_sy,line_error;
 wire signed [12:0] twice_error=$signed(line_error)*13'sd2;
 reg [6:0] stamp;
 reg signed [31:0] stamp_x,stamp_y;
 reg wr_en;reg [17:0] wr_addr;reg [5:0] wr_pixel;
 // Skin capsules use the actual projected bones, not generated animation.
 // Radius four logical pixels (eight panel pixels); four stored shade codes.
 reg signed [31:0] disk_dx,disk_dy;
 reg [6:0] disk_distance;reg [2:0] skin_shade;
 function [5:0] square_small;
  input signed [31:0] value;
  begin
   case(value)
    -4,4:square_small=16;-3,3:square_small=9;
    -2,2:square_small=4;-1,1:square_small=1;
    0:square_small=0;default:square_small=63;
   endcase
  end
 endfunction

 wire triangle_inside=(e0>=0 && e1>=0 && e2>=0)||(e0<=0 && e1<=0 && e2<=0);
 always @* begin
  wr_en=0;wr_addr=0;wr_pixel=0;stamp_x=0;stamp_y=0;disk_dx=0;disk_dy=0;disk_distance=0;skin_shade=0;
  if(state==CLEAR)begin wr_en=1;wr_addr=clear_address;end
  if(state==TSCAN && triangle_inside)begin
   wr_en=1;wr_addr={scan_y[8:0],scan_x[8:0]};wr_pixel={(draw_group+3'd1),(draw_group<3 ? quantize_light(light_scan) : {draw_shade,1'b1})};
  end
  if(state==ESTAMP)begin stamp_x=$signed(line_x)+$signed({31'd0,stamp[0]});stamp_y=$signed(line_y)+$signed({31'd0,stamp[1]});end
  if(state==DSTAMP)begin
   case(stamp)
    0:begin stamp_x=$signed(line_x)-1;stamp_y=$signed(line_y)-1;end
    1:begin stamp_x=$signed(line_x);stamp_y=$signed(line_y)-1;end
    2:begin stamp_x=$signed(line_x)+1;stamp_y=$signed(line_y)-1;end
    3:begin stamp_x=$signed(line_x)-1;stamp_y=$signed(line_y);end
    4:begin stamp_x=$signed(line_x);stamp_y=$signed(line_y);end
    5:begin stamp_x=$signed(line_x)+1;stamp_y=$signed(line_y);end
    6:begin stamp_x=$signed(line_x)-1;stamp_y=$signed(line_y)+1;end
    7:begin stamp_x=$signed(line_x);stamp_y=$signed(line_y)+1;end
    default:begin stamp_x=$signed(line_x)+1;stamp_y=$signed(line_y)+1;end
   endcase
  end
  if((state==ESTAMP || state==DSTAMP) && draw_group<2)begin
   disk_dx=$signed({25'd0,(stamp%7'd9)})-32'sd4;
   disk_dy=$signed({25'd0,(stamp/7'd9)})-32'sd4;
   disk_distance=square_small(disk_dx)+square_small(disk_dy);
   stamp_x=$signed(line_x)+disk_dx;stamp_y=$signed(line_y)+disk_dy;
   // Radial coverage at the contour and directional diffuse/specular bands.
   // The outer shades are preblended with the viewport background.
   if(disk_distance>14)skin_shade=1;
   else if(disk_distance>11)skin_shade=2;
   else if(disk_dx>=-2 && disk_dx<=0 && disk_dy>=-2 && disk_dy<=0)skin_shade=7;
   else if(disk_dx+disk_dy<0)skin_shade=6;
   else if(disk_dx+disk_dy<3)skin_shade=5;
   else skin_shade=3;
  end
  if((state==ESTAMP || state==DSTAMP) && (draw_group>=2 || disk_distance<=16) && in_viewport(draw_group,stamp_x,stamp_y))begin
   wr_en=1;wr_addr={stamp_y[8:0],stamp_x[8:0]};wr_pixel={(draw_group+3'd1),(draw_group<2 ? skin_shade : {draw_shade,1'b1})};
  end
 end
 wire filtered_en,depth_busy;wire [17:0] filtered_addr;wire [5:0] filtered_pixel;
 wire signed [31:0] capsule_front=disk_distance<2 ? 32'sd1024 : disk_distance<8 ? 32'sd768 : disk_distance<13 ? 32'sd512 : 32'sd256;
 wire signed [31:0] fragment_q8=state==TSCAN ? scan_depth : line_depth-(draw_group<2 ? capsule_front : 32'sd256);
 twin_depth_test u_depth_test(.clk(clk),.rst(rst),.in_valid(wr_en),.in_clear(state==CLEAR),
  .in_test(draw_group<3),.in_address(wr_addr),.in_pixel(wr_pixel),.in_depth(quantize_depth(fragment_q8)),
  .out_valid(filtered_en),.out_address(filtered_addr),.out_pixel(filtered_pixel),.busy(depth_busy));
 twin_crop_storage_app_v1 u_compact_storage(
  .clk(clk),.wr_en(filtered_en),.wr_addr(filtered_addr),.wr_pixel(filtered_pixel),
  .back_bank(back_bank),.front_bank(front_bank),.front_ready(front_ready),
  .video_addr(video_addr),.video_pixel(video_pixel));
 assign busy=state!=IDLE;
 reg [4:0] retained_mask,publish_mask;
 integer g;
 always @* begin
  retained_mask=front_valid_mask&~invalidate_mask;
  publish_mask=work_valid&work_seen&~invalidate_mask;
  for(g=0;g<5;g=g+1)begin
   if({17'd0,front_source_ages[g*16 +:16]}+{1'b0,(now_ms-front_arrival_ms)}>((g==4 && (front_ui_status[3:0]==3 || front_ui_status[3:0]==4)) ? 1200 : MAX_AGE_MS))retained_mask[g]=0;
   if({17'd0,work_ages[g*16 +:16]}+{1'b0,(now_ms-work_arrival)}>((g==4 && (work_ui_status[3:0]==3 || work_ui_status[3:0]==4)) ? 1200 : MAX_AGE_MS))publish_mask[g]=0;
  end
  if(epoch_changed)begin retained_mask=0;publish_mask=0;end
 end
 always @(posedge clk)begin
  if(rst)begin
   state<=IDLE;front_bank<=0;back_bank<=1;scene_release<=0;front_ready<=0;front_valid_mask<=0;front_fixture<=0;
   front_source_ages<=0;front_arrival_ms<=0;front_hand_ns<=0;front_face_ns<=0;front_epoch<=0;front_sequence<=0;
   front_capture_sequence<=32'hffffffff;front_eye_metrics<=0;published_scenes<=0;rejected_primitives<=0;
   vertex_addr<=0;edge_addr<=0;triangle_addr<=0;clear_address<=0;clear_group<=0;
   nv<=0;ne<=0;nt<=0;vertex_index<=0;edge_index<=0;triangle_index<=0;dot_index<=0;stamp<=0;
   work_valid<=0;work_seen<=0;work_fixture<=0;work_ages<=0;work_offsets<=0;work_hand_ns<=0;work_face_ns<=0;
   work_epoch<=0;work_sequence<=0;work_capture<=0;work_eyes<=0;work_arrival<=0;
   front_actor_slot<=1;front_actor_track_id<=32'hffffffff;front_ui_status<=32'h00000f00;front_display_generation<=0;
   front_confidence<=0;front_trajectory_points<=0;front_association_flags<=0;
   work_actor_slot<=1;work_actor_track_id<=32'hffffffff;work_ui_status<=32'h00000f00;work_display_generation<=0;
   work_confidence<=0;work_trajectory_points<=0;work_association_flags<=0;
   projection_x<=0;projection_y<=0;projection_z<=0;projection_depth<=0;input_y<=0;input_group<=0;
   ax<=0;ay<=0;bx<=0;by<=0;cx<=0;cy<=0;xmin<=0;xmax<=0;ymin<=0;ymax<=0;scan_x<=0;scan_y<=0;
   e0<=0;e1<=0;e2<=0;row0<=0;row1<=0;row2<=0;step_x0<=0;step_x1<=0;step_x2<=0;step_y0<=0;step_y1<=0;step_y2<=0;
   az<=0;bz<=0;cz<=0;tri_area<=0;tri_nx<=0;tri_ny<=0;
   gradient_x<=0;gradient_y<=0;row_depth<=0;scan_depth<=0;
   line_depth<=0;target_depth<=0;line_depth_step<=0;triangle_shade<=4;
   div_start<=0;div_n<=0;div_d<=0;
   light_pass<=0;ia<=0;ib<=0;ic<=0;la<=0;lb<=0;lc<=0;face_light<=0;
   light_a<=0;light_nx<=0;light_ny<=0;light_gx<=0;light_gy<=0;light_row<=0;light_scan<=0;
   draw_group<=0;draw_shade<=0;line_x<=0;line_y<=0;target_x<=0;target_y<=0;dx<=0;dy<=0;step_sx<=0;step_sy<=0;line_error<=0;
  end else begin
   div_start<=0;scene_release<=0;
   front_valid_mask<=retained_mask;
   case(state)
    IDLE:if(scene_valid)begin
     work_actor_slot<=actor_slot;work_actor_track_id<=actor_track_id;work_ui_status<=ui_status;work_display_generation<=display_generation;
     work_confidence<=classification_confidence;work_trajectory_points<=trajectory_points;work_association_flags<=association_flags;
     light_pass<=1;
     nv<=vertex_count;ne<=edge_count;nt<=triangle_count;work_valid<=valid_mask;work_seen<=0;work_fixture<=fixture;
     work_ages<=source_ages;work_offsets<=group_offsets;work_hand_ns<=source_hand_ns;work_face_ns<=source_face_ns;
     work_epoch<=session_epoch;work_sequence<=scene_sequence;work_capture<=source_capture_sequence;work_eyes<=eye_metrics;work_arrival<=arrival_ms;
     clear_address<={9'd70,9'd24};clear_group<=0;back_bank<=~front_bank;vertex_index<=0;edge_index<=0;triangle_index<=0;dot_index<=0;state<=CLEAR;
    end
    CLEAR:begin
     if(clear_address[8:0]==clear_right)begin
      if(clear_address[17:9]==clear_bottom)begin
       if(clear_group==4)begin if(nv==0)state<=DRAIN;else state<=VREQ;end
       else begin clear_group<=clear_group+1'b1;clear_address<=clear_next_group;end
      end else clear_address<={clear_next_row,clear_left};
     end else clear_address<=clear_address+1'b1;
    end
    VREQ:begin vertex_addr<=vertex_index[6:0];state<=VWAIT;end
    VWAIT:state<=VPROJ0;
    VPROJ0:begin
     input_group<=vertex_data[50:48];input_y<=$signed(vertex_data[31:16]);
     // Screen projection and recorded image-plane strokes are 2D. Applying
     // the model-view yaw to these groups would distort the actual path.
     projection_x<=vertex_data[50:48]>=3 ? $signed(vertex_data[15:0])*32'sd256 :
       $signed(vertex_data[15:0])*32'sd230-$signed(vertex_data[47:32])*32'sd111;
     projection_z<=vertex_data[50:48]>=3 ? 32'sd0 :
       $signed(vertex_data[15:0])*32'sd111+$signed(vertex_data[47:32])*32'sd230;
     state<=VPROJ1;
    end
    VPROJ1:begin projection_y<=input_group>=3 ? $signed(input_y)*32'sd256 :
      $signed(input_y)*32'sd253-($signed(projection_z)>>>8)*32'sd38;
     projection_depth<=($signed(input_y)*32'sd38+($signed(projection_z)>>>8)*32'sd253)>>>4;state<=VSTORE;end
    VSTORE:begin
     light_sum[vertex_index[6:0]]<=0;light_count[vertex_index[6:0]]<=0;vertex_light[vertex_index[6:0]]<=1024;
     pz[vertex_index[6:0]]<=projection_depth[23:0];
     pg[vertex_index[6:0]]<=input_group;pv[vertex_index[6:0]]<=in_viewport(input_group,screen_x,screen_y);
     if(in_viewport(input_group,screen_x,screen_y))work_seen[input_group]<=1;
     px[vertex_index[6:0]]<=screen_x[10:0];py[vertex_index[6:0]]<=screen_y[10:0];point_style[vertex_index[6:0]]<=2;
     if(vertex_index+1'b1>=nv)begin if(nt!=0)state<=TREQ;else state<=ENEXT;end
     else begin vertex_index<=vertex_index+1'b1;state<=VREQ;end
    end
    TREQ:begin triangle_addr<=triangle_index[5:0];state<=TWAIT;end
    TWAIT:state<=TLATCH;
    TLATCH:begin
     if(triangle_data[7:0]<nv && triangle_data[15:8]<nv && triangle_data[23:16]<nv &&
        pv[triangle_data[6:0]] && pv[triangle_data[14:8]] && pv[triangle_data[22:16]] &&
        pg[triangle_data[6:0]]==pg[triangle_data[14:8]] && pg[triangle_data[6:0]]==pg[triangle_data[22:16]])begin
      ia<=triangle_data[6:0];ib<=triangle_data[14:8];ic<=triangle_data[22:16];
      az<=$signed(depth_read);la<=light_read;
      ax<=px[triangle_data[6:0]];ay<=py[triangle_data[6:0]];bx<=px[triangle_data[14:8]];by<=py[triangle_data[14:8]];
      cx<=px[triangle_data[22:16]];cy<=py[triangle_data[22:16]];draw_group<=pg[triangle_data[6:0]];draw_shade<=triangle_data[25:24];state<=TLOAD_B;
     end else begin if(!light_pass)rejected_primitives<=rejected_primitives+1'b1;
      if(triangle_index+1'b1>=nt)begin if(light_pass)begin light_pass<=0;vertex_index<=0;state<=LDIV;end else state<=ENEXT;end else begin triangle_index<=triangle_index+1'b1;state<=TREQ;end
     end
    end
    TLOAD_B:begin bz<=$signed(depth_read);lb<=light_read;state<=TLOAD_C;end
    TLOAD_C:begin cz<=$signed(depth_read);lc<=light_read;state<=TBOUNDS;end
    TBOUNDS:begin
     xmin<=min3(ax,bx,cx);xmax<=max3(ax,bx,cx);ymin<=min3(ay,by,cy);ymax<=max3(ay,by,cy);state<=TSETUP;
    end
    TSETUP:begin
     scan_x<=xmin;scan_y<=ymin;
     tri_area<=($signed(bx)-$signed(ax))*($signed(cy)-$signed(ay))-($signed(cx)-$signed(ax))*($signed(by)-$signed(ay));
     light_a<=$signed({21'd0,la});
     light_nx<=($signed({21'd0,lb})-$signed({21'd0,la}))*($signed(cy)-$signed(ay))-($signed({21'd0,lc})-$signed({21'd0,la}))*($signed(by)-$signed(ay));
     light_ny<=($signed(bx)-$signed(ax))*($signed({21'd0,lc})-$signed({21'd0,la}))-($signed(cx)-$signed(ax))*($signed({21'd0,lb})-$signed({21'd0,la}));
     tri_nx<=(bz-az)*($signed(cy)-$signed(ay))-(cz-az)*($signed(by)-$signed(ay));
     tri_ny<=($signed(bx)-$signed(ax))*(cz-az)-($signed(cx)-$signed(ax))*(bz-az);
     e0<=($signed(xmin)-$signed(ax))*($signed(by)-$signed(ay))-($signed(ymin)-$signed(ay))*($signed(bx)-$signed(ax));
     e1<=($signed(xmin)-$signed(bx))*($signed(cy)-$signed(by))-($signed(ymin)-$signed(by))*($signed(cx)-$signed(bx));
     e2<=($signed(xmin)-$signed(cx))*($signed(ay)-$signed(cy))-($signed(ymin)-$signed(cy))*($signed(ax)-$signed(cx));
     row0<=($signed(xmin)-$signed(ax))*($signed(by)-$signed(ay))-($signed(ymin)-$signed(ay))*($signed(bx)-$signed(ax));
     row1<=($signed(xmin)-$signed(bx))*($signed(cy)-$signed(by))-($signed(ymin)-$signed(by))*($signed(cx)-$signed(bx));
     row2<=($signed(xmin)-$signed(cx))*($signed(ay)-$signed(cy))-($signed(ymin)-$signed(cy))*($signed(ax)-$signed(cx));
     step_x0<=$signed(by)-$signed(ay);step_x1<=$signed(cy)-$signed(by);step_x2<=$signed(ay)-$signed(cy);
     step_y0<=$signed(ax)-$signed(bx);step_y1<=$signed(bx)-$signed(cx);step_y2<=$signed(cx)-$signed(ax);if(draw_group<3)state<=TXDIV;else if(light_pass)begin if(triangle_index+1'b1>=nt)begin if(light_pass)begin light_pass<=0;vertex_index<=0;state<=LDIV;end else state<=ENEXT;end else begin triangle_index<=triangle_index+1'b1;state<=TREQ;end end else state<=TSCAN;
    end
    TXDIV:begin div_n<=tri_nx;div_d<=tri_area;div_start<=1;state<=TXWAIT;end
    TXWAIT:if(div_done)begin
     if(div_zero || div_overflow)begin
      if(!light_pass)rejected_primitives<=rejected_primitives+1'b1;
      if(triangle_index+1'b1>=nt)begin if(light_pass)begin light_pass<=0;vertex_index<=0;state<=LDIV;end else state<=ENEXT;end else begin triangle_index<=triangle_index+1'b1;state<=TREQ;end
     end else begin gradient_x<=div_q;state<=TYDIV;end
    end
    TYDIV:begin div_n<=tri_ny;div_d<=tri_area;div_start<=1;state<=TYWAIT;end
    TYWAIT:if(div_done)begin
     gradient_y<=div_q;
     row_depth<=az+gradient_x*($signed(xmin)-$signed(ax))+div_q*($signed(ymin)-$signed(ay));
     scan_depth<=az+gradient_x*($signed(xmin)-$signed(ax))+div_q*($signed(ymin)-$signed(ay));
     triangle_shade<=diffuse_shade(gradient_x+div_q);
     if(light_pass)begin
      face_light<=surface_light(gradient_x+div_q);state<=LACC_A;
     end else state<=LXDIV;
    end
    LACC_A,LACC_B,LACC_C:begin
     light_sum[sum_addr]<=sum_read+face_light;light_count[sum_addr]<=count_read+1'b1;
     if(state==LACC_A)state<=LACC_B;
     else if(state==LACC_B)state<=LACC_C;
     else if(triangle_index+1'b1>=nt)begin light_pass<=0;vertex_index<=0;state<=LDIV;end
     else begin triangle_index<=triangle_index+1'b1;state<=TREQ;end
    end
    LDIV:begin
     if(count_read==0)begin
      vertex_light[vertex_index[6:0]]<=1024;
      if(vertex_index+1'b1>=nv)begin triangle_index<=0;state<=TREQ;end else vertex_index<=vertex_index+1'b1;
     end else begin div_n<=$signed({14'd0,sum_read});div_d<=$signed({25'd0,count_read});div_start<=1;state<=LWAIT;end
    end
    LWAIT:if(div_done)begin
     vertex_light[vertex_index[6:0]]<=div_q[10:0];
     if(vertex_index+1'b1>=nv)begin triangle_index<=0;state<=TREQ;end else begin vertex_index<=vertex_index+1'b1;state<=LDIV;end
    end
    LXDIV:begin div_n<=light_nx;div_d<=tri_area;div_start<=1;state<=LXWAIT;end
    LXWAIT:if(div_done)begin light_gx<=div_q;state<=LYDIV;end
    LYDIV:begin div_n<=light_ny;div_d<=tri_area;div_start<=1;state<=LYWAIT;end
    LYWAIT:if(div_done)begin
     light_gy<=div_q;
     light_row<=light_a+light_gx*($signed(xmin)-$signed(ax))+div_q*($signed(ymin)-$signed(ay));
     light_scan<=light_a+light_gx*($signed(xmin)-$signed(ax))+div_q*($signed(ymin)-$signed(ay));state<=TSCAN;
    end
    TSCAN:begin
     if(scan_x>=xmax)begin
      if(scan_y>=ymax)begin
       if(triangle_index+1'b1>=nt)begin if(light_pass)begin light_pass<=0;vertex_index<=0;state<=LDIV;end else state<=ENEXT;end else begin triangle_index<=triangle_index+1'b1;state<=TREQ;end
      end else begin
       light_row<=light_row+light_gy;light_scan<=light_row+light_gy;
       row_depth<=row_depth+gradient_y;scan_depth<=row_depth+gradient_y;
       scan_x<=xmin;scan_y<=scan_y+1'b1;row0<=row0+step_y0;row1<=row1+step_y1;row2<=row2+step_y2;
       e0<=row0+step_y0;e1<=row1+step_y1;e2<=row2+step_y2;
      end
     end else begin light_scan<=light_scan+light_gx;scan_depth<=scan_depth+gradient_x;scan_x<=scan_x+1'b1;e0<=e0+step_x0;e1<=e1+step_x1;e2<=e2+step_x2;end
    end
    ENEXT:if(edge_index>=ne)state<=DNEXT;else state<=EREQ;
    EREQ:begin edge_addr<=edge_index[6:0];state<=EWAIT;end
    EWAIT:state<=ELATCH;
    ELATCH:begin
     if(edge_data[7:0]<nv && edge_data[15:8]<nv && pv[edge_data[6:0]] && pv[edge_data[14:8]] && pg[edge_data[6:0]]==pg[edge_data[14:8]])begin
      line_depth<=$signed(depth_read);
      line_x<=px[edge_data[6:0]];line_y<=py[edge_data[6:0]];target_x<=px[edge_data[14:8]];target_y<=py[edge_data[14:8]];
      draw_group<=pg[edge_data[6:0]];draw_shade<=edge_data[17:16];state<=ELOAD_B;
      if(edge_data[17:16]==3 && edge_data[7:0]==edge_data[15:8])point_style[edge_data[6:0]]<=3;
      if(pg[edge_data[6:0]]==4)begin
       point_style[edge_data[6:0]]<=edge_data[17:16];
       point_style[edge_data[14:8]]<=edge_data[17:16];
      end
     end else begin edge_index<=edge_index+1'b1;state<=ENEXT;rejected_primitives<=rejected_primitives+1'b1;end
    end
    ELOAD_B:begin target_depth<=$signed(depth_read);state<=ESETUP;end
    ESETUP:begin
     dx<=line_x<target_x?target_x-line_x:line_x-target_x;dy<=line_y<target_y?line_y-target_y:target_y-line_y;
     step_sx<=line_x<target_x?12'sd1:-12'sd1;step_sy<=line_y<target_y?12'sd1:-12'sd1;
     line_error<=(line_x<target_x?target_x-line_x:line_x-target_x)+(line_y<target_y?line_y-target_y:target_y-line_y);
     stamp<=0;state<=draw_group<3 ? EZDIV : ESTAMP;
    end
    EZDIV:begin
     if(dx==0 && dy==0)begin line_depth_step<=0;state<=ESTAMP;end
     else begin div_n<=target_depth-line_depth;div_d<=dx>=-dy ? dx : -dy;div_start<=1;state<=EZWAIT;end
    end
    EZWAIT:if(div_done)begin line_depth_step<=div_q;state<=ESTAMP;end
    ESTAMP:if(stamp==(draw_group<2 ? 80 : draw_group==2 ? 0 : 3))begin stamp<=0;state<=ESTEP;end else stamp<=stamp+1'b1;
    ESTEP:if(line_x==target_x && line_y==target_y)begin edge_index<=edge_index+1'b1;state<=ENEXT;end
     else begin
      line_depth<=line_depth+line_depth_step;
      line_error<=line_error+(twice_error>=dy?dy:12'sd0)+(twice_error<=dx?dx:12'sd0);
      if(twice_error>=dy)line_x<=line_x+step_sx;if(twice_error<=dx)line_y<=line_y+step_sy;
      stamp<=0;state<=ESTAMP;
     end
    DNEXT:if(dot_index>=nv)state<=DRAIN;
     else if(pv[dot_index[6:0]] && (pg[dot_index[6:0]]!=2 || point_style[dot_index[6:0]]==3))begin
      line_depth<=$signed(depth_read);
      line_x<=px[dot_index[6:0]];line_y<=py[dot_index[6:0]];draw_group<=pg[dot_index[6:0]];draw_shade<=point_style[dot_index[6:0]];
      stamp<=0;state<=DSTAMP;
     end else dot_index<=dot_index+1'b1;
    DSTAMP:if(stamp==(draw_group<2 ? 80 : 8))begin dot_index<=dot_index+1'b1;state<=DNEXT;end else stamp<=stamp+1'b1;
    // PUBLISH means ready for the next vblank, with no hidden pipeline drain.
    DRAIN:if(!depth_busy)state<=PUBLISH;
    PUBLISH:if(vblank)begin
     front_actor_slot<=work_actor_slot;front_actor_track_id<=work_actor_track_id;front_ui_status<=work_ui_status;front_display_generation<=work_display_generation;
     front_confidence<=work_confidence;front_trajectory_points<=work_trajectory_points;front_association_flags<=work_association_flags;
     front_bank<=back_bank;front_ready<=1;front_valid_mask<=publish_mask;front_fixture<=work_fixture;
     front_source_ages<=work_ages;front_arrival_ms<=work_arrival;front_hand_ns<=work_hand_ns;front_face_ns<=work_face_ns;
     front_epoch<=work_epoch;front_sequence<=work_sequence;front_capture_sequence<=work_capture;front_eye_metrics<=work_eyes;
     published_scenes<=published_scenes+1'b1;scene_release<=1;state<=RELEASE;
    end
    RELEASE:if(!scene_valid)state<=IDLE;
    default:state<=IDLE;
   endcase
  end
 end
endmodule
`default_nettype wire
