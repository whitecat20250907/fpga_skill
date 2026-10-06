`timescale 1ns/1ps
module uart_loop_tb;
reg clk=0, rx=1;
wire tx;
localparam real BIT_NS=1.0e9/115200.0;
integer received=0;
reg test_done=0;
reg [7:0] expected[0:5];
reg [7:0] actual;
integer k,j;
uart_top dut(.I_sysclk(clk),.I_uart_rx(rx),.O_uart_tx(tx));
always #20 clk=~clk;
task send_byte(input [7:0] value);
integer b;
begin
rx=0; #(BIT_NS);
for(b=0;b<8;b=b+1) begin rx=value[b]; #(BIT_NS); end
rx=1; #(BIT_NS);
end
endtask
initial begin
expected[0]=8'h55; expected[1]=8'hAA; expected[2]=8'h00;
expected[3]=8'hFF; expected[4]=8'h31; expected[5]=8'h95;
#100000; // Wait beyond the roughly 82 us internal reset.
for(k=0;k<6;k=k+1) begin
send_byte(expected[k]);
wait(received==k+1); // No transmit queue: pace requests.
#(2*BIT_NS);
end
$display("PASS: 6 UART bytes echoed correctly at 25 MHz / 115200 baud");
test_done=1;
end
initial begin
forever begin
@(negedge tx); #(BIT_NS/2);
if(tx !== 1'b0) $fatal(1,"Invalid start bit");
for(j=0;j<8;j=j+1) begin #(BIT_NS); actual[j]=tx; end
#(BIT_NS);
if(tx !== 1'b1) $fatal(1,"Invalid stop bit");
if(received>=6) $fatal(1,"Unexpected byte");
if(actual !== expected[received]) $fatal(1,"Byte %0d mismatch: expected %h got %h",received,expected[received],actual);
$display("RX[%0d] = %h",received,actual);
received=received+1;
end
end

endmodule
