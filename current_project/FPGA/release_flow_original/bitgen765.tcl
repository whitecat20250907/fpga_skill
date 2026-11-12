if {[catch {
import_device ph1_90.db -package PH1A90SEG324 -speed 2
import_db {C:/qianrushifpga/fpga_skill/projects/hmi_optimization_20261027/F04_route748/final.db}
clear_sdc -user
read_sdc original.sdc
update_timing -mode final
report_timing_status -file final.ts
report_area -io_info -file physical.area
check_timing -verbose -file check_timing.rpt
set f [open final.ts r];set report [read $f];close $f
foreach key {SWNS STNS HWNS HTNS} {
 if {![regexp [format {%s:\s*([-+0-9.]+)ns} $key] $report all metric($key)]} {error "Missing final metric $key"}
}
if {!($metric(SWNS)>0 && $metric(HWNS)>0 && $metric(STNS)==0 && $metric(HTNS)==0)} {error "Nonpositive original-budget final timing"}
bitgen -bit exposure765.bit
export_bitgen_param -file bitgen_params.f
puts BIT765_GENERATED_NO_HARDWARE_WRITE
} problem]} {puts stderr $problem;puts stderr $::errorInfo;exit 1}
exit 0
