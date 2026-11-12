if {[catch {
import_device ph1_90.db -package PH1A90SEG324 -speed 2
import_db {C:/qianrushifpga/fpga_skill/projects/hmi_fpga_exposure_only_20261101/reports/direct_build_20261101_193519_102828/imx415_pcie_4k_before_formal_closure.db}
clear_sdc -user
read_sdc {C:/qianrushifpga/fpga_skill/projects/hmi_optimization_20261027/F04_route748/input_user.sdc}
# Sourced at top level by the complete source entry after its own initial route.
# Native exports use literal local paths: no procedure-variable path boundary.
# No prior checkpoint import, RTL/pin changes, new exception or relaxed budget.
proc formal_read {p} {set f [open $p r];set t [read $f];close $f;return $t}
proc formal_commands {p} {
 set answer {}
 foreach l [split [formal_read $p] \n] {set l [string trim $l];if {$l ne "" && ![string match \#* $l]} {lappend answer $l}}
 return $answer
}
proc formal_metrics {p} {
 set answer {};set t [formal_read $p]
 foreach key {SWNS STNS HWNS HTNS} {
  if {![regexp [format {%s:\s*([-+0-9.]+)ns} $key] $t all v]} {error "Missing actual $key in $p"}
  lappend answer $v
 }
 return $answer
}
proc formal_positive {p} {lassign [formal_metrics $p] s st h ht;return [expr {$s>0 && $h>0 && $st==0 && $ht==0}]}
proc formal_inventory {p} {
 set answer {};set f [open $p w]
 foreach c [get_cells -filter {ASYNC_REG == true} -verbose] {set n [get_property NAME $c];lappend answer $n;puts $f "cell=$n async_reg=[get_property ASYNC_REG $c]"}
 close $f;if {[llength $answer]<128} {error "Incomplete actual synchronizer inventory"};return [lsort $answer]
}
proc formal_reset_cell {} {
 set c [get_cells -filter {NAME == u_cam_video_source/u_mipi_csi_rx/u_csi_rx_phy/sampler_reset_drive_reg_syn_3} -verbose]
 if {[llength $c]!=1} {error "Missing exact common reset FF"};return [lindex $c 0]
}
proc formal_position {} {set c [formal_reset_cell];return [list [get_property PLACED_COL $c] [get_property PLACED_ROW $c] [get_property PLACED_OFFSET $c]]}
proc formal_reset_graph {} {
 set answer {}
 foreach p [get_pins -of [list [formal_reset_cell]] -verbose] {
  set rows {}
  foreach n [get_nets -of [list $p] -verbose] {
   set ends {};foreach e [get_pins -of [list $n] -verbose] {lappend ends [get_property NAME $e]}
   lappend rows [list [get_property NAME $n] [lsort $ends]]
  }
  lappend answer [list [get_property NAME $p] [lsort $rows]]
 }
 if {![llength $answer]} {error "No actual reset FF graph"};return [lsort $answer]
}
proc formal_capture_report {wanted fallback} {
 if {![file isfile $wanted] && [file isfile $fallback]} {file rename $fallback $wanted}
 if {![file isfile $wanted] || [file size $wanted]==0} {error "Missing actual report $wanted"}
}
proc formal_target_compare {a b} {
 foreach k {0 2 1 3} {if {[lindex $a $k]<[lindex $b $k]} {return -1};if {[lindex $a $k]>[lindex $b $k]} {return 1}}
 return 0
}

export_sdc -file before.sdc
export_sdc -ip -file before_ip.sdc
set initial_graph [formal_reset_graph]
set initial_async [formal_inventory before_async.txt]
set f [open graph_before.txt w];puts $f $initial_graph;close $f
update_timing -mode final
report_timing_status -file baseline.ts
if {[formal_metrics baseline.ts] ne {-0.070 -0.070 0.020 0.000}} {error "Baseline timing does not reproduce719"}
set_param route post_route_opt high
set_param route postrt_opt_extra_round 4
set_param route fix_hold high
route
fix_hold
# Diagnostic capture BEFORE any graph acceptance decision. Never bitgen here.
set actual_graph [formal_reset_graph]
set f [open graph_after_route.txt w];puts $f $actual_graph;close $f
set f [open graph_equal.txt w];puts $f [expr {$actual_graph eq $initial_graph}];close $f
export_db diagnostic_after_route.db
write_verilog

update_timing -mode final
report_timing_status -file route748.ts
set passed [formal_positive route748.ts]
export_sdc -file after.sdc
export_sdc -ip -file after_ip.sdc
if {[formal_commands before.sdc] ne [formal_commands after.sdc] || [formal_commands before_ip.sdc] ne [formal_commands after_ip.sdc]} {error "Constraints changed"}
if {[formal_inventory after_async.txt] ne $initial_async} {error "Protected synchronizers changed"}
set f [open graph_after.txt w];puts $f [formal_reset_graph];close $f
update_timing -mode final
report_timing_status -file final.ts
report_timing_summary -include_ignored -ep_num 50 -path_num 4 -file final_all.timing
export_db final.db
write_verilog
puts "ROUTE748_COMPLETE positive=$passed"
} problem]} {puts stderr $problem;puts stderr $::errorInfo;exit 1}
exit 0
