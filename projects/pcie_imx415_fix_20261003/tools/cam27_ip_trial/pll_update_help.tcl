puts "READ_ONLY_PLL_UPDATE_HELP"
foreach task_command {update_pll_param export_verilog read_verilog analyze create_project elaborate print_ip_config report_cell get_cells get_property} {
    puts "HELP_COMMAND=$task_command"
    set task_rc [catch {$task_command -help} task_result]
    puts "RC=$task_rc RESULT=$task_result"
}
exit
