onerror {quit -code 1 -force}
onbreak {if {[examine -radix unsigned /tb_demo06_dbuf/done] == "1"} {quit -code 0 -force} else {quit -code 1 -force}}
if {![file exists work_dbuf]} {vlib work_dbuf}
vlog -work work_dbuf -sv ../uisrc/03_ip/ui_dbuf/sfifo/sfifo.v ../uisrc/03_ip/ui_dbuf/uidbuf.v tb_demo06_dbuf.sv
vsim -c -voptargs=+acc work_dbuf.tb_demo06_dbuf
run -all
quit -code 1 -force
