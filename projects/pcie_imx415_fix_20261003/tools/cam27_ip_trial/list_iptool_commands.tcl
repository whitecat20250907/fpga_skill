set task_out [open "E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/tools/cam27_ip_trial/iptool_commands.txt" w]
puts $task_out [lsort [info commands]]
close $task_out
exit
