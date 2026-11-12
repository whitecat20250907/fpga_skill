`timescale 1ns/1ps
// HCIC16 command: magic[4],version1,mode6,threshold8,reserved0,sequenceLE32,
// CRC32LE of first12 bytes. Only validated commands change pending config.
module hci01_uart_config #(parameter CLOCK_HZ=25000000,BAUD=115200,TIMEOUT_CYCLES=500000)(
 input wire clk,rst_n,uart_rx,
 output reg [13:0] config_value,output reg [31:0] accepted_sequence,
 output reg [31:0] rejected,complete_packets,output reg config_valid);
 wire rx_synced,byte_valid;wire [7:0] byte_data;
 uart_rx_input_sync u_input_sync(.I_clk(clk),.I_uart_rx(uart_rx),.O_uart_rx(rx_synced));
 ui_uart_rx #(.BAUD_DIV(CLOCK_HZ/BAUD-1))u_rx(.I_clk(clk),.I_uart_rstn(rst_n),.I_uart_rx(rx_synced),
  .O_uart_rdata(byte_data),.O_uart_rvalid(byte_valid));
 reg [31:0] search,crc,timer;
 reg [127:0] packet;
 reg [4:0] position;
 reg has_sequence;
 function [31:0] crc_byte;
  input [31:0] c;input [7:0] b;reg [31:0] q;integer j;
  begin q=c^b;for(j=0;j<8;j=j+1)q=(q>>1)^(q[0]?32'hedb88320:0);crc_byte=q;end
 endfunction
 localparam [31:0] MAGIC=32'h43494348;
 wire [31:0] search_next={byte_data,search[31:8]};
 wire [31:0] received_crc={byte_data,packet[119:96]};
 wire [31:0] delta=packet[95:64]-accepted_sequence;
 wire legal=packet[39:32]==1&&packet[47:46]==0&&packet[45:43]<=4&&packet[63:56]==0;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin config_value<=14'd8192;accepted_sequence<=0;rejected<=0;complete_packets<=0;config_valid<=1;
   search<=0;crc<=32'hffffffff;timer<=0;packet<=0;position<=0;has_sequence<=0;end
  else if(byte_valid)begin
   timer<=0;
   if(position==0)begin
    search<=search_next;
    if(search_next==MAGIC)begin
     packet[31:0]<=MAGIC;position<=4;search<=0;
     crc<=crc_byte(crc_byte(crc_byte(crc_byte(32'hffffffff,8'h48),8'h43),8'h49),8'h43);
    end
   end else begin
    packet[position*8+:8]<=byte_data;
    if(position<12)crc<=crc_byte(crc,byte_data);
    if(position==15)begin
     position<=0;search<=0;complete_packets<=complete_packets+1'b1;
     if(received_crc==~crc&&legal&&(!has_sequence||(delta!=0&&!delta[31])))begin
      config_value<={packet[55:48],packet[45:40]};accepted_sequence<=packet[95:64];has_sequence<=1;config_valid<=1;
     end else rejected<=rejected+1'b1;
    end else position<=position+1'b1;
   end
  end else if(position!=0)begin
   if(timer==TIMEOUT_CYCLES-1)begin position<=0;search<=0;timer<=0;rejected<=rejected+1'b1;end
   else timer<=timer+1'b1;
  end
 end
endmodule
