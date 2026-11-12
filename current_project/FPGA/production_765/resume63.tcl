set caller [file dirname [file normalize [info script]]]
source [file join $caller resume_prefix63.tcl]
source [file join $caller build_direct_config.tcl]
set td_direct_input $td_direct_project
set td_direct_before [td_direct_binary $td_direct_input]
set td_direct_started [clock seconds]
set formal_margin_guard_script [file join $caller validation guard_formal_setup_guidance_v2.py]
set td_direct_out {C:/qianrushifpga/fpga_skill/projects/hmi_fpga_roi_pipeline_20261028/reports/resume_same_place_v4_20261027}
cd $td_direct_out
if {[catch {
 import_device $td_direct_device_db -package $td_direct_package -speed $td_direct_speed
 import_db {C:/qianrushifpga/fpga_skill/projects/hmi_fpga_roi_pipeline_20261028/reports/direct_build_20261027_214525_39160/pre_source_pair_guard_place.db}
 puts SAME_SOURCE_SAME_PLACE_CHECKPOINT_NOT_NEW_SYNTHESIS
 source [file join $caller resume_body63.tcl]
} err]} {puts stderr $err;puts stderr $::errorInfo;exit 1}
exit 0
