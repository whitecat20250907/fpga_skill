create_clock -name {clk_25m} -period 40.000 -waveform {0.000 20.000} [get_ports {I_sys_clk_25m}]

derive_clocks
rename_clock -name {S_clk} [get_clocks {u_pll/pll_inst.clkc[0]}]
rename_clock -name {S_clk_x2} [get_clocks {u_pll/pll_inst.clkc[1]}]
rename_clock -name {S_clk_x4} [get_clocks {u_pll/pll_inst.clkc[2]}]
rename_clock -name {S_clk_x4_90d} [get_clocks {u_pll/pll_inst.clkc[3]}]
rename_clock -name {S_lp_clk} [get_clocks {u_pll/pll_inst.clkc[4]}]
set_clock_groups -exclusive -group [get_clocks {S_clk}] -group [get_clocks {S_clk_x2}] -group [get_clocks {S_clk_x4}] -group [get_clocks {S_clk_x4_90d}] -group [get_clocks {S_lp_clk}]
