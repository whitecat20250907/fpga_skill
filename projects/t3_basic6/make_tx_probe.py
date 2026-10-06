"""Derive a small CSI-2 TX byte-order probe from the licensed vendor sources.

The original s0_vendor_415 checkout remains unchanged.  The probe is useful
before camera/ISP/compressor integration because its YUYV payload is exact.
"""

from __future__ import annotations

import shutil
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "s0_vendor_415"
TARGET = HERE / "s0_tx_probe"
VERILOG = {
    "uisrc/01_rtl/system_top_tx_tpg.v",
    "uisrc/01_rtl/yuv422_tpg_axis.v",
    "uisrc/01_rtl/csi2_frame_tx.v",
    "uisrc/03_ip/dphy_tx_general/mipi_dphy_tx_wrapper.enc.v",
}
IP = {"uisrc/03_ip/al_ip/ui_pll_dsi/pll_dsi.ipc"}
PINS = {
    "I_sysclk_25m", "I_dsi_en", "O_mipi_dsi_hs_clk_p",
    "O_mipi_dsi_hs_data_p", "O_mipi_dsi_lp_clk_p",
    "O_mipi_dsi_lp_clk_n", "O_mipi_dsi_lp_data_p",
    "O_mipi_dsi_lp_data_n",
}


def make() -> None:
    TARGET.mkdir(exist_ok=True)
    shutil.copytree(SOURCE / "uisrc", TARGET / "uisrc", dirs_exist_ok=True)
    adc = SOURCE / "uisrc/04_pin/fpga_pin.adc"
    selected = []
    for line in adc.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("set_pin_assignment"):
            continue
        if any("{ " + p + " " in line or "{ " + p + "[" in line for p in PINS):
            selected.append(line)
    assert len(selected) == 17, (len(selected), selected)
    (TARGET / "uisrc/04_pin/fpga_pin.adc").write_text(
        "# AFC03 FPGA-to-RK CSI-2 TX pins, copied from vendor project.\n"
        + "\n".join(selected) + "\n", encoding="utf-8"
    )
    (TARGET / "uisrc/04_pin/timing.sdc").write_text(
        "create_clock -name sys_clk -period 40.000 "
        "[get_ports {I_sysclk_25m}]\n"
        "derive_clocks\n",
        encoding="utf-8",
    )

    project_text = (SOURCE / "fpga_prj.al").read_text(encoding="utf-8")
    # TD's .al is XML-like, not XML (it has BitgenProperty:: and bare P&R),
    # so preserve its syntax and replace only well-scoped project fragments.
    project_text = project_text.replace(SOURCE.as_posix(), TARGET.as_posix())
    source_block = re.search(r"<Source_Files>.*?</Source_Files>", project_text, re.S)
    assert source_block
    new_sections = []
    for category, wanted in (
        ("Verilog", VERILOG), ("ADC_FILE", {"uisrc/04_pin/fpga_pin.adc"}),
        ("SDC_FILE", {"uisrc/04_pin/timing.sdc"}), ("IP_FILE", IP),
    ):
        section = re.search(rf"<{category}>.*?</{category}>", source_block.group(), re.S)
        assert section, category
        entries = []
        present = set()
        for match in re.finditer(r'<File Path="([^"]+)">.*?</File>', section.group(), re.S):
            if match.group(1).strip() in wanted:
                entries.append(match.group())
                present.add(match.group(1).strip())
        for path in sorted(wanted - present):
            assert (TARGET / path).exists(), path
            entries.append(
                f'            <File Path="{path}">\n'
                '                <FileInfo>\n'
                '                    <Attr Name="UsedInSyn" Val="true"/>\n'
                '                    <Attr Name="UsedInP&R" Val="true"/>\n'
                '                    <Attr Name="BelongTo" Val="design_1"/>\n'
                '                    <Attr Name="CompileOrder" Val="1"/>\n'
                '                </FileInfo>\n'
                '            </File>'
            )
        new_sections.append("        <" + category + ">\n" + "\n".join(entries) +
                            "\n        </" + category + ">")
    replacement = "<Source_Files>\n" + "\n".join(new_sections) + "\n    </Source_Files>"
    project_text = project_text.replace(source_block.group(), replacement)
    project_text = project_text.replace("<LABEL>system_top</LABEL>",
                                        "<LABEL>system_top_tx_tpg</LABEL>")
    project_text = project_text.replace("<MODULE>system_top</MODULE>",
                                        "<MODULE>system_top_tx_tpg</MODULE>")
    (TARGET / "fpga_prj.al").write_text(project_text, encoding="utf-8")
    (TARGET / "build.tcl").write_text(
        "if {[catch {\n"
        f"  cd {{{TARGET.as_posix()}}}\n"
        "  import_device ph1_90.db -package PH1A90SEG324 -speed 2\n"
        f"  open_project {{{(TARGET / 'fpga_prj.al').as_posix()}}}\n"
        "  launch_runs syn_1\n  wait_run syn_1 -quiet\n"
        "  launch_runs phy_1\n  wait_run phy_1 -quiet\n"
        "} err]} { puts stderr $err; exit 1 }\nexit 0\n",
        encoding="utf-8",
    )
    assert all((TARGET / p).exists() for p in VERILOG | IP)
    print(f"Created {TARGET} with {len(selected)} pin assignments")


if __name__ == "__main__":
    make()
