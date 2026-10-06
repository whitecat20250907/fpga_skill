`timescale 1ns/1ps
module tb_csi_snapshot;
reg src_clk=0,dst_clk=0,rst_n=0,run_src=1,passed=0;
always #7 if(run_src)src_clk=~src_clk;
always #4 dst_clk=~dst_clk;
reg [31:0] n=0;
wire [191:0] stats={n+32'd5,n+32'd4,n+32'd3,n+32'd2,n+32'd1,n};
wire [223:0] snap;wire [31:0] status,delta;
csi_stats_snapshot #(.PERIOD(100)) dut(src_clk,dst_clk,rst_n,stats,snap,status,delta);
always @(posedge src_clk) if(rst_n)n<=n+1;
reg [30:0] last=0;integer snapshots=0;
always @(negedge dst_clk) if(rst_n && status[31:1]!=0 && status[31:1]!=last)begin
 last=status[31:1];snapshots=snapshots+1;
 for(integer k=0;k<6;k=k+1)
  if(snap[k*32+:32]!==snap[31:0]+k)$fatal(1,"torn stats");
 if(snapshots>1 && (delta<54||delta>60))$fatal(1,"clock delta %d",delta);
end
initial begin
 #35 rst_n=1;#10000;
 if(snapshots<10)$fatal(1,"missing snapshot");
 // A stopped source must keep the last coherent counters and busy=1.
 @(negedge src_clk);run_src=0;#2000;
 if(!status[0])$fatal(1,"stopped clock falsely acknowledges");
 // Restore and reset: pending requests and counters start cleanly.
 rst_n=0;#25;run_src=1;rst_n=1;last=0;snapshots=0;#2500;
 if(snapshots<2)$fatal(1,"no reset recovery");
 passed=1;$display("PASS coherent counter snapshots, clock measurement, stopped clock and reset");$finish;
end
initial begin #50000;$fatal(1,"timeout");end
endmodule
