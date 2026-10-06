`timescale 1ns/1ps
// Only ChipWatcher is replaced. This test drives the FDMA user interface;
// it does NOT instantiate ui_FDMA, DDR controller, PHY or physical memory.
module cwc(input clk,input [15:0] probe0,input probe1,probe2,probe3,probe4,
 input [15:0] probe5,probe6,input probe7,probe8,probe9,probe10,
 input [2:0] probe11,input probe12);
endmodule
module tb_fdma_checker;
reg clk=0;always #5 clk=~clk;
reg resetn=0;
wire [11:0] wa,ra;
wire wreq,rreq,wready,rready,error,config_error;
wire [15:0] wsize,rsize;
wire [127:0] wdata;
reg wbusy=0,rbusy=0,wvalid=0,rvalid=0;
reg [127:0] rdata=0;
wire [31:0] errors,bursts,rounds;
reg test_done=0;
reg [127:0] memory[0:15];
integer burst,index,expected_address,flip_bit,expected_errors=0;
ui_fdma_test #(.AXI_ADDR_WIDTH(12),.AXI_DATA_WIDTH(128),.TEST_MEM_SIZE(200),
 .MEM_CAPACITY_BYTES(256),.FDMA_BURST_LEN(4),.ADDR_MEM_OFFSET(16)) dut(
 .I_clk(clk),.I_fdma_rstn(resetn),.O_fdma_waddr(wa),.O_fdma_wareq(wreq),
 .O_fdma_wsize(wsize),.I_fdma_wbusy(wbusy),.O_fdma_wdata(wdata),.I_fdma_wvalid(wvalid),.O_fdma_wready(wready),
 .O_fdma_raddr(ra),.O_fdma_rareq(rreq),.O_fdma_rsize(rsize),.I_fdma_rbusy(rbusy),
 .I_fdma_rdata(rdata),.I_fdma_rvalid(rvalid),.O_fdma_rready(rready),
 .test_error(error),.test_error_count(errors),.test_completed_bursts(bursts),.test_completed_rounds(rounds),.config_error(config_error));
wire invalid_error,invalid_wreq,invalid_rreq;
ui_fdma_test #(.AXI_ADDR_WIDTH(12),.AXI_DATA_WIDTH(128),.TEST_MEM_SIZE(512),
 .MEM_CAPACITY_BYTES(256),.FDMA_BURST_LEN(4),.ADDR_MEM_OFFSET(0)) invalid_dut(
 .I_clk(clk),.I_fdma_rstn(resetn),.I_fdma_wbusy(1'b0),.I_fdma_wvalid(1'b0),
 .I_fdma_rbusy(1'b0),.I_fdma_rdata(128'd0),.I_fdma_rvalid(1'b0),
 .O_fdma_wareq(invalid_wreq),.O_fdma_rareq(invalid_rreq),.config_error(invalid_error),
 .O_fdma_waddr(),.O_fdma_wsize(),.O_fdma_wdata(),.O_fdma_wready(),
 .O_fdma_raddr(),.O_fdma_rsize(),.O_fdma_rready(),.test_error(),
 .test_error_count(),.test_completed_bursts(),.test_completed_rounds());
always @(posedge clk)begin
 if(resetn && (wreq||rreq))begin
  if(wa<16 || wa+64>216 || ra!==wa)$fatal(1,"Out of configured address region wa=%0d ra=%0d",wa,ra);
  if(wsize!=4||rsize!=4)$fatal(1,"FDMA size units are beats");
 end
 if(invalid_wreq||invalid_rreq)$fatal(1,"Invalid configuration issued traffic");
end
task transact(input integer corrupt);
 reg [127:0] original;
 begin
  wait(wreq);@(negedge clk);
  expected_address=16+(burst%3)*64;
  if(wa!==expected_address)$fatal(1,"Address walk burst%0d got%0d expected%0d",burst,wa,expected_address);
  wbusy=1;repeat(2)@(negedge clk);
  for(index=0;index<4;index=index+1)begin
   repeat(index%3)@(negedge clk);
   wvalid=1;
   @(posedge clk);memory[(wa>>4)+index]=wdata;
   // Independent progress/lane coverage checks, not a constant-zero pass.
   if(index==0 && wdata[127:112]===wdata[15:0])$fatal(1,"Pattern does not distinguish lanes");
   @(negedge clk);wvalid=0;
  end
  wbusy=0;
  wait(rreq);@(negedge clk);rbusy=1;repeat(2)@(negedge clk);
  for(index=0;index<4;index=index+1)begin
   repeat((index+1)%3)@(negedge clk);
   original=memory[(ra>>4)+index];rdata=original;
   if(corrupt>=0 && index==1)begin rdata[corrupt]=~original[corrupt];expected_errors=expected_errors+1;end
   rvalid=1;@(posedge clk);@(negedge clk);rvalid=0;
  end
  rbusy=0;
  wait(bursts==burst+1);repeat(3)@(negedge clk);
  if(errors!==expected_errors)$fatal(1,"Error count got%0d expected%0d",errors,expected_errors);
  if(error!==(expected_errors!=0))$fatal(1,"Sticky error lost or asserted early");
 end
endtask
initial begin
 repeat(5)@(negedge clk);resetn=1;
 wait(dut.rst_cnt[10]);
 if(config_error||!invalid_error)$fatal(1,"Configuration bounds checker");
 // Two clean passes, then one injected error at representative low/high bits.
 for(burst=0;burst<12;burst=burst+1)begin
  case(burst)
   6:flip_bit=0;7:flip_bit=15;8:flip_bit=16;9:flip_bit=63;10:flip_bit=127;
   default:flip_bit=-1;
  endcase
  transact(flip_bit);
 end
 if(bursts!=12 || rounds!=4 || errors!=5)$fatal(1,"Liveness/round summary");
 // Recalibration reset must clear diagnostics and restart at region beginning.
 resetn=0;repeat(4)@(negedge clk);resetn=1;
 wait(dut.rst_cnt[10]);wait(wreq);@(negedge clk);
 if(error||errors||bursts||rounds||wa!=16)$fatal(1,"Reset/recovery");
 test_done=1;
 $display("FDMA CHECKER PASS: 12 bursts/4 rounds, 5 single-bit injections incl bit127, bounded nonmultiple span, reset, invalid-config no traffic");
 $stop;
end
initial begin #1000000;$fatal(1,"FDMA timeout");end
endmodule
