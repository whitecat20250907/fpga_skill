onerror {quit -code 1 -force}
onbreak {resume}
if {![file exists ispold]} {vlib ispold}
vlog -work ispold -sv +define+BASELINE_TEST ../fpga/uisrc/03_ip/ui_isp/ui_top_demosaic.v ../evidence/isp_before/ui_raw_matrix_3x3_buffer.v ../evidence/isp_before/ui_bilinear_interpolation.v ../evidence/isp_before/ui_line_buffer_demosaic.v ../evidence/isp_before/ui_zhenghe.v ../fpga/uisrc/03_ip/ui_isp/ui_mipi_to_raw_converter.v ../fpga/uisrc/03_ip/ui_isp/ui_ram_demosaic/ui_ram_demosaic.v ../fpga/uisrc/03_ip/ui_isp/ui_ram_zhenghe/ui_ram_zhenghe.v tb_isp_golden.sv
vsim -c -voptargs=+acc -onfinish stop ispold.tb_isp_golden
run -all
if {[examine -radix binary /tb_isp_golden/done] != "1111"} {quit -code 1 -force}
quit -code 0 -force
