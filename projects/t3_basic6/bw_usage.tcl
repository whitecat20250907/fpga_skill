foreach cmd {connect_cable download program} {
    if {[catch {$cmd -help} err]} {puts stderr "$cmd usage: $err"}
}
exit
