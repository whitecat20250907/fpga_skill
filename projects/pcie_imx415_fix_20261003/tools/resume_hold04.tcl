# Resume ONLY this freshly rebuilt 04 routed database; no source/SDC edits.
# Invoke td_commands_prompt.exe with this Tcl file as its only argument.
# Requires python on the same PATH solely for read-only SHA-256 checks.
set task_script_dir [file dirname [file normalize [info script]]]
set task_root [file dirname $task_script_dir]
set task_fpga [file join $task_root fpga]
set task_checkpoint_dir [file join $task_root evidence direct_build_20261004_224133_26828]
set task_checkpoint [file join $task_checkpoint_dir imx415_pcie_4k_pr.db]
set task_checkpoint_expected 9e6026891ce7053996017ee2484cb9f2967c6173b09b9ff672bc421c7dd7df90
set task_source_expected bbfdab091401733f3b3ab645d1cb4ff95561b406f6b08984ee2a051c90549196
set task_name imx415_pcie_4k_hold04
set task_started [clock seconds]
set task_stamp [clock format $task_started -format %Y%m%d_%H%M%S]
set task_out [file join $task_root evidence resume_hold04_${task_stamp}_[pid]]
set task_stage initialize

proc task_read_binary {path} {
    set f [open $path rb]
    set value [read $f]
    close $f
    return $value
}
proc task_mark {stage} {
    global task_out task_stage
    set task_stage $stage
    puts "RESUME_HOLD04_STAGE=$stage"
    set f [open [file join $task_out resume.stage] w]
    puts $f $stage
    close $f
}
proc task_require_output {path} {
    global task_started
    if {![file isfile $path] || [file size $path] == 0} {
        error "Required new output missing or empty: $path"
    }
    if {[file mtime $path] < $task_started} {
        error "Output predates this checkpoint-resume invocation: $path"
    }
}
proc task_fingerprints {} {
    global task_fpga task_checkpoint
    # All current uisrc/al_ip dependencies plus the .al, not generated run files.
    # Excluding historical backup/ copies is the only source filter.
    return [exec python -c {
import hashlib,sys
from pathlib import Path
fpga=Path(sys.argv[1]);checkpoint=Path(sys.argv[2])
files={fpga/'imx415_pcie_4k.al'}
for child in ('uisrc','al_ip'):
    files.update(p for p in (fpga/child).rglob('*') if p.is_file() and 'backup' not in p.parts)
h=hashlib.sha256()
for p in sorted(files,key=lambda p:p.relative_to(fpga).as_posix()):
    h.update(p.relative_to(fpga).as_posix().encode('utf-8')+b'\0'+hashlib.sha256(p.read_bytes()).digest())
print(h.hexdigest(),hashlib.sha256(checkpoint.read_bytes()).hexdigest(),len(files))
} $task_fpga $task_checkpoint]
}
proc task_verify_inputs {label} {
    global task_source_expected task_checkpoint_expected task_out
    lassign [task_fingerprints] task_source_sha task_checkpoint_sha task_source_count
    set f [open [file join $task_out ${label}.fingerprints] w]
    puts $f "source_sha256=$task_source_sha"
    puts $f "source_files=$task_source_count"
    puts $f "checkpoint_sha256=$task_checkpoint_sha"
    close $f
    if {$task_source_sha ne $task_source_expected} {
        error "Current source changed from the approved 04 candidate; fresh rebuild required: $task_source_sha"
    }
    if {$task_checkpoint_sha ne $task_checkpoint_expected} {
        error "04 fresh checkpoint changed; refusing stale/different database: $task_checkpoint_sha"
    }
}

