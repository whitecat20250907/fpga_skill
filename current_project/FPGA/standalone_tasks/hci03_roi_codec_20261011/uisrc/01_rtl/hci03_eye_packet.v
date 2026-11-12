`timescale 1ns/1ps
// Each real eye-measurement pulse is captured independently of UART polling.
// Eight complete reports in supplier ERAM; busy/full publication drops a
// WHOLE report and records its source FID. The eye engine is never stalled.
module hci03_eye_packet #(parameter EYE=0)(
 input wire clk,rst_n,s_valid,input wire [767:0] s_result,
 input wire [31:0] engine_received,engine_skipped,engine_deadline,
 output wire [63:0] m_data,output wire m_valid,m_first,m_last,input wire m_ready,
 output reg [31:0] received,queued,sent,dropped,last_dropped_frame_id,errors,
 output reg [3:0] occupancy,high_water
);
 localparam [7:0] EYE_ID=EYE;
 reg writing;reg [4:0] write_word,read_word;reg [2:0] wp,rp;
 reg [767:0] result_copy;reg [255:0] header_copy;reg [95:0] counters_copy;
 reg [31:0] crc;reg [63:0] held_data;reg held_valid,read_pending;
 wire pop=held_valid&&m_ready;wire retire=pop&&read_word==17;
 wire commit=writing&&write_word==17;
 wire [63:0] body_word=write_word<4?header_copy[write_word*64+:64]:
  write_word<16?result_copy[(write_word-4)*64+:64]:
  write_word==16?counters_copy[63:0]:{~crc32(crc,counters_copy[95:64]),counters_copy[95:64]};
 wire rd_en=rst_n&&occupancy!=0&&!held_valid&&!read_pending;
 wire [63:0] ram_data;
 hci02_eram_sdp #(.DATA_WIDTH(64),.DEPTH(256))u_reports(
  .clk(clk),.wr_en(writing),.rd_en(rd_en),.wr_addr({wp,write_word}),.rd_addr({rp,read_word}),.wr_data(body_word),.rd_data(ram_data));
 assign m_data=held_data;assign m_valid=rst_n&&held_valid;
 assign m_first=read_word==0;assign m_last=read_word==17;
 // Exact balanced GF(2) matrices are generated and verified by the helper.
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
 function [31:0] crc64;
  input [31:0] c;input [63:0] d;reg [95:0] v;
  begin v={d,c};
   crc64[0]=^(v & 96'h4d101df481b4e5a481b4e5a);
   crc64[1]=^(v & 96'h9a203be90369cb590369cb5);
   crc64[2]=^(v & 96'h1344077d206d396b206d396b);
   crc64[3]=^(v & 96'h26880efa40da72d740da72d7);
   crc64[4]=^(v & 96'h4d101df481b4e5af81b4e5af);
   crc64[5]=^(v & 96'h9a203be90369cb5e0369cb5e);
   crc64[6]=^(v & 96'h3091760d4ec8d8e64ec8d8e6);
   crc64[7]=^(v & 96'h6122ec1a9d91b1cd9d91b1cd);
   crc64[8]=^(v & 96'hc245d8353b23639a3b23639a);
   crc64[9]=^(v & 96'h805ab1b53e5d896e3e5d896e);
   crc64[10]=^(v & 96'h46462b534a05c8634a05c86);
   crc64[11]=^(v & 96'h8c8c56a6940b90c6940b90c);
   crc64[12]=^(v & 96'h11918ad4d2817218d2817218);
   crc64[13]=^(v & 96'h232315a9a502e430a502e430);
   crc64[14]=^(v & 96'h46462b534a05c8604a05c860);
   crc64[15]=^(v & 96'h8c8c56a6940b90c0940b90c0);
   crc64[16]=^(v & 96'h1dc9ac92600c6fda600c6fda);
   crc64[17]=^(v & 96'h3b935924c018dfb5c018dfb5);
   crc64[18]=^(v & 96'h7726b2498031bf6a8031bf6a);
   crc64[19]=^(v & 96'hee4d649300637ed500637ed5);
   crc64[20]=^(v & 96'hd84bc8f948ddb3f048ddb3f0);
   crc64[21]=^(v & 96'hb446902dd9a029bbd9a029bb);
   crc64[22]=^(v & 96'h6c5c2184fb5b1d2cfb5b1d2c);
   crc64[23]=^(v & 96'hd8b84309f6b63a59f6b63a59);
   crc64[24]=^(v & 96'hb5a187cca5773ae8a5773ae8);
   crc64[25]=^(v & 96'h6f920e4602f53b8a02f53b8a);
   crc64[26]=^(v & 96'hdf241c8c05ea771505ea7715);
   crc64[27]=^(v & 96'hba9938c743cfa07143cfa071);
   crc64[28]=^(v & 96'h71e37051cf840eb8cf840eb8);
   crc64[29]=^(v & 96'he3c6e0a39f081d709f081d70);
   crc64[30]=^(v & 96'hc35cc098760b74bb760b74bb);
   crc64[31]=^(v & 96'h826880efa40da72da40da72d);
  end
 endfunction

 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   writing<=0;write_word<=0;read_word<=0;wp<=0;rp<=0;result_copy<=0;header_copy<=0;counters_copy<=0;
   crc<=32'hffffffff;held_data<=0;held_valid<=0;read_pending<=0;
   received<=0;queued<=0;sent<=0;dropped<=0;last_dropped_frame_id<=0;errors<=0;occupancy<=0;high_water<=0;
  end else begin
   read_pending<=rd_en;
   if(read_pending)begin held_data<=ram_data;held_valid<=1;end
   if(pop)begin
    held_valid<=0;
    if(retire)begin read_word<=0;rp<=rp+1'b1;sent<=sent+1'b1;end else read_word<=read_word+1'b1;
   end
   case({commit,retire})2'b10:begin occupancy<=occupancy+1'b1;if(occupancy+1'b1>high_water)high_water<=occupancy+1'b1;end
    2'b01:occupancy<=occupancy-1'b1;default:;endcase
   if(writing)begin
    if(commit)begin writing<=0;wp<=wp+1'b1;queued<=queued+1'b1;end
    else begin write_word<=write_word+1'b1;crc<=crc64(crc,body_word);end
   end
   if(s_valid)begin
    received<=received+1'b1;
    if(writing||occupancy==8)begin dropped<=dropped+1'b1;last_dropped_frame_id<=s_result[63:32];end
    else begin
     writing<=1;write_word<=0;crc<=32'hffffffff;result_copy<=s_result;
     header_copy<={sent,received+1'b1,32'd0,last_dropped_frame_id,dropped,queued,16'd144,EYE_ID,8'd1,32'h33454348};
     counters_copy<={engine_deadline,engine_skipped,engine_received};
    end
   end
   if(occupancy>8||(retire&&occupancy==0))errors[0]<=1;
  end
 end
 // synthesis translate_off
 initial if(EYE<0||EYE>1)$fatal(1,"eye packet identity");
 // synthesis translate_on
endmodule
