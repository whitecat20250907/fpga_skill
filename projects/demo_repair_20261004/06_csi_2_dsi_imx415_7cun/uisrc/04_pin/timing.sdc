create_clock -name {sys_clk} -period 40.000 -waveform {0.000 20.000} [get_ports {I_sysclk_25m}]
create_clock -name {ddr_clk} -period 10.000 -waveform {0.000 5.000} [get_ports {I_ddr_clk}]
# Nominal IMX415 binning mode:891Mbps/lane, source-synchronous HS445.5MHz.
# This constrains the intended rate; it does not measure camera MCLK or link rate.
create_clock -name {csi_hs_clk} -period 2.244669 [get_ports {I_clk_hs_p}]

derive_clocks

# Actual ui_pll.v C0=75MHz,C1=25MHz; old names were interchanged.
rename_clock -name {S_clk_70m} [get_clocks {X_ui_pll/pll_inst.clkc[0]}]
rename_clock -name {S_clk_25m} [get_clocks {X_ui_pll/pll_inst.clkc[1]}]
rename_clock -name {S_clk} [get_clocks {X_ui_pll/pll_inst.clkc[2]}]
rename_clock -name {S_clk_x2} [get_clocks {X_ui_pll/pll_inst.clkc[3]}]
rename_clock -name {S_clk_x4} [get_clocks {X_ui_pll/pll_inst.clkc[4]}]
rename_clock -name {S_clk_x4_90d} [get_clocks {X_ui_pll/pll_inst.clkc[5]}]
rename_clock -name {S_lp_clk} [get_clocks {X_ui_pll/pll_inst.clkc[6]}]

# CLK_DIV249,SCL_DIV124:toggle every125 source cycles, full period250.
# C1 and board reference both25MHz, zero phase in this IP.
create_generated_clock -name {camera_i2c_scl} -source [get_ports {I_sysclk_25m}] -divide_by 250 [get_nets {X_ui_cfg_imx415/X_ui_i2c/scl_clk}]

# Keep related PLL outputs and derived I2C timed against each other.
# Only independent families use async cuts, across explicit FIFO/2FF CDC.
set_clock_groups -asynchronous \
    -group [get_clocks {sys_clk S_clk_25m S_clk_70m S_clk S_clk_x2 S_clk_x4 S_clk_x4_90d S_lp_clk camera_i2c_scl}] \
    -group [get_clocks {ddr_clk X_ui_ddr/*}] \
    -group [get_clocks {csi_hs_clk X_mipi_dphy_rx_over_lvds_wrapper/*}]
