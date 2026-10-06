`timescale 1ns/1ps
module tb_demo06_isp;
reg clk=0;always #5 clk=~clk;
reg resetn=0,valid=0,sof=0,last=0;reg [39:0] raw=0;
wire source_ready,v,out_sof,out_last;wire [127:0] rgb;reg sink_ready=0;
reg done=0;integer sent,received=0,cycle=0;
reg stalled=0;reg [129:0] held;
ui_isp_top #(.IMG_WIDTH(16),.IMG_HEIGHT(3)) dut(
 .I_clk(clk),.I_rst_n(resetn),.I_tlast(last),.I_tuser(sof),.I_tdata(raw),.I_tvalid(valid),.I_tdest(10'd0),
 .I_tready(source_ready),.O_tready(sink_ready),.O_tdata(rgb),.O_tlast(out_last),.O_tuser(out_sof),.O_tvalid(v));
always @(negedge clk)begin cycle=cycle+1;sink_ready=(cycle%17>=6);end
always @(posedge clk)if(resetn)begin
 if(stalled && (!v||{rgb,out_last,out_sof}!==held))$fatal(1,"ISP unstable output under backpressure");
 stalled=v&&!sink_ready;held={rgb,out_last,out_sof};
 if(v&&sink_ready)begin
  if(out_sof!==(received%12==0)||out_last!==(received%4==3))$fatal(1,"ISP marks beat%0d sof%0d last%0d",received,out_sof,out_last);
  if(received>=24)$fatal(1,"Extra ISP beat");
  // Known boundary values. RAW<=50 -> BLC0, LUT2.2[0]=240,
  // gamma floor((240*256-2048)/4096)=14; contrast floor(-114*140/128)+128=3;
  // brightness+5 =>8; vendor saturation gray floor(8*255/256)=7.
  // White clamps255 before saturation, which becomes floor(255*255/256)=254.
  if(received<12 && rgb!=={4{32'h00070707}})$fatal(1,"Black boundary RGB %h expected four 00070707",rgb);
  if(received>=12 && rgb!=={4{32'h00fefefe}})$fatal(1,"White boundary RGB %h expected four 00fefefe",rgb);
  received=received+1;
 end
end
initial begin
 repeat(6)@(negedge clk);resetn=1;
 for(sent=0;sent<24;sent=sent+1)begin
  @(negedge clk);valid=1;sof=(sent%12==0);last=(sent%4==3);
  raw=(sent<12)?{4{10'd32}}:{4{10'd1023}};
  @(posedge clk);while(!source_ready)@(posedge clk);
  @(negedge clk);valid=0;sof=0;last=0;
  repeat(sent%3)@(negedge clk);
 end
 wait(received==24);repeat(40)@(negedge clk);
 done=1;$display("DEMO06 ISP WRAPPER PASS: two16x3 frames, actual entire BLC/demosaic/AWB/cut/gamma/contrast/brightness/saturation, exact24beats + SOF/TLAST, black/white RGB, input/output holes and stalls");$stop;
end
initial begin #1000000;$fatal(1,"ISP wrapper timeout");end
endmodule
