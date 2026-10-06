onerror {quit -code 1 -force}
if {![info exists bar_decode10_old_run]} {set bar_decode10_old_run 0}
onbreak {
    if {$bar_decode10_old_run && [examine -radix binary /tb_bar_decode10/old_failure_detected] eq "1"} {
        puts "EXPECTED_OLD_DECODE_FAILURE_EXIT=3"
        quit -code 3 -force
    }
    if {[examine -radix binary /tb_bar_decode10/test_done] ne "1"} {quit -code 1 -force}
    resume
}
set task_root E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003
set task_source [file join $task_root tools bar_decode10]
set task_mode [expr {$bar_decode10_old_run ? "old_fail" : "new_pass"}]
set task_out [file join $task_source evidence ${task_mode}_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[pid]]
if {[file exists $task_out]} {error "Refusing existing evidence output"}
file mkdir $task_out
cd $task_out
transcript file [file join $task_out simulation.log]
transcript on
puts "BAR_DECODE10_OUTPUT=$task_out"
vmap -c
vlib work
vlog -sv +incdir+$task_source [file join $task_source read_probe.sv] [file join $task_source tb_bar_decode10.sv]
if {$bar_decode10_old_run} {vsim -c -voptargs=+acc -onfinish stop work.tb_bar_decode10 +OLD_FATAL} else {vsim -c -voptargs=+acc -onfinish stop work.tb_bar_decode10}
run -all
if {$bar_decode10_old_run} {error "Old decoder failed to reject golden expectations"}
if {[examine -radix binary /tb_bar_decode10/test_done] ne "1"} {error "Test did not complete"}
puts "PASS_STAGED_BAR_DECODE10_NO_TD_NO_BOARD"
quit -code 0 -force
