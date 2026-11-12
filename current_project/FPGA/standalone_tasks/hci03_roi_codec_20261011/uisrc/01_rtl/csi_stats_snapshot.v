// Coherent diagnostics. The source holds all counters until the next request;
// the returned toggle crosses two FFs before the destination samples the bus.
module csi_stats_snapshot #(parameter PERIOD=12500000,STATS_WIDTH=192)(
 input src_clk,dst_clk,rst_n,input [STATS_WIDTH-1:0] src_stats,
 output reg [STATS_WIDTH+31:0] snapshot,output [31:0] status,
 output reg [31:0] clock_delta);
 reg [31:0] source_cycles;
 reg [STATS_WIDTH+31:0] held;
 reg request,ack;
 // Assert both domains together, including when a clock is stopped. Release
 // each only on its own clock edges; a pending request waits for source resume.
 (* async_reg="true" *) reg [2:0] src_reset_sync,dst_reset_sync;
 wire src_rst_n=src_reset_sync[2];
 wire dst_rst_n=dst_reset_sync[2];
 always @(posedge src_clk or negedge rst_n)
  if(!rst_n) src_reset_sync<=3'b000;
  else src_reset_sync<={src_reset_sync[1:0],1'b1};
 always @(posedge dst_clk or negedge rst_n)
  if(!rst_n) dst_reset_sync<=3'b000;
  else dst_reset_sync<={dst_reset_sync[1:0],1'b1};
 (* async_reg="true" *) reg req1,req2,ack1,ack2;
 reg [$clog2(PERIOD)-1:0] timer;
 reg [30:0] sequence_count;
 reg [31:0] previous_cycles;
 reg seen;
 wire busy=request!=seen;
 assign status={sequence_count,busy};
 always @(posedge src_clk or negedge src_rst_n) begin
  if(!src_rst_n) begin source_cycles<=0;held<=0;req1<=0;req2<=0;ack<=0;end
  else begin
   source_cycles<=source_cycles+1'b1;
   req1<=request;req2<=req1;
   if(req2!=ack) begin held<={source_cycles,src_stats};ack<=req2;end
  end
 end
 always @(posedge dst_clk or negedge dst_rst_n) begin
  if(!dst_rst_n) begin request<=0;ack1<=0;ack2<=0;timer<=0;seen<=0;
   snapshot<=0;sequence_count<=0;clock_delta<=0;previous_cycles<=0;end
  else begin
   ack1<=ack;ack2<=ack1;
   if(ack2!=seen) begin
    snapshot<=held;seen<=ack2;sequence_count<=sequence_count+1'b1;
    previous_cycles<=held[STATS_WIDTH+31:STATS_WIDTH];
    clock_delta<=sequence_count==0 ? 0 : held[STATS_WIDTH+31:STATS_WIDTH]-previous_cycles;
   end
   if(timer==PERIOD-1) begin
    timer<=0;
    if(!busy) request<=~request;
   end else timer<=timer+1'b1;
  end
 end
endmodule