if {[catch {
    if {![file isfile $task_checkpoint]} {error "Missing fresh checkpoint: $task_checkpoint"}
    if {[file exists $task_out]} {error "Refusing existing output directory: $task_out"}
    file mkdir $task_out
    puts "RESUME_HOLD04_OUTPUT=$task_out"
    task_verify_inputs before
    set task_meta [open [file join $task_out resume.inputs] w]
    puts $task_meta "checkpoint=$task_checkpoint"
    puts $task_meta "checkpoint_sha256=$task_checkpoint_expected"
    puts $task_meta "source_sha256=$task_source_expected"
    puts $task_meta "device=PH1A90SEG324 speed=2"
    puts $task_meta "mode=resume_fresh_04_route_checkpoint_fix_hold_high"
    puts $task_meta "start_epoch=$task_started"
    puts $task_meta "mtbf_status=independent_unresolved_physical_async_reg_attribute_investigation"
    close $task_meta
    set task_mtbf [open [file join $task_out mtbf.status] w]
    puts $task_mtbf "UNRESOLVED: physical async_reg attributes/MTBF coverage are under independent investigation."
    puts $task_mtbf "MTBF file presence is neither required nor treated as proof of CDC safety in this hold-only resume."
    close $task_mtbf
    # Keep the original checkpoint/debug databases intact. The copied cw tree
    # supports a later debugger setup without writing back into the source run.
    if {[file isdirectory [file join $task_checkpoint_dir cw]]} {
        file copy [file join $task_checkpoint_dir cw] [file join $task_out cw]
    }
    cd $task_out
    task_mark import_fresh_checkpoint
    import_device ph1_90.db -package PH1A90SEG324 -speed 2
    import_db $task_checkpoint
    task_mark fix_hold_high
    set_param route fix_hold high
    set_param bitgen compress on
    report_param
    fix_hold

    task_mark final_reports
    update_timing -mode final
    report_timing_status -file ${task_name}_phy.ts
    report_timing_summary -file ${task_name}_pr.timing
    report_timing_exception -file ${task_name}_exception.timing
    check_timing -verbose -file ${task_name}_chk.timing
    report_area -io_info -file ${task_name}_phy.area
    flow_status -file hold_flow.status
    report_clock_utilization -file hold_clock_utilization.txt
    report_qor -step route -file hold.qor
    export_db ${task_name}_pr.db
    foreach task_file [list ${task_name}_phy.ts ${task_name}_pr.timing \
            ${task_name}_exception.timing ${task_name}_chk.timing \
            ${task_name}_phy.area hold_flow.status hold_clock_utilization.txt \
            hold.qor ${task_name}_pr.db] {
        task_require_output [file join $task_out $task_file]
    }
    set task_timing [task_read_binary [file join $task_out ${task_name}_phy.ts]]
    foreach task_metric {SWNS HWNS STNS HTNS} {
        set task_pattern [format {%s:\s*([-+0-9.]+)ns} $task_metric]
        if {![regexp $task_pattern $task_timing all task_value]} {
            error "Cannot parse final $task_metric; timing acceptance unresolved"
        }
        puts "RESUME_HOLD04_TIMING_${task_metric}_NS=$task_value"
        if {$task_value < 0} {error "Final $task_metric is negative ($task_value ns); bit generation refused"}
    }
    task_verify_inputs after_hold

    task_mark bitgen_compressed
    # Explicit option: load_run_param did not preserve compression in direct04.
    bitgen -bit ${task_name}.bit -compress
    export_bitgen_param -file .bitgen_param.f
    foreach task_file [list ${task_name}.bit ${task_name}_compress.bit .bitgen_param.f] {
        task_require_output [file join $task_out $task_file]
    }
    # Debugger setup is separate from routed setup/hold acceptance and bitgen.
    if {[catch {setup_debugger -prj $task_name} task_debug_error]} {
        set f [open [file join $task_out debugger.status] w]
        puts $f "UNRESOLVED: $task_debug_error"
        close $f
        puts "RESUME_HOLD04_DEBUGGER_WARNING=$task_debug_error"
    }
    task_verify_inputs after_bitgen
    task_mark complete
    puts "RESUME_HOLD04_COMPLETE=$task_out"
    puts "RESUME_HOLD04_BIT=[file join $task_out ${task_name}_compress.bit]"
    puts "RESUME_HOLD04_MTBF=INDEPENDENT_UNRESOLVED"
} task_error]} {
    puts stderr "RESUME_HOLD04_FAILED_STAGE=$task_stage"
    puts stderr "RESUME_HOLD04_OUTPUT=$task_out"
    puts stderr $task_error
    if {[info exists ::errorInfo]} {puts stderr $::errorInfo}
    if {[file isdirectory $task_out]} {
        set f [open [file join $task_out resume.failure] w]
        puts $f "stage=$task_stage"
        puts $f $task_error
        close $f
    }
    exit 1
}
exit 0
