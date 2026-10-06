if {[catch {connect_cable -host_name localhost} err]} {
    puts stderr "CABLE_ERROR: $err"; exit 1
}
list_cable
if {[catch {download -bit {E:/qianrufpga/fpga-lab/projects/t3_basic6/s2_meta_monitor/fpga_prj_Runs/phy_1/fpga_prj.bit} -mode jtag -spd 7 -cable 0} err]} {
    puts stderr "DOWNLOAD_ERROR: $err"; exit 1
}
exit
