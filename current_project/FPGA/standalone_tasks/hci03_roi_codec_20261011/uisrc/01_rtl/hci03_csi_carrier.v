`timescale 1ns/1ps
// Fixed YUYV-labelled CSI container, whose bytes are HCS3/HCR3 protocol.
// Gather one COMPLETE line in vendor ERAM before exposing its first word.
// Prefetch preserves a continuous line through CSI header/gap backpressure.
// Complete a started carrier frame using empty CRC-protected chunks, then
// wait for real input at its next first line. No endless empty-frame stream.
module hci03_csi_carrier #(
 parameter LINE_BYTES=1440,FRAME_ROWS=128,IDLE_CYCLES=2000,
 parameter WORDS=LINE_BYTES/4,DATA_WORDS=WORDS-8
)(
 input wire clk,rst_n,input wire [31:0] s_data,input wire s_valid,s_first,output wire s_ready,
 output wire [31:0] m_data,output wire m_valid,m_sof,m_last,input wire m_ready,
 output reg [31:0] carrier_frames,chunks,empty_chunks,errors,
 output reg [63:0] input_bytes,container_bytes
);
 localparam FILL=0,CRC_HEADER=1,EMIT=2;
 reg [1:0] state;reg [15:0] fill_words,valid_words,line_index,emit_word,unissued,read_position;
 reg [31:0] idle_cycles,body_crc,header_crc;reg [2:0] crc_index;
 reg [15:0] first_offset;reg [255:0] header;
 reg [63:0] data_queue;reg qread,qwrite,rd_pending;reg [1:0] qcount;
 wire push=s_valid&&s_ready;
 assign s_ready=rst_n&&state==FILL&&fill_words<DATA_WORDS;
 wire output_body=emit_word>=8&&emit_word<8+valid_words;
 wire pop=m_valid&&m_ready&&output_body;
 wire [2:0] next_queue_count={1'b0,qcount}+rd_pending-pop;
 wire rd_en=state==EMIT&&unissued!=0&&next_queue_count<2;
 wire [31:0] ram_data;
 hci02_eram_sdp #(.DATA_WIDTH(32),.DEPTH(512))u_line(
  .clk(clk),.wr_en(push),.rd_en(rd_en),.wr_addr(fill_words[8:0]),.rd_addr(read_position[8:0]),.wr_data(s_data),.rd_data(ram_data));
 // Filled by creation script from the already verified balanced CRC matrix.
 function [31:0] crc32;
  input [31:0] c;input [31:0] d;reg [63:0] v;
  begin v={d,c};
   crc32[0]=^(v & 64'h4d101df04d101df);
   crc32[1]=^(v & 64'h9a203be09a203be);
   crc32[2]=^(v & 64'h1344077d1344077d);
   crc32[3]=^(v & 64'h26880efa26880efa);
   crc32[4]=^(v & 64'h4d101df44d101df4);
   crc32[5]=^(v & 64'h9a203be99a203be9);
   crc32[6]=^(v & 64'h3091760d3091760d);
   crc32[7]=^(v & 64'h6122ec1a6122ec1a);
   crc32[8]=^(v & 64'hc245d835c245d835);
   crc32[9]=^(v & 64'h805ab1b5805ab1b5);
   crc32[10]=^(v & 64'h46462b5046462b5);
   crc32[11]=^(v & 64'h8c8c56a08c8c56a);
   crc32[12]=^(v & 64'h11918ad411918ad4);
   crc32[13]=^(v & 64'h232315a9232315a9);
   crc32[14]=^(v & 64'h46462b5346462b53);
   crc32[15]=^(v & 64'h8c8c56a68c8c56a6);
   crc32[16]=^(v & 64'h1dc9ac921dc9ac92);
   crc32[17]=^(v & 64'h3b9359243b935924);
   crc32[18]=^(v & 64'h7726b2497726b249);
   crc32[19]=^(v & 64'hee4d6493ee4d6493);
   crc32[20]=^(v & 64'hd84bc8f9d84bc8f9);
   crc32[21]=^(v & 64'hb446902db446902d);
   crc32[22]=^(v & 64'h6c5c21846c5c2184);
   crc32[23]=^(v & 64'hd8b84309d8b84309);
   crc32[24]=^(v & 64'hb5a187ccb5a187cc);
   crc32[25]=^(v & 64'h6f920e466f920e46);
   crc32[26]=^(v & 64'hdf241c8cdf241c8c);
   crc32[27]=^(v & 64'hba9938c7ba9938c7);
   crc32[28]=^(v & 64'h71e3705171e37051);
   crc32[29]=^(v & 64'he3c6e0a3e3c6e0a3);
   crc32[30]=^(v & 64'hc35cc098c35cc098);
   crc32[31]=^(v & 64'h826880ef826880ef);
  end
 endfunction
 wire flush=state==FILL&&!push&&(fill_words!=0||line_index!=0)&&idle_cycles>=IDLE_CYCLES-1;
 wire full_line=push&&fill_words==DATA_WORDS-1;
 assign m_valid=state==EMIT&&(!output_body||qcount!=0);
 assign m_sof=m_valid&&line_index==0&&emit_word==0;
 assign m_last=m_valid&&emit_word==WORDS-1;
 assign m_data=emit_word<8?header[emit_word*32+:32]:output_body?(qread?data_queue[63:32]:data_queue[31:0]):32'd0;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=FILL;fill_words<=0;valid_words<=0;line_index<=0;emit_word<=0;unissued<=0;read_position<=0;
   idle_cycles<=0;body_crc<=32'hffffffff;header_crc<=32'hffffffff;crc_index<=0;first_offset<=16'hffff;header<=0;
   data_queue<=0;qread<=0;qwrite<=0;rd_pending<=0;qcount<=0;
   carrier_frames<=0;chunks<=0;empty_chunks<=0;errors<=0;input_bytes<=0;container_bytes<=0;
  end else begin
   rd_pending<=rd_en;
   if(rd_en)begin read_position<=read_position+1'b1;unissued<=unissued-1'b1;end
   if(rd_pending)begin
    if(qwrite)data_queue[63:32]<=ram_data;else data_queue[31:0]<=ram_data;qwrite<=~qwrite;
   end
   if(pop)qread<=~qread;
   case({rd_pending,pop})2'b10:qcount<=qcount+1'b1;2'b01:qcount<=qcount-1'b1;default:;endcase
   case(state)
    FILL:begin
     if(push)begin
      fill_words<=fill_words+1'b1;body_crc<=crc32(body_crc,s_data);input_bytes<=input_bytes+4;idle_cycles<=0;
      if(s_first&&first_offset==16'hffff)first_offset<=fill_words<<2;
     end else if(fill_words!=0||line_index!=0)begin if(idle_cycles<IDLE_CYCLES)idle_cycles<=idle_cycles+1'b1;end
     if(full_line||flush)begin
      valid_words<=full_line?fill_words+1'b1:fill_words;
      unissued<=full_line?fill_words+1'b1:fill_words;read_position<=0;emit_word<=0;qread<=0;qwrite<=0;qcount<=0;rd_pending<=0;
      header[31:0]<=32'h33534348;header[39:32]<=8'd1;header[47:40]<=fill_words==0&&!push?8'd1:8'd0;header[63:48]<=16'd32;
      header[95:64]<=chunks;header[111:96]<=full_line?(fill_words+1'b1)<<2:fill_words<<2;header[127:112]<=line_index;
      header[159:128]<=carrier_frames;header[191:160]<=~(full_line?crc32(body_crc,s_data):body_crc);
      header[207:192]<=first_offset==16'hffff&&push&&s_first?fill_words<<2:first_offset;header[223:208]<=0;header[255:224]<=0;
      header_crc<=32'hffffffff;crc_index<=0;state<=CRC_HEADER;
      if(fill_words==0&&!push)empty_chunks<=empty_chunks+1'b1;
     end
    end
    CRC_HEADER:begin
     header_crc<=crc32(header_crc,header[crc_index*32+:32]);
     if(crc_index==6)begin header[255:224]<=~crc32(header_crc,header[223:192]);state<=EMIT;end
     else crc_index<=crc_index+1'b1;
    end
    EMIT:begin
     // CSI may stall before payload, but this producer cannot underflow once
     // its first word is accepted. Both header and zero padding are ready.
     if(emit_word>=8&&output_body&&qcount==0)errors[0]<=1;
     if(m_valid&&m_ready)begin
      if(m_last)begin
       if(qcount!=(output_body?1:0)||rd_pending||unissued!=0)errors[1]<=1;
       state<=FILL;fill_words<=0;body_crc<=32'hffffffff;first_offset<=16'hffff;idle_cycles<=0;
       chunks<=chunks+1'b1;container_bytes<=container_bytes+LINE_BYTES;
       if(line_index==FRAME_ROWS-1)begin line_index<=0;carrier_frames<=carrier_frames+1'b1;end else line_index<=line_index+1'b1;
      end else emit_word<=emit_word+1'b1;
     end
    end
    default:state<=FILL;
   endcase
  end
 end
 // synthesis translate_off
 initial if(LINE_BYTES<64||LINE_BYTES%8!=0||DATA_WORDS>512||FRAME_ROWS<1||FRAME_ROWS>1080||IDLE_CYCLES<1)$fatal(1,"carrier geometry");
 // synthesis translate_on
endmodule
