# Small actual-pin physical trial, no debugger/bitgen/board operation.
# Every path is task-specific PROC LOCAL: native commands can mutate globals.
proc csi09_physical_trial {csi09_trial_dir} {
    set csi09_project_root [file dirname [file dirname $csi09_trial_dir]]
    set csi09_ip_dir [file join $csi09_project_root fpga uisrc 03_ip mipi_csi_2]
    set csi09_output_dir [file join $csi09_trial_dir evidence td_route_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[pid]]
    if {[file exists $csi09_output_dir]} {error "Refusing existing trial output"}
    file mkdir $csi09_output_dir
    cd $csi09_output_dir
    puts "CSI09_TD_OUTPUT=$csi09_output_dir"
    set csi09_bundle_path [file join $csi09_output_dir csi09_bundle.v]
    set csi09_bundle_fd [open $csi09_bundle_path w]
    foreach csi09_file {csi_rx_phy.v csi_rx_hs_data_phy.v rx_clk_gen.v td_local09_top.v} {
        set csi09_src_path [file join $csi09_trial_dir $csi09_file]
        if {![file isfile $csi09_src_path]} {error "Missing candidate: $csi09_src_path"}
        puts $csi09_bundle_fd "`include \"$csi09_src_path\""
    }
    foreach csi09_file {csi_rx_clock_det.v csi_rx_byte_align.v auto_delay_ctl.v} {
        set csi09_src_path [file join $csi09_ip_dir $csi09_file]
        if {![file isfile $csi09_src_path]} {error "Missing dependency: $csi09_src_path"}
        puts $csi09_bundle_fd "`include \"$csi09_src_path\""
    }
    close $csi09_bundle_fd
    import_device ph1_90.db -package PH1A90SEG324 -speed 2
    set_param rtl directive:async_reg on
    set csi09_cmd [list analyze -file $csi09_bundle_path]
    puts "CSI09_CMD=$csi09_cmd"
    eval $csi09_cmd
    elaborate -top td_local09_top
    set csi09_adc_path [file join $csi09_trial_dir td_local09.adc]
    set csi09_sdc_path [file join $csi09_trial_dir td_local09.sdc]
    foreach csi09_path [list $csi09_adc_path $csi09_sdc_path] {
        if {![file isfile $csi09_path] || [file size $csi09_path]==0} {error "Missing constraint: $csi09_path"}
    }
    # Positional-file APIs match the verified project flow. Never execute an
    # empty native file argument and continue as if the constraints were read.
    set csi09_cmd [list read_adc $csi09_adc_path]
    puts "CSI09_CMD=$csi09_cmd"
    eval $csi09_cmd
    set csi09_cmd [list read_sdc $csi09_sdc_path]
    puts "CSI09_CMD=$csi09_cmd"
    eval $csi09_cmd
    optimize_rtl
    optimize_gate -packarea csi09_gate.area
    legalize_phy_inst
    export_db csi09_gate.db
    set_param rtl directive:async_reg on
    set_param place async_reg on
    set_param route fix_hold high
    set_param flow bad_qor_check off
    puts "CSI09_STAGE=place"
    place
    update_timing -mode manhattan
    report_timing_summary -file csi09_place.timing
    report_area -io_info -file csi09_place.area
    export_db csi09_place.db
    puts "CSI09_STAGE=route"
    route
    update_timing -mode final
    report_timing_status -file csi09_final.ts
    report_timing_summary -file csi09_final.timing
    report_timing_exception -file csi09_exceptions.timing
    check_timing -verbose -file csi09_check.timing
    report_area -io_info -file csi09_route.area
    report_clock_utilization -file csi09_clocks.txt
    export_db csi09_route.db
    puts "CSI09_ROUTE_COMPLETE_NO_BITGEN=$csi09_output_dir"
    set csi09_ts_fd [open [file join $csi09_output_dir csi09_final.ts] r]
    set csi09_ts_text [read $csi09_ts_fd]
    close $csi09_ts_fd
    if {![regexp {SWNS:\s*([-+0-9.]+)ns} $csi09_ts_text all csi09_setup] ||
        ![regexp {HWNS:\s*([-+0-9.]+)ns} $csi09_ts_text all csi09_hold]} {error "Cannot parse final timing"}
    puts "CSI09_FINAL_SETUP_NS=$csi09_setup HOLD_NS=$csi09_hold"
    if {$csi09_setup<0 || $csi09_hold<0} {error "Tiny physical timing failed; do not integrate/download"}
    # Official post-route exports. These files must belong to this same routed
    # DB; exported files are not themselves a successful SDF simulation.
    set csi09_sdf_path [file join $csi09_output_dir csi09_phy_sim.sdf]
    set csi09_v_path [file join $csi09_output_dir csi09_phy_sim.v]
    set csi09_cmd [list write_sdf -check_corner SLOW_FAST -file $csi09_sdf_path]
    puts "CSI09_CMD=$csi09_cmd"
    eval $csi09_cmd
    set csi09_cmd [list write_verilog -sdf $csi09_sdf_path $csi09_v_path]
    puts "CSI09_CMD=$csi09_cmd"
    eval $csi09_cmd
    foreach csi09_path [list $csi09_sdf_path $csi09_v_path] {
        if {![file isfile $csi09_path] || [file size $csi09_path]==0} {error "Missing matched SDF/netlist export: $csi09_path"}
    }
    puts "CSI09_MATCHED_ROUTE_EXPORTS_COMPLETE=$csi09_output_dir"
}
set csi09_script_dir [file dirname [file normalize [info script]]]
if {[catch {csi09_physical_trial $csi09_script_dir} csi09_error]} {
    puts stderr "CSI09_TRIAL_ERROR=$csi09_error"
    puts stderr $::errorInfo
    exit 1
}
exit 0
