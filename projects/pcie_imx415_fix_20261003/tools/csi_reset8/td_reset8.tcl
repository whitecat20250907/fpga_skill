# Independent current-source synthesis trial: no place, route or bitgen.
set trial [file dirname [file normalize [info script]]]
set task_root [file dirname [file dirname $trial]]
set source_ip [file join $task_root fpga uisrc 03_ip mipi_csi_2]
set out [file join $trial evidence td_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[pid]]
if {[file exists $out]} {error "Refusing existing trial output"}
file mkdir $out
cd $out
puts "RESET8_TD_OUTPUT=$out"
if {[catch {
    import_device ph1_90.db -package PH1A90SEG324 -speed 2
    set_param rtl directive:async_reg on
    # Each analyze invocation replaces the standalone source file set in TD.
    # One include bundle analyzes the whole trial in a single command.
    set bundle [open reset8_bundle.v w]
    foreach f {csi_rx_phy.v csi_rx_hs_data_phy.v td_reset8_top.v} {
        puts $bundle "`include \"[file join $trial $f]\""
    }
    foreach f {rx_clk_gen.v csi_rx_clock_det.v csi_rx_byte_align.v auto_delay_ctl.v} {
        puts $bundle "`include \"[file join $source_ip $f]\""
    }
    close $bundle
    analyze -file reset8_bundle.v
    elaborate -top td_reset8_top
    read_adc -file [file join $trial td_reset8.adc]
    optimize_rtl
    optimize_gate -packarea reset8_gate.area
    legalize_phy_inst
    report_area -file reset8.area
    export_db reset8_gate.db
    set syncs [get_cells -hier -filter {ASYNC_REG == 1}]
    set log [open reset8_async_cells.txt w]
    foreach c $syncs {puts $log [get_property NAME $c]}
    close $log
    puts "RESET8_ASYNC_CELL_COUNT=[llength $syncs]"
    puts "PASS_RESET8_TD_SYNTH_ONLY_NOT_BIT_OR_STA"
} err]} {
    puts stderr "FAIL_RESET8_TD=$err"
    puts stderr $::errorInfo
    exit 1
}
exit 0
