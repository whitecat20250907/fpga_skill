onerror {quit -code 1 -force}
onbreak {quit -code 1 -force}
if {![file exists work]} {vlib work}
vlog -sv ../tools/csi_rx_clock_det_safe.v tb_csi_clock.sv
vsim -c work.tb_csi_clock
run -all
quit -code 0 -force
