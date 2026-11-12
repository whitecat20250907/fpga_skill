    candidate_restore_control_attribute $td_direct_out
    cdc_attribute_audit place $td_direct_out
    update_timing -mode manhattan
    report_timing_status -file ${td_direct_name}_place.ts
    report_timing_summary -file ${td_direct_name}_place.timing
    report_area -io_info -file ${td_direct_name}_phy.area
    flow_status -file place_flow.status
    report_clock_utilization -file place_clock_utilization.txt
    export_db ${td_direct_name}_place.db

    td_direct_mark route
    if {$td_direct_fix_hold_high} {set_param route fix_hold high}
    route
    cdc_attribute_audit route $td_direct_out
    if {$td_direct_fix_hold_high} {
        td_direct_mark fix_hold_high
        fix_hold
    }
    td_direct_mark formal_complete_source_closure
    export_db ${td_direct_name}_before_formal_closure.db
    source [file join $td_direct_out formal_forwarded_clock_closure.tcl]
    cdc_attribute_audit formal_closure $td_direct_out
    td_direct_mark strict_final_reports
    report_area -io_info -file ${td_direct_name}_phy.area
    update_timing -mode final
    report_timing_status -file ${td_direct_name}_phy.ts
    report_timing_summary -file ${td_direct_name}_pr.timing
    report_timing_exception -file ${td_direct_name}_exception.timing
    check_timing -verbose -file ${td_direct_name}_chk.timing
    flow_status -file route_flow.status
    report_clock_utilization -file route_clock_utilization.txt
    set td_direct_cdc_status CDC_DEFERRED_TO_ISOLATED_REPORT
    set task_cdc_f [open [file join $td_direct_out cdc.status] w]
    puts $task_cdc_f "status=$td_direct_cdc_status"
    puts $task_cdc_f "Independent native report/CDC analysis still required; no MTBF acceptance inferred."
    close $task_cdc_f
    export_db ${td_direct_name}_pr.db

    set f [open ${td_direct_name}_phy.ts r];set strict_ts [read $f];close $f
    foreach key {SWNS STNS HWNS HTNS} {
        if {![regexp [format {%s:\s*([-+0-9.]+)ns} $key] $strict_ts all value]} {error "Missing strict final STA $key"}
        set strict_metric($key) $value
    }
    if {!($strict_metric(SWNS)>0 && $strict_metric(HWNS)>0 && $strict_metric(STNS)==0 && $strict_metric(HTNS)==0)} {error "Strict final STA failed; own DB retained, no diagnostic bitgen"}
    td_direct_mark bitgen
    # Existing phy run's compress/boot properties remain authoritative.
    bitgen -bit ${td_direct_name}.bit
    setup_debugger -prj $td_direct_name
    export_bitgen_param -file .bitgen_param.f

    td_direct_mark verify_outputs
    foreach td_direct_file [list ${td_direct_name}_place.db ${td_direct_name}_pr.db \
            ${td_direct_name}.bit ${td_direct_name}_phy.ts ${td_direct_name}_pr.timing \
            ${td_direct_name}_chk.timing] {
        td_direct_require [file join $td_direct_out $td_direct_file]
    }
    set td_direct_bit [file join $td_direct_out ${td_direct_name}.bit]
    set td_direct_compressed [file join $td_direct_out ${td_direct_name}_compress.bit]
    if {[file exists $td_direct_compressed]} {
        td_direct_require $td_direct_compressed
        set td_direct_bit $td_direct_compressed
    }
    if {[td_direct_binary $td_direct_input] ne $td_direct_before} {
        error "Source .al changed during build; inspect before accepting outputs"
    }
    set td_direct_timing [td_direct_binary [file join $td_direct_out ${td_direct_name}_phy.ts]]
    if {![regexp {SWNS:\s*([-+0-9.]+)ns} $td_direct_timing all td_direct_swns] ||
            ![regexp {HWNS:\s*([-+0-9.]+)ns} $td_direct_timing all td_direct_hwns]} {
        error "Unrecognized final setup/hold report; validation unresolved"
    }
    puts "DIRECT_BUILD_TIMING_SWNS_NS=$td_direct_swns HWNS_NS=$td_direct_hwns"
    if {$td_direct_swns < 0 || $td_direct_hwns < 0} {
        error "Diagnostic bit generated; final setup/hold failed"
    }
    td_direct_mark complete
    puts "SAME_PLACED_DB_RESUME_COMPLETE=$td_direct_out"
    puts "DIRECT_BUILD_BIT=$td_direct_bit"
    puts "DIRECT_BUILD_CDC_STATUS=$td_direct_cdc_status"
    puts "Review clock coverage, CDC, warnings and live board behavior separately."
