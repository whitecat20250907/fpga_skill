`timescale 1ns/1ps
module uart_case #(parameter N=10)(input clk,output reg done=0);
localparam BIT_TIME=80;
reg [N*8-1:0] data=0;
reg request=0;
wire tx;
integer received=0;
ui_uart_tx_block #(.TX_BYTES(N),.BAUD_DIV(7)) dut(
 .I_sysclk(clk),.O_uart_tx(tx),.I_uart_tx_buf(data),.I_uart_tx_buf_en(request));
function [7:0] golden(input integer packet,input integer index);
 golden=8'h31+index+packet*8'h40;
endfunction
initial begin: sender
 integer packet,index;
 wait(dut.uart_rstn);repeat(3) @(negedge clk);
 for(packet=0;packet<2;packet=packet+1) begin
  for(index=0;index<N;index=index+1)data[index*8+:8]=golden(packet,index);
  request=1;@(negedge clk);request=0;
  wait(dut.uart_wbusy);
  // Accepted packet must remain coherent even if the caller changes its bus.
  @(negedge clk);data='1;
  wait(received==(packet+1)*N);
  wait(dut.S_UART_TX==0);repeat(15) @(negedge clk);
 end
 repeat(100) @(negedge clk);
 if(received!=2*N)$fatal(1,"N=%0d byte count %0d",N,received);
 done=1;
 $display("UART PASS N=%0d packets=2 bytes=%0d",N,received);
end
initial begin: receiver
 reg [7:0] byte_value;
 integer bit_index;
 forever begin
  @(negedge tx);
  if(received>=2*N)$fatal(1,"Unexpected extra UART byte N=%0d",N);
  #(BIT_TIME/2);if(tx!==0)$fatal(1,"Missing start bit");
  for(bit_index=0;bit_index<8;bit_index=bit_index+1)begin
   #(BIT_TIME);byte_value[bit_index]=tx;
  end
  #(BIT_TIME);if(tx!==1)$fatal(1,"Bad stop bit");
  if(byte_value!==golden(received/N,received%N))
   $fatal(1,"UART N=%0d index=%0d got %h expected %h",N,received,byte_value,golden(received/N,received%N));
  received=received+1;
 end
end
endmodule
module tb_uart_block;
reg clk=0;always #5 clk=~clk;
wire d1,d10,d16;
reg test_done=0;
uart_case #(.N(1)) a(clk,d1);
uart_case #(.N(10)) b(clk,d10);
uart_case #(.N(16)) c(clk,d16);
initial begin wait(d1&&d10&&d16);test_done=1;$display("ALL UART BLOCK CHECKS PASS");$stop;end
initial begin #1000000;$fatal(1,"UART timeout");end
endmodule
