onerror {quit -code 1 -force}
onbreak {resume}
transcript file runtime_golden.log
if {![file exists work_runtime]} {vlib work_runtime}
vlog -work work_runtime -sv ../../fpga/uisrc/03_ip/ui_isp/ui_ram_demosaic/ui_ram_demosaic.v ../../fpga/uisrc/03_ip/ui_isp/ui_BLC.v ui_top_demosaic.v ../../fpga/uisrc/03_ip/ui_isp/ui_raw_matrix_3x3_buffer.v ui_bilinear_interpolation.v tb_bayer_runtime.sv
vsim -c -voptargs=+acc -onfinish stop work_runtime.tb_bayer_runtime
run -all
if {[examine -radix binary /tb_bayer_runtime/done] != "1"} {quit -code 1 -force}
quit -code 0 -force
