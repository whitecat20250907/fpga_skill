"""Clone the proven 75 MHz link and add cumulative bridge overflow evidence."""

from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "s4b_f3_csi_75m"
TARGET = HERE / "s4c_f3_csi_75m_monitor"


def main() -> None:
    if TARGET.exists():
        raise SystemExit(f"Target exists; refusing to overwrite: {TARGET}")
    shutil.copytree(SOURCE / "uisrc", TARGET / "uisrc")
    for name in ("system_top_f3.v", "yuyv_quad_async_bridge.v",
                 "lz4_line_packetizer.v"):
        text = (HERE / "rtl" / name).read_text(encoding="utf-8")
        if name == "system_top_f3.v":
            text = text.replace("pll_dsi u_ui_pll_dsi", "pll u_ui_pll_dsi")
        (TARGET / "uisrc/01_rtl" / name).write_text(text, encoding="utf-8")
    project = (SOURCE / "fpga_prj.al").read_text(encoding="utf-8")
    (TARGET / "fpga_prj.al").write_text(
        project.replace(SOURCE.as_posix(), TARGET.as_posix()), encoding="utf-8")
    for script in ("build.tcl", "build_syn.tcl"):
        content = (SOURCE / script).read_text(encoding="utf-8")
        (TARGET / script).write_text(
            content.replace(SOURCE.as_posix(), TARGET.as_posix()), encoding="utf-8")
    print(TARGET)


if __name__ == "__main__":
    main()
