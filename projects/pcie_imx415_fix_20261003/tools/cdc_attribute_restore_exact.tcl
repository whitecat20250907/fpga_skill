# TD 6.2.2 candidate: exact gate inventory validation/restoration after the
# second insert_debugger, BEFORE place. Never invokes TD or changes a design
# merely by being sourced. SWUG105 get_cells -filter NAME == / set_property;
# SWUG106 4.3.4 async_reg is DONT_TOUCH during synthesis when attached in RTL.
# This cannot reconstruct an optimized-away synchronizer or prove CDC/MTBF.

proc cdc_exact_bool {value} {
    return [expr {[string tolower $value] in {1 true yes on}}]
}

proc cdc_exact_gate_inventory {gate_audit expected_count} {
    if {![file isfile $gate_audit]} {error "Missing original gate inventory: $gate_audit"}
    set fh [open $gate_audit r]
    set text [read $fh]
    close $fh
    set phase ""
    set reported -1
    set names {}
    foreach line [split $text \n] {
        set line [string trim $line]
        if {[regexp {^phase=(.*)$} $line -> phase_value]} {set phase $phase_value}
        if {[regexp {^async_reg_count=([0-9]+)$} $line -> count]} {set reported $count}
        if {[regexp {^cell=(.+) async_reg=(.+)$} $line -> name value]} {
            if {![cdc_exact_bool $value]} {error "Original gate entry was not true: $name"}
            # These names are interpolated only into TD's property expression,
            # never eval/Tcl code. Reject quotes/newlines/expression injection.
            if {[regexp {[\s"\\&|=()]} $name]} {error "Unsupported exact cell name: $name"}
            if {[lsearch -exact $names $name] >= 0} {error "Duplicate gate entry: $name"}
            lappend names $name
        }
    }
    if {$phase ne "gate" || $reported != $expected_count || [llength $names] != $expected_count} {
        error "Gate inventory mismatch: phase=$phase reported=$reported parsed=[llength $names] expected=$expected_count"
    }
    return $names
}

proc cdc_exact_validate {gate_audit expected_count output_file} {
    if {[file exists $output_file]} {error "Refusing to overwrite CDC validation evidence: $output_file"}
    set names [cdc_exact_gate_inventory $gate_audit $expected_count]
    set fh [open $output_file w]
    puts $fh "source_gate_inventory=[file normalize $gate_audit]"
    puts $fh "expected_count=$expected_count"
    set objects {}
    set problems {}
    foreach name $names {
        # NAME equality deliberately avoids get_cells glob [] bus indexing.
        # TD's filter parser treats quotes as part of a string value; unlike
        # Vivado, the documented equality value must be unquoted here.
        set matches [get_cells -filter [format {NAME == %s} $name] -verbose]
        if {[llength $matches] != 1} {
            puts $fh "missing_or_ambiguous name=$name matches=[llength $matches]"
            lappend problems $name
            continue
        }
        set object [lindex $matches 0]
        set real_name [get_property NAME $object]
        set class [get_property CLASS $object]
        set ref_name [get_property REF_NAME $object]
        set type [get_property TYPE $object]
        set async [get_property ASYNC_REG $object]
        puts $fh "name=$name object=$object NAME=$real_name CLASS=$class REF_NAME=$ref_name TYPE=$type ASYNC_REG=$async"
        # This helper is for this frozen gate netlist immediately before place;
        # its original sequentials are AL_MAP_SEQ, not arbitrary/debug cells.
        if {$real_name ne $name || $class ne "cell" || $ref_name ne "AL_MAP_SEQ" || $type ne "AL_MAP_SEQ"} {
            lappend problems $name
            continue
        }
        lappend objects $object
    }
    puts $fh "validated_count=[llength $objects]"
    puts $fh "problem_count=[llength $problems]"
    close $fh
    if {[llength $problems] || [llength $objects] != $expected_count} {
        error "CDC exact-object validation failed; no properties changed. See $output_file"
    }
    return [list $names $objects]
}

# Preferred path: real TD OOC trials show the original properties can become
# visible again solely by re-enabling the documented global parameters. Do
# not call set_property when this exact original set already survives.
proc cdc_exact_reenable_after_debugger {gate_audit expected_count output_directory} {
    if {![file isdirectory $output_directory]} {error "CDC verification requires an existing fresh output directory"}
    set_param rtl directive:async_reg on
    set_param place async_reg on
    set validated [cdc_exact_validate $gate_audit $expected_count [file join $output_directory cdc_exact_after_reenable.txt]]
    set names [lindex $validated 0]
    set objects [lindex $validated 1]
    foreach object $objects {
        if {![cdc_exact_bool [get_property ASYNC_REG $object]]} {
            error "Original attribute remains missing after re-enabling parameters on $object; no set_property performed"
        }
    }
    set visible [get_cells -filter {ASYNC_REG == true} -verbose]
    set visible_names {}
    foreach object $visible {lappend visible_names [get_property NAME $object]}
    if {[lsort $visible_names] ne [lsort $names]} {
        error "Re-enabled ASYNC_REG set differs from the exact gate inventory; no set_property performed"
    }
    puts "CDC_EXACT_REENABLED=[llength $visible]; original property set verified without setters; placement/MTBF still required"
    return $visible
}

# Explicit fallback only if the root-owned flow has proved a real loss after
# parameter re-enable. Not needed for the independently reproduced OOC case.
proc cdc_exact_restore_after_debugger {gate_audit expected_count output_directory} {
    if {![file isdirectory $output_directory]} {error "CDC restoration requires an existing fresh output directory"}
    set validated [cdc_exact_validate $gate_audit $expected_count [file join $output_directory cdc_exact_before_restore.txt]]
    set names [lindex $validated 0]
    set objects [lindex $validated 1]

    # Check every currently attributed object before any mutation: restoration
    # must not conceal a mismatched main model or mark unrelated watcher cells.
    set before [get_cells -filter {ASYNC_REG == true} -verbose]
    foreach object $before {
        set name [get_property NAME $object]
        if {[lsearch -exact $names $name] < 0} {
            error "Unexpected attributed cell outside gate inventory: $name; no properties changed"
        }
    }

    set_param rtl directive:async_reg on
    foreach object $objects {
        set_property ASYNC_REG true [list $object]
        if {![cdc_exact_bool [get_property ASYNC_REG $object]]} {
            error "TD did not retain ASYNC_REG after setting exact object $object; discard this design/checkpoint"
        }
    }
    set after [get_cells -filter {ASYNC_REG == true} -verbose]
    set after_names {}
    foreach object $after {lappend after_names [get_property NAME $object]}
    if {[lsort $after_names] ne [lsort $names]} {
        error "CDC exact restoration set mismatch; discard this design/checkpoint"
    }
    set_param place async_reg on
    set fh [open [file join $output_directory cdc_exact_after_restore.txt] w]
    puts $fh "status=EXACT_PROPERTIES_RESTORED_NOT_CDC_OR_MTBF_PASS"
    puts $fh "async_reg_count=[llength $after]"
    foreach name $after_names {puts $fh "cell=$name async_reg=1"}
    close $fh
    puts "CDC_EXACT_RESTORED=[llength $after]; original gate DONT_TOUCH preservation retained, placement/report still required"
    return $after
}
