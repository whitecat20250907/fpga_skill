onerror {quit -code 1 -force}
onbreak {selfcheck_break}
proc selfcheck_break {} {
    if {[catch {examine -radix binary /tb_phy_diag08/test_done} done] || $done ne "1"} {
        quit -code 1 -force
    }
    resume
}
set root E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003
set source [file join $root tools phy_diag08]
set out [file join $root evidence phy_diag08_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[pid]]
if {[file exists $out]} {error "Refusing existing evidence directory"}
file mkdir $out
cd $out
transcript file [file join $out simulation.log]
transcript on
puts "PHY_DIAG08_OUTPUT=$out"
vmap -c
vlib work
vlog -sv [file join $source isp_header_stubs.v] [file join $source rx_digital_stubs.v] \
    [file join $root fpga uisrc 03_ip vid_pipeline csi_stats_snapshot.v] \
    [file join $root fpga uisrc 03_ip mipi_csi_2 csi_rx_hdr_ecc.v] \
    [file join $root fpga uisrc 03_ip mipi_csi_2 csi_rx_packet_handler.v] \
    [file join $source mipi_csi_rx.v] [file join $source cam_video_source.v] \
    [file join $source tb_phy_diag08.sv]
vsim -c -voptargs=+acc -onfinish stop work.tb_phy_diag08
run -all
if {[examine -radix binary /tb_phy_diag08/test_done] ne "1"} {error "Diagnostic selfcheck did not finish"}
puts "PASS PHY_DIAG08_STAGED_ONLY_NO_TD_OR_BOARD"
quit -code 0 -force
