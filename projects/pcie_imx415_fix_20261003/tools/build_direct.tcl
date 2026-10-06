# Full source rebuild for TD 6.2.2 Release_2026.1_SP2.
# Run by supplying THIS SCRIPT as the only argument to td_commands_prompt.exe.
# No launch_runs/wait_run, imported old checkpoint, or fabricated run marker.
# Existing .al file sets/IP/global includes/attributes and run properties remain
# the authority. All newly generated outputs go to a never-before-used directory.

set task_script_dir [file dirname [file normalize [info script]]]
set task_root [file dirname $task_script_dir]
set task_fpga [file join $task_root fpga]
set task_project [file join $task_fpga imx415_pcie_4k.al]
set task_source_project $task_project
set task_name imx415_pcie_4k
set task_top imx415_pcie_top
set task_started [clock seconds]
set task_stamp [clock format $task_started -format %Y%m%d_%H%M%S]
set task_out [file join $task_root evidence direct_build_${task_stamp}_[pid]]
set task_stage initialize
source [file join $task_script_dir cdc_attribute_audit.tcl]
source [file join $task_script_dir cdc_attribute_restore_exact.tcl]

proc task_read_binary {path} {
    set f [open $path rb]
    set data [read $f]
    close $f
    return $data
}
proc task_mark {stage} {
    global task_out task_stage
    set task_stage $stage
    puts "DIRECT_BUILD_STAGE=$stage"
    set f [open [file join $task_out build.stage] w]
    puts $f $stage
    close $f
}
proc task_require_output {path} {
    global task_started
    if {![file isfile $path] || [file size $path] == 0} {
        error "Expected output is missing or empty: $path"
    }
    if {[file mtime $path] < $task_started} {
        error "Output predates this direct build: $path"
    }
}

