`timescale 1ns/1ps
// One real UART RX and one length-aware parser. HCIC16 keeps HCI01 controls;
// HCIR64 atomically updates three trusted ROI descriptors after CRC/geometry/
// modulo-sequence validation. A recognised packet body is never re-scanned
// for a second embedded command.
module hci02_command_rx #(
 parameter CLOCK_HZ=25000000,BAUD=115200,TIMEOUT_CYCLES=500000,
 parameter WIDTH=1920,HEIGHT=1080,
 parameter MAX_EYE_WIDTH=256,MAX_EYE_HEIGHT=128,
 parameter MAX_FACE_WIDTH=448,MAX_FACE_HEIGHT=448
)(
 input wire clk,rst_n,uart_rx,
 output reg [13:0] config_value,
 output reg [31:0] accepted_sequence,rejected,complete_packets,
 output reg config_valid,
 output reg [191:0] roi_windows,output reg [2:0] roi_enable,
 output reg [31:0] roi_sequence,roi_rejected,roi_packets,
 output reg [15:0] roi_ttl,output reg roi_valid
);
 wire rx_synced,byte_valid;wire [7:0] byte_data;
 uart_rx_input_sync u_input_sync(.I_clk(clk),.I_uart_rx(uart_rx),.O_uart_rx(rx_synced));
 ui_uart_rx #(.BAUD_DIV(CLOCK_HZ/BAUD-1))u_rx(.I_clk(clk),.I_uart_rstn(rst_n),.I_uart_rx(rx_synced),
  .O_uart_rdata(byte_data),.O_uart_rvalid(byte_valid));
 reg [31:0] search,crc,timer;reg [511:0] packet;
 reg [6:0] position,length;
 reg roi_packet,has_sequence,has_roi_sequence;
 function [31:0] crc_byte;
  input [31:0] c;input [7:0] b;reg [31:0] q;integer j;
  begin q=c^b;for(j=0;j<8;j=j+1)q=(q>>1)^(q[0]?32'hedb88320:0);crc_byte=q;end
 endfunction
 localparam [31:0] MAGIC_IC=32'h43494348,MAGIC_IR=32'h52494348;
 wire [31:0] search_next={byte_data,search[31:8]};
 wire [31:0] received_crc=roi_packet?{byte_data,packet[503:480]}:{byte_data,packet[119:96]};
 wire [31:0] delta_ic=packet[95:64]-accepted_sequence;
 wire [31:0] delta_ir=packet[95:64]-roi_sequence;
 wire legal_ic=packet[39:32]==1&&packet[47:46]==0&&packet[45:43]<=4&&packet[63:56]==0;
 wire [191:0] windows={packet[383:320],packet[287:224],packet[191:128]};
 function geometry_ok;
  input [191:0] wds;input [2:0] enable;
  integer j;reg [15:0] x,y,w,h;reg ok;
  begin ok=1;
   for(j=0;j<3;j=j+1)begin
    x=wds[j*64+:16];y=wds[j*64+16+:16];w=wds[j*64+32+:16];h=wds[j*64+48+:16];
    if(enable[j]&&(w==0||h==0||{1'b0,x}+{1'b0,w}>WIDTH||{1'b0,y}+{1'b0,h}>HEIGHT||
     w>(j==2?MAX_FACE_WIDTH:MAX_EYE_WIDTH)||h>(j==2?MAX_FACE_HEIGHT:MAX_EYE_HEIGHT)))ok=0;
   end
   geometry_ok=ok;
  end
 endfunction
 wire legal_ir=packet[39:32]==1&&packet[47:43]==0&&packet[55:48]==64&&packet[63:56]==0&&
  packet[111:96]>=1&&packet[111:96]<=4095&&packet[127:112]==0&&
  packet[223:192]==0&&packet[319:288]==0&&packet[415:384]==0&&packet[479:416]==0&&
  geometry_ok(windows,packet[42:40]);
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   config_value<=14'd8192;accepted_sequence<=0;rejected<=0;complete_packets<=0;config_valid<=1;
   roi_windows<=0;roi_enable<=0;roi_sequence<=0;roi_rejected<=0;roi_packets<=0;roi_ttl<=0;roi_valid<=0;
   search<=0;crc<=32'hffffffff;timer<=0;packet<=0;position<=0;length<=0;
   roi_packet<=0;has_sequence<=0;has_roi_sequence<=0;
  end else if(byte_valid)begin
   timer<=0;
   if(position==0)begin
    search<=search_next;
    if(search_next==MAGIC_IC||search_next==MAGIC_IR)begin
     packet<=0;packet[31:0]<=search_next;position<=4;search<=0;
     roi_packet<=search_next==MAGIC_IR;length<=search_next==MAGIC_IR?64:16;
     crc<=crc_byte(crc_byte(crc_byte(crc_byte(32'hffffffff,8'h48),8'h43),8'h49),byte_data);
    end
   end else begin
    packet[position*8+:8]<=byte_data;
    if(position<length-4)crc<=crc_byte(crc,byte_data);
    if(position==length-1)begin
     position<=0;search<=0;
     if(roi_packet)begin
      roi_packets<=roi_packets+1'b1;
      if(received_crc==~crc&&legal_ir&&(!has_roi_sequence||(delta_ir!=0&&!delta_ir[31])))begin
       roi_windows<=windows;roi_enable<=packet[42:40];roi_sequence<=packet[95:64];
       roi_ttl<=packet[111:96];roi_valid<=1;has_roi_sequence<=1;
      end else roi_rejected<=roi_rejected+1'b1;
     end else begin
      complete_packets<=complete_packets+1'b1;
      if(received_crc==~crc&&legal_ic&&(!has_sequence||(delta_ic!=0&&!delta_ic[31])))begin
       config_value<={packet[55:48],packet[45:40]};accepted_sequence<=packet[95:64];config_valid<=1;has_sequence<=1;
      end else rejected<=rejected+1'b1;
     end
    end else position<=position+1'b1;
   end
  end else if(position!=0)begin
   if(timer==TIMEOUT_CYCLES-1)begin
    position<=0;search<=0;timer<=0;
    if(roi_packet)roi_rejected<=roi_rejected+1'b1;else rejected<=rejected+1'b1;
   end else timer<=timer+1'b1;
  end
 end
endmodule
