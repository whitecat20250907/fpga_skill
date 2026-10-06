onerror {quit -code 1 -force}
onbreak {resume}
if {![file exists elasticwork]} {vlib elasticwork}
vlog -work elasticwork -sv ../fpga/uisrc/03_ip/ui_isp/ui_BLC.v ../fpga/uisrc/03_ip/ui_isp/ui_image_cut/ui_image_cut.v ../fpga/uisrc/03_ip/ui_isp/ui_gamma/*.v ../fpga/uisrc/03_ip/ui_isp/ui_contrast_adj/ui_contrast_adj.v ../fpga/uisrc/03_ip/ui_isp/ui_brightness_adj/ui_Brightness_adj.v ../fpga/uisrc/03_ip/ui_isp/ui_saturation_adj/ui_Saturation_adj.v tb_isp_elastic.sv
vsim -c -voptargs=+acc -onfinish stop elasticwork.tb_isp_elastic
run -all
if {[examine -radix binary /tb_isp_elastic/completed] != "1"} {quit -code 1 -force}
quit -code 0 -force
