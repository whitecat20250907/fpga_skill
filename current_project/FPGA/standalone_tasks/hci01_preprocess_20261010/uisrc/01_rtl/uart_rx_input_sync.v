// Dedicated asynchronous UART input capture. Only rx_sync feeds consumers.
// UART is idle-high; no raw-pin reset/enable enters either synchronizer stage.
module uart_rx_input_sync(input I_clk,input I_uart_rx,output O_uart_rx);
 (* ASYNC_REG="TRUE" *) reg rx_meta=1'b1;
 (* ASYNC_REG="TRUE" *) reg rx_sync=1'b1;
 always @(posedge I_clk)begin
  rx_meta<=I_uart_rx;
  rx_sync<=rx_meta;
 end
 assign O_uart_rx=rx_sync;
endmodule
