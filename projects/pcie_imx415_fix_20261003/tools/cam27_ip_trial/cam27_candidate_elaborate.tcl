# Standalone candidate only, expressly no optimize/place/route/bitgen.
cd E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/tools/cam27_ip_trial
if {[catch {
    import_device ph1_90.db -package PH1A90SEG324 -speed 2
    analyze -file cam_pll27.v
    analyze -file cam_clock27_monitor.v
    elaborate -top cam_pll27
    write_verilog cam27_candidate_elaborated.v
    export_db cam27_candidate_elaborated.db
} task_result task_options]} {
    puts "TRIAL_ERROR=$task_result"
    puts [dict get $task_options -errorinfo]
    exit 1
}
puts "CANDIDATE_ELABORATE_DONE_ONLY"
exit
