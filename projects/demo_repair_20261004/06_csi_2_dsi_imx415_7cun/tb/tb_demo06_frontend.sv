`timescale 1ns/1ps
module tb_demo06_frontend;
reg hs=0,video=0; always #5 hs=~hs;always #7 video=~video;
reg resetn=0,valid=0;reg [31:0] data=0;
wire [39:0] raw;wire v,sof,last;reg ready=0;
wire [31:0] packets,crc_errors,ecc_errors,wc_errors,timeouts,overflows;wire error_pulse;
reg done=0;
ui06_csi_frontend #(.CROP_WIDTH(16),.CROP_HEIGHT(3)) dut(
 .I_hs_clk(hs),.I_reset_n(resetn),.I_hs_valid(valid),.I_hs_data(data),
 .I_video_clk(video),.I_video_reset_n(resetn),.O_tdata(raw),.O_tvalid(v),.O_tuser(sof),.O_tlast(last),.I_tready(ready),
 .O_raw_packets(packets),.O_crc_errors(crc_errors),.O_ecc_errors(ecc_errors),.O_wc_errors(wc_errors),
 .O_timeout_errors(timeouts),.O_fifo_overflows(overflows),.O_error_pulse(error_pulse));
function automatic [7:0] ecc(input [23:0] d);
 begin
 ecc[0]=d[0]^d[1]^d[2]^d[4]^d[5]^d[7]^d[10]^d[11]^d[13]^d[16]^d[20]^d[21]^d[22]^d[23];
 ecc[1]=d[0]^d[1]^d[3]^d[4]^d[6]^d[8]^d[10]^d[12]^d[14]^d[17]^d[20]^d[21]^d[22]^d[23];
 ecc[2]=d[0]^d[2]^d[3]^d[5]^d[6]^d[9]^d[11]^d[12]^d[15]^d[18]^d[20]^d[21]^d[22];
 ecc[3]=d[1]^d[2]^d[3]^d[7]^d[8]^d[9]^d[13]^d[14]^d[15]^d[19]^d[20]^d[21]^d[23];
 ecc[4]=d[4]^d[5]^d[6]^d[7]^d[8]^d[9]^d[16]^d[17]^d[18]^d[19]^d[20]^d[22]^d[23];
 ecc[5]=d[10]^d[11]^d[12]^d[13]^d[14]^d[15]^d[16]^d[17]^d[18]^d[19]^d[21]^d[22]^d[23];
 ecc[7:6]=0;
 end
endfunction
function automatic [15:0] crc_byte(input [15:0] c,input [7:0] b);
 integer n;reg [15:0] x;begin x=c;for(n=0;n<8;n=n+1)x=(x>>1)^((x[0]^b[n])?16'h8408:0);crc_byte=x;end
endfunction
function automatic [9:0] pixel(input integer f,y,x);pixel=(f*131+y*53+x*7+29)&1023;endfunction
task send_word(input [31:0] little);
 begin @(negedge hs);data={little[7:0],little[15:8],little[23:16],little[31:24]};valid=1;end
endtask
task gap(input integer n);
 begin @(negedge hs);valid=0;data=0;repeat(n-1)@(negedge hs);end
endtask
task header(input [7:0] id,input [15:0] wc,input integer bad);
 reg[23:0] h;begin h={wc,id};send_word({ecc(h)^bad[7:0],h});end
endtask
reg[7:0] bytes[0:63];reg[9:0] p[0:3];reg[15:0] c;reg[31:0] word;
integer f,y,x,g,j,k;
task line(input integer frame,row,input integer bad_crc);
 begin
  for(g=0;g<6;g=g+1)begin
   for(j=0;j<4;j=j+1)p[j]=pixel(frame,row,g*4+j);
   for(j=0;j<4;j=j+1)bytes[g*5+j]=p[j][9:2];
   bytes[g*5+4]={p[3][1:0],p[2][1:0],p[1][1:0],p[0][1:0]};
  end
  c=16'hffff;for(j=0;j<30;j=j+1)c=crc_byte(c,bytes[j]);
  if(bad_crc)c=c^16'h0001;
  bytes[30]=c[7:0];bytes[31]=c[15:8];
  header(8'h2b,16'd30,0);
  for(k=0;k<8;k=k+1)begin
   word={bytes[k*4+3],bytes[k*4+2],bytes[k*4+1],bytes[k*4]};
   send_word(word);
   if(k==2||k==5)gap(3); // Legal payload holes must not become TLAST.
  end
  gap(1); // Minimum legacy PHY packet boundary: no fixed4cycle drain.
 end
endtask
integer accepted=0,cycle=0,frame,row,group,lane;
reg [41:0] stalled;reg was_stalled=0;
always @(negedge video)begin cycle=cycle+1;ready=(cycle%11>3);end
always @(posedge video)if(resetn)begin
 if(was_stalled&&{raw,last,sof}!==stalled)$fatal(1,"Frontend output changed while stalled");
 was_stalled=v&&!ready;stalled={raw,last,sof};
 if(v&&ready&&accepted<24)begin
  frame=accepted/12;row=(accepted%12)/4;group=accepted%4;
  for(lane=0;lane<4;lane=lane+1)
   if(raw[lane*10+:10]!==pixel(frame,row+1,(group+1)*4+lane))$fatal(1,"RAW crop/order accepted%0d lane%0d got%0d",accepted,lane,raw[lane*10+:10]);
  if(sof!==(accepted%12==0)||last!==(group==3))$fatal(1,"SOF/TLAST accepted%0d",accepted);
  accepted=accepted+1;
 end
end
initial begin
 repeat(8)@(negedge hs);resetn=1;gap(8);
 for(f=0;f<2;f=f+1)begin
  header(0,0,0);gap(1);
  for(y=0;y<4;y=y+1)line(f,y,0);
  header(1,0,0);gap(8);
 end
 wait(accepted==24);repeat(12)@(negedge video);
 if(packets!=8||crc_errors||ecc_errors||wc_errors||timeouts||overflows)$fatal(1,"Clean counters");
 // CRC diagnosis is explicit: streamed pixels cannot be withdrawn at footer.
 header(0,0,0);gap(1);line(3,0,1);header(1,0,0);gap(8);
 if(crc_errors!=1||packets!=8)$fatal(1,"CRC detection/count");
 header(8'h2b,16'd30,1);gap(8);
 if(ecc_errors!=1)$fatal(1,"ECC diagnosis");
 done=1;$display("DEMO06 FRONTEND PASS: high-byte legacy adaptation, WC30 last2payload+CRC, valid holes, 1cycle packet gaps, crop, Gray CDC/stalls, CRC/ECC counters");$stop;
end
initial begin #1000000;$fatal(1,"Frontend timeout");end
endmodule
