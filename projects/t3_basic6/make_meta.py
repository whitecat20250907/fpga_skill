"""Create a separate TD project for the on-wire FPGA monitor header."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "s1_noddr_passthrough"
TARGET = HERE / "s2_meta_monitor"


def main() -> None:
    if TARGET.exists():
        raise SystemExit(f"Target exists; refusing to overwrite: {TARGET}")
    shutil.copytree(SOURCE / "uisrc", TARGET / "uisrc")
    for name in ("system_top_noddr.v", "camera_meta_overlay.v"):
        shutil.copy2(HERE / "rtl" / name, TARGET / "uisrc/01_rtl" / name)
    project = (SOURCE / "fpga_prj.al").read_text(encoding="utf-8")
    project = project.replace(SOURCE.as_posix(), TARGET.as_posix())
    anchor = '            <File Path="uisrc/01_rtl/yuyv_quad_async_bridge.v">'
    addition = (
        '            <File Path="uisrc/01_rtl/camera_meta_overlay.v">\n'
        '                <FileInfo>\n'
        '                    <Attr Name="UsedInSyn" Val="true"/>\n'
        '                    <Attr Name="UsedInP&R" Val="true"/>\n'
        '                    <Attr Name="BelongTo" Val="design_1"/>\n'
        '                    <Attr Name="CompileOrder" Val="1003"/>\n'
        '                </FileInfo>\n'
        '            </File>\n'
    )
    assert project.count(anchor) == 1
    project = project.replace(anchor, addition + anchor, 1)
    assert re.search(r"<MODULE>system_top_noddr</MODULE>", project)
    (TARGET / "fpga_prj.al").write_text(project, encoding="utf-8")
    build = (SOURCE / "build.tcl").read_text(encoding="utf-8")
    build = build.replace(SOURCE.as_posix(), TARGET.as_posix())
    (TARGET / "build.tcl").write_text(build, encoding="utf-8")
    print(TARGET)


if __name__ == "__main__":
    main()
