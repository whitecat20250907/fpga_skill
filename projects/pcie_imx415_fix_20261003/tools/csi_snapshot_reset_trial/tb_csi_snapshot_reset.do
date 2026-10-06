onerror {quit -code 1 -force}
onbreak {quit -code 1 -force}
if {![file exists work]} {vlib work}
vlog -sv ../../fpga/uisrc/03_ip/vid_pipeline/csi_stats_snapshot.v ../../tb/tb_csi_snapshot_reset.sv
vsim -c work.tb_csi_snapshot_reset
run -all
if {[examine /tb_csi_snapshot_reset/passed] != 1} {quit -code 1 -force}
quit -code 0 -force
