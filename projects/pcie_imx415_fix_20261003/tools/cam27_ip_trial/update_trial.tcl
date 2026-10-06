# Parent-authorized single-module elaborate/PLL-update only. No optimization,
# placement, routing, bitgen, project-source changes, or hardware access.
set task_dir [file dirname [file normalize [info script]]]
cd $task_dir
if {[catch {
    import_device ph1_90.db -package PH1A90SEG324 -speed 2
    puts "HELP_UPDATE_PLL_PARAM"
    update_pll_param -help
    puts "HELP_WRITE_VERILOG"
    write_verilog -help
    analyze -file cam27_trial_seed.v
    elaborate -top cam27_trial
    puts "ELABORATE_DONE"
    write_verilog cam27_before_update.v
    export_db cam27_before_update.db
    puts "BEFORE_UPDATE"
    update_pll_param -module cam27_trial -inst pll_inst -debug
    puts "AFTER_UPDATE"
    write_verilog cam27_after_update.v
    export_db cam27_after_update.db
} task_result task_options]} {
    puts "TRIAL_ERROR=$task_result"
    puts [dict get $task_options -errorinfo]
    exit 1
}
puts "STANDALONE_PLL_UPDATE_DONE"
exit
