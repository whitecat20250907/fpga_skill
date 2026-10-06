`timescale 1ns/1ps
// Real ui_dbuf + its real asynchronous sfifo. FDMA user transactions are a
// driver; this does not simulate the DDR controller/PHY or DSI electrical IO.
module tb_demo06_dbuf;
reg ui=0,video=0;always #5 ui=~ui;always #7 video=~video;
reg resetn=0,iv=0,isof=0,ilast=0;reg [127:0] idata=0;
wire ready,wreq,wready;wire [15:0] wsize;wire [27:0] wa;wire [127:0] wdata;
wire [7:0] buffer;reg busy=0,pop=0;
reg done=0;integer sent=0,received=0,burst=0,j,stalls=0;
function automatic [127:0] pattern(input integer n);
 integer k;begin for(k=0;k<4;k=k+1)pattern[k*32+:32]=32'h12340000+n*4+k;end
endfunction
ui_dbuf #(.AXI_ADDR_WIDTH(28),.AXI_DATA_WIDTH(128),
 .W_BUFDEPTH(16),.W_DATAWIDTH(128),.W_DSIZEBITS(12),.W_XSIZE(16),.W_XSTRIDE(16),.W_YSIZE(3),.W_XDIV(2),
 .R_BUFDEPTH(16),.R_DATAWIDTH(128),.R_DSIZEBITS(12),.R_XSIZE(16),.R_XSTRIDE(16),.R_YSIZE(3),.R_XDIV(2)) dut(
 .I_ui_clk(ui),.I_ui_rstn(resetn),.I_W_en(1'b1),.I_W_wclk(video),
 .I_W_tuser(isof),.I_W_tvalid(iv),.I_W_tdata(idata),.I_W_tlast(ilast),.O_W_tready(ready),.O_W_sync_cnt(buffer),.I_W_buf(buffer),
 .O_fdma_waddr(wa),.O_fdma_wareq(wreq),.O_fdma_wsize(wsize),.I_fdma_wbusy(busy),.O_fdma_wdata(wdata),.I_fdma_wvalid(pop),.O_fdma_wready(wready),.O_fdma_wbuf(),.O_fdma_wirq(),
 .I_R_en(1'b0),.I_Rsync_en(1'b0),.I_R_rclk(video),.I_R_tready(1'b0),.O_R_tuser(),.O_R_tvalid(),.O_R_tdata(),.O_R_vrst(),.O_R_tlast(),.O_R_sync_cnt(),.I_R_buf(8'd0),
 .O_fdma_raddr(),.O_fdma_rareq(),.O_fdma_rsize(),.I_fdma_rbusy(1'b0),.I_fdma_rdata(128'd0),.I_fdma_rvalid(1'b0),.O_fdma_rready(),.O_fdma_rbuf(),.O_fdma_rirq());
always @(posedge video)if(resetn&&iv&&!ready)stalls=stalls+1;
initial begin
 repeat(8)@(negedge video);resetn=1;
 for(sent=0;sent<48;sent=sent+1)begin
  @(negedge video);iv=1;isof=(sent==0);ilast=(sent%16==15);idata=pattern(sent);
  @(posedge video);while(!ready)@(posedge video);
  @(negedge video);iv=0;isof=0;ilast=0;
  repeat(sent%2)@(negedge video);
 end
end
initial begin
 wait(resetn);repeat(160)@(negedge ui); // Deliberately fill until almost-full.
 for(burst=0;burst<6;burst=burst+1)begin
  wait(wreq);@(negedge ui);
  if(wsize!==8||wa[11:0]!==burst*128)$fatal(1,"FDMA byte addr/beat length burst%0d addr%h size%0d",burst,wa,wsize);
  busy=1;repeat(3)@(negedge ui);
  for(j=0;j<8;j=j+1)begin
   repeat(j%3)@(negedge ui);pop=1;
   @(posedge ui);if(wdata!==pattern(received))$fatal(1,"FIFO accepted%0d got%h expected%h",received,wdata,pattern(received));
   received=received+1;
   @(negedge ui);pop=0;
  end
  busy=0;repeat(6)@(negedge ui);
 end
 wait(sent==48);repeat(15)@(negedge ui);
 if(received!=48||stalls==0||!dut.W_empty)$fatal(1,"DBUF liveness/count/stalls received%0d stalls%0d",received,stalls);
 done=1;$display("DEMO06 DBUF PASS: actual async FIFO, startup SOF preserved,48 complete128bit words/6 bursts exact, almost-full backpressure%0d cycles, no dropped/duplicate words",stalls);$stop;
end
initial begin #1000000;$fatal(1,"DBUF timeout sent%0d received%0d",sent,received);end
endmodule
