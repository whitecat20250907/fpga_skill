`timescale 1ns/1ps
`default_nettype none
// Shared setup arithmetic: 32 iterations once per triangle/edge, never a
// combinational divider on the one-fragment-per-cycle drawing path.
module twin_signed_divider(
 input wire clk,input wire rst,input wire start,
 input wire signed [31:0] numerator,input wire signed [31:0] denominator,
 output reg busy,output reg done,output reg signed [31:0] quotient,
 output reg divide_zero,output reg overflow
);
 reg [31:0] work,divisor;
 reg [32:0] remainder;
 reg negative,will_overflow;reg [5:0] remaining;
 wire [32:0] trial={remainder[31:0],work[31]};
 wire subtract=trial>={1'b0,divisor};
 wire [31:0] next_work={work[30:0],subtract};
 always @(posedge clk)begin
  if(rst)begin
   busy<=0;done<=0;quotient<=0;divide_zero<=0;overflow<=0;
   work<=0;divisor<=0;remainder<=0;negative<=0;will_overflow<=0;remaining<=0;
  end else begin
   done<=0;
   if(start && !busy)begin
    divide_zero<=denominator==0;
    overflow<=0;
    if(denominator==0)begin quotient<=0;done<=1;end
    else begin
     work<=numerator[31] ? -numerator : numerator;
     divisor<=denominator[31] ? -denominator : denominator;
     negative<=numerator[31]^denominator[31];
     will_overflow<=numerator==32'sh80000000 && denominator==-32'sd1;
     remainder<=0;remaining<=32;busy<=1;
    end
   end else if(busy)begin
    work<=next_work;
    remainder<=subtract ? trial-{1'b0,divisor} : trial;
    remaining<=remaining-1'b1;
    if(remaining==1)begin
     quotient<=will_overflow ? 32'sh7fffffff : negative ? -$signed(next_work) : $signed(next_work);
     overflow<=will_overflow;done<=1;busy<=0;
    end
   end
  end
 end
endmodule
`default_nettype wire
