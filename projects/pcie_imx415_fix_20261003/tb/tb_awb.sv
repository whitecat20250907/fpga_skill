`timescale 1ns/1ps
// Behavioral divider checks the AWB controller, not the encrypted IP timing.
module divider(input clk,rst,start,input [31:0] denominator,
 input [47:0] numerator,output reg [47:0] quotient,output reg done);
 reg [47:0] q[0:49]; reg [49:0] v;
 integer k;
 always @(posedge clk) begin
  if(rst) begin v<=0;done<=0;quotient<=0;end
  else begin
   v<={v[48:0],start}; q[0]<=denominator ? numerator/denominator : 0;
   for(k=1;k<50;k=k+1) q[k]<=q[k-1];
   done<=v[49]; quotient<=q[49];
  end
 end
endmodule

module tb_awb;
 reg clk=0; always #5 clk=~clk;
 reg rst_n=0,iv=0,il=0,iu=0,ready=1;
 reg [12:0] width=16,height=2; reg [95:0] data=0;
 wire ir,ov,ol,ou;wire [95:0] out;
 ui_awb dut(.I_clk(clk),.I_rst_n(rst_n),.I_img_width(width),.I_img_height(height),
  .I_tlast(il),.I_tuser(iu),.I_tdata(data),.I_tvalid(iv),.I_tready(ir),
  .O_tlast(ol),.O_tuser(ou),.O_tdata(out),.O_tvalid(ov),.O_tready(ready));
 reg [95:0] expected[0:4095];reg exp_last[0:4095],exp_sof[0:4095];
 integer sent=0,received=0,cycles=0;reg stalled=0;reg [97:0] held;
 always @(negedge clk) if(rst_n) ready=($urandom_range(0,4)!=0);
 always @(posedge clk) if(rst_n) begin
  cycles=cycles+1;
  if(cycles>20000) $fatal(1,"AWB timeout");
  if(stalled && (!ov || {ou,ol,out}!==held)) $fatal(1,"AWB output changed during stall");
  stalled=ov&&!ready;held={ou,ol,out};
  if(ov&&ready) begin
   if(received>=sent) $fatal(1,"Unexpected AWB output");
   if(out!==expected[received] || ol!==exp_last[received] || ou!==exp_sof[received])
    $fatal(1,"AWB mismatch beat=%0d got=%h expected=%h SOF/LAST=%b%b expected=%b%b",received,out,expected[received],ou,ol,exp_sof[received],exp_last[received]);
   received=received+1;
  end
 end
 task frame(input integer w,h,r,g,b,gr,gb);
  integer x,y,p,rr,bb;
  begin
   @(negedge clk);width=w;height=h;
   rr=(r*gr)>>16;if(rr>255)rr=255;
   bb=(b*gb)>>16;if(bb>255)bb=255;
   for(y=0;y<h;y=y+1) for(x=0;x<w/4;x=x+1) begin
    @(negedge clk);iv=1;il=(x==w/4-1);iu=(x==0&&y==0);
    for(p=0;p<4;p=p+1) begin
     data[p*24+:24]={r[7:0],g[7:0],b[7:0]};
     expected[sent][p*24+:24]={rr[7:0],g[7:0],bb[7:0]};
    end
    exp_last[sent]=il;exp_sof[sent]=iu;
    @(posedge clk);while(!ir) @(posedge clk);
    sent=sent+1;
   end
   @(negedge clk);iv=0;iu=0;il=0;
  end
 endtask
 initial begin
  repeat(5) @(negedge clk);rst_n=1;
  frame(16,2,40,80,160,65536,65536);repeat(100) @(negedge clk);
  frame(16,2,40,80,160,131072,32768);repeat(100) @(negedge clk);
  frame(16,2,160,40,20,131072,32768);
  // The new division completes during this long frame; gains must stay fixed.
  frame(256,4,160,40,20,131072,32768);repeat(100) @(negedge clk);
  frame(16,2,160,40,20,32768,131072);repeat(100) @(negedge clk);
  frame(16,2,0,0,0,32768,131072);repeat(100) @(negedge clk);
  frame(16,2,80,40,20,32768,131072);
  repeat(20) @(negedge clk);
  if(received!=sent) $fatal(1,"AWB lost data %0d/%0d",received,sent);
  $display("PASS AWB: %0d beats, four-pixel sums, frame-latched gains, markers, stalls, saturation, black frame",received);
  $finish;
 end
endmodule
