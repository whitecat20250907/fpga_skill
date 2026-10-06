# Sole positional argument to td_commands_prompt.exe; do not add -tcl.
# Inert until the root-owned launcher supplies a verified CURRENT checkpoint.
# SWUG105 4.9.9: import Optimize Placement/Optimize Routing DB, then report.
# There is deliberately no synthesis/place/route/bitgen/export/set_property.
proc mtbf_mark {phase} {
    set f [open [file join $::env(MTBF_OUTPUT) stage.txt] w]
    puts $f $phase
    close $f
    puts "ISOLATED_MTBF_STAGE=$phase"
    flush stdout
}
if {[catch {
    foreach key {MTBF_CHECKPOINT MTBF_OUTPUT MTBF_CHECKPOINT_STAGE MTBF_BUILD_ID} {
        if {![info exists ::env($key)] || $::env($key) eq ""} {
            error "Missing launcher environment variable $key"
        }
    }
    if {![file isfile $::env(MTBF_CHECKPOINT)]} {error "Missing checkpoint"}
    if {![file isdirectory $::env(MTBF_OUTPUT)]} {error "Missing fresh diagnostic directory"}
    if {$::env(MTBF_CHECKPOINT_STAGE) ni {pr place}} {error "Checkpoint stage must be pr or place"}
    set script_dir [file dirname [file normalize [info script]]]
    source [file join $script_dir cdc_attribute_audit.tcl]
    cd $::env(MTBF_OUTPUT)
    puts "ISOLATED_MTBF_BUILD_ID=$::env(MTBF_BUILD_ID)"
    puts "ISOLATED_MTBF_CHECKPOINT=$::env(MTBF_CHECKPOINT)"
    puts "ISOLATED_MTBF_CHECKPOINT_STAGE=$::env(MTBF_CHECKPOINT_STAGE)"
    mtbf_mark import_device
    import_device ph1_90.db -package PH1A90SEG324 -speed 2
    mtbf_mark import_checkpoint
    import_db $::env(MTBF_CHECKPOINT)
    mtbf_mark audit_imported_attributes
    cdc_attribute_audit imported $::env(MTBF_OUTPUT)
    # These switches expose retained original metadata. They cannot repair
    # missing original placement, constraints, clocks or RTL synchronizers.
    # The launcher requires timing-qualified same-build outputs; the original
    # flow must have used both switches BEFORE placement (review its log).
    set_param rtl directive:async_reg on
    set_param place async_reg on
    mtbf_mark audit_visible_attributes
    set cells [cdc_attribute_audit visible $::env(MTBF_OUTPUT)]
    if {[llength $cells] == 0} {error "No retained attributed physical synchronizers; MTBF unresolved"}
    mtbf_mark report_mtbf_minimal
    # First investigation excludes optional -cdc_sink_pin, which was present
    # at the earlier native crash. This is a diagnostic, not a proven fix.
    report_mtbf -file [file join $::env(MTBF_OUTPUT) mtbf.rpt]
    if {![file isfile [file join $::env(MTBF_OUTPUT) mtbf.rpt]] ||
        [file size [file join $::env(MTBF_OUTPUT) mtbf.rpt]] == 0} {
        error "MTBF command produced no report; never treat this as PASS"
    }
    mtbf_mark complete_report_requires_review
    puts "ISOLATED_MTBF_REPORT_GENERATED_REQUIRES_REVIEW"
} error_message]} {
    puts stderr "ISOLATED_MTBF_FAILED=$error_message"
    if {[info exists ::errorInfo]} {puts stderr $::errorInfo}
    exit 1
}
exit 0
