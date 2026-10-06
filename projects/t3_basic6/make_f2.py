"""Create an isolated TD project with the three-stage FPGA preprocess pipeline."""

from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "s2_meta_monitor"
TARGET = HERE / "s3_f2_preprocess"


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
    for name in ("system_top_f2.v", "camera_meta_overlay.v",
                 "gauss3x3_yuyv_quad.v", "histeq_yuyv_quad.v"):
        shutil.copy2(HERE / "rtl" / name, TARGET / "uisrc/01_rtl" / name)
    project = (SOURCE / "fpga_prj.al").read_text(encoding="utf-8")
    project = project.replace(SOURCE.as_posix(), TARGET.as_posix())
    project = project.replace("system_top_noddr.v", "system_top_f2.v")
    project = project.replace("system_top_noddr", "system_top_f2")
    anchor = '            <File Path="uisrc/01_rtl/yuyv_quad_async_bridge.v">'
    assert project.count(anchor) == 1
    project = project.replace(anchor,
                              entry("gauss3x3_yuyv_quad.v", 1004)
                              + entry("histeq_yuyv_quad.v", 1005) + anchor, 1)
    (TARGET / "fpga_prj.al").write_text(project, encoding="utf-8")
    build = (SOURCE / "build.tcl").read_text(encoding="utf-8")
    (TARGET / "build.tcl").write_text(
        build.replace(SOURCE.as_posix(), TARGET.as_posix()), encoding="utf-8")
    print(TARGET)


if __name__ == "__main__":
    main()
