"""Clone S4 with the vendor's 75 MHz DSI PLL for CSI link integrity trials."""

from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "s4_f3_csi_container"
TARGET = HERE / "s4b_f3_csi_75m"


def main() -> None:
    if TARGET.exists():
        raise SystemExit(f"Target exists; refusing to overwrite: {TARGET}")
    shutil.copytree(SOURCE / "uisrc", TARGET / "uisrc")
    project = (SOURCE / "fpga_prj.al").read_text(encoding="utf-8")
    project = project.replace(SOURCE.as_posix(), TARGET.as_posix())
    old = "uisrc/03_ip/al_ip/ui_pll_dsi/pll_dsi.ipc"
    new = "uisrc/03_ip/al_ip/ui_pll_dsi/pll.ipc"
    if project.count(old) != 1:
        raise RuntimeError("Expected one 125 MHz PLL IP declaration")
    (TARGET / "fpga_prj.al").write_text(project.replace(old, new), encoding="utf-8")
    top = TARGET / "uisrc/01_rtl/system_top_f3.v"
    content = top.read_text(encoding="utf-8")
    if content.count("pll_dsi u_ui_pll_dsi") != 1:
        raise RuntimeError("Unexpected top-level PLL instantiation")
    top.write_text(content.replace("pll_dsi u_ui_pll_dsi", "pll u_ui_pll_dsi"),
                   encoding="utf-8")
    for script in ("build.tcl", "build_syn.tcl"):
        text = (SOURCE / script).read_text(encoding="utf-8")
        (TARGET / script).write_text(
            text.replace(SOURCE.as_posix(), TARGET.as_posix()), encoding="utf-8")
    print(TARGET)


if __name__ == "__main__":
    main()
