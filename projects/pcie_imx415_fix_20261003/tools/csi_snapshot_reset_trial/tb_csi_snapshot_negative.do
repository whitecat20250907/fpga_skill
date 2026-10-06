onerror {quit -code 1 -force}
onbreak {quit -code 1 -force}
if {![file exists work]} {vlib work}
vlog -sv raw_release_negative.v ../../tb/tb_csi_snapshot_reset.sv
vsim -c work.tb_csi_snapshot_reset
run -all
if {[examine /tb_csi_snapshot_reset/passed] == 1} {quit -code 2 -force}
quit -code 1 -force
