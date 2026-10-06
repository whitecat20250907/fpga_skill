onerror {quit -code 1 -force}
onbreak {if {[examine -radix unsigned /tb_demo06_frontend/done] == "1"} {quit -code 0 -force} else {quit -code 1 -force}}
if {![file exists work_frontend]} {vlib work_frontend}
vlog -work work_frontend -sv ../uisrc/03_ip/csi_integrity/csi_rx_hdr_ecc.v ../uisrc/03_ip/csi_integrity/csi_rx_packet_handler.v ../uisrc/03_ip/csi_integrity/csi_rx_10bit_unpack.v ../uisrc/03_ip/csi_integrity/csi_rx_vid2stream.v ../uisrc/03_ip/csi_integrity/sfifo.v ../uisrc/03_ip/csi_integrity/image_correction.v ../uisrc/03_ip/csi_integrity/ui06_csi_frontend.v tb_demo06_frontend.sv
vsim -c -voptargs=+acc work_frontend.tb_demo06_frontend
run -all
quit -code 1 -force
