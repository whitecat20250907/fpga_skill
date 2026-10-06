onerror {quit -code 1 -force}
onbreak {resume}
if {![file exists paramwork]} {vlib paramwork}
vlog -work paramwork -sv ../fpga/uisrc/03_ip/ui_isp/ui_gamma/*.v ../fpga/uisrc/03_ip/ui_isp/ui_contrast_adj/ui_contrast_adj.v tb_isp_parameters.sv
vsim -c -voptargs=+acc -onfinish stop paramwork.tb_isp_parameters
run -all
if {[examine -radix binary /tb_isp_parameters/completed] != "1"} {quit -code 1 -force}
quit -code 0 -force