if {[catch {
    if {![file isfile $task_project]} {error "Missing current source project: $task_project"}
    if {[file exists $task_out]} {error "Refusing an existing output directory: $task_out"}
    set task_project_before [task_read_binary $task_project]
    file mkdir $task_out
    # ROM/config paths embedded in primitives resolve against process cwd;
    # IP XML paths also need the project cwd. Stage the complete source tree
    # under this fresh output directory instead of changing cwd mid-import.
    # Never copy old *_Runs or import an old physical checkpoint.
    file copy [file join $task_fpga uisrc] [file join $task_out uisrc]
    file copy [file join $task_fpga al_ip] [file join $task_out al_ip]
    set task_project [file join $task_out [file tail $task_source_project]]
    file copy $task_source_project $task_project
    set task_build_fpga $task_out
    puts "DIRECT_BUILD_OUTPUT=$task_out"
    puts "DIRECT_BUILD_PROJECT=$task_project"
    set task_meta [open [file join $task_out build.inputs] w]
    puts $task_meta "project=$task_project"
    puts $task_meta "source_project=$task_source_project"
    puts $task_meta "top=$task_top"
    puts $task_meta "device=PH1A90SEG324 speed=2"
    puts $task_meta "start_epoch=$task_started"
    puts $task_meta "mode=fresh_source_single_run"
    close $task_meta

    # Official single-run API, also used in TD/scripts/DefaultFlow.tcl prepare.
    # Opening the CURRENT .al retains all 138 analyzed source dependencies;
    # never open the stale phy_1/*.prj or read an old gate.db.
    cd $task_out
    task_mark analyze_current_project
    import_device ph1_90.db -package PH1A90SEG324 -speed 2
    open_project $task_project -single_run
    load_run_param -run syn_1
    # SWUG105 page 102: TD 6.2.2 async_reg is off unless these are enabled.
    # In single-run/direct mode the -run option is not needed here.
    set_param rtl directive:async_reg on
    report_param
    cd $task_out

    task_mark elaborate
    elaborate -top $task_top
    # Same IP constraints and model association as generated settings.cfg.
    read_adc -ip al_pcie_ip -file [file join $task_build_fpga al_ip PH1_LOGIC_PCIE.adc]
    read_sdc -ip al_pcie_ip [file join $task_build_fpga al_ip PH1_LOGIC_PCIE.sdc]
    export_db ${task_name}_elaborate.db

    task_mark optimize_rtl
    read_adc [file join $task_build_fpga uisrc 04_pin imx415_pcie.adc]
    read_sdc [file join $task_build_fpga uisrc 04_pin imx415_pcie.sdc]
    insert_debugger
    optimize_rtl
    cdc_attribute_audit rtl $task_out
    report_area -file ${task_name}_rtl.area
    export_db ${task_name}_rtl.db

    task_mark optimize_gate
    # The existing synthesis run's area option is -packarea.
    optimize_gate -packarea ${task_name}_gate.area
    legalize_phy_inst
    cdc_attribute_audit gate $task_out
    update_timing
    report_timing_status -file ${task_name}_gate.ts
    report_timing_summary -file ${task_name}_gate.timing
    flow_status -file gate_flow.status
    export_db ${task_name}_gate.db

    task_mark load_physical_parameters
    # Preserve Default_PhysicalDesign_Strategy and all current phy_1 properties,
    # including flow bad_qor_check off and bitgen compress on. Then add only the
    # documented synchronizer-placement option required for async_reg/MTBF.
    load_run_param -run phy_1
    cdc_attribute_audit phy_parameters $task_out
    set_param rtl directive:async_reg on
    set_param place async_reg on
    # The 24MHz -> generated 100kHz I2C clock has real hold skew.
    # Normal hold repair skips paths worse than -1ns; high is TD's documented
    # hold-repair setting. This changes routing, not timing constraints.
    set_param route fix_hold high
    report_param

    task_mark place
    insert_debugger
    cdc_attribute_audit debugger $task_out
    # Debugger may run a separate OOC flow and load another strategy.
    set_param rtl directive:async_reg on
    set_param place async_reg on
    set_param route fix_hold high
    set task_gate_inventory [file join $task_out cdc_attributes_gate.txt]
    set task_f [open $task_gate_inventory r]
    set task_inventory_contents [read $task_f]
    close $task_f
    if {![regexp {async_reg_count=([0-9]+)} $task_inventory_contents all task_async_count]} {
        error "Missing exact gate synchronizer inventory"
    }
    cdc_exact_reenable_after_debugger $task_gate_inventory $task_async_count $task_out
    place
    cdc_attribute_audit place $task_out
    update_timing -mode manhattan
    report_timing_status -file ${task_name}_place.ts
    report_timing_summary -file ${task_name}_place.timing
    report_area -io_info -file ${task_name}_phy.area
    flow_status -file place_flow.status
    report_clock_utilization -file place_clock_utilization.txt
    export_db ${task_name}_place.db

    task_mark route
    route
    cdc_attribute_audit route $task_out
    report_area -io_info -file ${task_name}_phy.area
    update_timing -mode final
    report_timing_status -file ${task_name}_phy.ts
    report_timing_summary -file ${task_name}_pr.timing
    report_timing_exception -file ${task_name}_exception.timing
    check_timing -verbose -file ${task_name}_chk.timing
    flow_status -file route_flow.status
    report_clock_utilization -file route_clock_utilization.txt
    # Supported for PH1A with the enabled RTL/place async_reg parameters.
    # TD's native report_mtbf crashed after a completed route in build05.
    # Preserve the routed DB and timing-qualified bit before investigating
    # MTBF in an isolated process; Tcl catch cannot recover a native crash.
    set task_cdc_status MTBF_PENDING_ISOLATED_REPORT
    export_db ${task_name}_pr.db

    task_mark bitgen
    bitgen -bit ${task_name}.bit -compress
    setup_debugger -prj $task_name
    export_bitgen_param -file .bitgen_param.f

    task_mark verify_outputs
    foreach task_file [list ${task_name}_elaborate.db ${task_name}_rtl.db \
            ${task_name}_gate.db ${task_name}_place.db ${task_name}_pr.db \
            ${task_name}.bit ${task_name}_compress.bit ${task_name}_phy.ts \
            ${task_name}_pr.timing ${task_name}_chk.timing] {
        task_require_output [file join $task_out $task_file]
    }
    if {[task_read_binary $task_source_project] ne $task_project_before} {
        error "The source .al changed during this build; inspect before accepting outputs"
    }
    set task_timing [task_read_binary [file join $task_out ${task_name}_phy.ts]]
    if {![regexp {SWNS:\s*([-+0-9.]+)ns} $task_timing all task_swns] ||
            ![regexp {HWNS:\s*([-+0-9.]+)ns} $task_timing all task_hwns]} {
        error "Unable to parse final setup/hold report; physical validation is unresolved"
    }
    puts "DIRECT_BUILD_TIMING_SWNS_NS=$task_swns HWNS_NS=$task_hwns"
    if {$task_swns < 0 || $task_hwns < 0} {
        error "Diagnostic bit generated, but final setup/hold timing did not pass"
    }
    task_mark complete
    puts "DIRECT_BUILD_COMPLETE=$task_out"
    puts "DIRECT_BUILD_BIT=[file join $task_out ${task_name}_compress.bit]"
    puts "DIRECT_BUILD_CDC_STATUS=$task_cdc_status"
    puts "Check detailed clock coverage/CDC/warnings before hardware acceptance."
} task_error]} {
    puts stderr "DIRECT_BUILD_FAILED_STAGE=$task_stage"
    puts stderr "DIRECT_BUILD_OUTPUT=$task_out"
    puts stderr $task_error
    if {[info exists ::errorInfo]} {puts stderr $::errorInfo}
    exit 1
}
exit 0
