# Run from a separate TD command process; close this target in TD GUI first.
if {[catch {
  cd {E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/evidence/skill_helper_uart_clone_20261004}
  import_device ph1_90.db -package PH1A90SEG324 -speed 2
  open_project {E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/evidence/skill_helper_uart_clone_20261004/fpga_prj.al}
  set build_started [clock seconds]
  reset_runs syn_1
  launch_runs syn_1
  wait_run syn_1 -quiet
  launch_runs phy_1
  wait_run phy_1 -quiet
  set build_bit {fpga_prj_Runs/phy_1/fpga_prj.bit}
  if {![file exists $build_bit] || [file mtime $build_bit] < $build_started} {
    error {TD did not generate a fresh bitstream}
  }
} err]} { puts stderr $err; exit 1 }
exit 0
