// Whole-frame time division for the first video release. The camera remains
// 1080P60. With model mode active, alternate preview opportunities leave the
// intervening source frames available to all three same-frame model planes.
// Arbitration never withdraws an in-flight AXI valid or resets either channel.
`timescale 1ns/1ps
`default_nettype none
module model_preview_admission(
 input wire clk,rst_n,model_enable,source_sof,preview_busy,model_busy,
 output wire preview_allowed,model_allowed
);
 reg odd;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)odd<=0;
  else if(!model_enable)odd<=0;
  else if(source_sof)odd<=!odd;
 end
 assign preview_allowed=!model_enable||(!odd&&!model_busy);
 // Source SOF has priority, including a simultaneous delayed model SOF.
 // A denied model frame leaves the bounded host credit pending.
 assign model_allowed=!preview_busy&&!source_sof;
endmodule
`default_nettype wire
