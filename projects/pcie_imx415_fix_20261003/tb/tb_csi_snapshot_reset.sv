`timescale 1ns/1ps
module snapshot_reset_case #(
 parameter integer ID=0, SRC_HALF=7, DST_HALF=4, PERIOD=16
)(output reg passed=0);
 reg src_clk=0,dst_clk=0,rst_n=0,run_src=1,run_dst=1;
 always #(SRC_HALF) if(run_src) src_clk=~src_clk;
 always #(DST_HALF) if(run_dst) dst_clk=~dst_clk;
 reg [31:0] n=0;
 wire [191:0] stats={n^32'h6a5a1234,n+32'd700,n-32'd321,
                    ~n,n+32'd19,n};
 wire [223:0] snapshot;
 wire [31:0] status,clock_delta;
 csi_stats_snapshot #(.PERIOD(PERIOD)) dut(
  .src_clk(src_clk),.dst_clk(dst_clk),.rst_n(rst_n),.src_stats(stats),
  .snapshot(snapshot),.status(status),.clock_delta(clock_delta));
 always @(posedge src_clk or negedge rst_n)
  if(!rst_n) n<=32'h12560000+ID;
  else n<=n+1;

 // Golden event is the actual source request acceptance, before NBA updates.
 reg [223:0] expected=0;
 reg pending=0;
 reg [30:0] last_seq=0;
 reg [31:0] last_cycles=0;
 integer received=0,total_received=0,resets=0;
 always @(negedge rst_n) begin
  expected=0;pending=0;last_seq=0;last_cycles=0;received=0;resets=resets+1;
 end
 always @(posedge src_clk) if(dut.src_rst_n && dut.req2!=dut.ack) begin
  if(pending) $fatal(1,"case %0d duplicate source accept",ID);
  expected={dut.source_cycles,stats};pending=1;
 end
 always @(negedge dst_clk) begin
  if(!dut.dst_rst_n) begin
   if(snapshot!==224'd0 || status!==32'd0 || clock_delta!==32'd0)
    $fatal(1,"case %0d destination not held reset",ID);
  end else if(status[31:1]!=last_seq) begin
   if(status[31:1]!==last_seq+1'b1 || !pending)
    $fatal(1,"case %0d phantom/duplicate completion seq %0d pending %0d",ID,status[31:1],pending);
   if(snapshot!==expected)
    $fatal(1,"case %0d torn/stale bundle: actual %h expected %h",ID,snapshot,expected);
   if(last_seq==0) begin
    if(clock_delta!==32'd0) $fatal(1,"case %0d first post-reset delta nonzero",ID);
   end else if(clock_delta!==expected[223:192]-last_cycles)
    $fatal(1,"case %0d source clock delta mismatch",ID);
   last_seq=status[31:1];last_cycles=expected[223:192];
   pending=0;received=received+1;total_received=total_received+1;
  end
 end

 // Functional reset must never release before three local positive edges.
 integer src_release_edges=0,dst_release_edges=0;
 always @(negedge rst_n) begin src_release_edges=0;dst_release_edges=0;end
 always @(posedge src_clk) if(rst_n) src_release_edges=src_release_edges+1;
 always @(posedge dst_clk) if(rst_n) dst_release_edges=dst_release_edges+1;
 always @(posedge dut.src_rst_n) if(src_release_edges<3)
  $fatal(1,"case %0d asynchronous source reset release",ID);
 always @(posedge dut.dst_rst_n) if(dst_release_edges<3)
  $fatal(1,"case %0d asynchronous destination reset release",ID);

 task automatic pulse_reset(input real ns);
  begin
   rst_n=0;
   #(ns);
   if(dut.src_rst_n!==0 || dut.dst_rst_n!==0)
    $fatal(1,"case %0d reset did not assert asynchronously",ID);
   rst_n=1;
  end
 endtask
 reg [31:0] stopped_seq;
 reg [223:0] stopped_snapshot;
 initial begin
  #1.3 rst_n=1;
  wait(received>=6);
  // Sub-cycle pulse (0.4ns) while a request is in flight; both chains assert.
  wait(status[0]);#0.13;pulse_reset(0.4);
  wait(received>=4);
  // Source has prepared the bus and ACK but destination has not consumed it.
  wait(dut.ack!=dut.seen);#0.07;pulse_reset(0.6);
  wait(received>=4);
  // ACK is at the last synchronizer stage, immediately before consumption.
  wait(dut.ack2!=dut.seen);#0.09;pulse_reset(0.3);
  wait(received>=4);

  // Stop the source: allow any previous ACK to drain, then no false completion.
  wait(!status[0]);@(negedge src_clk);run_src=0;
  #(12*DST_HALF);
  stopped_seq=status>>1;stopped_snapshot=snapshot;
  #(8*PERIOD*DST_HALF);
  if(!status[0] || (status>>1)!==stopped_seq || snapshot!==stopped_snapshot)
   $fatal(1,"case %0d stopped source fabricated completion",ID);
  // No-reset resume must complete the outstanding request coherently.
  run_src=1;wait((status>>1)>stopped_seq);wait(!status[0]);

  // Reset while source is stopped. Destination can run and queue one request,
  // but source cannot release its reset or return an ACK until its clock resumes.
  @(negedge src_clk);run_src=0;#0.23;pulse_reset(0.5);
  #(8*PERIOD*DST_HALF);
  if(dut.src_rst_n!==0 || (status>>1)!==0 || !status[0] || snapshot!==224'd0)
   $fatal(1,"case %0d stopped source reset/release mismatch",ID);
  run_src=1;wait(received>=4);

  // Stop destination and reset it too: raw reset must clear state without clocks.
  wait(!status[0]);@(negedge dst_clk);run_dst=0;
  #0.17;pulse_reset(0.7);#(10*SRC_HALF);
  if(dut.dst_rst_n!==0 || snapshot!==224'd0 || status!==0)
   $fatal(1,"case %0d stopped destination did not remain reset",ID);
  run_dst=1;wait(received>=4);

  $display("PASS snapshot reset case=%0d src_half=%0d dst_half=%0d coherent=%0d resets=%0d",ID,SRC_HALF,DST_HALF,total_received,resets);
  passed=1;
 end
 initial begin #100000;$fatal(1,"snapshot reset case %0d timeout",ID);end
endmodule

module tb_csi_snapshot_reset;
 wire a,b;
 reg passed=0;
 snapshot_reset_case #(.ID(0),.SRC_HALF(21),.DST_HALF(4),.PERIOD(16)) fast_dst(a);
 snapshot_reset_case #(.ID(1),.SRC_HALF(4),.DST_HALF(20),.PERIOD(19)) slow_dst(b);
 initial begin wait(a&&b);passed=1;
  $display("PASS held-bundle reset/stop/restart with both asynchronous clock ratios");$finish;end
endmodule
