onerror {quit -code 1 -force}
onbreak {quit -code 1 -force}
if {![file exists work_csi]} {vlib work_csi}
vmap csi_test work_csi
vlog -work csi_test -sv ../fpga/uisrc/03_ip/mipi_csi_2/csi_rx_hdr_ecc.v ../fpga/uisrc/03_ip/mipi_csi_2/csi_rx_packet_handler.v ../fpga/uisrc/03_ip/mipi_csi_2/csi_rx_10bit_unpack.v ../fpga/uisrc/03_ip/mipi_csi_2/csi_rx_vid2stream.v ../fpga/uisrc/03_ip/mipi_csi_2/sfifo.v E:/qianrufpga/fpga-lab/examples/06_csi_2_dsi_imx415_7cun/uisrc/03_ip/dsi/hdl_source/display_config/crc16_8b.v tb_csi_integrity.sv
vsim -c csi_test.tb_csi_integrity
run -all
quit -code 0 -force
