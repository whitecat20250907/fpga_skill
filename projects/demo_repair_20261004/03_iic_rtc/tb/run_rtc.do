onerror {quit -code 1 -force}
onbreak {if {[examine -radix unsigned /tb_rtc_poll/test_done] == "1"} {quit -code 0 -force} else {quit -code 1 -force}}
if {![file exists work_rtc]} {vlib work_rtc}
vlog -work work_rtc ../uisrc/03_ip/uiuart_tx.v ../uisrc/03_ip/uart_tx_block.v ../uisrc/01_rtl/rtc_clock_ds1337.v
vlog -sv -work work_rtc tb_rtc_poll.sv
vsim -voptargs=+acc work_rtc.tb_rtc_poll
run 10 ms
if {[examine -radix unsigned /tb_rtc_poll/test_done] != "1"} {quit -code 1 -force}
quit -code 0 -force
