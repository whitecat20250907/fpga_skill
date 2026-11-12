# Source-declared viewer ASYNC_REG bits, located through real FF Q/D topology.
# Only the two terminal reset-release flags may be absent before this step.
# No timing exceptions, clocks, RTL or placement constraints are changed.
set viewer_guard [file join $output_directory validation review_input_viewer_physical.py]
set viewer_before [file join $output_directory viewer_async_before.txt]
file copy [file join $output_directory hmi_async_after.txt] $viewer_before
exec $monitor_guard_python -X utf8 -B $viewer_guard --build $output_directory --netlist $netlist --attrs $viewer_before --out [file join $output_directory viewer_identified] --collect-terminal-attributes
source [file join $output_directory viewer_identified declared_cells.tcl]
set viewer_old {};set viewer_repaired {}
foreach object [get_cells -filter {ASYNC_REG == true} -verbose] {lappend viewer_old [get_property NAME $object]}
foreach name $viewer_declared_async_cells {
    set objects [get_cells -filter [format {NAME == %s} $name] -verbose]
    if {[llength $objects]!=1} {error "Viewer sync FF disappeared: $name"}
    set object [lindex $objects 0]
    if {[lsearch -exact $viewer_old $name]<0} {set_property ASYNC_REG true [list $object];lappend viewer_repaired $name}
    if {[get_property ASYNC_REG $object] ni {1 true on}} {error "Viewer property recovery failed: $name"}
}
set viewer_after {};set viewer_file [open [file join $output_directory hmi_async_after.txt] w]
foreach object [get_cells -filter {ASYNC_REG == true} -verbose] {
    lappend viewer_after [get_property NAME $object]
    puts $viewer_file "cell=[get_property NAME $object] async_reg=[get_property ASYNC_REG $object]"
}
close $viewer_file
if {[lsort $viewer_after] ne [lsort [concat $viewer_old $viewer_repaired]]} {error "Unrelated ASYNC_REG changed"}
exec $monitor_guard_python -X utf8 -B $viewer_guard --build $output_directory --netlist $netlist --attrs [file join $output_directory hmi_async_after.txt] --out [file join $output_directory viewer_structure]
puts "VIEWER_DECLARED_ASYNC_RECOVERED=$viewer_repaired"
