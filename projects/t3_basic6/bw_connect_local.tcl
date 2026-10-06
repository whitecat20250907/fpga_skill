if {[catch {connect_cable -host_name localhost} err]} {puts stderr "connect_cable: $err"}
if {[catch {list_cable} err]} {puts stderr "list_cable: $err"}
exit
