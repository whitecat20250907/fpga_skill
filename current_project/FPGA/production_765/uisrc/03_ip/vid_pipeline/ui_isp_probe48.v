// Diagnostic export, not an ISP correction. Four chronological pixels per beat.
// Stage is stable for the capture epoch. Selected output is a two-slot queue with occupancy-based ready.
// RAW10 RGB3 transport: R=bits7:0,G=bits9:8 (upper6 zero),B=A0+p/B0+p.
// RAW is cropped sensor RAW10 before BLC; BLC stage retains exact10-bit values.
`timescale 1ns/1ps
module ui_isp_probe48(
 input wire clk,rst_n,input wire[2:0] stage,
 input wire[39:0] raw_crop,raw_blc,
 input wire[95:0] rgb_processed,rgb_demo,rgb_ccm,rgb_awb,rgb_gamma,rgb_pre_cnr,
 input wire[7:0] valid,last,user,output wire[7:0] ready,
 output wire[95:0] out_data,output wire out_valid,out_last,out_user,
 input wire out_ready
);
 // Ready depends only on registered occupancy. No combinational path from
 // the downstream FIFO-full through probe selection back into the ISP.
 reg [97:0] slot0,slot1;
 reg read_pointer,write_pointer;
 reg [1:0] count;
 wire full=count[1];
 wire push=valid[stage] && !full;
 wire pop=(count!=0) && out_ready;
 wire [97:0] front=read_pointer?slot1:slot0;
 assign out_data=front[95:0];
 assign out_last=front[96];
 assign out_user=front[97];
 assign out_valid=(count!=0);
 assign ready=!full?(8'b00000001<<stage):8'b0;
 reg[95:0] selected;
 integer p;
 always @* begin
  selected=rgb_processed;
  case(stage)
   1:for(p=0;p<4;p=p+1) selected[24*p+:24]={raw_crop[10*p+:8],6'b0,raw_crop[10*p+8+:2],8'ha0+p[7:0]};
   2:for(p=0;p<4;p=p+1) selected[24*p+:24]={raw_blc[10*p+:8],6'b0,raw_blc[10*p+8+:2],8'hb0+p[7:0]};
   3:selected=rgb_demo;
   4:selected=rgb_ccm;
   5:selected=rgb_awb;
   6:selected=rgb_gamma;
   7:selected=rgb_pre_cnr;
   default:selected=rgb_processed;
  endcase
 end
 always @(posedge clk or negedge rst_n)
  if(!rst_n)begin slot0<=0;slot1<=0;read_pointer<=0;write_pointer<=0;count<=0;end
  else begin
   if(push)begin
    if(write_pointer)slot1<={user[stage],last[stage],selected};
    else slot0<={user[stage],last[stage],selected};
    write_pointer<=!write_pointer;
   end
   if(pop)read_pointer<=!read_pointer;
   case({push,pop})
    2'b10:count<=count+1'b1;
    2'b01:count<=count-1'b1;
    default:count<=count;
   endcase
  end
endmodule
