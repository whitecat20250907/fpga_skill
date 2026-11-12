`timescale 1ns/1ps
`default_nettype none
module twin_tick_ms #(parameter integer CLOCKS_PER_MS=50000)(
 input wire clk,input wire rst,output reg [31:0] now_ms
);
 reg [15:0] count;
 always @(posedge clk)begin
  if(rst)begin count<=0;now_ms<=0;end
  else if(count==CLOCKS_PER_MS-1)begin count<=0;now_ms<=now_ms+1'b1;end
  else count<=count+1'b1;
 end
endmodule
`default_nettype wire
