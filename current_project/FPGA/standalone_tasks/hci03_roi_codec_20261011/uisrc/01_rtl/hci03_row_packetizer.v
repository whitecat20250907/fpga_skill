`timescale 1ns/1ps
// HCR3 v1: 72-byte CRC-protected header and variable striped lane body.
// One granted row bank remains SEND until the final 64-bit word is accepted.
// Wire pairs are padded only to the maximum ACTUAL encoded lane length;
// zero padding is excluded from lane lengths and never enters the codec.
module hci03_row_packetizer(
 input wire clk,rst_n,
 input wire [2:0] row_valid,row_bank,output reg [2:0] row_ready,
 input wire [767:0] row_metadata,input wire [95:0] row_crc,
 input wire [35:0] row_modes,input wire [323:0] row_lengths,
 output wire [323:0] read_addr,input wire [575:0] read_pairs,
 output reg [2:0] release_valid,release_bank,
 output reg [63:0] m_data,output wire m_valid,m_first,m_last,input wire m_ready,
 output reg [31:0] packets,output reg [63:0] raw_bytes,payload_bytes,wire_bytes,
 output wire [1:0] active_roi
);
 localparam IDLE=0,CRC_HEADER=1,HEADER=2,BODY=3;
 reg [1:0] state,selected,round_robin,group_index;
 reg selected_bank;reg [575:0] header;
 reg [3:0] header_word;reg [4:0] crc_word;
 reg [31:0] header_crc;reg [8:0] pair_index,pair_count;
 reg [107:0] lengths;reg [15:0] actual_payload;reg [31:0] actual_raw;
 reg [15:0] actual_wire;reg [1:0] choice;reg found;
 integer k,l;reg [8:0] maximum;reg [15:0] summed;
 reg [543:0] next_header;reg [255:0] metadata;
 genvar q,a;
 generate for(q=0;q<3;q=q+1)begin:roi_address
  for(a=0;a<12;a=a+1)begin:lane_address
   assign read_addr[q*108+a*9+:9]=selected==q?(pair_index<<1):9'd0;
  end
 end endgenerate
 function [31:0] crc_word32;
  input [31:0] c;input [31:0] d;reg [63:0] v;
  begin v={d,c};
   crc_word32[0]=^(v & 64'h4d101df04d101df);
   crc_word32[1]=^(v & 64'h9a203be09a203be);
   crc_word32[2]=^(v & 64'h1344077d1344077d);
   crc_word32[3]=^(v & 64'h26880efa26880efa);
   crc_word32[4]=^(v & 64'h4d101df44d101df4);
   crc_word32[5]=^(v & 64'h9a203be99a203be9);
   crc_word32[6]=^(v & 64'h3091760d3091760d);
   crc_word32[7]=^(v & 64'h6122ec1a6122ec1a);
   crc_word32[8]=^(v & 64'hc245d835c245d835);
   crc_word32[9]=^(v & 64'h805ab1b5805ab1b5);
   crc_word32[10]=^(v & 64'h46462b5046462b5);
   crc_word32[11]=^(v & 64'h8c8c56a08c8c56a);
   crc_word32[12]=^(v & 64'h11918ad411918ad4);
   crc_word32[13]=^(v & 64'h232315a9232315a9);
   crc_word32[14]=^(v & 64'h46462b5346462b53);
   crc_word32[15]=^(v & 64'h8c8c56a68c8c56a6);
   crc_word32[16]=^(v & 64'h1dc9ac921dc9ac92);
   crc_word32[17]=^(v & 64'h3b9359243b935924);
   crc_word32[18]=^(v & 64'h7726b2497726b249);
   crc_word32[19]=^(v & 64'hee4d6493ee4d6493);
   crc_word32[20]=^(v & 64'hd84bc8f9d84bc8f9);
   crc_word32[21]=^(v & 64'hb446902db446902d);
   crc_word32[22]=^(v & 64'h6c5c21846c5c2184);
   crc_word32[23]=^(v & 64'hd8b84309d8b84309);
   crc_word32[24]=^(v & 64'hb5a187ccb5a187cc);
   crc_word32[25]=^(v & 64'h6f920e466f920e46);
   crc_word32[26]=^(v & 64'hdf241c8cdf241c8c);
   crc_word32[27]=^(v & 64'hba9938c7ba9938c7);
   crc_word32[28]=^(v & 64'h71e3705171e37051);
   crc_word32[29]=^(v & 64'he3c6e0a3e3c6e0a3);
   crc_word32[30]=^(v & 64'hc35cc098c35cc098);
   crc_word32[31]=^(v & 64'h826880ef826880ef);
  end
 endfunction
 always @* begin
  choice=0;found=0;
  case(round_robin)
   0:begin if(row_valid[0])begin choice=0;found=1;end else if(row_valid[1])begin choice=1;found=1;end else if(row_valid[2])begin choice=2;found=1;end end
   1:begin if(row_valid[1])begin choice=1;found=1;end else if(row_valid[2])begin choice=2;found=1;end else if(row_valid[0])begin choice=0;found=1;end end
   default:begin if(row_valid[2])begin choice=2;found=1;end else if(row_valid[0])begin choice=0;found=1;end else if(row_valid[1])begin choice=1;found=1;end end
  endcase
  metadata=row_metadata[choice*256+:256];maximum=0;summed=0;next_header=0;
  // All fields are little-endian. Unused eye lanes are required to be zero.
  next_header[31:0]=32'h33524348;next_header[39:32]=1;next_header[47:40]={6'd0,choice};
  next_header[55:48]=choice==2?8'd3:8'd1;next_header[63:56]=metadata[215:208];
  next_header[95:64]=packets;next_header[127:96]=metadata[31:0];next_header[159:128]=metadata[63:32];
  next_header[223:160]=metadata[127:64];next_header[255:224]=metadata[159:128];
  next_header[287:256]=metadata[191:160];next_header[303:288]=metadata[207:192];
  next_header[319:304]={4'd0,row_modes[choice*12+:12]};
  for(k=0;k<12;k=k+1)begin
   next_header[320+k*16+:16]={7'd0,row_lengths[choice*108+k*9+:9]};
   summed=summed+row_lengths[choice*108+k*9+:9];
   if(row_lengths[choice*108+k*9+:9]>maximum)maximum=row_lengths[choice*108+k*9+:9];
  end
  next_header[543:512]=row_crc[choice*32+:32];
  row_ready=0;if(state==IDLE&&found)row_ready[choice]=1;
  m_data=0;
  if(state==HEADER)m_data=header[header_word*64+:64];
  else if(state==BODY)for(k=0;k<4;k=k+1)begin
   l=group_index*4+k;
   if((pair_index<<1)<lengths[l*9+:9])m_data[k*16+:8]=read_pairs[selected*192+l*16+:8];
   if((pair_index<<1)+1<lengths[l*9+:9])m_data[k*16+8+:8]=read_pairs[selected*192+l*16+8+:8];
  end
  release_valid=0;release_bank=0;
  if(m_valid&&m_ready&&m_last)begin release_valid[selected]=1;release_bank[selected]=selected_bank;end
 end
 assign m_valid=state==HEADER||state==BODY;
 assign m_first=state==HEADER&&header_word==0;
 assign m_last=state==BODY&&pair_index==pair_count-1'b1&&(selected!=2||group_index==2);
 assign active_roi=selected;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=IDLE;selected<=0;round_robin<=0;selected_bank<=0;header<=0;header_word<=0;crc_word<=0;header_crc<=32'hffffffff;
   pair_index<=0;pair_count<=0;group_index<=0;lengths<=0;actual_payload<=0;actual_raw<=0;actual_wire<=0;
   packets<=0;raw_bytes<=0;payload_bytes<=0;wire_bytes<=0;
  end else case(state)
   IDLE:if(found)begin
    selected<=choice;selected_bank<=row_bank[choice];header<={32'd0,next_header};
    lengths<=row_lengths[choice*108+:108];pair_count<=(maximum+9'd1)>>1;pair_index<=0;group_index<=0;
    actual_payload<=summed;actual_raw<=metadata[247:216];actual_wire<=16'd72+(((maximum+9'd1)>>1)*(choice==2?16'd24:16'd8));
    header_crc<=32'hffffffff;crc_word<=0;header_word<=0;state<=CRC_HEADER;
   end
   CRC_HEADER:begin
    header_crc<=crc_word32(header_crc,header[crc_word*32+:32]);
    if(crc_word==16)begin header[575:544]<=~crc_word32(header_crc,header[543:512]);state<=HEADER;end
    else crc_word<=crc_word+1'b1;
   end
   HEADER:if(m_ready)begin
    if(header_word==8)state<=BODY;else header_word<=header_word+1'b1;
   end
   BODY:if(m_ready)begin
    if(m_last)begin
     packets<=packets+1'b1;raw_bytes<=raw_bytes+actual_raw;payload_bytes<=payload_bytes+actual_payload;wire_bytes<=wire_bytes+actual_wire;
     round_robin<=selected==2?2'd0:selected+1'b1;state<=IDLE;
    end else if(selected==2&&group_index!=2)group_index<=group_index+1'b1;
    else begin group_index<=0;pair_index<=pair_index+1'b1;end
   end
   default:state<=IDLE;
  endcase
 end
endmodule
