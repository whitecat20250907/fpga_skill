onerror {quit -code 1 -force}
onbreak {test_break}
proc test_break {} {
    if {[catch {examine -radix binary /tb_sampler_reset/test_done} done] || $done ne "1"} {quit -code 1 -force}
    resume
}
set task_root E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003
set test_root [file join $task_root tools csi_fast6]
set stamp [clock format [clock seconds] -format %Y%m%d_%H%M%S]
set test_out [file join $test_root evidence sampler_${stamp}_[pid]]
if {[file exists $test_out]} {error "Refusing existing test output"}
file mkdir $test_out
cd $test_out
transcript file [file join $test_out simulation.log]
transcript on
puts "SAMPLER6_OUTPUT=$test_out"
vmap -c
vlib work
vlog -sv E:/qianrufpga/TD/sim_release/ph1/ph1_logic_io.v E:/qianrufpga/TD/sim_release/ph1/ph1_logic_dynamic_idelay.v E:/qianrufpga/TD/sim_release/ph1/ph1_phy_gsr.v [file join $test_root csi_rx_hs_data_phy.v] [file join $test_root csi_rx_hs_data_phy_reference.v] [file join $task_root fpga uisrc 03_ip mipi_csi_2 csi_rx_byte_align.v] [file join $test_root tb_sampler_reset.sv]
vsim -c -voptargs=+acc -onfinish stop work.tb_sampler_reset work.PH1_PHY_GSR
run -all
if {[examine -radix binary /tb_sampler_reset/test_done] ne "1"} {error "Sampler reset selfcheck did not complete"}
puts "PASS CSI_FAST6_SAMPLER_ALL_DIGITAL_CHECKS"
quit -code 0 -force
