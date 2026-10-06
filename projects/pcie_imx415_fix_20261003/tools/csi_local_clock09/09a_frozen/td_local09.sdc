create_clock -name sys_clk -period 40 [get_ports {sys_clk}]
create_clock -name mipi_hs_clk -period 2.244668 [get_ports {mipi_clk_hs_rx_p}]
derive_clocks
set csi09_ref_clocks [get_clocks {sys_clk}]
set csi09_hs_clocks [get_clocks {mipi_hs_clk phy/u_rx_clk_gen/U_io_clk_div_0.clkout phy/u_rx_clk_gen/U_io_clk_div_0.clkdivout phy/u_rx_clk_gen/U_io_clk_div_1.clkout phy/u_rx_clk_gen/U_io_clk_div_1.clkdivout}]
puts "CSI09_CLOCKS: ref=$csi09_ref_clocks hs=$csi09_hs_clocks"
if {[llength $csi09_ref_clocks]!=1 || [llength $csi09_hs_clocks]!=5} {error "Missing exact clock collection"}
# Only independent system reference vs CSI source. All IO/fabric divisions
# remain related and their recovery/removal/data paths stay under real STA.
set_clock_groups -asynchronous -group $csi09_ref_clocks -group $csi09_hs_clocks
