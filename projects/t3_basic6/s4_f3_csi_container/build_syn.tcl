if {[catch {
  cd {E:/qianrufpga/fpga-lab/projects/t3_basic6/s4_f3_csi_container}
  import_device ph1_90.db -package PH1A90SEG324 -speed 2
  open_project {E:/qianrufpga/fpga-lab/projects/t3_basic6/s4_f3_csi_container/fpga_prj.al}
  reset_runs phy_1
  reset_runs syn_1
  launch_runs syn_1
  wait_run syn_1 -quiet
} err]} { puts stderr $err; exit 1 }
exit 0
