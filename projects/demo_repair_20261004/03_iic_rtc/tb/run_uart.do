onerror {quit -code 1 -force}
onbreak {if {[examine -radix unsigned /tb_uart_block/test_done] == "1"} {quit -code 0 -force} else {quit -code 1 -force}}
if {![file exists work]} {vlib work}
vlog ../uisrc/03_ip/uiuart_tx.v ../uisrc/03_ip/uart_tx_block.v
vlog -sv tb_uart_block.sv
vsim -voptargs=+acc work.tb_uart_block
run 1 ms
if {[examine -radix unsigned /tb_uart_block/test_done] != "1"} {quit -code 1 -force}
quit -code 0 -force
