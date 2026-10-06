"""Build a separate no-DDR camera-to-RK TD project from the vendor baseline."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "s0_vendor_415"
TARGET = HERE / "s1_noddr_passthrough"


def file_entry(path: str, order: int) -> str:
    return (
        f'            <File Path="{path}">\n'
        '                <FileInfo>\n'
        '                    <Attr Name="UsedInSyn" Val="true"/>\n'
        '                    <Attr Name="UsedInP&R" Val="true"/>\n'
        '                    <Attr Name="BelongTo" Val="design_1"/>\n'
        f'                    <Attr Name="CompileOrder" Val="{order}"/>\n'
        '                </FileInfo>\n'
        '            </File>\n'
    )


def main() -> None:
    TARGET.mkdir(exist_ok=True)
    shutil.copytree(SOURCE / "uisrc", TARGET / "uisrc", dirs_exist_ok=True)
    for name in ("system_top_noddr.v", "yuyv_quad_async_bridge.v"):
        shutil.copy2(HERE / "rtl" / name, TARGET / "uisrc/01_rtl" / name)
    adc = (SOURCE / "uisrc/04_pin/fpga_pin.adc").read_text(encoding="utf-8")
    adc = "\n".join(line for line in adc.splitlines()
                    if "I_ddr_clk" not in line and "I_button" not in line) + "\n"
    (TARGET / "uisrc/04_pin/fpga_pin.adc").write_text(adc, encoding="utf-8")
    (TARGET / "uisrc/04_pin/timing.sdc").write_text(
        "create_clock -name sys_clk -period 40.000 "
        "[get_ports {I_sysclk_25m}]\n"
        "# IMX415 SYS_MODE=5, 4 lanes: 891 Mb/s per lane (Sony mode table).\n"
        "# Forwarded clock is half the data rate, 445.5 MHz.\n"
        "# PH1_PHY_LCLK_V2 divides it by 2 and 4 for the receiver.\n"
        "# Confirm the programmed sensor mode on the live board for signoff.\n"
        "create_clock -name cam_hs_lane -period 2.244 "
        "[get_ports {I_clk_hs_p}]\n"
        "derive_clocks\n"
        "# The sensor-forwarded clock and both board PLL families are\n"
        "# physically asynchronous. Crossings use Gray-pointer FIFOs or\n"
        "# explicit synchronizers; test them in CDC simulation.\n"
        "set_clock_groups -asynchronous "
        "-group [get_clocks {cam_hs_lane "
        "X_mipi_dphy_rx_over_lvds_wrapper/u_rx_clk_gen/U_io_clk_div_0.clkout "
        "X_mipi_dphy_rx_over_lvds_wrapper/u_rx_clk_gen/U_io_clk_div_0.clkdivout "
        "X_mipi_dphy_rx_over_lvds_wrapper/u_rx_clk_gen/U_io_clk_div_1.clkdivout}] "
        "-group [get_clocks {sys_clk "
        "X_ui_pll/pll_inst.clkc[0] X_ui_pll/pll_inst.clkc[3] "
        "u_ui_pll_dsi/pll_inst.clkc[0] u_ui_pll_dsi/pll_inst.clkc[1] "
        "u_ui_pll_dsi/pll_inst.clkc[2] u_ui_pll_dsi/pll_inst.clkc[3] "
        "u_ui_pll_dsi/pll_inst.clkc[4]}]\n",
        encoding="utf-8",
    )
    original = (SOURCE / "fpga_prj.al").read_text(encoding="utf-8")
    project = original.replace(SOURCE.as_posix(), TARGET.as_posix())
    project = re.sub(r'<File Path="uisrc/01_rtl/system_top.v">.*?</File>\s*',
                     '', project, count=1, flags=re.S)
    project = re.sub(r'<File Path="uisrc/03_ip/al_ip/ui_ddr/ui_ddr.ipc">.*?</File>\s*',
                     '', project, count=1, flags=re.S)
    project = re.sub(r'<File Path="al_ip/VPI_0/VPI_0.xml">.*?</File>\s*',
                     '', project, count=1, flags=re.S)
    project = project.replace(
        "        <Verilog>\n",
        "        <Verilog>\n" + file_entry("uisrc/01_rtl/system_top_noddr.v", 1001)
        + file_entry("uisrc/01_rtl/yuyv_quad_async_bridge.v", 1002), 1,
    )
    project = project.replace("<LABEL>system_top</LABEL>",
                              "<LABEL>system_top_noddr</LABEL>")
    project = project.replace("<MODULE>system_top</MODULE>",
                              "<MODULE>system_top_noddr</MODULE>")
    (TARGET / "fpga_prj.al").write_text(project, encoding="utf-8")
    (TARGET / "build.tcl").write_text(
        "if {[catch {\n"
        f"  cd {{{TARGET.as_posix()}}}\n"
        "  import_device ph1_90.db -package PH1A90SEG324 -speed 2\n"
        f"  open_project {{{(TARGET / 'fpga_prj.al').as_posix()}}}\n"
        "  reset_runs phy_1\n  reset_runs syn_1\n"
        "  launch_runs syn_1\n  wait_run syn_1 -quiet\n"
        "  launch_runs phy_1\n  wait_run phy_1 -quiet\n"
        "} err]} { puts stderr $err; exit 1 }\nexit 0\n",
        encoding="utf-8",
    )
    print(TARGET)


if __name__ == "__main__":
    main()
