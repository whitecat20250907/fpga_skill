puts "READ_ONLY_STANDALONE_API_DISCOVERY"
puts [lsort [info commands *verilog*]]
puts [lsort [info commands *help*]]
puts [lsort [info commands *netlist*]]
puts [lsort [info commands *export*]]
puts [lsort [info commands *write*]]
foreach task_args [list {help update_pll_param} {update_pll_param -h} {read_verilog -h} {analyze -h} {create_project -h} {elaborate -h} {export_db -h} {write_verilog -h}] {
    puts "COMMAND=$task_args"
    set task_rc [catch {eval $task_args} task_result]
    puts "RC=$task_rc RESULT=$task_result"
}
exit
