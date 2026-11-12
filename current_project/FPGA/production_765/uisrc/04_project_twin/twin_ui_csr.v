`timescale 1ns/1ps
`default_nettype none
// Stable mailbox plus toggle/ack CDC. The mailbox is held until a matching
// HFT2 display_generation is visible DURING vertical blank. No active frame
// can combine the next UI state with the preceding scene.
module twin_ui_csr(
 input wire bar_clk,ui_clk,rst_n,
 input wire write_valid,input wire [31:0] write_address,write_data,input wire [3:0] write_strobe,
 input wire read_valid,input wire [31:0] read_address,
 output reg read_select,output reg [31:0] read_data,
 input wire ui_blank,input wire [31:0] scene_generation,
 output reg [991:0] front,output reg front_valid,
 output wire[31:0]source_pip,
 output wire busy,output reg [31:0] rejected
);
 reg [31:0] shadow[0:30];reg [991:0] mailbox;
 reg request_toggle,ack_toggle;
 (* async_reg="true" *) reg [2:0] ack_sync;
 (* async_reg="true" *) reg [2:0] req_sync;
 reg pending;reg [991:0] pending_data;reg pending_toggle;
 // Asynchronous assertion, synchronous release separately in each domain.
 // The request/ack mailbox cannot drive downstream RAM control from a raw
 // reset release, even though its data handshake is otherwise atomic.
 (* async_reg="true" *) reg [2:0] bar_up,ui_up;
 always @(posedge bar_clk or negedge rst_n)
  if(!rst_n)bar_up<=0;else bar_up<={bar_up[1:0],1'b1};
 always @(posedge ui_clk or negedge rst_n)
  if(!rst_n)ui_up<=0;else ui_up<={ui_up[1:0],1'b1};
 wire bar_rst_n=bar_up[2],ui_rst_n=ui_up[2];
 assign source_pip=mailbox[22*32+:32];
 assign busy=!bar_rst_n || request_toggle!=ack_sync[2];
 integer i;wire [19:0] wa=write_address[19:0],ra=read_address[19:0];
 always @(posedge bar_clk or negedge bar_rst_n) begin
  if(!bar_rst_n)begin
   for(i=0;i<31;i=i+1)shadow[i]<=0;
   mailbox<=0;request_toggle<=0;ack_sync<=0;read_select<=0;read_data<=0;rejected<=0;
  end else begin
   ack_sync<={ack_sync[1:0],ack_toggle};
   if(write_valid && wa>=20'hc80 && wa<=20'hcfc)begin
    if(write_strobe!=4'hf || wa[1:0]!=0 || busy)rejected<=rejected+1'b1;
    else if(wa==20'hcfc)begin
     if(write_data==32'h55490001)begin
      for(i=0;i<31;i=i+1)mailbox[i*32+:32]<=shadow[i];
      request_toggle<=!request_toggle;
     end else rejected<=rejected+1'b1;
    end else shadow[(wa-20'hc80)>>2]<=write_data;
   end
   if(read_valid)begin
    read_select<=ra>=20'hc80 && ra<=20'hcfc && ra[1:0]==0;
    if(ra==20'hcfc)read_data<={30'd0,request_toggle,busy};
    else if(ra==20'hcf0)read_data<=32'h55493131;
    else if(ra==20'hcf4)read_data<=rejected;
    else if(ra>=20'hc80 && ra<20'hcfc && ra[1:0]==0)read_data<=shadow[(ra-20'hc80)>>2];
    else read_data<=0;
   end
  end
 end
 always @(posedge ui_clk or negedge ui_rst_n)begin
  if(!ui_rst_n)begin req_sync<=0;ack_toggle<=0;pending<=0;pending_data<=0;pending_toggle<=0;front<=0;front_valid<=0;end
  else begin
   req_sync<={req_sync[1:0],request_toggle};
   if(!pending && req_sync[2]!=ack_toggle)begin pending_data<=mailbox;pending_toggle<=req_sync[2];pending<=1;end
   if(pending && ui_blank && scene_generation==pending_data[30*32+:32])begin
    front<=pending_data;front_valid<=1;ack_toggle<=pending_toggle;pending<=0;
   end
  end
 end
endmodule
`default_nettype wire
