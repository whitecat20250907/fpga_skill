# Native game target UI, 2026-10-26

The native GTK 3.22 client, real Freeciv server, campaign and hotseat rules remain authoritative. The selection layout now presents up to eight semantic targets on two widely spaced rails and a ninth “more targets” card. All original candidates remain reachable by paging. Kind 14 is a page control inside the existing confirm action; the five external actions and existing native target identities are unchanged.

Cards and read-only UDP geometry share centers and actual width/height. UTF-8 labels are JSON escaped so the existing ASCII-decoding bridge remains compatible. Numbered map annotations identify card locations; they are not additional selectable targets. Selection connects a card to its original map location. Four recruitment roles, income, moves, combat, server ownership and turn handoff remain native.

The start page uses separated asymmetric choices and shares MENU_RECTS between drawing and target output. Native battle enters fullscreen independently of the start window. HMI's launcher now runs the game as linaro when its owning service is root; Freeciv correctly refuses root servers. CPU affinity remains 0,1; the main pipeline is not restarted for a game layout change.

## Build

The imported build-arm64 Meson cache refers to /userdata/freeciv-rk3576-gaze-demo. A normal ninja invocation entered repeated regeneration and was stopped; this was not counted as a successful build. The final native client was built with the existing Meson GUI-main compile command and link command, replacing that stale absolute project root with this repository and running in this repository's build-arm64. Only gui_main.c (including demo_control.inc) and final client linking were required; no claim of a clean full upstream build.

Before future clean builds regenerate Meson in a new build directory with the same toolchain/options. Do not run the archived cache as though it were relocatable. Exact commands used for this deployment are recorded in the HMI v51 evidence directory. No compiler environment or dependency archives are part of this change.

## Validation and rollback

Actual ARM64 board integration uses the native nonce/UDP interface: campaign start, all pages, native recruitment, four production choices, and a real production-change acknowledgement. Synthetic coordinates exercise the software protocol; they do not certify human eye accuracy or a complete battle replay. Main services continue in parallel. The final measured target count, spacing and binary hash are in CURRENT_DEPLOYMENT_v51.md and game_v51_test.json in the sibling integration evidence directory.

Prior source, menu and client are in /home/linaro/pcie_fix_20261003/game_v51_previous. Restore those three together while the owned client is stopped. Do not restore an old client over a running process or change native rules to make tests pass. Existing .maintenance files were not included in the maintenance commit.
