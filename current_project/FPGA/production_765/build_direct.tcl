# TD Windows CLI takes this ONE script path; the template consumes argv.
set td_direct_caller_dir [file dirname [file normalize [info script]]]
set formal_margin_guard_script [file join $td_direct_caller_dir validation guard_formal_setup_guidance_v2.py]
set argv [list [file join $td_direct_caller_dir imx415_pcie_4k.al] [file join $td_direct_caller_dir build_direct_config.tcl]]
source [file join $td_direct_caller_dir td_build_direct.tcl]
