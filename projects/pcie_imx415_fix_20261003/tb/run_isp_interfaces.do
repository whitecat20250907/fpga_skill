onerror {quit -code 1 -force}
onbreak {resume}
if {![file exists ifacework]} {vlib ifacework}
vlog -work ifacework -sv ../fpga/uisrc/03_ip/ui_isp/image_correction.v ../fpga/uisrc/03_ip/ui_isp/ui_line_buffer_demosaic.v ../fpga/uisrc/03_ip/ui_isp/ui_ram_demosaic/ui_ram_demosaic.v tb_isp_interfaces.sv
vsim -c -voptargs=+acc -onfinish stop ifacework.tb_isp_interfaces
run -all
if {[examine -radix binary /tb_isp_interfaces/completed] != "1"} {quit -code 1 -force}
quit -code 0 -force
