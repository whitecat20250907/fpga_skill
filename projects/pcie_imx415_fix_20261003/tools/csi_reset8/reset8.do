onerror {quit -code 1 -force}
onbreak {test_break}
proc test_break {} {
    if {[catch {examine -radix binary /tb_csi_reset8/test_done} done] || $done ne "1"} {quit -code 1 -force}
    resume
}
set task_root E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003
set test_root [file join $task_root tools csi_reset8]
set out [file join $test_root evidence modelsim_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[pid]]
if {[file exists $out]} {error "Refusing existing test output"}
file mkdir $out
cd $out
transcript file [file join $out simulation.log]
transcript on
puts "CSI_RESET8_OUTPUT=$out"
vmap -c
vlib work
vlog -sv E:/qianrufpga/TD/sim_release/ph1/ph1_logic_io.v E:/qianrufpga/TD/sim_release/ph1/ph1_logic_dynamic_idelay.v E:/qianrufpga/TD/sim_release/ph1/ph1_phy_gsr.v [file join $test_root csi_rx_hs_data_phy.v] [file join $test_root csi_rx_phy.v] [file join $task_root fpga uisrc 03_ip mipi_csi_2 csi_rx_byte_align.v] [file join $task_root fpga uisrc 03_ip mipi_csi_2 csi_rx_clock_det.v] [file join $task_root fpga uisrc 03_ip mipi_csi_2 auto_delay_ctl.v] [file join $test_root tb_csi_reset8.sv]
vsim -c -voptargs=+acc -onfinish stop work.tb_csi_reset8 work.PH1_PHY_GSR
run -all
if {[examine -radix binary /tb_csi_reset8/test_done] ne "1"} {error "CSI reset8 selfcheck did not complete"}
puts "PASS CSI_RESET8_DIGITAL_GOLDEN"
quit -code 0 -force
