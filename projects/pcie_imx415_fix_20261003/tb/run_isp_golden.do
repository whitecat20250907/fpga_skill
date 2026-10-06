onerror {quit -code 1 -force}
onbreak {resume}
if {![file exists ispwork]} {vlib ispwork}
vlog -work ispwork -sv ../fpga/uisrc/03_ip/ui_isp/ui_ram_demosaic/ui_ram_demosaic.v ../fpga/uisrc/03_ip/ui_isp/ui_BLC.v ../fpga/uisrc/03_ip/ui_isp/ui_top_demosaic.v ../fpga/uisrc/03_ip/ui_isp/ui_raw_matrix_3x3_buffer.v ../fpga/uisrc/03_ip/ui_isp/ui_bilinear_interpolation.v tb_isp_golden.sv
vsim -c -voptargs=+acc -onfinish stop ispwork.tb_isp_golden
run -all
if {[examine -radix binary /tb_isp_golden/done] != "1111"} {quit -code 1 -force}
quit -code 0 -force
