if {![info exists env(T3_BIT_PATH)]} {
    puts stderr "T3_BIT_PATH is unset"; exit 2
}
if {[catch {connect_cable -host_name localhost} err]} {
    puts stderr "AL-LINK connection failed: $err"; exit 3
}
list_cable
if {[catch {download -bit $env(T3_BIT_PATH) -mode jtag -spd 7 -cable 0} err]} {
    puts stderr "SRAM download failed: $err"; exit 4
}
exit 0
