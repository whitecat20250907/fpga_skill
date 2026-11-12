`timescale 1ns/1ps
// Ready/valid 4-pixel spatial engine. Three rotating horizontal-result banks.
// Replicate image boundaries; drain EOL and final row even with next SOF held.
// STAGE0: Gaussian or bypass. STAGE1: bypass/Sobel/dark-mask/erode/dilate.
module hci01_spatial_quad #(
 parameter WIDTH=1920,HEIGHT=1080,STAGE=0,
 parameter GROUPS=WIDTH/4
)(
 input wire clk,rst_n,input wire [31:0] s_data,
 input wire s_valid,s_sof,s_last,input wire [13:0] s_config,
 output wire s_ready,input wire m_ready,
 output reg [31:0] m_data,output reg m_valid,m_sof,m_last,m_eof,
 output reg [13:0] m_config,output reg [31:0] errors,
 output reg [31:0] frames);
 reg [75:0] bank0[0:GROUPS-1],bank1[0:GROUPS-1],bank2[0:GROUPS-1];
 reg [10:0] in_col,bottom_col;
 reg [11:0] in_row,flush_row;
 reg [1:0] bank_select,flush_bank,bottom_bank;
 reg [31:0] previous_group;
 reg [7:0] left_pixel;
 reg flush_pending,bottom_active,in_frame;
 reg [13:0] active_config;
 wire advance=!m_valid||m_ready;
 assign s_ready=advance&&!flush_pending&&!bottom_active;
 wire take=s_valid&&s_ready;
 wire [13:0] current_config=s_sof?s_config:active_config;
 wire [2:0] input_op=STAGE==0?(current_config[1]?3'd0:3'd5):current_config[5:3];
 wire [2:0] stored_op=STAGE==0?(active_config[1]?3'd0:3'd5):active_config[5:3];
 wire [10:0] col=s_sof?11'd0:in_col;
 wire [11:0] row=s_sof?12'd0:in_row;
 wire [1:0] current_bank=s_sof?2'd0:bank_select;
 wire accepted=take&&(in_frame||s_sof);
 function [31:0] mask;
  input [31:0] d;input [7:0] threshold;
  integer j;begin for(j=0;j<4;j=j+1)mask[j*8+:8]=d[j*8+:8]<threshold?8'hff:8'd0;end
 endfunction
 wire [31:0] pixels=(input_op==3||input_op==4)?mask(s_data,current_config[13:6]):s_data;
 function [75:0] horizontal;
  input [7:0] left;input [31:0] center;input [7:0] right;
  reg [7:0] p[0:5];reg [9:0] sum;reg signed [8:0] diff;
  integer j;
  begin
   p[0]=left;p[1]=center[7:0];p[2]=center[15:8];p[3]=center[23:16];p[4]=center[31:24];p[5]=right;
   for(j=0;j<4;j=j+1)begin
    sum={2'b0,p[j]}+{1'b0,p[j+1],1'b0}+{2'b0,p[j+2]};
    diff=$signed({1'b0,p[j+2]})-$signed({1'b0,p[j]});
    horizontal[j*19+:19]={diff,sum};
   end
  end
 endfunction
 function [31:0] combine;
  input [75:0] upper,center,lower;input [2:0] op;
  integer j,hu,hc,hl,du,dc,dl,gx,gy,v;
  begin
   for(j=0;j<4;j=j+1)begin
    hu=upper[j*19+:10];hc=center[j*19+:10];hl=lower[j*19+:10];
    du=$signed(upper[j*19+10+:9]);dc=$signed(center[j*19+10+:9]);dl=$signed(lower[j*19+10+:9]);
    case(op)
     3'd1:begin gx=du+2*dc+dl;gy=hu-hl;v=((gx<0?-gx:gx)+(gy<0?-gy:gy))>>2;if(v>255)v=255;end
     3'd3:v=(hu==1020&&hc==1020&&hl==1020)?255:0;
     3'd4:v=(hu!=0||hc!=0||hl!=0)?255:0;
     default:v=(hu+2*hc+hl+8)>>4;
    endcase
    combine[j*8+:8]=v[7:0];
   end
  end
 endfunction
 wire flush_now=advance&&flush_pending&&!bottom_active;
 wire emit_now=flush_now||(accepted&&input_op!=0&&input_op!=2&&col!=0);
 wire [10:0] emit_col=flush_now?GROUPS-1:col-1'b1;
 wire [11:0] emit_row=flush_now?flush_row:row;
 wire [1:0] emit_bank=flush_now?flush_bank:current_bank;
 wire [75:0] h_now=flush_now?horizontal(left_pixel,previous_group,previous_group[31:24]):horizontal(left_pixel,previous_group,pixels[7:0]);
 wire [75:0] q0=bank0[emit_col],q1=bank1[emit_col],q2=bank2[emit_col];
 reg [75:0] center_h,upper_h;
 always @*begin
  case(emit_bank)
   0:begin center_h=q2;upper_h=q1;end
   1:begin center_h=q0;upper_h=q2;end
   default:begin center_h=q1;upper_h=q0;end
  endcase
  if(emit_row==1)upper_h=center_h;
 end
 wire [75:0] b0=bank0[bottom_col],b1=bank1[bottom_col],b2=bank2[bottom_col];
 reg [75:0] last_h,prior_h;
 always @*begin
  case(bottom_bank)
   0:begin last_h=b0;prior_h=b2;end
   1:begin last_h=b1;prior_h=b0;end
   default:begin last_h=b2;prior_h=b1;end
  endcase
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   in_col<=0;in_row<=0;bank_select<=0;bottom_col<=0;bottom_bank<=0;
   previous_group<=0;left_pixel<=0;flush_pending<=0;bottom_active<=0;in_frame<=0;
   flush_row<=0;flush_bank<=0;active_config<=0;
   m_data<=0;m_valid<=0;m_sof<=0;m_last<=0;m_eof<=0;m_config<=0;errors<=0;frames<=0;
  end else if(advance)begin
   m_valid<=0;m_sof<=0;m_last<=0;m_eof<=0;
   if(take&&!accepted)errors[0]<=1;
   if(accepted)begin
    if(s_sof)begin
     if(in_frame)errors[1]<=1;
     active_config<=s_config;in_frame<=1;
    end
    if(s_last!=(col==GROUPS-1))errors[2]<=1;
    if(row>=HEIGHT)errors[3]<=1;
    if(input_op==0||input_op==2)begin
     m_valid<=1;m_data<=input_op==2?mask(s_data,current_config[13:6]):s_data;
     m_sof<=s_sof;m_last<=s_last;m_eof<=s_last&&(row==HEIGHT-1);m_config<=current_config;
     if(s_last&&row==HEIGHT-1)begin in_frame<=0;frames<=frames+1'b1;end
    end else begin
     if(col==0)begin previous_group<=pixels;left_pixel<=pixels[7:0];end
     else begin previous_group<=pixels;left_pixel<=previous_group[31:24];end
     if(s_last)begin flush_pending<=1;flush_row<=row;flush_bank<=current_bank;end
    end
    if(s_last)begin in_col<=0;in_row<=row+1'b1;bank_select<=current_bank==2?0:current_bank+1'b1;end
    else begin in_col<=col+1'b1;in_row<=row;bank_select<=current_bank;end
   end
   if(emit_now)begin
    case(emit_bank)0:bank0[emit_col]<=h_now;1:bank1[emit_col]<=h_now;default:bank2[emit_col]<=h_now;endcase
    if(HEIGHT==1||emit_row!=0)begin
     m_valid<=1;m_data<=HEIGHT==1?combine(h_now,h_now,h_now,stored_op):combine(upper_h,center_h,h_now,stored_op);
     m_sof<=((HEIGHT==1?emit_row==0:emit_row==1)&&emit_col==0);
     m_last<=emit_col==GROUPS-1;m_eof<=HEIGHT==1&&emit_col==GROUPS-1;m_config<=active_config;
     if(HEIGHT==1&&emit_col==GROUPS-1)begin in_frame<=0;frames<=frames+1'b1;end
    end
   end
   if(bottom_active)begin
    m_valid<=1;m_data<=combine(prior_h,last_h,last_h,stored_op);m_last<=bottom_col==GROUPS-1;
    m_eof<=bottom_col==GROUPS-1;m_config<=active_config;
    if(bottom_col==GROUPS-1)begin bottom_active<=0;in_frame<=0;frames<=frames+1'b1;end
    else bottom_col<=bottom_col+1'b1;
   end else if(flush_now)begin
    flush_pending<=0;
    if(HEIGHT>1&&flush_row==HEIGHT-1)begin bottom_active<=1;bottom_col<=0;bottom_bank<=flush_bank;end
   end
  end
 end
 // synthesis translate_off
 initial if(WIDTH<4||WIDTH%4!=0||WIDTH>4096||HEIGHT<1||HEIGHT>4095||STAGE<0||STAGE>1)$fatal(1,"Unsupported spatial geometry/stage");
 // synthesis translate_on
endmodule
