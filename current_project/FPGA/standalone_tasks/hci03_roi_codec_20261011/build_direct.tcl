# TD Windows CLI takes this ONE script path; the template consumes argv.
set td_direct_caller_dir [file dirname [file normalize [info script]]]
set argv [list [file join $td_direct_caller_dir fpga_prj.al] [file join $td_direct_caller_dir build_direct_config.tcl]]
source [file join $td_direct_caller_dir td_build_direct.tcl]
