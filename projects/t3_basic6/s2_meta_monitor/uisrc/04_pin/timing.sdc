create_clock -name sys_clk -period 40.000 [get_ports {I_sysclk_25m}]
# IMX415 SYS_MODE=5, 4 lanes: 891 Mb/s per lane (Sony mode table).
# Forwarded clock is half the data rate, 445.5 MHz.
# PH1_PHY_LCLK_V2 divides it by 2 and 4 for the receiver.
# Confirm the programmed sensor mode on the live board for signoff.
create_clock -name cam_hs_lane -period 2.244 [get_ports {I_clk_hs_p}]
derive_clocks
# The sensor-forwarded clock and both board PLL families are
# physically asynchronous. Crossings use Gray-pointer FIFOs or
# explicit synchronizers; test them in CDC simulation.
set_clock_groups -asynchronous -group [get_clocks {cam_hs_lane X_mipi_dphy_rx_over_lvds_wrapper/u_rx_clk_gen/U_io_clk_div_0.clkout X_mipi_dphy_rx_over_lvds_wrapper/u_rx_clk_gen/U_io_clk_div_0.clkdivout X_mipi_dphy_rx_over_lvds_wrapper/u_rx_clk_gen/U_io_clk_div_1.clkdivout}] -group [get_clocks {sys_clk X_ui_pll/pll_inst.clkc[0] X_ui_pll/pll_inst.clkc[3] u_ui_pll_dsi/pll_inst.clkc[0] u_ui_pll_dsi/pll_inst.clkc[1] u_ui_pll_dsi/pll_inst.clkc[2] u_ui_pll_dsi/pll_inst.clkc[3] u_ui_pll_dsi/pll_inst.clkc[4]}]
