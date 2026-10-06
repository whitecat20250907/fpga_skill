onerror {quit -code 1 -force}
onbreak {quit -code 1 -force}
if {![file exists work]} {vlib work}
vlog -sv ../fpga/uisrc/03_ip/vid_pipeline/pack4_rgb24_to_128.v tb_pack4.sv
vsim -c work.tb_pack4
run -all
quit -code 0 -force
