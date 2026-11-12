`timescale 1ns/1ps
// Lock each accepted source through its complete packet. Rotation occurs
// after last acceptance, so ready feature queues cannot starve behind rows.
module hci03_packet_merge3(
 input wire clk,rst_n,input wire [191:0] s_data,input wire [2:0] s_valid,s_first,s_last,
 output wire [2:0] s_ready,output wire [63:0] m_data,output wire m_valid,m_first,m_last,input wire m_ready,
 output reg [95:0] packets,output reg [31:0] errors
);
 reg active,started;reg [1:0] selected,rotation;reg [1:0] choice;reg found;integer i,j;
 always @*begin
  choice=0;found=0;
  for(i=0;i<3;i=i+1)begin
   j=rotation+i;if(j>=3)j=j-3;
   if(!found&&s_valid[j])begin choice=j;found=1;end
  end
 end
 assign m_data=s_data[selected*64+:64];assign m_valid=rst_n&&active&&s_valid[selected];
 assign m_first=s_first[selected];assign m_last=s_last[selected];
 assign s_ready=active&&rst_n?((3'b001<<selected)&{3{m_ready}}):3'd0;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin active<=0;started<=0;selected<=0;rotation<=0;packets<=0;errors<=0;end
  else begin
   if(!active&&found)begin active<=1;selected<=choice;started<=0;end
   if(m_valid&&m_ready)begin
    if(m_first!=!started)errors[0]<=1;started<=1;
    if(m_last)begin
     active<=0;started<=0;rotation<=selected==2?0:selected+1'b1;
     packets[selected*32+:32]<=packets[selected*32+:32]+1'b1;
    end
   end
  end
 end
endmodule
