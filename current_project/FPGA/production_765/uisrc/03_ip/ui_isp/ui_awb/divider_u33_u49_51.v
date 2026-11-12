// Precision51 exact unsigned 49/33 restoring divider. One request per complete
// AWB frame, latency50 clocks:49 quotient bits and one output-register clock.
// Default AWB MIN_NEUTRAL_PIXELS=1024 => qualifying frame requests are separated
// by >=256 accepted four-pixel beats. Busy requests are flagged, never queued as
// if accepted. No divisor truncation, floating point, reciprocal or gain change.
`timescale 1ns/1ps
module divider_u33_u49_51(
 input wire clk,rst,start,input wire[32:0]denominator,input wire[48:0]numerator,
 output reg done,output reg[48:0]quotient,output reg[32:0]remainder,
 output reg busy,output reg overrun
);
 reg[48:0] work_q;
 reg[32:0] work_r,divisor;
 reg[5:0] remaining;
 wire[33:0] shifted={work_r,work_q[48]};
 wire take=shifted>={1'b0,divisor};
 wire[33:0] difference=shifted-{1'b0,divisor};
 always @(posedge clk or posedge rst)
  if(rst)begin done<=0;quotient<=0;remainder<=0;busy<=0;overrun<=0;work_q<=0;work_r<=0;divisor<=0;remaining<=0;end
  else begin
   done<=0;
   if(start&&busy)overrun<=1;
   if(start&&!busy)begin
    busy<=1;work_q<=numerator;work_r<=0;divisor<=denominator;remaining<=49;
   end else if(busy)begin
    if(remaining!=0)begin
     work_q<={work_q[47:0],take};
     work_r<=take?difference[32:0]:shifted[32:0];
     remaining<=remaining-1'b1;
    end else begin
     quotient<=work_q;remainder<=work_r;done<=1;busy<=0;
    end
   end
  end
endmodule
