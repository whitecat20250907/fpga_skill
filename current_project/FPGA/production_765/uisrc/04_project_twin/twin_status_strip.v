`timescale 1ns/1ps
`default_nettype none
// Read-only presentation of the existing atomic CSR mailbox. Bottom result
// chips return immediately when neither menu nor calibration/report is active.
module twin_status_strip(
 input wire [9:0] x,y,input wire fresh,
 input wire [31:0] menu,menu_lo,menu_hi,calibration,phase,errors,hits,quality,
 output reg visible,output reg [23:0] background,ink,
 output reg [7:0] code,output reg [3:0] glyph_x,glyph_y
);
 `include "dashboard_labels.vh"
 function bcd_valid;
  input [15:0] bcd;
  begin bcd_valid=bcd[3:0]<=9 && bcd[7:4]<=9 && bcd[11:8]<=9 && bcd[15:12]<=9;end
 endfunction
 function [7:0] digit;
  input [15:0] bcd;input integer position;input valid_number;
  reg [3:0] n;
  begin
   n=0;digit=32;
   if(!valid_number || !bcd_valid(bcd))digit=45;
   else begin
    case(position)0:n=bcd[15:12];1:n=bcd[11:8];2:n=bcd[7:4];default:n=bcd[3:0];endcase
    if(position==3 || (position==2 && bcd>=16'h0010) || (position==1 && bcd>=16'h0100) || (position==0 && bcd>=16'h1000))digit=48+n;
   end
  end
 endfunction
 reg [3:0] menu_count,menu_index;reg score_visible;
 reg [15:0] number;reg number_valid;integer cell_id,column,local_x,i;
 reg [5:0] heading;reg [63:0] menu_text;reg [17:0] progress_width;
 always @*begin
  menu_count=menu[8:5];menu_index=menu[4:1];menu_text={menu_hi,menu_lo};
  score_visible=phase[7:0]>=1 && phase[7:0]<=4;
  visible=fresh && (menu[0] || score_visible) && x>=32 && x<992 && y>=488 && y<568;
  background=24'h181d24;ink=24'hedf0f3;code=32;glyph_x=x[3:0];glyph_y=y[3:0];
  number=0;number_valid=0;cell_id=0;column=0;local_x=0;heading=52;progress_width=calibration[25:18]*18'd928;
  if(y==488 || y==567 || x==32 || x==991)background=24'h343e49;
  if(menu[0])begin
   if(x>=48 && x<80 && y>=496 && y<512)code=label_char(52,(x-48)>>4);
   if(x>=80 && x<336 && y>=520 && y<552)begin
    column=(x-80)>>5;code=menu_text[column*8+:8];if(code==0)code=32;
    glyph_x=(x-80)>>1;glyph_y=(y-520)>>1;
   end
   if(x>=880 && x<960 && y>=496 && y<512)begin
    case((x-880)>>4)0:code=menu_count>0 && menu_index<menu_count?49+menu_index:45;1:code=47;2:code=menu_count<=9?48+menu_count:45;default:code=32;endcase
   end
   for(i=0;i<9;i=i+1)if(i<menu_count && x>=568+i*40 && x<576+i*40 && y>=536 && y<544)background=i==menu_index?24'h7cc9d2:24'h343e49;
  end else if(score_visible)begin
   case(phase[7:0])1:heading=53;2:heading=54;3:heading=55;default:heading=56;endcase
   if(x>=48 && x<176 && y>=496 && y<512)begin code=label_char(heading,(x-48)>>4);ink=24'h7cc9d2;end
   if(y>=520 && y<536)begin
    glyph_y=y-520;
    if(x>=48 && x<208)begin cell_id=0;local_x=x-48;end
    else if(x>=240 && x<400)begin cell_id=1;local_x=x-240;end
    else if(x>=432 && x<592)begin cell_id=2;local_x=x-432;end
    else if(x>=624 && x<784)begin cell_id=3;local_x=x-624;end
    else if(x>=816 && x<976)begin cell_id=4;local_x=x-816;end
    else cell_id=5;
    column=local_x>>4;glyph_x=local_x[3:0];
    case(cell_id)
     0:begin number=errors[15:0];number_valid=phase[8];if(column<2)code=label_char(57,column);end
     1:begin number=errors[31:16];number_valid=phase[9];case(column)0:code=80;1:code=57;2:code=48;default:code=32;endcase end
     2:begin number=hits[15:0];number_valid=phase[10];if(column<2)code=label_char(58,column);end
     3:begin number=hits[31:16];number_valid=phase[11];if(column<2)code=label_char(59,column);end
     4:begin number=quality[15:0];number_valid=phase[12];if(column<2)code=label_char(60,column);end
     default:begin number=0;number_valid=0;end
    endcase
    if(cell_id<5)begin
     if(column>=4 && column<8)code=digit(number,column-4,number_valid);
     if(column==8)code=cell_id<2?112:37;
     if(column==9 && cell_id<2)code=120;
    end
   end
   if(y>=544 && y<560 && phase[7:0]>=3)begin
    if(x>=48 && x<80)code=label_char(61,(x-48)>>4);
    if(x>=112 && x<192)begin
     column=(x-112)>>4;
     if(column<2)code=digit({8'd0,quality[23:16]},column+2,phase[13]);
     else if(column==2)code=47;
     else code=digit({8'd0,quality[31:24]},column-1,phase[13] && quality[31:24]!=0);
    end
   end
   if(phase[7:0]<3 && x>=48 && x<976 && y>=550 && y<554)background=(calibration[25:18]==255 || x-48<(progress_width>>8))?24'h7cc9d2:24'h343e49;
  end
 end
endmodule
`default_nettype wire
