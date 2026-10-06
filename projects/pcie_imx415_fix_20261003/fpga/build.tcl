if {[catch {
 cd {E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/fpga}
 import_device ph1_90.db -package PH1A90SEG324 -speed 2
 open_project {E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/fpga/imx415_pcie_4k.al}
 set build_started [clock seconds]
 # Full builds must invalidate previously completed runs before launch.
 # Preserve historical evidence outside Runs before invoking this script.
 reset_runs syn_1
 launch_runs syn_1
 wait_run syn_1 -quiet
 launch_runs phy_1
 wait_run phy_1 -quiet
 set build_bit {imx415_pcie_4k_Runs/phy_1/imx415_pcie_4k_compress.bit}
 if {![file exists $build_bit] || [file mtime $build_bit] < $build_started} {
  error "Full build did not produce a fresh bitstream"
 }
} err]} { puts stderr $err; exit 1 }
exit 0
