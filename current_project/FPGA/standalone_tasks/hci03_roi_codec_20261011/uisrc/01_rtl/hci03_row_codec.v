`timescale 1ns/1ps
// Nonblocking real crop -> two owned row banks -> parallel lossless codecs.
// Descriptor acceptance grants one SEND bank; release after all packet bytes
// consumed is mandatory. No FREE reuse of CAP/ENC/READY/SEND storage.
module hci03_row_codec #(
 parameter CHANNELS=1,MAX_WIDTH=256,NL=4*CHANNELS,CAPACITY=MAX_WIDTH/4
)(
 input wire clk,rst_n,input wire s_valid,s_sof,s_last,s_eof,
 input wire [127:0] s_data,input wire [31:0] s_gray,input wire [2:0] s_count,
 input wire [15:0] s_x,s_y,s_origin_x,s_origin_y,s_width,s_height,
 input wire [31:0] s_frame_id,s_config_sequence,input wire [63:0] s_time_us,input wire [7:0] s_flags,
 output wire s_ready,input wire m_ready,output wire m_valid,m_bank,
 output wire [255:0] m_metadata,output wire [31:0] m_raw_crc32,
 output wire [NL-1:0] m_lane_modes,output wire [NL*9-1:0] m_lane_lengths,
 input wire [NL*9-1:0] read_addr,output wire [NL*16-1:0] read_pairs,
 input wire release_valid,release_bank,
 output reg [31:0] received_rows,encoded_rows,sent_rows,dropped_rows,last_dropped_frame_id,errors,
 output wire [1:0] occupancy,output reg [1:0] high_water
);
 localparam FREE=0,CAP=1,WAIT_ENC=2,ENC=3,READY=4,SEND=5;
 reg [2:0] ownership[0:1];reg [31:0] row_sequence[0:1];
 reg [255:0] metadata[0:1];reg [31:0] row_crc[0:1];
 reg [NL-1:0] modes[0:1];reg [NL*9-1:0] lengths[0:1];
 reg capturing,drop_row,cap_bank;reg [15:0] cap_pixels;
 reg enc_active,enc_bank,enc_start,tx_active,tx_bank;reg [NL-1:0] done_seen;
 wire [NL-1:0] core_busy,core_done,core_done_bank,core_mode;
 wire [NL*9-1:0] core_length;wire [NL*32-1:0] core_errors;
 wire starting=s_x==0;
 wire any_free=ownership[0]==FREE||ownership[1]==FREE;
 wire selected_bank=starting?(ownership[0]==FREE?1'b0:1'b1):cap_bank;
 wire [255:0] selected_metadata=metadata[cap_bank];
 wire [16:0] next_pixels=(starting?17'd0:{1'b0,cap_pixels})+s_count;
 wire geometry_bad=s_width==0||s_width>MAX_WIDTH||s_height==0||s_y>=s_height;
 wire identity_bad=!starting&&(s_frame_id!=selected_metadata[31:0]||s_config_sequence!=selected_metadata[63:32]||
  s_time_us!=selected_metadata[127:64]||{s_origin_y,s_origin_x}!=selected_metadata[159:128]||
  {s_height,s_width}!=selected_metadata[191:160]||s_y!=selected_metadata[207:192]||s_flags!=selected_metadata[215:208]);
 wire beat_bad=s_count==0||s_count>4||geometry_bad||!s_flags[3]||identity_bad||
  (!starting&&s_x!=cap_pixels)||next_pixels>s_width||s_last!=(next_pixels==s_width)||
  s_eof!=(s_last&&s_y==s_height-1'b1)||s_sof!=(starting&&s_y==0);
 wire take=s_valid&&!beat_bad&&(starting?any_free:(capturing&&!drop_row));
 assign s_ready=1'b1;
 assign occupancy=(ownership[0]!=FREE?2'd1:2'd0)+(ownership[1]!=FREE?2'd1:2'd0);
 wire both_ready=ownership[0]==READY&&ownership[1]==READY;
 wire ready_bank=ownership[0]!=READY?1'b1:(both_ready&&$signed(row_sequence[0]-row_sequence[1])>0?1'b1:1'b0);
 wire output_bank=tx_active?tx_bank:ready_bank;
 assign m_valid=!tx_active&&(ownership[0]==READY||ownership[1]==READY);
 assign m_bank=output_bank;assign m_metadata=metadata[output_bank];assign m_raw_crc32=row_crc[output_bank];
 assign m_lane_modes=modes[output_bank];assign m_lane_lengths=lengths[output_bank];
 wire both_wait=ownership[0]==WAIT_ENC&&ownership[1]==WAIT_ENC;
 wire waiting_bank=ownership[0]!=WAIT_ENC?1'b1:(both_wait&&$signed(row_sequence[0]-row_sequence[1])>0?1'b1:1'b0);
 genvar g;
 generate for(g=0;g<NL;g=g+1)begin:lane
  localparam PIXEL=g/CHANNELS,CHANNEL=g%CHANNELS;
  // Odd source origins yield e.g. 3 pixels then 4 at local x=3.
  // Stripe by actual local pixel position, rather than compact beat index.
  wire [1:0] capture_index=PIXEL-s_x[1:0];
  wire [16:0] capture_x={1'b0,s_x}+capture_index;
  wire [8:0] capture_address=capture_x[10:2];
  wire [7:0] value;
  if(CHANNELS==1)assign value=s_gray[capture_index*8+:8];
  else assign value=s_data[capture_index*32+CHANNEL*8+:8];
  wire [15:0] w=metadata[enc_bank][175:160];
  wire [8:0] n=(w+16'd3-PIXEL)>>2;
  hci03_lz1_lane #(.N(CAPACITY))u_codec(.clk(clk),.rst_n(rst_n),
   .cap_valid(take&&s_count>capture_index),.cap_gray(value),.cap_addr(capture_address),.cap_line_start(capture_address==0),.cap_bank(selected_bank),
   .start(enc_start),.start_bank(enc_bank),.start_length(n),.errors(core_errors[g*32+:32]),
   .busy(core_busy[g]),.done(core_done[g]),.done_bank(core_done_bank[g]),.done_mode(core_mode[g]),.done_length(core_length[g*9+:9]),
   .read_bank(output_bank),.read_mode(modes[output_bank][g]),.read_addr(read_addr[g*9+:9]),.read_data(read_pairs[g*16+:8]),
   .read_addr_next(read_addr[g*9+:9]+9'd1),.read_data_next(read_pairs[g*16+8+:8]));
 end endgenerate
 function [31:0] crc8;
  input [31:0] c;input [7:0] d;reg [39:0] v;
  begin v={d,c};
   crc8[0]=^(v & 40'h400000104);
   crc8[1]=^(v & 40'h900000209);
   crc8[2]=^(v & 40'h1300000413);
   crc8[3]=^(v & 40'h2600000826);
   crc8[4]=^(v & 40'h4d0000104d);
   crc8[5]=^(v & 40'h9a0000209a);
   crc8[6]=^(v & 40'h3000004030);
   crc8[7]=^(v & 40'h6100008061);
   crc8[8]=^(v & 40'hc2000100c2);
   crc8[9]=^(v & 40'h8000020080);
   crc8[10]=^(v & 40'h400040004);
   crc8[11]=^(v & 40'h800080008);
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
 function [31:0] crc16;
  input [31:0] c;input [15:0] d;reg [47:0] v;
  begin v={d,c};
   crc16[0]=^(v & 48'h4d1000104d1);
   crc16[1]=^(v & 48'h9a2000209a2);
   crc16[2]=^(v & 48'h134400041344);
   crc16[3]=^(v & 48'h268800082688);
   crc16[4]=^(v & 48'h4d1000104d10);
   crc16[5]=^(v & 48'h9a2000209a20);
   crc16[6]=^(v & 48'h309100403091);
   crc16[7]=^(v & 48'h612200806122);
   crc16[8]=^(v & 48'hc2450100c245);
   crc16[9]=^(v & 48'h805a0200805a);
   crc16[10]=^(v & 48'h46404000464);
   crc16[11]=^(v & 48'h8c8080008c8);
   crc16[12]=^(v & 48'h119110001191);
   crc16[13]=^(v & 48'h232320002323);
   crc16[14]=^(v & 48'h464640004646);
   crc16[15]=^(v & 48'h8c8c80008c8c);
   crc16[16]=^(v & 48'h1dc900001dc9);
   crc16[17]=^(v & 48'h3b9300003b93);
   crc16[18]=^(v & 48'h772600007726);
   crc16[19]=^(v & 48'hee4d0000ee4d);
   crc16[20]=^(v & 48'hd84b0000d84b);
   crc16[21]=^(v & 48'hb4460000b446);
   crc16[22]=^(v & 48'h6c5c00006c5c);
   crc16[23]=^(v & 48'hd8b80000d8b8);
   crc16[24]=^(v & 48'hb5a10000b5a1);
   crc16[25]=^(v & 48'h6f9200006f92);
   crc16[26]=^(v & 48'hdf240000df24);
   crc16[27]=^(v & 48'hba990000ba99);
   crc16[28]=^(v & 48'h71e3000071e3);
   crc16[29]=^(v & 48'he3c60000e3c6);
   crc16[30]=^(v & 48'hc35c0000c35c);
   crc16[31]=^(v & 48'h826800008268);
  end
 endfunction
 function [31:0] crc24;
  input [31:0] c;input [23:0] d;reg [55:0] v;
  begin v={d,c};
   crc24[0]=^(v & 56'h4d1010104d101);
   crc24[1]=^(v & 56'h9a2030209a203);
   crc24[2]=^(v & 56'h13440704134407);
   crc24[3]=^(v & 56'h26880e0826880e);
   crc24[4]=^(v & 56'h4d101d104d101d);
   crc24[5]=^(v & 56'h9a203b209a203b);
   crc24[6]=^(v & 56'h30917640309176);
   crc24[7]=^(v & 56'h6122ec806122ec);
   crc24[8]=^(v & 56'hc245d800c245d8);
   crc24[9]=^(v & 56'h805ab100805ab1);
   crc24[10]=^(v & 56'h4646200046462);
   crc24[11]=^(v & 56'h8c8c50008c8c5);
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
 function [31:0] crc48;
  input [31:0] c;input [47:0] d;reg [79:0] v;
  begin v={d,c};
   crc48[0]=^(v & 80'h4d101df481b01df481b);
   crc48[1]=^(v & 80'h9a203be903603be9036);
   crc48[2]=^(v & 80'h1344077d206d077d206d);
   crc48[3]=^(v & 80'h26880efa40da0efa40da);
   crc48[4]=^(v & 80'h4d101df481b41df481b4);
   crc48[5]=^(v & 80'h9a203be903693be90369);
   crc48[6]=^(v & 80'h3091760d4ec8760d4ec8);
   crc48[7]=^(v & 80'h6122ec1a9d91ec1a9d91);
   crc48[8]=^(v & 80'hc245d8353b23d8353b23);
   crc48[9]=^(v & 80'h805ab1b53e5db1b53e5d);
   crc48[10]=^(v & 80'h46462b534a062b534a0);
   crc48[11]=^(v & 80'h8c8c56a6940c56a6940);
   crc48[12]=^(v & 80'h11918ad4d2818ad4d281);
   crc48[13]=^(v & 80'h232315a9a50215a9a502);
   crc48[14]=^(v & 80'h46462b534a052b534a05);
   crc48[15]=^(v & 80'h8c8c56a6940b56a6940b);
   crc48[16]=^(v & 80'h1dc9ac92600cac92600c);
   crc48[17]=^(v & 80'h3b935924c0185924c018);
   crc48[18]=^(v & 80'h7726b2498031b2498031);
   crc48[19]=^(v & 80'hee4d6493006364930063);
   crc48[20]=^(v & 80'hd84bc8f948ddc8f948dd);
   crc48[21]=^(v & 80'hb446902dd9a0902dd9a0);
   crc48[22]=^(v & 80'h6c5c2184fb5b2184fb5b);
   crc48[23]=^(v & 80'hd8b84309f6b64309f6b6);
   crc48[24]=^(v & 80'hb5a187cca57787cca577);
   crc48[25]=^(v & 80'h6f920e4602f50e4602f5);
   crc48[26]=^(v & 80'hdf241c8c05ea1c8c05ea);
   crc48[27]=^(v & 80'hba9938c743cf38c743cf);
   crc48[28]=^(v & 80'h71e37051cf847051cf84);
   crc48[29]=^(v & 80'he3c6e0a39f08e0a39f08);
   crc48[30]=^(v & 80'hc35cc098760bc098760b);
   crc48[31]=^(v & 80'h826880efa40d80efa40d);
  end
 endfunction
 function [31:0] crc72;
  input [31:0] c;input [71:0] d;reg [103:0] v;
  begin v={d,c};
   crc72[0]=^(v & 104'h4d101df481b4e5af11b4e5af1);
   crc72[1]=^(v & 104'h9a203be90369cb5e3369cb5e3);
   crc72[2]=^(v & 104'h1344077d206d396bc66d396bc6);
   crc72[3]=^(v & 104'h26880efa40da72d78cda72d78c);
   crc72[4]=^(v & 104'h4d101df481b4e5af18b4e5af18);
   crc72[5]=^(v & 104'h9a203be90369cb5e3069cb5e30);
   crc72[6]=^(v & 104'h3091760d4ec8d8e691c8d8e691);
   crc72[7]=^(v & 104'h6122ec1a9d91b1cd2291b1cd22);
   crc72[8]=^(v & 104'hc245d8353b23639a4423639a44);
   crc72[9]=^(v & 104'h805ab1b53e5d896e785d896e78);
   crc72[10]=^(v & 104'h46462b534a05c8601a05c8601);
   crc72[11]=^(v & 104'h8c8c56a6940b90c0240b90c02);
   crc72[12]=^(v & 104'h11918ad4d28172180581721805);
   crc72[13]=^(v & 104'h232315a9a502e4300a02e4300a);
   crc72[14]=^(v & 104'h46462b534a05c8601405c86014);
   crc72[15]=^(v & 104'h8c8c56a6940b90c0280b90c028);
   crc72[16]=^(v & 104'h1dc9ac92600c6fdaa10c6fdaa1);
   crc72[17]=^(v & 104'h3b935924c018dfb54318dfb543);
   crc72[18]=^(v & 104'h7726b2498031bf6a8631bf6a86);
   crc72[19]=^(v & 104'hee4d649300637ed50d637ed50d);
   crc72[20]=^(v & 104'hd84bc8f948ddb3f0ebddb3f0eb);
   crc72[21]=^(v & 104'hb446902dd9a029bb27a029bb27);
   crc72[22]=^(v & 104'h6c5c2184fb5b1d2cbf5b1d2cbf);
   crc72[23]=^(v & 104'hd8b84309f6b63a597eb63a597e);
   crc72[24]=^(v & 104'hb5a187cca5773ae80d773ae80d);
   crc72[25]=^(v & 104'h6f920e4602f53b8aebf53b8aeb);
   crc72[26]=^(v & 104'hdf241c8c05ea7715d7ea7715d7);
   crc72[27]=^(v & 104'hba9938c743cfa0715ecfa0715e);
   crc72[28]=^(v & 104'h71e37051cf840eb84d840eb84d);
   crc72[29]=^(v & 104'he3c6e0a39f081d709a081d709a);
   crc72[30]=^(v & 104'hc35cc098760b74bbc40b74bbc4);
   crc72[31]=^(v & 104'h826880efa40da72d780da72d78);
  end
 endfunction
 function [31:0] crc96;
  input [31:0] c;input [95:0] d;reg [127:0] v;
  begin v={d,c};
   crc96[0]=^(v & 128'h4d101df481b4e5af182fa07f182fa07);
   crc96[1]=^(v & 128'h9a203be90369cb5e305f40fe305f40f);
   crc96[2]=^(v & 128'h1344077d206d396bc60be81fc60be81f);
   crc96[3]=^(v & 128'h26880efa40da72d78c17d03f8c17d03f);
   crc96[4]=^(v & 128'h4d101df481b4e5af182fa07e182fa07e);
   crc96[5]=^(v & 128'h9a203be90369cb5e305f40fd305f40fd);
   crc96[6]=^(v & 128'h3091760d4ec8d8e6913c7bfd913c7bfd);
   crc96[7]=^(v & 128'h6122ec1a9d91b1cd2278f7fa2278f7fa);
   crc96[8]=^(v & 128'hc245d8353b23639a44f1eff444f1eff4);
   crc96[9]=^(v & 128'h805ab1b53e5d896e786125ee786125ee);
   crc96[10]=^(v & 128'h46462b534a05c860140b1db0140b1db);
   crc96[11]=^(v & 128'h8c8c56a6940b90c028163b7028163b7);
   crc96[12]=^(v & 128'h11918ad4d28172180502c76e0502c76e);
   crc96[13]=^(v & 128'h232315a9a502e4300a058edc0a058edc);
   crc96[14]=^(v & 128'h46462b534a05c860140b1db9140b1db9);
   crc96[15]=^(v & 128'h8c8c56a6940b90c028163b7228163b72);
   crc96[16]=^(v & 128'h1dc9ac92600c6fdaa1ae8ce3a1ae8ce3);
   crc96[17]=^(v & 128'h3b935924c018dfb5435d19c6435d19c6);
   crc96[18]=^(v & 128'h7726b2498031bf6a86ba338d86ba338d);
   crc96[19]=^(v & 128'hee4d649300637ed50d74671a0d74671a);
   crc96[20]=^(v & 128'hd84bc8f948ddb3f0eb6a3432eb6a3432);
   crc96[21]=^(v & 128'hb446902dd9a029bb2756926327569263);
   crc96[22]=^(v & 128'h6c5c2184fb5b1d2cbf2fdec0bf2fdec0);
   crc96[23]=^(v & 128'hd8b84309f6b63a597e5fbd817e5fbd81);
   crc96[24]=^(v & 128'hb5a187cca5773ae80d3d81050d3d8105);
   crc96[25]=^(v & 128'h6f920e4602f53b8aebf9f80debf9f80d);
   crc96[26]=^(v & 128'hdf241c8c05ea7715d7f3f01ad7f3f01a);
   crc96[27]=^(v & 128'hba9938c743cfa0715e651a335e651a33);
   crc96[28]=^(v & 128'h71e37051cf840eb84d48ce614d48ce61);
   crc96[29]=^(v & 128'he3c6e0a39f081d709a919cc29a919cc2);
   crc96[30]=^(v & 128'hc35cc098760b74bbc4a1c382c4a1c382);
   crc96[31]=^(v & 128'h826880efa40da72d78c17d0378c17d03);
  end
 endfunction
 wire [95:0] rgb={s_data[119:96],s_data[87:64],s_data[55:32],s_data[23:0]};
 wire [31:0] seed=starting?32'hffffffff:row_crc[cap_bank];
 wire [31:0] next_crc;
 generate if(CHANNELS==1)begin:gray_crc
  assign next_crc=s_count==1?crc8(seed,s_gray[7:0]):s_count==2?crc16(seed,s_gray[15:0]):
   s_count==3?crc24(seed,s_gray[23:0]):crc32(seed,s_gray);
 end else begin:rgb_crc
  assign next_crc=s_count==1?crc24(seed,rgb[23:0]):s_count==2?crc48(seed,rgb[47:0]):s_count==3?crc72(seed,rgb[71:0]):crc96(seed,rgb);
 end endgenerate
 integer k;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   ownership[0]<=FREE;ownership[1]<=FREE;row_sequence[0]<=0;row_sequence[1]<=0;
   metadata[0]<=0;metadata[1]<=0;row_crc[0]<=0;row_crc[1]<=0;modes[0]<=0;modes[1]<=0;lengths[0]<=0;lengths[1]<=0;
   capturing<=0;drop_row<=0;cap_bank<=0;cap_pixels<=0;enc_active<=0;enc_bank<=0;enc_start<=0;done_seen<=0;tx_active<=0;tx_bank<=0;
   received_rows<=0;encoded_rows<=0;sent_rows<=0;dropped_rows<=0;last_dropped_frame_id<=0;errors<=0;high_water<=0;
  end else begin
   enc_start<=0;
   if(occupancy>high_water)high_water<=occupancy;
   if(release_valid)begin
    if(tx_active&&release_bank==tx_bank&&ownership[tx_bank]==SEND)begin
     ownership[tx_bank]<=FREE;tx_active<=0;sent_rows<=sent_rows+1'b1;
    end else errors[2]<=1;
   end
   if(m_valid&&m_ready)begin ownership[ready_bank]<=SEND;tx_active<=1;tx_bank<=ready_bank;end
   if(!enc_active&&(ownership[0]==WAIT_ENC||ownership[1]==WAIT_ENC))begin
    enc_bank<=waiting_bank;enc_active<=1;enc_start<=1;done_seen<=0;ownership[waiting_bank]<=ENC;
   end
   if(enc_active)begin
    done_seen<=done_seen|core_done;
    for(k=0;k<NL;k=k+1)if(core_done[k])begin
     modes[enc_bank][k]<=core_mode[k];lengths[enc_bank][k*9+:9]<=core_length[k*9+:9];
     if(core_done_bank[k]!=enc_bank||core_length[k*9+:9]>((metadata[enc_bank][175:160]+3-k/CHANNELS)>>2))errors[3]<=1;
    end
    if(&(done_seen|core_done))begin ownership[enc_bank]<=READY;enc_active<=0;encoded_rows<=encoded_rows+1'b1;end
   end
   if(|core_errors)errors[3]<=1;
   if(s_valid)begin
    if(starting)begin
     received_rows<=received_rows+1'b1;
     if(capturing)begin ownership[cap_bank]<=FREE;capturing<=0;errors[1]<=1;end
     if(!any_free||beat_bad)begin
      drop_row<=!s_last;capturing<=0;dropped_rows<=dropped_rows+1'b1;last_dropped_frame_id<=s_frame_id;
      if(!any_free)errors[0]<=1;if(beat_bad)errors[1]<=1;
     end else begin
      cap_bank<=selected_bank;cap_pixels<=s_count;capturing<=!s_last;drop_row<=0;
      ownership[selected_bank]<=s_last?WAIT_ENC:CAP;row_sequence[selected_bank]<=received_rows;
      metadata[selected_bank]<={8'd0,({16'd0,s_width}*CHANNELS),s_flags,s_y,s_height,s_width,s_origin_y,s_origin_x,s_time_us,s_config_sequence,s_frame_id};
      row_crc[selected_bank]<=s_last?~next_crc:next_crc;
     end
    end else if(capturing&&!drop_row)begin
     if(beat_bad)begin
      ownership[cap_bank]<=FREE;capturing<=0;drop_row<=!s_last;errors[1]<=1;dropped_rows<=dropped_rows+1'b1;last_dropped_frame_id<=s_frame_id;
     end else begin
      cap_pixels<=next_pixels[15:0];row_crc[cap_bank]<=s_last?~next_crc:next_crc;
      if(s_last)begin ownership[cap_bank]<=WAIT_ENC;capturing<=0;end
     end
    end else if(drop_row)begin if(s_last)drop_row<=0;end
    else begin errors[1]<=1;dropped_rows<=dropped_rows+1'b1;last_dropped_frame_id<=s_frame_id;drop_row<=!s_last;end
   end
  end
 end
 // synthesis translate_off
 initial if((CHANNELS!=1&&CHANNELS!=3)||MAX_WIDTH<8||MAX_WIDTH>448||MAX_WIDTH%8!=0)$fatal(1,"Unsupported owned row geometry");
 // synthesis translate_on
endmodule
