`timescale 1ns/1ps
// Two accepted RGB quad beats. s_ready depends only on registered occupancy,
// removing DBUF's Gray->binary/used-count/ready path from the HCI post stage.
// One beat/cycle in steady state, with a conservative full-to-space bubble.
module hci02_video_readycut(
 input wire clk,rst_n,input wire [127:0] s_data,input wire s_valid,s_sof,s_last,s_eof,
 input wire [13:0] s_config,output wire s_ready,input wire m_ready,
 output wire [127:0] m_data,output wire m_valid,m_sof,m_last,m_eof,output wire [13:0] m_config,
 output wire [1:0] occupancy
);
 reg [144:0] memory[0:1];reg write_bank,read_bank;reg [1:0] count;
 assign s_ready=count<2;assign m_valid=count!=0;
 assign {m_config,m_eof,m_last,m_sof,m_data}=memory[read_bank];
 assign occupancy=count;
 wire push=s_valid&&s_ready,pop=m_valid&&m_ready;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin count<=0;write_bank<=0;read_bank<=0;end
  else begin
   if(push)begin memory[write_bank]<={s_config,s_eof,s_last,s_sof,s_data};write_bank<=~write_bank;end
   if(pop)read_bank<=~read_bank;
   case({push,pop})2'b10:count<=count+1'b1;2'b01:count<=count-1'b1;default:;endcase
  end
 end
endmodule
