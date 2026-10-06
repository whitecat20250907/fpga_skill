onerror {quit -code 1 -force}
onbreak {if {[examine -radix unsigned /tb_fdma_checker/test_done] == "1"} {quit -code 0 -force} else {quit -code 1 -force}}
if {![file exists work]} {vlib work}
vlog ../uisrc/01_rtl/fdma_test.v
vlog -sv tb_fdma_checker.sv
vsim -voptargs=+acc work.tb_fdma_checker
run 1 ms
if {[examine -radix unsigned /tb_fdma_checker/test_done] != "1"} {quit -code 1 -force}
quit -code 0 -force
