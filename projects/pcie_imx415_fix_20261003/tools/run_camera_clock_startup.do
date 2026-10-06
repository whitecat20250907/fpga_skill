onerror {quit -code 1 -force}
onbreak {
    if {[catch {examine -radix binary /tb_camera_clock_startup/test_done} done] || $done ne "1"} {quit -code 1 -force}
    resume
}
# ModelSim do macros do not update Tcl info script to this filename.
set test_root E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003
if {[info exists ::env(CAMERA_STARTUP_TASK_ROOT)]} {set test_root [file normalize $::env(CAMERA_STARTUP_TASK_ROOT)]}
set stamp [clock format [clock seconds] -format %Y%m%d_%H%M%S]
set out [file join $test_root evidence camera_clock_startup_${stamp}_[pid]]
if {[file exists $out]} {error "Refusing existing simulation output"}
file mkdir $out
cd $out
transcript file [file join $out simulation.log]
puts "CAMERA_CLOCK_STARTUP_OUTPUT=$out"
vmap -c
vlib startup_work
vmap camera_startup startup_work
vlog -work camera_startup -sv [file join $test_root tools camera_clock_startup.v] [file join $test_root tools tb_camera_clock_startup.sv]
vsim -c -voptargs=+acc -onfinish stop camera_startup.tb_camera_clock_startup
run -all
if {[examine -radix binary /tb_camera_clock_startup/test_done] ne "1"} {error "Startup digital selfcheck did not complete"}
puts "PASS CAMERA_CLOCK_STARTUP_DIGITAL_ALL"
puts "No analog PLL/PHY, rail, IO waveform or sensor-clock-source proof; fresh TD/hardware validation remains required."
quit -code 0 -force
