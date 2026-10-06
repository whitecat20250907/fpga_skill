onerror {quit -code 1 -force}
onbreak {quit -code 1 -force}
if {![file exists work_csi_cal]} {vlib work_csi_cal}
vmap csi_cal_test work_csi_cal
vlog -work csi_cal_test -sv ../fpga/uisrc/03_ip/mipi_csi_2/auto_delay_ctl.v ../fpga/uisrc/03_ip/mipi_csi_2/csi_rx_phy.v ../fpga/uisrc/03_ip/mipi_csi_2/csi_rx_clock_det.v ../fpga/uisrc/03_ip/mipi_csi_2/csi_rx_byte_align.v tb_csi_calibration.sv
vsim -c csi_cal_test.tb_csi_calibration
run -all
quit -code 0 -force
