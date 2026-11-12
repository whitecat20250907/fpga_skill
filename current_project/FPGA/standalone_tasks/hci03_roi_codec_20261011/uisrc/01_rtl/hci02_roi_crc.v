`timescale 1ns/1ps
// CRC32 reflected EDB88320, balanced reduction-XOR transforms. Eyes carry one
// luminance byte; the face carries R,G,B bytes in this order with no X padding.
// One ROI pixel each clock, so no three-byte serializer can stall CSI bursts.
module hci02_roi_crc(
 input wire clk,rst_n,s_valid,input wire [1:0] s_roi,
 input wire [31:0] s_data,input wire [7:0] s_gray,input wire s_sof,s_eof,
 input wire [15:0] s_width,s_height,output wire s_ready,
 output wire [95:0] last_crc,completed_windows,last_pixels,last_face_sum,
 output reg [31:0] errors
);
 function [31:0] crc8;
  input [31:0] c;input [7:0] d;reg [39:0] v;
  begin
   v={d,c};
   crc8[0]=^(v & 40'h0400000104);
   crc8[1]=^(v & 40'h0900000209);
   crc8[2]=^(v & 40'h1300000413);
   crc8[3]=^(v & 40'h2600000826);
   crc8[4]=^(v & 40'h4d0000104d);
   crc8[5]=^(v & 40'h9a0000209a);
   crc8[6]=^(v & 40'h3000004030);
   crc8[7]=^(v & 40'h6100008061);
   crc8[8]=^(v & 40'hc2000100c2);
   crc8[9]=^(v & 40'h8000020080);
   crc8[10]=^(v & 40'h0400040004);
   crc8[11]=^(v & 40'h0800080008);
   crc8[12]=^(v & 40'h1100100011);
   crc8[13]=^(v & 40'h2300200023);
   crc8[14]=^(v & 40'h4600400046);
   crc8[15]=^(v & 40'h8c0080008c);
   crc8[16]=^(v & 40'h1d0100001d);
   crc8[17]=^(v & 40'h3b0200003b);
   crc8[18]=^(v & 40'h7704000077);
   crc8[19]=^(v & 40'hee080000ee);
   crc8[20]=^(v & 40'hd8100000d8);
   crc8[21]=^(v & 40'hb4200000b4);
   crc8[22]=^(v & 40'h6c4000006c);
   crc8[23]=^(v & 40'hd8800000d8);
   crc8[24]=^(v & 40'hb5000000b5);
   crc8[25]=^(v & 40'h6f0000006f);
   crc8[26]=^(v & 40'hdf000000df);
   crc8[27]=^(v & 40'hba000000ba);
   crc8[28]=^(v & 40'h7100000071);
   crc8[29]=^(v & 40'he3000000e3);
   crc8[30]=^(v & 40'hc3000000c3);
   crc8[31]=^(v & 40'h8200000082);
  end
 endfunction
 function [31:0] crc24;
  input [31:0] c;input [23:0] d;reg [55:0] v;
  begin
   v={d,c};
   crc24[0]=^(v & 56'h04d1010104d101);
   crc24[1]=^(v & 56'h09a2030209a203);
   crc24[2]=^(v & 56'h13440704134407);
   crc24[3]=^(v & 56'h26880e0826880e);
   crc24[4]=^(v & 56'h4d101d104d101d);
   crc24[5]=^(v & 56'h9a203b209a203b);
   crc24[6]=^(v & 56'h30917640309176);
   crc24[7]=^(v & 56'h6122ec806122ec);
   crc24[8]=^(v & 56'hc245d800c245d8);
   crc24[9]=^(v & 56'h805ab100805ab1);
   crc24[10]=^(v & 56'h04646200046462);
   crc24[11]=^(v & 56'h08c8c50008c8c5);
   crc24[12]=^(v & 56'h11918a0011918a);
   crc24[13]=^(v & 56'h23231500232315);
   crc24[14]=^(v & 56'h46462b0046462b);
   crc24[15]=^(v & 56'h8c8c56008c8c56);
   crc24[16]=^(v & 56'h1dc9ac001dc9ac);
   crc24[17]=^(v & 56'h3b9359003b9359);
   crc24[18]=^(v & 56'h7726b2007726b2);
   crc24[19]=^(v & 56'hee4d6400ee4d64);
   crc24[20]=^(v & 56'hd84bc800d84bc8);
   crc24[21]=^(v & 56'hb4469000b44690);
   crc24[22]=^(v & 56'h6c5c21006c5c21);
   crc24[23]=^(v & 56'hd8b84300d8b843);
   crc24[24]=^(v & 56'hb5a18700b5a187);
   crc24[25]=^(v & 56'h6f920e006f920e);
   crc24[26]=^(v & 56'hdf241c00df241c);
   crc24[27]=^(v & 56'hba993800ba9938);
   crc24[28]=^(v & 56'h71e3700071e370);
   crc24[29]=^(v & 56'he3c6e000e3c6e0);
   crc24[30]=^(v & 56'hc35cc000c35cc0);
   crc24[31]=^(v & 56'h82688000826880);
  end
 endfunction
 reg [31:0] running_crc[0:2],pixel_count[0:2],crc_done[0:2],frames_done[0:2],pixels_done[0:2];
 reg in_window[0:2];
 reg [31:0] red,green,blue,face_red,face_green,face_blue;
 wire legal_id=s_roi<3;
 wire [31:0] base_crc=s_sof?32'hffffffff:(legal_id?running_crc[s_roi]:32'hffffffff);
 wire [31:0] next_crc=s_roi==2?crc24(base_crc,s_data[23:0]):crc8(base_crc,s_gray);
 wire [31:0] next_count=s_sof?32'd1:(legal_id?pixel_count[s_roi]+1'b1:0);
 assign s_ready=1;
 assign last_crc={crc_done[2],crc_done[1],crc_done[0]};
 assign completed_windows={frames_done[2],frames_done[1],frames_done[0]};
 assign last_pixels={pixels_done[2],pixels_done[1],pixels_done[0]};
 assign last_face_sum={face_blue,face_green,face_red};
 integer j;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   for(j=0;j<3;j=j+1)begin running_crc[j]<=32'hffffffff;pixel_count[j]<=0;crc_done[j]<=0;frames_done[j]<=0;pixels_done[j]<=0;in_window[j]<=0;end
   red<=0;green<=0;blue<=0;face_red<=0;face_green<=0;face_blue<=0;errors<=0;
  end else if(s_valid)begin
   if(!legal_id)errors[1]<=1;
   else begin
    if(s_sof&&in_window[s_roi]||!s_sof&&!in_window[s_roi])errors[0]<=1;
    running_crc[s_roi]<=next_crc;pixel_count[s_roi]<=next_count;in_window[s_roi]<=1;
    if(s_roi==2)begin
     red<=s_sof?s_data[7:0]:red+s_data[7:0];
     green<=s_sof?s_data[15:8]:green+s_data[15:8];blue<=s_sof?s_data[23:16]:blue+s_data[23:16];
    end
    if(s_eof)begin
     if(next_count!=s_width*s_height)errors[2]<=1;
     in_window[s_roi]<=0;crc_done[s_roi]<=~next_crc;frames_done[s_roi]<=frames_done[s_roi]+1'b1;pixels_done[s_roi]<=next_count;
     if(s_roi==2)begin
      face_red<=s_sof?s_data[7:0]:red+s_data[7:0];face_green<=s_sof?s_data[15:8]:green+s_data[15:8];face_blue<=s_sof?s_data[23:16]:blue+s_data[23:16];
     end
    end
   end
  end
 end
endmodule
