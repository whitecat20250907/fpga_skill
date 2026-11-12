# Freeciv RK3576 demo maintenance

Read README.md, DEPLOY_RK3576.md, INPUT_PROTOCOL.md and TEST_REPORT.md first.

## Product constraints

- Keep the native Freeciv GTK 3.22 client and real server rules. One short fixed-map military scene is sufficient.
- Exactly five main actions: wake, confirm, cancel, next unit, end turn. Dynamic semantic target snapping, never a fixed 8x8 grid.
- Ordinary gaze must not execute commands. Confirmation exits selection. Preserve smoothing, hysteresis, stale-sample rejection and event deduplication.
- Keep the map visible during city production management. Preserve original asset and source licenses.
- Avoid browser engines, heavyweight 3D engines, extra inference, background polling services, and autostart by default.
- Main application inference has priority. Measure game alone and alongside the actual main application before promising a performance budget.

## User-authorized scope update, 2026-10-20

The user explicitly requested deploying an official open-source MediaPipe gesture recognizer on RK3576. This permits the optional hand inference module despite the earlier no-extra-inference constraint. Keep it in a separate environment, reuse the existing PCIe RGB preview, preserve the original gaze NPU and drivers, and make action sending opt-in. No new camera capture, USB camera, or autostart. The user deferred live human testing; official fixture inference and software event tests must not be called human usability or real-human gaze NPU acceptance. Independent native game and full battle acceptance already passed on the board.

## Source layout

## User-authorized scope update, 2026-10-21

The user rejected the overly small military demo. Keep five actions, native
rules and semantic snapping, but implement obvious recruitment, four unit
roles, income control points, continuing enemy reinforcements, combat risk
and an expansion-to-siege campaign. Old battle acceptance does not validate
the new campaign. The dashboard must show actual hand/head/eye features and
a 3D twin driven by existing landmarks; retire generic algorithm artwork.

The user also requested a start page and selected two players taking turns
on the same RK3576. Implement real native human-versus-human ownership and
a deliberate handover, sharing the existing camera/model. This does not
authorize another camera/inference instance or claiming two-user gaze
calibration/identity verification without actual tests.

The repository contains the full modified upstream source in upstream/freeciv-3.2.6. The primary custom logic is client/gui-gtk-3.22/demo_control.inc; gui_main.c, mapctrl.c, mapview.c and demo_control.h contain integration hooks. The patch is an initial provenance snapshot, not the authoritative source: edit the actual source files and update documentation.

## Work safely and report evidence

The Windows build and a complete game were verified. ARM64 support is a porting target until this exact revision is compiled and played on a board. Record architecture, OS, commit, display session, build results, gameplay, CPU and memory in a dated board report. Do not equate a successful compile, headless server or emulated test with playable board verification.

Inspect existing changes before updates. Never reset or clean user work, stop unrelated services, alter NPU/GPU drivers, replace the main program's Python environment, or commit passwords/tokens. Integration with the user's main program should be a small optional adapter preserving existing bindings. Use a branch and commits for maintenance; push only when authorized by the user. Do not create agents unless explicitly requested.

