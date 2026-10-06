create_clock -name sysclk -period 40.000 [get_ports {I_sysclk}]
# RTC ui_i2c uses an actual derived fabric clock, not a clock enable.
# SYSCLKHZ=25MHz, CLK_DIV=250, SCL_DIV=125: toggle every126 input clocks.
create_generated_clock -name rtc_i2c_scl -source [get_ports {I_sysclk}] -divide_by 252 [get_nets {X_ui_i2c/scl_clk}]
