onerror {quit -code 1 -force}
onbreak {quit -code 1 -force}
vlib work
vmap work work
vlog -sv ../../01_rtl/uart_top.v ../../03_ip/uiuart_rx.v ../../03_ip/uiuart_tx.v uart_loop_tb.sv
vsim -voptargs=+acc work.uart_loop_tb
onfinish stop
add wave sim:/uart_loop_tb/clk sim:/uart_loop_tb/rx sim:/uart_loop_tb/tx
add wave sim:/uart_loop_tb/dut/uart_rstn_i sim:/uart_loop_tb/dut/uart_rvalid
add wave -radix hexadecimal sim:/uart_loop_tb/dut/uart_rdata
run 2 ms
if {[examine -radix unsigned sim:/uart_loop_tb/test_done] != 1} {
  echo "FAIL: simulation did not complete"
  quit -code 1 -force
}
