create_clock -name sys_clk -period 40.000 [get_ports {I_sysclk_25m}]
derive_clocks
