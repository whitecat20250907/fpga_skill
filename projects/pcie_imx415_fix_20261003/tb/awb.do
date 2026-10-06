onerror {quit -code 1 -force}
onbreak {quit -code 1 -force}
if {![file exists work]} {vlib work}
vlog -sv ../fpga/uisrc/03_ip/ui_isp/ui_awb/ui_awb.v tb_awb.sv
vsim -c work.tb_awb
run -all
quit -code 0 -force
