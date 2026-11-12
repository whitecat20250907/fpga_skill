`timescale 1ns/1ps
// Four histogram banks, full accepted counts, previous-frame CDF LUT.
// First frame and a constant previous frame use exact identity. No hist shift.
// 32-cycle unsigned divider per mapped bin; source waits during build/clear.
module hci01_histeq_quad #(parameter WIDTH=1920,HEIGHT=1080,BINS=64)(
 input wire clk,rst_n,input wire [31:0] s_data,
 input wire s_valid,s_sof,s_last,s_eof,input wire [13:0] s_config,input wire invalidate_lut,
 output wire s_ready,input wire m_ready,
 output reg [31:0] m_data,output reg m_valid,m_sof,m_last,m_eof,
 output reg [13:0] m_config,output reg [31:0] errors,
 output reg [31:0] frames,output reg lut_valid);
 localparam TOTAL=WIDTH*HEIGHT,CBITS=$clog2(TOTAL/4+1),BBITS=$clog2(BINS);
 localparam CLEAR=0,RUN=1,SCAN=2,MAP=3,DIVIDE=4;
 reg [2:0] state;
 reg [CBITS-1:0] hist0[0:BINS-1],hist1[0:BINS-1],hist2[0:BINS-1],hist3[0:BINS-1];
 reg [7:0] lut[0:BINS-1];
 reg [BBITS-1:0] bin;
 reg [31:0] cdf,cdf_min,denominator,dividend,quotient,remainder;
 reg [5:0] bit_count;
 reg found_min,lut_poisoned;
 reg [31:0] pixel_count;
 reg in_frame;
 wire advance=!m_valid||m_ready;
 assign s_ready=state==RUN&&advance;
 wire take=s_valid&&s_ready;
 wire [BBITS-1:0] b0=s_data[7-:BBITS],b1=s_data[15-:BBITS],b2=s_data[23-:BBITS],b3=s_data[31-:BBITS];
 wire [31:0] bin_count={ {(32-CBITS){1'b0}},hist0[bin]}+hist1[bin]+hist2[bin]+hist3[bin];
 wire [31:0] next_cdf=cdf+bin_count;
 wire [31:0] next_min=(!found_min&&bin_count!=0)?next_cdf:cdf_min;
 wire [32:0] trial={remainder,dividend[31]};
 wire ge=trial>={1'b0,denominator};
 wire [31:0] quotient_next={quotient[30:0],ge};
 integer k;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=CLEAR;bin<=0;cdf<=0;cdf_min<=0;denominator<=0;found_min<=0;
   dividend<=0;quotient<=0;remainder<=0;bit_count<=0;lut_valid<=0;lut_poisoned<=0;
   pixel_count<=0;in_frame<=0;m_valid<=0;m_data<=0;m_sof<=0;m_last<=0;m_eof<=0;m_config<=0;errors<=0;frames<=0;
  end else begin
   if(advance)begin
    m_valid<=0;m_sof<=0;m_last<=0;m_eof<=0;
    if(take)begin
     if(!in_frame&&!s_sof)errors[0]<=1;
     if(in_frame&&s_sof)errors[1]<=1;
     if(in_frame||s_sof)begin
      m_valid<=1;m_sof<=s_sof;m_last<=s_last;m_eof<=s_eof;m_config<=s_config;
      m_data[7:0]<=lut_valid&&!s_config[2]?lut[b0]:s_data[7:0];
      m_data[15:8]<=lut_valid&&!s_config[2]?lut[b1]:s_data[15:8];
      m_data[23:16]<=lut_valid&&!s_config[2]?lut[b2]:s_data[23:16];
      m_data[31:24]<=lut_valid&&!s_config[2]?lut[b3]:s_data[31:24];
      hist0[b0]<=hist0[b0]+1'b1;hist1[b1]<=hist1[b1]+1'b1;hist2[b2]<=hist2[b2]+1'b1;hist3[b3]<=hist3[b3]+1'b1;
      pixel_count<=s_sof?4:pixel_count+4;in_frame<=1;
      if(s_eof)begin
       if((s_sof?4:pixel_count+4)!=TOTAL||!s_last)errors[2]<=1;
       state<=SCAN;bin<=0;cdf<=0;cdf_min<=0;found_min<=0;in_frame<=0;frames<=frames+1'b1;lut_poisoned<=0;
      end
     end
    end
   end
   case(state)
    CLEAR:begin
     hist0[bin]<=0;hist1[bin]<=0;hist2[bin]<=0;hist3[bin]<=0;
     if(bin==BINS-1)begin bin<=0;state<=RUN;end else bin<=bin+1'b1;
    end
    SCAN:begin
     cdf<=next_cdf;cdf_min<=next_min;if(bin_count!=0)found_min<=1;
     if(bin==BINS-1)begin
      if(next_cdf!=TOTAL)errors[3]<=1;
      denominator<=next_cdf-next_min;cdf<=0;bin<=0;
      if(next_cdf==next_min)begin lut_valid<=0;state<=CLEAR;end else state<=MAP;
     end else bin<=bin+1'b1;
    end
    MAP:begin
     cdf<=next_cdf;
     if(next_cdf<=cdf_min)begin
      lut[bin]<=0;
      if(bin==BINS-1)begin bin<=0;lut_valid<=!lut_poisoned;state<=CLEAR;end else bin<=bin+1'b1;
     end else begin
      dividend<=(next_cdf-cdf_min)*32'd255;quotient<=0;remainder<=0;bit_count<=31;state<=DIVIDE;
     end
    end
    DIVIDE:begin
     dividend<={dividend[30:0],1'b0};quotient<=quotient_next;
     remainder<=ge?trial-{1'b0,denominator}:trial[31:0];
     if(bit_count==0)begin
      lut[bin]<=quotient_next[7:0];
      if(bin==BINS-1)begin bin<=0;lut_valid<=!lut_poisoned;state<=CLEAR;end
      else begin bin<=bin+1'b1;state<=MAP;end
     end else bit_count<=bit_count-1'b1;
    end
    default:;
   endcase
   // Bypassed source frames are not histogram input. On return, use exact
   // identity until one new processed frame has supplied a complete histogram.
   if(invalidate_lut)begin lut_valid<=0;lut_poisoned<=1;end
  end
 end
 // synthesis translate_off
 initial if(WIDTH<4||WIDTH%4!=0||HEIGHT<1||TOTAL>16777216||BINS<2||BINS>256||(BINS&(BINS-1))!=0)$fatal(1,"Unsupported histogram parameters");
 // synthesis translate_on
endmodule
