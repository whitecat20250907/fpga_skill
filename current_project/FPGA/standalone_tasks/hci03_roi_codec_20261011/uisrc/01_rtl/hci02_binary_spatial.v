`timescale 1ns/1ps
// Runtime-size one-bit3x3 erosion/dilation. Three small horizontal-result
// row banks; replicated borders, independent EOL and bottom-row drain.
// One input/output pixel per clock in the row interior; output is held on
// stalls. Geometry/op are accepted only at SOF, with no whole-image9read loop.
module hci02_binary_spatial #(parameter MAX_WIDTH=256,MAX_HEIGHT=128)(
 input wire clk,rst_n,input wire s_data,s_valid,s_sof,s_last,s_op,
 input wire [15:0] s_width,s_height,output wire s_ready,
 input wire m_ready,output reg m_data,m_valid,m_sof,m_last,m_eof,
 output reg [31:0] errors
);
 reg bank0[0:MAX_WIDTH-1],bank1[0:MAX_WIDTH-1],bank2[0:MAX_WIDTH-1];
 reg [15:0] in_col,in_row,flush_row,bottom_col,width,height;
 reg [1:0] bank_select,flush_bank,bottom_bank;
 reg previous,left_pixel,flush_pending,bottom_active,in_frame,op;
 wire advance=!m_valid||m_ready;
 assign s_ready=advance&&!flush_pending&&!bottom_active;
 wire take=s_valid&&s_ready;
 wire accepted=take&&(in_frame||s_sof);
 wire [15:0] col=s_sof?0:in_col,row=s_sof?0:in_row;
 wire [15:0] iw=s_sof?s_width:width,ih=s_sof?s_height:height;
 wire io=s_sof?s_op:op;
 wire [1:0] ib=s_sof?0:bank_select;
 function combine;
  input a,b,c,operation;
  begin combine=operation?(a|b|c):(a&b&c);end
 endfunction
 wire flush_now=advance&&flush_pending&&!bottom_active;
 wire emit_now=flush_now||(accepted&&col!=0);
 wire [15:0] emit_col=flush_now?width-1:col-1'b1;
 wire [15:0] emit_row=flush_now?flush_row:row;
 wire [1:0] emit_bank=flush_now?flush_bank:ib;
 wire horizontal=combine(left_pixel,previous,flush_now?previous:s_data,op);
 wire q0=bank0[emit_col],q1=bank1[emit_col],q2=bank2[emit_col];
 reg center_h,upper_h;
 always @*begin
  case(emit_bank)0:begin center_h=q2;upper_h=q1;end 1:begin center_h=q0;upper_h=q2;end default:begin center_h=q1;upper_h=q0;end endcase
  if(emit_row==1)upper_h=center_h;
 end
 wire b0=bank0[bottom_col],b1=bank1[bottom_col],b2=bank2[bottom_col];reg last_h,prior_h;
 always @*begin
  case(bottom_bank)0:begin last_h=b0;prior_h=b2;end 1:begin last_h=b1;prior_h=b0;end default:begin last_h=b2;prior_h=b1;end endcase
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   in_col<=0;in_row<=0;flush_row<=0;bottom_col<=0;width<=0;height<=0;bank_select<=0;flush_bank<=0;bottom_bank<=0;
   previous<=0;left_pixel<=0;flush_pending<=0;bottom_active<=0;in_frame<=0;op<=0;
   m_data<=0;m_valid<=0;m_sof<=0;m_last<=0;m_eof<=0;errors<=0;
  end else if(advance)begin
   m_valid<=0;m_sof<=0;m_last<=0;m_eof<=0;
   if(take&&!accepted)errors[0]<=1;
   if(accepted)begin
    if(s_sof)begin
     if(in_frame)errors[1]<=1;
     width<=s_width;height<=s_height;op<=s_op;in_frame<=1;
     if(s_width==0||s_height==0||s_width>MAX_WIDTH||s_height>MAX_HEIGHT)errors[4]<=1;
    end
    if(s_last!=(col==iw-1))errors[2]<=1;
    if(row>=ih)errors[3]<=1;
    if(col==0)begin previous<=s_data;left_pixel<=s_data;end
    else begin previous<=s_data;left_pixel<=previous;end
    if(s_last)begin flush_pending<=1;flush_row<=row;flush_bank<=ib;end
    if(s_last)begin in_col<=0;in_row<=row+1'b1;bank_select<=ib==2?0:ib+1'b1;end
    else begin in_col<=col+1'b1;in_row<=row;bank_select<=ib;end
   end
   if(emit_now)begin
    case(emit_bank)0:bank0[emit_col]<=horizontal;1:bank1[emit_col]<=horizontal;default:bank2[emit_col]<=horizontal;endcase
    if(height==1||emit_row!=0)begin
     m_valid<=1;m_data<=height==1?horizontal:combine(upper_h,center_h,horizontal,op);
     m_sof<=((height==1?emit_row==0:emit_row==1)&&emit_col==0);m_last<=emit_col==width-1;
     m_eof<=height==1&&emit_col==width-1;
     if(height==1&&emit_col==width-1)in_frame<=0;
    end
   end
   if(bottom_active)begin
    m_valid<=1;m_data<=combine(prior_h,last_h,last_h,op);m_last<=bottom_col==width-1;m_eof<=bottom_col==width-1;
    if(bottom_col==width-1)begin bottom_active<=0;in_frame<=0;end else bottom_col<=bottom_col+1'b1;
   end else if(flush_now)begin
    flush_pending<=0;
    if(height>1&&flush_row==height-1)begin bottom_active<=1;bottom_col<=0;bottom_bank<=flush_bank;end
   end
  end
 end
endmodule
