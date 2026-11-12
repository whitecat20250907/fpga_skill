`timescale 1ns/1ps
// Single-clock inferred RAM FIFO with a held synchronous-read output register.
// It absorbs active-line ROI work; serial ROI selection must not immediately
// backpressure the camera's small RAW FIFO. No memory reset loop or async read.
module hci02_stream_fifo #(parameter WIDTH=130,DEPTH=16384,PBITS=$clog2(DEPTH))(
 input wire clk,rst_n,input wire [WIDTH-1:0] s_data,input wire s_valid,output wire s_ready,
 output reg [WIDTH-1:0] m_data,output reg m_valid,input wire m_ready,
 output wire [31:0] occupancy,output reg [31:0] high_water
);
 reg [WIDTH-1:0] memory[0:DEPTH-1];reg [PBITS-1:0] wr,rd;reg [PBITS:0] count;
 wire advance=!m_valid||m_ready;
 wire pop=count!=0&&advance;
 assign s_ready=count<DEPTH||pop;
 wire push=s_valid&&s_ready;
 assign occupancy=count+m_valid;
 always @(posedge clk)begin
  if(rst_n&&push)memory[wr]<=s_data;
  if(rst_n&&pop)m_data<=memory[rd];
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin wr<=0;rd<=0;count<=0;m_valid<=0;high_water<=0;end
  else begin
   if(push)wr<=wr+1'b1;
   if(pop)rd<=rd+1'b1;
   if(advance)m_valid<=pop;
   case({push,pop})
    2'b10:count<=count+1'b1;
    2'b01:count<=count-1'b1;
    default:;
   endcase
   if(occupancy>high_water)high_water<=occupancy;
  end
 end
 // synthesis translate_off
 initial if(DEPTH<2||(DEPTH&(DEPTH-1))!=0)$fatal(1,"ROI pixel FIFO depth must be a power of two");
 // synthesis translate_on
endmodule
