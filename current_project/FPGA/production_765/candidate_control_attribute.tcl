proc monitor_native_command {script_path command} {
    set f [open $script_path w];puts $f $command;close $f
    source $script_path
}
set monitor_guard_python {C:/Users/zjh13/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe}
set monitor_guard_script {C:/qianrushifpga/fpga_skill/projects/hmi_fpga_exposure_only_20261101/validation/guard_clock_monitor_cdc_v7.py}
set monitor_guard_parser {C:/qianrushifpga/fpga_skill/projects/hmi_fpga_exposure_only_20261101/validation/review_combined_structure.py}
set candidate_guard_python {C:/Users/zjh13/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe}
set candidate_guard_script {C:/qianrushifpga/fpga_skill/projects/hmi_fpga_exposure_only_20261101/validation/guard_ui_up_source_pair_v2.py}
set candidate_guard_parser {C:/qianrushifpga/fpga_skill/projects/hmi_fpga_exposure_only_20261101/validation/review_combined_structure.py}
# Configure candidate_guard_python, candidate_guard_script and
# candidate_guard_parser to frozen build inputs before sourcing this file.
# Saves the actual placed DB BEFORE any guard can fail. Never bitgens here.
proc candidate_restore_control_attribute {output_directory} {
    global candidate_guard_python candidate_guard_script candidate_guard_parser monitor_guard_python monitor_guard_script monitor_guard_parser
    if {[file normalize [pwd]] ne [file normalize $output_directory]} {error "Guard output directory is not the actual native working directory"}
    export_db pre_source_pair_guard_place.db
    write_verilog
    set netlist [file join $output_directory imx415_pcie_top_out.v]
    set audit [file join $output_directory source_pair_graph]
    exec $candidate_guard_python -X utf8 -B $candidate_guard_script --parser $candidate_guard_parser --netlist $netlist --out $audit
    source [file join $audit approved_cells.tcl]
    if {[llength $candidate_source_pair_cells]<1 || [llength $candidate_source_pair_cells]>2} {error "Unexpected exact source FF cell count"}
    set before {}
    foreach c [get_cells -filter {ASYNC_REG == true} -verbose] {lappend before [get_property NAME $c]}
    set repaired {};set expected $before
    foreach name $candidate_source_pair_cells {
        set objects [get_cells -filter [format {NAME == %s} $name] -verbose]
        if {[llength $objects]!=1} {error "Approved source FF disappeared: $name"}
        set c [lindex $objects 0]
        if {[get_property NAME $c] ne $name} {error "Native object identity mismatch"}
        if {[lsearch -exact $before $name]<0} {
            set_property ASYNC_REG true [list $c]
            lappend expected $name;lappend repaired $name
        }
        if {[get_property ASYNC_REG $c] ni {1 true on}} {error "Source FF property recovery failed"}
    }
    set after {}
    foreach c [get_cells -filter {ASYNC_REG == true} -verbose] {lappend after [get_property NAME $c]}
    if {[lsort $expected] ne [lsort $after]} {error "Unrelated ASYNC_REG properties changed"}
    set f [open [file join $output_directory source_declared_control_attribute.txt] w]
    puts $f "approved_exact_cells=$candidate_source_pair_cells"
    puts $f "repaired_exact_cells=$repaired"
    puts $f "before_count=[llength $before] after_count=[llength $after]"
    close $f
    puts "SOURCE_DECLARED_TWB_CONTROL_ASYNC_COMPLETE=[llength $repaired]"
    set monitor_inventory [file join $output_directory clock_monitor_async_before.txt]
    set mf [open $monitor_inventory w]
    foreach object [get_cells -filter {ASYNC_REG == true} -verbose] {
        puts $mf "cell=[get_property NAME $object] async_reg=[get_property ASYNC_REG $object]"
    }
    close $mf
    # Recover only physically proven FFs declared ASYNC_REG by the new CSR
    # source. Packing may drop the attribute on a third synchronization stage.
    # Baseline projects without the new module skip this additional guard.
    if {[file exists [file join $output_directory uisrc 04_project_twin twin_ui_csr.v]]} {
        set hmi_guard [file join $output_directory validation review_hmi_sync.py]
        exec $monitor_guard_python -X utf8 -B $hmi_guard --netlist $netlist --async-inventory $monitor_inventory --out [file join $output_directory hmi_sync_identified.json] --identify
        source [file join $output_directory hmi_sync_identified.tcl]
        set hmi_before {};set hmi_repaired {}
        foreach object [get_cells -filter {ASYNC_REG == true} -verbose] {lappend hmi_before [get_property NAME $object]}
        foreach name $hmi_declared_async_cells {
            set objects [get_cells -filter [format {NAME == %s} $name] -verbose]
            if {[llength $objects]!=1} {error "HMI declared sync FF missing: $name"}
            set object [lindex $objects 0]
            if {[lsearch -exact $hmi_before $name]<0} {set_property ASYNC_REG true [list $object];lappend hmi_repaired $name}
            if {[get_property ASYNC_REG $object] ni {1 true on}} {error "HMI sync property recovery failed: $name"}
        }
        set hmi_after {};set mf [open [file join $output_directory hmi_async_after.txt] w]
        foreach object [get_cells -filter {ASYNC_REG == true} -verbose] {
            lappend hmi_after [get_property NAME $object]
            puts $mf "cell=[get_property NAME $object] async_reg=[get_property ASYNC_REG $object]"
        }
        close $mf
        if {[lsort $hmi_after] ne [lsort [concat $hmi_before $hmi_repaired]]} {error "Unrelated ASYNC_REG properties changed in HMI recovery"}
        exec $monitor_guard_python -X utf8 -B $hmi_guard --netlist $netlist --async-inventory [file join $output_directory hmi_async_after.txt] --out [file join $output_directory hmi_sync_structure.json]
        puts "HMI_DECLARED_ASYNC_RECOVERED=$hmi_repaired"
    }
    if {[file exists [file join $output_directory uisrc 01_rtl hmi_input_viewer.v]]} {
        source [file join $output_directory viewer_attribute_restore.tcl]
    }
    set gray_guard_out [file join $output_directory ingress_gray_guard]
    exec $monitor_guard_python -X utf8 -B [file join $output_directory validation guard_sampler_distribution.py] --parser $monitor_guard_parser --netlist $netlist --inventory [file join $output_directory hmi_async_after.txt] --out [file join $output_directory sampler_distribution.json]
    exec $monitor_guard_python -X utf8 -B [file join $output_directory validation guard_ingress_gray.py] --parser $monitor_guard_parser --netlist $netlist --inventory [file join $output_directory hmi_async_after.txt] --ingress-rtl [file join $output_directory uisrc 04_project_twin twin_bar_ingress.v] --out $gray_guard_out
    set camera_gray_guard_out [file join $output_directory camera_gray_guard]
    exec $monitor_guard_python -X utf8 -B [file join $output_directory validation guard_camera_gray.py] --parser $monitor_guard_parser --netlist $netlist --inventory [file join $output_directory hmi_async_after.txt] --fifo-rtl [file join $output_directory uisrc 03_ip mipi_csi_2 sfifo.v] --detector-rtl [file join $output_directory uisrc 03_ip mipi_csi_2 csi_rx_clock_det.v] --out $camera_gray_guard_out
    exec $monitor_guard_python -X utf8 -B [file join $output_directory validation merge_gray_guards.py] $gray_guard_out $camera_gray_guard_out
    set monitor_guard_out [file join $output_directory clock_monitor_cdc_guard]
    exec $monitor_guard_python -X utf8 -B $monitor_guard_script --parser $monitor_guard_parser --netlist $netlist --async-inventory $monitor_inventory --out $monitor_guard_out
    set monitor_original_user [file join $output_directory original_user_before_monitor.sdc]
    monitor_native_command [file join $output_directory monitor_native_export_before.tcl] [list export_sdc -file $monitor_original_user]
    set mf [open $monitor_original_user r];set monitor_user_prefix [read $mf];close $mf
    set mf [open [file join $monitor_guard_out approved_monitor_entry.sdc] r];set monitor_only_entries [read $mf];close $mf
    set monitor_registered [file join $output_directory registered_monitor_user.sdc]
    set mf [open $monitor_registered w]
    puts -nonewline $mf $monitor_user_prefix;puts $mf ""
    puts -nonewline $mf $monitor_only_entries
    set gf [open [file join $gray_guard_out gray_skew.sdc] r];set gray_constraints [read $gf];close $gf
    puts $mf "";puts -nonewline $mf $gray_constraints;close $mf
    clear_sdc -user
    monitor_native_command [file join $output_directory monitor_native_read_registered.tcl] [list read_sdc $monitor_registered]
    monitor_native_command [file join $output_directory monitor_native_export_after.tcl] [list export_sdc -file [file join $output_directory monitor_registered_export.sdc]]
    file copy -force [file join $monitor_guard_out approved_monitor_pin_names.txt] [file join $output_directory clock_monitor_constraints_applied.txt]
    puts EXACT_NEW_MONITOR_ASYNC_ENTRY_PINS_FORMALLY_REGISTERED=6
}
