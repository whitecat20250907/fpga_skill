`timescale 1ns/1ps
// Protocol/line-boundary test. No PHY or CDC model is used. The source supplies
// complete CSI-2 headers, RAW10 payloads and CRC footers at a throttled rate.
module tb_physical_crop;
 reg clk=0;always #4 clk=~clk;
 reg resetn=0,valid=0;reg [31:0] data=0;
 wire [31:0] payload,packets,crc_errors,ecc_errors,wc_errors,timeouts;
 wire payload_valid,payload_last,line_start,fs,unpack_valid,unpack_last,unpack_error,packet_error;
 wire [2:0] payload_bytes;wire [39:0] raw;
 csi_rx_packet_handler parser(.I_clock(clk),.I_reset_n(resetn),.I_enable(1'b1),.I_count_enable(1'b1),
  .I_data(data),.I_data_valid(valid),.O_packet_done(),.O_sync_wait(),
  .O_payload_out(payload),.O_payload_valid(payload_valid),.O_payload_bytes(payload_bytes),.O_payload_last(payload_last),
  .O_vsync_out(fs),.O_in_frame(),.O_in_line(line_start),.O_packet_error(packet_error),
  .O_raw_packets(packets),.O_crc_errors(crc_errors),.O_ecc_errors(ecc_errors),.O_wc_errors(wc_errors),.O_timeout_errors(timeouts));
 csi_rx_10bit_unpack unpack(.I_clock(clk),.I_reset_n(resetn),.I_enable(1'b1),.I_line_in(line_start),
  .I_data_in(payload),.I_din_valid(payload_valid),.I_din_bytes(payload_bytes),.I_din_last(payload_last),
  .O_data_out(raw),.O_dout_valid(unpack_valid),.O_dout_last(unpack_last),.O_unpack_error(unpack_error));
 reg [14:0] vstart=35,vend=756,hend=321;
 reg [12:0] width=1280,height=720;
 reg [1:0] cfg_bayer=3,frame_bayer=3;
 wire crop_valid,crop_last,crop_sof,raw_ready,crop_ready;wire [39:0] crop_data;
 image_correction crop(.I_clk(clk),.I_rst_n(resetn),.I_v_start(vstart),.I_v_end(vend),.I_h_end(hend),
  .I_raw_tdata(raw),.I_raw_tdest(10'd0),.I_raw_tlast(unpack_last),.I_raw_tvalid(unpack_valid),.I_raw_tuser(fs),.I_raw_tready(raw_ready),
  .O_raw_tdata(crop_data),.O_raw_tdest(),.O_raw_tlast(crop_last),.O_raw_tvalid(crop_valid),.O_raw_tuser(crop_sof),.O_raw_tready(crop_ready));
 // Same metadata latch as cam_video_source, BEFORE the elastic BLC register.
 always @(posedge clk or negedge resetn)
  if(!resetn)frame_bayer<=3;
  else if(crop_valid&&crop_ready&&crop_sof)frame_bayer<=cfg_bayer;
 wire [39:0] blc_data;wire blc_valid,blc_last,blc_sof,isp_ready;
 ui_BLC #(.Black_level_offset_r0(0),.Black_level_offset_r1(0),.Black_level_offset_r2(0),.Black_level_offset_r3(0)) blc(
  .I_clk(clk),.I_rst_n(resetn),.I_tdata(crop_data),.I_tdest(10'd0),.I_tvalid(crop_valid),.I_tlast(crop_last),.I_tuser(crop_sof),.I_tready(crop_ready),
  .O_tdata(blc_data),.O_tdest(),.O_tvalid(blc_valid),.O_tlast(blc_last),.O_tuser(blc_sof),.O_tready(isp_ready));
 wire [127:0] rgb,packed_data;wire rgb_valid,rgb_last,rgb_sof,rgb_ready;
 wire packed_valid,packed_last,packed_final,packed_sof,packed_eof;wire [31:0] frame_count;
 ui_top_demosaic #(.BAYER_MODE("GBRG")) isp(.I_clk(clk),.I_rst_n(resetn),.I_bayer_mode(frame_bayer),.I_img_width(width),.I_img_height(height),
  .I_axi4s_tdata(blc_data),.I_axi4s_tdest(10'd0),.I_axi4s_tlast(blc_last),.I_axi4s_tvalid(blc_valid),.I_axi4s_tuser(blc_sof),.I_axi4s_tready(isp_ready),
  .O_tdata(rgb),.O_tvalid(rgb_valid),.O_tlast(rgb_last),.O_tuser(rgb_sof),.O_tready(rgb_ready));
 pack4_rgb24_to_128 packer(.clk(clk),.rst_n(resetn),.enable(1'b1),.cfg_img_height(height),
  .s_tdata(rgb),.s_tvalid(rgb_valid),.s_tready(rgb_ready),.s_tlast(rgb_last),.s_tuser(rgb_sof),
  .m_tdata(packed_data),.m_tvalid(packed_valid),.m_tready(1'b1),.m_tlast(packed_last),.m_frame_last(packed_final),.sof(packed_sof),.eof(packed_eof),.frame_count_out(frame_count));
 function automatic [7:0] ecc(input [23:0] d);
  begin
   ecc[0]=d[0]^d[1]^d[2]^d[4]^d[5]^d[7]^d[10]^d[11]^d[13]^d[16]^d[20]^d[21]^d[22]^d[23];
   ecc[1]=d[0]^d[1]^d[3]^d[4]^d[6]^d[8]^d[10]^d[12]^d[14]^d[17]^d[20]^d[21]^d[22]^d[23];
   ecc[2]=d[0]^d[2]^d[3]^d[5]^d[6]^d[9]^d[11]^d[12]^d[15]^d[18]^d[20]^d[21]^d[22];
   ecc[3]=d[1]^d[2]^d[3]^d[7]^d[8]^d[9]^d[13]^d[14]^d[15]^d[19]^d[20]^d[21]^d[23];
   ecc[4]=d[4]^d[5]^d[6]^d[7]^d[8]^d[9]^d[16]^d[17]^d[18]^d[19]^d[20]^d[22]^d[23];
   ecc[5]=d[10]^d[11]^d[12]^d[13]^d[14]^d[15]^d[16]^d[17]^d[18]^d[19]^d[21]^d[22]^d[23];ecc[7:6]=0;
  end
 endfunction
 function automatic [15:0] crc_byte(input [15:0] c,input [7:0] b);
  integer n;reg [15:0] x;begin x=c;for(n=0;n<8;n=n+1)x=(x>>1)^((x[0]^b[n])?16'h8408:0);crc_byte=x;end
 endfunction
 function automatic integer site(input integer y,x);
  site=(!(y%2)&&(x%2))?2:((y%2&&!(x%2))?0:1); // physical GBRG
 endfunction
 function automatic integer raw8(input integer y,x);
  raw8=(site(y,x)==0?180:(site(y,x)==1?90:20))+(x%13)+(y%11);
 endfunction
 function automatic [9:0] pixel(input integer y,x);
  pixel=(raw8(y,x)*4)+((x+y)%4); // exercise all low-two-bit RAW10 lanes
 endfunction
 function automatic integer mirror(input integer a,size);
  if(size==1)mirror=0;else if(a<0)mirror=-a;else if(a>=size)mirror=2*size-2-a;else mirror=a;
 endfunction
 integer physical_width=1944,physical_height=1097,first_row=36,expected_rows=720;
 integer raw_index=0,crop_index=0,rgb_index=0,pack_index=0,eof_count=0,sof_count=0;
 integer saved_frame_count=0,check_active=0,case_id=0;
 function automatic integer sampled(input integer y,x);
  sampled=raw8(first_row+mirror(y,height),4+mirror(x,width));
 endfunction
 function automatic integer channel(input integer y,x,c);
  integer s,n;begin
   s=site(y,x);
   if(s==c)channel=sampled(y,x);
   else if(s==1)begin
    n=site(y,x^1);
    if(n==c)channel=(sampled(y,x-1)+sampled(y,x+1))/2;
    else channel=(sampled(y-1,x)+sampled(y+1,x))/2;
   end else if(c==1)channel=(sampled(y-1,x)+sampled(y+1,x)+sampled(y,x-1)+sampled(y,x+1))/4;
   else channel=(sampled(y-1,x-1)+sampled(y-1,x+1)+sampled(y+1,x-1)+sampled(y+1,x+1))/4;
  end
 endfunction
 reg [7:0] byte_queue[0:255];integer head=0,tail=0,queued=0;
 integer lane,xpos,ypos,expect_rgb,bi;
 always @(posedge clk) if(resetn&&check_active)begin
  if(packet_error||unpack_error)$fatal(1,"case%0d protocol/unpack error",case_id);
  if(unpack_valid)begin
   if(!raw_ready)$fatal(1,"case%0d source backpressure; test rate too high",case_id);
   ypos=raw_index/(physical_width/4);xpos=(raw_index%(physical_width/4))*4;
   for(lane=0;lane<4;lane=lane+1)
    if(raw[10*lane+:10]!==pixel(ypos,xpos+lane))$fatal(1,"RAW coordinate/lane mismatch y%0d x%0d",ypos,xpos+lane);
   if(unpack_last!==(xpos==physical_width-4))$fatal(1,"RAW line marker mismatch");
   raw_index=raw_index+1;
  end
  if(crop_valid&&crop_ready)begin
   ypos=crop_index/(width/4);xpos=(crop_index%(width/4))*4;
   for(lane=0;lane<4;lane=lane+1)
    if(crop_data[10*lane+:10]!==pixel(first_row+ypos,4+xpos+lane))$fatal(1,"crop coordinate/lane mismatch");
   if(crop_last!==(xpos==width-4)||crop_sof!==(crop_index==0))$fatal(1,"crop SOF/TLAST mismatch");
   crop_index=crop_index+1;
  end
  if(rgb_valid&&rgb_ready)begin
   ypos=rgb_index/(width/4);xpos=(rgb_index%(width/4))*4;
   if(isp.frame_bayer_mode!==2'd3)$fatal(1,"Bayer metadata changed within frame");
   if(rgb_sof!==(rgb_index==0)||rgb_last!==(xpos==width-4))$fatal(1,"ISP SOF/TLAST mismatch");
   for(lane=0;lane<4;lane=lane+1)begin
    expect_rgb=(channel(ypos,xpos+lane,0)<<16)|(channel(ypos,xpos+lane,1)<<8)|channel(ypos,xpos+lane,2);
    if(rgb[32*lane+:32]!==expect_rgb)$fatal(1,"case%0d RGB y%0d x%0d got%08x want%08x",case_id,ypos,xpos+lane,rgb[32*lane+:32],expect_rgb);
    byte_queue[tail]=expect_rgb>>16;tail=(tail+1)%256;
    byte_queue[tail]=expect_rgb>>8;tail=(tail+1)%256;
    byte_queue[tail]=expect_rgb;tail=(tail+1)%256;queued=queued+3;
   end
   rgb_index=rgb_index+1;
  end
  if(packed_valid)begin
   if(queued<16)$fatal(1,"packer produced extra bytes");
   for(bi=0;bi<16;bi=bi+1)begin
    if(packed_data[8*bi+:8]!==byte_queue[head])$fatal(1,"packed_data RGB byte ordering mismatch byte%0d",pack_index*16+bi);
    head=(head+1)%256;queued=queued-1;
   end
   if(packed_sof!==(pack_index==0)||packed_last!==((pack_index+1)%(width*3/16)==0))$fatal(1,"packed_data SOF/EOL mismatch");
   if(packed_final!==packed_eof)$fatal(1,"EOF not aligned with final data");
   if(packed_eof)begin
    if(pack_index+1!=width*height*3/16)$fatal(1,"premature EOF");
    eof_count=eof_count+1;
   end
   if(packed_sof)sof_count=sof_count+1;
   pack_index=pack_index+1;
  end
 end
 task gap(input integer n);begin @(negedge clk);valid=0;repeat(n-1)@(negedge clk);end endtask
 task word(input [31:0] w);begin @(negedge clk);data=w;valid=1;@(negedge clk);valid=0;end endtask
 task header(input [7:0] id,input [15:0] wc);reg [23:0] h;begin h={wc,id};word({ecc(h),h});end endtask
 reg [7:0] line_bytes[0:8191];reg [9:0] px[0:3];reg [15:0] crc;
 integer row,g,j,k,wc,total;reg [31:0] w;
 task send_line(input integer y);begin
  wc=physical_width*5/4;
  for(g=0;g<physical_width/4;g=g+1)begin
   for(j=0;j<4;j=j+1)begin px[j]=pixel(y,g*4+j);line_bytes[g*5+j]=px[j][9:2];end
   line_bytes[g*5+4]={px[3][1:0],px[2][1:0],px[1][1:0],px[0][1:0]};
  end
  crc=16'hffff;for(j=0;j<wc;j=j+1)crc=crc_byte(crc,line_bytes[j]);
  line_bytes[wc]=crc[7:0];line_bytes[wc+1]=crc[15:8];line_bytes[wc+2]=8'hda;line_bytes[wc+3]=8'h7c;
  header(8'h2b,wc);
  total=(wc+2+3)/4;
  for(k=0;k<total;k=k+1)begin w={line_bytes[k*4+3],line_bytes[k*4+2],line_bytes[k*4+1],line_bytes[k*4]};word(w);end
  gap(8);
 end endtask
 task run_frame(input integer id,pw,ph,iw,ih,vs,ve,rows,outrows,expected_eof);begin
  @(negedge clk);case_id=id;physical_width=pw;physical_height=ph;width=iw;height=ih;vstart=vs;vend=ve;hend=iw/4+1;
  first_row=vs+1;expected_rows=outrows;cfg_bayer=3;
  raw_index=0;crop_index=0;rgb_index=0;pack_index=0;head=0;tail=0;queued=0;eof_count=0;sof_count=0;check_active=1;saved_frame_count=frame_count;
  $display("START case%0d physical=%0dx%0d crop=%0dx%0d rows%0d..%0d",id,pw,ph,iw,ih,vs+1,ve-1);
  header(0,0);gap(8);
  for(row=0;row<ph;row=row+1)begin
   if(row==vs+3)cfg_bayer=0; // shadow write during frame must be ignored
   send_line(row);
   if(row%256==0)$display("PROGRESS case%0d physical_row%0d",id,row);
  end
  header(1,0);gap(8);repeat(iw/4+50)@(negedge clk);
  if(raw_index!=pw*ph/4)$fatal(1,"physical RAW count %0d",raw_index);
  if(crop_index!=iw*rows/4)$fatal(1,"crop rows got%0d want%0d",crop_index/(iw/4),rows);
  if(rgb_index!=iw*outrows/4||pack_index*16!=iw*outrows*3||queued!=0)$fatal(1,"ISP/packed_data rows got%0d bytes%0d queued%0d",rgb_index/(iw/4),pack_index*16,queued);
  if(eof_count!=expected_eof||sof_count!=1||frame_count!=saved_frame_count+expected_eof)$fatal(1,"frame markers EOF%0d SOF%0d framecount%0d",eof_count,sof_count,frame_count);
  if(crc_errors||ecc_errors||wc_errors||timeouts)$fatal(1,"protocol counters nonzero");
  $display("PASS case%0d physical%0dx%0d crop_input_rows%0d RGB_rows%0d bytes%0d EOF%0d all_pixels/golden/GBRG/lowbits/packedbytes",id,pw,ph,rows,outrows,pack_index*16,eof_count);
  check_active=0;
 end endtask
 reg done=0;
 initial begin
  repeat(6)@(negedge clk);resetn=1;gap(8);
  run_frame(0,1944,1097,1280,720,35,756,720,720,1);
  // No reset across a complete 720p -> 1080p boundary.
  run_frame(1,1944,1097,1920,1080,15,1096,1080,1080,1);
  run_frame(2,3888,2192,3840,2160,15,2176,2160,2160,1);
  // Isolate the historical incomplete frame: configured height1080 but only
  // physical y20..1096 arrive. No final-row DRAIN -> 1076 outputs and no EOF.
  @(negedge clk);resetn=0;repeat(6)@(negedge clk);resetn=1;gap(8);
  run_frame(3,1944,1097,1920,1080,19,1100,1077,1076,0);
  done=1;$display("PHYSICAL CROP HEIGHT PASS: full CSI packets; old1076/noEOF reproduced; new1080/4K exact;720->1080 without reset");$finish;
 end
 initial begin #800000000;$fatal(1,"physical crop timeout");end
endmodule
