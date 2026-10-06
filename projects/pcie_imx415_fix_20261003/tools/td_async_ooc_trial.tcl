# Independent tiny synthesis/OOC/attribute test only; no place/route/bitgen.
set trial_tools [file dirname [file normalize [info script]]]
set trial_root [file dirname $trial_tools]
set trial_out [file join $trial_root evidence td_async_ooc_trial_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[pid]]
if {[file exists $trial_out]} {error "Refusing existing trial output"}
file mkdir $trial_out
cd $trial_out
puts "ASYNC_OOC_TRIAL_OUTPUT=$trial_out"
source [file join $trial_tools cdc_attribute_audit.tcl]
source [file join $trial_tools cdc_attribute_restore_exact.tcl]
if {[catch {
    import_device ph1_90.db -package PH1A90SEG324 -speed 2
    set_param rtl directive:async_reg on
    file copy [file join $trial_tools td_async_ooc_trial.v] td_async_ooc_trial.v
    analyze -file td_async_ooc_trial.v
    elaborate -top td_async_ooc_trial
    insert_debugger
    optimize_rtl
    cdc_attribute_audit rtl $trial_out
    optimize_gate -packarea trial_gate.area
    legalize_phy_inst
    set trial_gate_cells [cdc_attribute_audit gate $trial_out]
    if {[llength $trial_gate_cells] != 3} {error "Expected three original RTL synchronizer cells"}
    export_db trial_gate.db
    # Exercise exact NAME comparison, including literal bus brackets, before
    # attributing the subsequent OOC result to anything in the helper.
    cdc_exact_validate [file join $trial_out cdc_attributes_gate.txt] 3 [file join $trial_out exact_before_debugger.txt]
    insert_debugger
    set trial_after [cdc_attribute_audit debugger $trial_out]
    puts "ASYNC_OOC_TRIAL_POST_DEBUG_COUNT=[llength $trial_after]"
    puts "TD_CURRENT_COMMANDS=[lsort [info commands current*]]"
    puts "TD_MODEL_COMMANDS=[lsort [info commands *model*]]"
    set_param place async_reg on
    set trial_place_only [cdc_attribute_audit reenable_place_only $trial_out]
    puts "ASYNC_OOC_TRIAL_AFTER_PLACE_ONLY_COUNT=[llength $trial_place_only]"
    set_param rtl directive:async_reg on
    set trial_reenable [cdc_attribute_audit reenable_parameters $trial_out]
    puts "ASYNC_OOC_TRIAL_AFTER_PARAMETER_REENABLE_COUNT=[llength $trial_reenable]"
    cdc_exact_reenable_after_debugger [file join $trial_out cdc_attributes_gate.txt] 3 $trial_out
    cdc_exact_restore_after_debugger [file join $trial_out cdc_attributes_gate.txt] 3 $trial_out
    cdc_attribute_audit restored $trial_out
    export_db trial_restored.db
    puts "PASS_ASYNC_OOC_TRIAL_PROPERTIES_ONLY"
} trial_error]} {
    puts stderr "FAIL_ASYNC_OOC_TRIAL=$trial_error"
    if {[info exists ::errorInfo]} {puts stderr $::errorInfo}
    exit 1
}
exit 0
