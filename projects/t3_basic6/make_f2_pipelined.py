"""Isolate the pipelined histogram revision for timing comparison."""

from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "s3_f2_preprocess"
TARGET = HERE / "s3b_f2_pipelined"


def main() -> None:
    if TARGET.exists():
        raise SystemExit(f"Target exists; refusing to overwrite: {TARGET}")
    shutil.copytree(SOURCE / "uisrc", TARGET / "uisrc")
    shutil.copy2(HERE / "rtl/histeq_yuyv_quad.v",
                 TARGET / "uisrc/01_rtl/histeq_yuyv_quad.v")
    project = (SOURCE / "fpga_prj.al").read_text(encoding="utf-8")
    project = project.replace(SOURCE.as_posix(), TARGET.as_posix())
    (TARGET / "fpga_prj.al").write_text(project, encoding="utf-8")
    build = (SOURCE / "build.tcl").read_text(encoding="utf-8")
    build = build.replace(SOURCE.as_posix(), TARGET.as_posix())
    (TARGET / "build.tcl").write_text(build, encoding="utf-8")
    syn_only = build.replace("  launch_runs phy_1\n  wait_run phy_1 -quiet\n", "")
    (TARGET / "build_syn.tcl").write_text(syn_only, encoding="utf-8")
    print(TARGET)


if __name__ == "__main__":
    main()
