## PH1A90SEG324-2 / PCIe Gen2 x1 / IMX415
create_clock -name sys_clk -period 40 -waveform {0 20} [get_ports {sys_clk}]
create_clock -name mipi_hs_clk -period 2.244668 [get_ports {mipi_clk_hs_rx_p}]
create_clock -name mipi_ref_clk -period 10.0 [get_ports {mipi_ref_clk_p}]
# Make the PCIe IP clocks visible when the root SDC is evaluated before mapping.
create_clock -name pcie_fix_core_clk -period 8.0 -waveform {0 1} [get_pins {u_sgdma_subsys/DEVICE_IS_PH1A$u_ph1a_if_ep/PH1A_PCIE_CORE_BLK$u_al_pcie_ip/uep_PH1_PHY_PCIE.core_clk}]
create_generated_clock -name pcie_fix_user_clk -source [get_pins {u_sgdma_subsys/DEVICE_IS_PH1A$u_ph1a_if_ep/PH1A_PCIE_CORE_BLK$u_al_pcie_ip/uep_PH1_PHY_PCIE.core_clk}] -phase 0 -multiply_by 1 -duty_cycle 25 [get_pins {u_sgdma_subsys/DEVICE_IS_PH1A$u_ph1a_if_ep/PH1A_PCIE_CORE_BLK$u_al_pcie_ip/u_al_pcie_ip_ph1_clock_ctrl/u_al_pcie_ip_ph1_core_pll/pll_inst.clkc[0]}]
derive_clocks
# CAM_I2C_CLK_DIV=239: half-period floor(239/2)+1=120 clocks.
create_generated_clock -name cam_i2c_scl -source [get_pins {u_ui_pll/pll_inst.clkc[2]}] -divide_by 240 [get_nets {u_cam_i2c_cfg/X_ui_i2c/scl_clk}]
set_clock_latency 1.000 -clock [get_clocks {pcie_fix_user_clk}]

# Independent clock sources, with all related divisions in the same group.
# PCIe clock names are scoped by the IP instance in TD.
# Clock grouping does not certify that every CDC circuit is safe.
set pcie_fix_sys_clocks [get_clocks {sys_clk u_sgdma_pll/pll_inst.clkc[0] u_sgdma_pll/pll_inst.clkc[1] u_cam_pll27/pll_inst.clkc[0] u_cam_pll27/pll_inst.clkc[1]}]
set pcie_fix_ui_clocks [get_clocks {mipi_ref_clk u_ui_pll/pll_inst.clkc[0] u_ui_pll/pll_inst.clkc[2] cam_i2c_scl}]
set pcie_fix_link_clocks [get_clocks {pcie_fix_core_clk pcie_fix_user_clk}]
set pcie_fix_mipi_clocks [get_clocks {mipi_hs_clk u_cam_video_source/u_mipi_csi_rx/u_csi_rx_phy/u_rx_clk_gen/U_io_clk_div_0.clkout u_cam_video_source/u_mipi_csi_rx/u_csi_rx_phy/u_rx_clk_gen/U_io_clk_div_0.clkdivout u_cam_video_source/u_mipi_csi_rx/u_csi_rx_phy/u_rx_clk_gen/U_io_clk_div_1.clkout u_cam_video_source/u_mipi_csi_rx/u_csi_rx_phy/u_rx_clk_gen/U_io_clk_div_1.clkdivout}]
puts "PCIE_FIX_CLOCKS: sys=$pcie_fix_sys_clocks ui=$pcie_fix_ui_clocks link=$pcie_fix_link_clocks mipi=$pcie_fix_mipi_clocks"
set pcie_fix_audit [open [file join [pwd] clock_collections.txt] w]
puts $pcie_fix_audit "sys=$pcie_fix_sys_clocks\nui=$pcie_fix_ui_clocks\nlink=$pcie_fix_link_clocks\nmipi=$pcie_fix_mipi_clocks\nall=[get_clocks {*}]"
close $pcie_fix_audit
foreach pcie_fix_group [list $pcie_fix_sys_clocks $pcie_fix_ui_clocks $pcie_fix_link_clocks $pcie_fix_mipi_clocks] {if {[llength $pcie_fix_group] == 0} {error "PCIe fix: empty asynchronous clock group"}}
set_clock_groups -asynchronous \
    -group $pcie_fix_sys_clocks \
    -group $pcie_fix_ui_clocks \
    -group $pcie_fix_link_clocks \
    -group $pcie_fix_mipi_clocks

# New DSI clocks share their one PLL and remain mutually timed.
# No additional clock-group cuts are introduced for the feature FIFO.
set twin_dsi_clocks [get_clocks {u_twin_dsi/u_pll/pll_inst.clkc[0] u_twin_dsi/u_pll/pll_inst.clkc[1] u_twin_dsi/u_pll/pll_inst.clkc[2] u_twin_dsi/u_pll/pll_inst.clkc[3] u_twin_dsi/u_pll/pll_inst.clkc[4]}]
puts "PROJECT_TWIN_DSI_CLOCKS=$twin_dsi_clocks"
if {[llength $twin_dsi_clocks] != 5} {error "Missing project DSI PLL clocks"}
