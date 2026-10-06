# Read-only TD 6.2.2 audit helper; never sourced/run by this file itself.
# Source from a root-owned fresh TD flow after elaboration/RTL/gate/place/route,
# then call cdc_attribute_audit $phase $output_directory.
# SWUG105 PDF pp.48,58-59: get_cells/filter and get/report_property.
# Uses -verbose intentionally: several TD collection commands suppress their
# returned collection outside a constraint context without this option.
# This records properties; it never marks extra flops, changes constraints,
# changes placement options, or declares MTBF/CDC safe on a nonempty count.
proc cdc_attribute_audit {phase output_directory} {
    if {![file isdirectory $output_directory]} {
        error "CDC attribute audit requires an existing output directory"
    }
    if {![regexp {^[A-Za-z0-9_]+$} $phase]} {
        error "CDC attribute phase must be a plain diagnostic name"
    }
    set output [file join $output_directory cdc_attributes_${phase}.txt]
    if {[file exists $output]} {
        error "Refusing to overwrite CDC audit evidence: $output"
    }
    set cells [get_cells -filter {ASYNC_REG == true} -verbose]
    set f [open $output w]
    puts $f "phase=$phase"
    puts $f "async_reg_count=[llength $cells]"
    foreach cell $cells {
        puts $f "cell=$cell async_reg=[get_property ASYNC_REG $cell]"
    }
    close $f
    puts "CDC_ATTRIBUTE_AUDIT phase=$phase count=[llength $cells] file=$output"
    if {[llength $cells] > 0} {
        # Report all available properties into the enclosing build transcript,
        # including the actual property spelling, type and physical flags.
        report_property [lindex $cells 0]
    } else {
        puts "CDC_ATTRIBUTE_AUDIT_MISSING: zero attributed synchronizer cells; unresolved, never PASS"
    }
    return $cells
}

# Optional strict checker for a root-owned fresh flow. Comparing whole counts
# does not identify equivalent optimizations; examine phase snapshots first.
# Use after the final place/route audit when the intended chain inventory is
# confirmed, not to fabricate properties onto a mismatched imported netlist.
proc cdc_attribute_require_nonzero {cells} {
    if {[llength $cells] == 0} {
        error "CDC attributes are absent: investigate the exact phase that lost them"
    }
}
