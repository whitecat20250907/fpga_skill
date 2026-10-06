if {[catch {
  cd {E:/qianrufpga/fpga-lab/projects/t3_basic6/s0_vendor_415}
  import_device ph1_90.db -package PH1A90SEG324 -speed 2
  open_project {E:/qianrufpga/fpga-lab/projects/t3_basic6/s0_vendor_415/fpga_prj.al}
  launch_runs syn_1
  wait_run syn_1 -quiet
  launch_runs phy_1
  wait_run phy_1 -quiet
} err]} { puts stderr $err; exit 1 }
exit 0
