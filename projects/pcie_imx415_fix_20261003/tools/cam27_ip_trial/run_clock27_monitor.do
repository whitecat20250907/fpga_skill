onerror {quit -code 1}
onbreak {quit -code 1}
if {![file exists monitor_work]} {vlib monitor_work}
vmap monitor_work monitor_work
vlog -work monitor_work cam_clock27_monitor.v tb_clock27_monitor.v
vsim -voptargs=+acc monitor_work.tb_clock27_monitor
run -all
if {[examine -radix unsigned /tb_clock27_monitor/done] != 1} {quit -code 1}
quit -code 0
