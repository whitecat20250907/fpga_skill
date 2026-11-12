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
 set c [get_cells -filter {NAME == u_cam_video_source/u_mipi_csi_rx/u_csi_rx_phy/sampler_reset_sync_reg[2]_syn_2} -verbose]
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
set formal_reset_moved 0
set formal_guide_used 0
export_sdc -file formal_user_before.sdc
export_sdc -ip -file formal_ip_before.sdc
set formal_original_user [formal_commands formal_user_before.sdc]
set formal_original_ip [formal_commands formal_ip_before.sdc]
set formal_original_async [formal_inventory formal_async_before.txt]
update_timing -mode final
report_timing_status -file formal_initial.ts
report_timing_summary -include_ignored -ep_num 50 -path_num 4 -file formal_initial_all_paths.timing
formal_capture_report formal_initial_all_paths.timing imx415_pcie_top_route.timingsummary
# F159 uses source-declared register fanout optimization. No post-route
# single-cell move or temporary timing guidance is applied to this candidate.
if {![formal_positive formal_initial.ts]} {
 puts F159_INITIAL_ORIGINAL_BUDGET_NONPOSITIVE_NO_SINGLE_CELL_RELOCATION
}

update_timing -mode final
report_timing_status -file formal_final.ts
report_timing_summary -include_ignored -ep_num 50 -path_num 4 -file formal_final_all_paths.timing
formal_capture_report formal_final_all_paths.timing imx415_pcie_top_route.timingsummary
export_sdc -file formal_user_final.sdc
export_sdc -ip -file formal_ip_final.sdc
if {[formal_commands formal_user_final.sdc] ne $formal_original_user || [formal_commands formal_ip_final.sdc] ne $formal_original_ip} {error "Formal final constraints changed"}
if {[formal_inventory formal_async_final.txt] ne $formal_original_async} {error "Formal synchronizer identities or attributes changed"}
exec $trace_guard_python -X utf8 -B $formal_margin_guard_script --baseline formal_initial_all_paths.timing --report formal_final_all_paths.timing --mode restored --out formal_actual_restored_guard
set f [open formal_closure.status w]
puts $f "reset_moved=$formal_reset_moved guide_used=$formal_guide_used original_user_IP_commands_equal=1"
puts $f "timing=[formal_metrics formal_final.ts]"
close $f
if {![formal_positive formal_final.ts]} {error "Formal original-budget STA is nonpositive; no bitgen"}
puts FORMAL_SOURCE_CLOSURE_ACCEPTED_AT_ORIGINAL_CONSTRAINTS
