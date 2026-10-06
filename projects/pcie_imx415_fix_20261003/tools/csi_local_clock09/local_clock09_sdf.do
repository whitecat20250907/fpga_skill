onerror {quit -code 1 -force}
onbreak {test_break_sdf}
proc test_break_sdf {} {
    if {[catch {examine -radix binary /tb_csi_local_clock09_sdf/test_done} done] || $done ne "1"} {quit -code 1 -force}
    resume
}
set test_root E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/tools/csi_local_clock09
set route_root [file join $test_root evidence td_route_20261005_071009_40084]
set out [file join $test_root evidence sdf_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[pid]]
file mkdir $out
cd $out
transcript file [file join $out simulation.log]
transcript on
puts "CSI_LOCAL_CLOCK09_SDF_OUTPUT=$out"
vmap -c
vlib work
set model_files [list E:/qianrufpga/TD/sim_release/common/al_phy_glbl.v E:/qianrufpga/TD/sim_release/ph1/ph1_phy_config_v2.sv E:/qianrufpga/TD/sim_release/ph1/ph1_phy_gsr.v E:/qianrufpga/TD/sim_release/ph1/ph1_phy_gclk_v2.v E:/qianrufpga/TD/sim_release/ph1/ph1_phy_sclk_v2.v E:/qianrufpga/TD/sim_release/ph1/ph1_phy_hr_bankref.v E:/qianrufpga/TD/sim_release/ph1/ph1_phy_pad.v E:/qianrufpga/TD/sim_release/ph1/ph1_phy_lclk_v2.v E:/qianrufpga/TD/sim_release/ph1/ph1_phy_lslice.v]
lappend model_files E:/qianrufpga/TD/sim_release/ph1/ph1_logic_io.v
eval vlog -sv $model_files [list [file join $route_root csi09_phy_sim.v] [file join $test_root tb_csi_local_clock09_sdf.sv]]
# The native exported netlist has its own initial $sdf_annotate, using this
# exact matching routed SDF. Do not apply a duplicate external annotation.
set delayed_flags {}
if {[info exists ::env(CSI09_EXPLICIT_DTC)] && $::env(CSI09_EXPLICIT_DTC) eq "1"} {
    lappend delayed_flags +delayed_timing_checks
}
for {set phase 0} {$phase<8} {incr phase} {
    eval vsim -c -novopt -onfinish stop +maxdelays +sdf_verbose +ntc_warn $delayed_flags [list -sdfreport=[file join $out unannotated_${phase}.txt] -gPHASE=$phase work.tb_csi_local_clock09_sdf work.PH1_PHY_GSR]
    run -all
    if {[examine -radix binary /tb_csi_local_clock09_sdf/test_done] ne "1"} {error "SDF test did not complete phase $phase"}
    quit -sim
}
puts "PASS CSI_LOCAL_CLOCK09_SDF_ALL_PHASES"
quit -code 0 -force
