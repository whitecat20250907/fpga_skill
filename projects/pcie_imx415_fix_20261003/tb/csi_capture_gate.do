onerror {quit -code 1 -force}
onbreak {quit -code 1 -force}
if {![file exists work_csi_gate]} {vlib work_csi_gate}
vmap csi_gate_test work_csi_gate
vlog -work csi_gate_test -sv ../fpga/uisrc/03_ip/mipi_csi_2/csi_rx_hdr_ecc.v ../fpga/uisrc/03_ip/mipi_csi_2/csi_rx_word_align.v ../fpga/uisrc/03_ip/mipi_csi_2/csi_rx_word_gear_box.v ../fpga/uisrc/03_ip/mipi_csi_2/csi_rx_packet_handler.v ../fpga/uisrc/03_ip/mipi_csi_2/csi_rx_10bit_unpack.v ../fpga/uisrc/03_ip/mipi_csi_2/csi_rx_vid2stream.v ../fpga/uisrc/03_ip/mipi_csi_2/sfifo.v ../fpga/uisrc/03_ip/mipi_csi_2/mipi_csi_rx.v E:/qianrufpga/fpga-lab/examples/06_csi_2_dsi_imx415_7cun/uisrc/03_ip/dsi/hdl_source/display_config/crc16_8b.v tb_csi_capture_gate.sv
vsim -c csi_gate_test.tb_csi_capture_gate
run -all
quit -code 0 -force
