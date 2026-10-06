"""Clone the vendor-pin-compatible F2 project and insert F3/F4 line codec."""

from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "s3b_f2_pipelined"
TARGET = HERE / "s4_f3_csi_container"


def entry(name: str, order: int) -> str:
    return (
        f'            <File Path="uisrc/01_rtl/{name}">\n'
        '                <FileInfo>\n'
        '                    <Attr Name="UsedInSyn" Val="true"/>\n'
        '                    <Attr Name="UsedInP&R" Val="true"/>\n'
        '                    <Attr Name="BelongTo" Val="design_1"/>\n'
        f'                    <Attr Name="CompileOrder" Val="{order}"/>\n'
        '                </FileInfo>\n'
        '            </File>\n'
    )


def main() -> None:
    if TARGET.exists():
        raise SystemExit(f"Target exists; refusing to overwrite: {TARGET}")
    shutil.copytree(SOURCE / "uisrc", TARGET / "uisrc")
    top = (HERE / "rtl/system_top_f2.v").read_text(encoding="utf-8")
    top = top.replace("module system_top_f2 (", "module system_top_f3 (")
    top = top.replace("// F1 -> F2 (gray/Gauss/histEq) -> F5 diagnostic header -> F4 MIPI link.",
                      "// F1 -> F2 gray/Gauss/histEq -> F3 four-lane LZ77 -> F4 CSI-2 container.")
    begin = top.index("    wire mon_valid, mon_sof, mon_last;")
    end = top.index("    yuyv_quad_async_bridge", begin)
    top = top[:begin] + """    wire comp_valid,comp_sof,comp_last,comp_overlap;
    wire [63:0] comp_data;
    lz4_line_packetizer #(.WIDTH(1920),.HEIGHT(1080),
                          .QUANT_BITS(4)) u_compress (
        .clk(rx_clk),.rst_n(sys_lock & tx_rst_n),
        .s_valid(eq_valid),.s_data(eq_data),
        .s_sof(eq_sof),.s_last(eq_last),
        .sensor_sof(csi_sof),
        .link_error({lane_error,overflow,gauss_overlap,eq_overlap}),
        .m_valid(comp_valid),.m_data(comp_data),
        .m_sof(comp_sof),.m_last(comp_last),
        .line_overlap(comp_overlap)
    );
""" + top[end:]
    top = top.replace(".s_valid(mon_valid), .s_data(mon_data),",
                      ".s_valid(comp_valid), .s_data(comp_data),")
    top = top.replace(".s_sof(mon_sof), .s_last(mon_last), .overflow(overflow),",
                      ".s_sof(comp_sof), .s_last(comp_last), .overflow(overflow),")
    top = top.replace(".H_ACTIVE(1920), .V_ACTIVE(1080)",
                      ".H_ACTIVE(1280), .V_ACTIVE(1080)")
    top = top.replace(".HIST_SHIFT(5)) u_histeq",
                      ".HIST_SHIFT(5),.BINS(64)) u_histeq")
    top = top.replace(".HEIGHT(1080)) u_gauss",
                      ".HEIGHT(1080),.BOTTOM_WAIT(1024)) u_gauss")
    assert "mon_valid" not in top and "H_ACTIVE(1280)" in top
    (HERE / "rtl/system_top_f3.v").write_text(top, encoding="utf-8")
    for name in ("system_top_f3.v", "lz1_lane_engine.v",
                 "lz4_line_packetizer.v", "histeq_yuyv_quad.v",
                 "gauss3x3_yuyv_quad.v"):
        shutil.copy2(HERE / "rtl" / name, TARGET / "uisrc/01_rtl" / name)
    project = (SOURCE / "fpga_prj.al").read_text(encoding="utf-8")
    project = project.replace(SOURCE.as_posix(), TARGET.as_posix())
    project = project.replace("system_top_f2.v", "system_top_f3.v")
    project = project.replace("system_top_f2", "system_top_f3")
    anchor = '            <File Path="uisrc/01_rtl/yuyv_quad_async_bridge.v">'
    assert project.count(anchor) == 1
    project = project.replace(anchor,
                              entry("lz1_lane_engine.v", 1006)
                              + entry("lz4_line_packetizer.v", 1007)
                              + anchor, 1)
    (TARGET / "fpga_prj.al").write_text(project, encoding="utf-8")
    build = (SOURCE / "build.tcl").read_text(encoding="utf-8")
    build = build.replace(SOURCE.as_posix(), TARGET.as_posix())
    (TARGET / "build.tcl").write_text(build, encoding="utf-8")
    syn_only = build.replace("  launch_runs phy_1\n  wait_run phy_1 -quiet\n", "")
    (TARGET / "build_syn.tcl").write_text(syn_only, encoding="utf-8")
    print(TARGET)


if __name__ == "__main__":
    main()
