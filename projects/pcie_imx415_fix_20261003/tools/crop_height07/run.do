onerror {quit -code 1 -force}
onbreak {resume}
transcript file physical_crop.log
if {![file exists work_crop]} {vlib work_crop}
vlog -work work_crop -sv src/csi_rx_hdr_ecc.v src/csi_rx_packet_handler.v src/csi_rx_10bit_unpack.v src/image_correction.v src/ui_BLC.v src/ui_ram_demosaic.v src/ui_raw_matrix_3x3_buffer.v src/ui_top_demosaic.v src/ui_bilinear_interpolation.v src/pack4_rgb24_to_128.v tb_physical_crop.sv
vsim -c -voptargs=+acc -onfinish stop work_crop.tb_physical_crop
run -all
if {[examine -radix binary /tb_physical_crop/done] != "1"} {quit -code 1 -force}
quit -code 0 -force
