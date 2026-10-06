# HDMI known RGB pattern candidate

Actual root-owned inventory: RK has no `/dev/fb*`; Xorg display `:0` runs XFCE through lightdm, Tk and `/usr/bin/xwd` are available. X11 output HDMI-1 is 1920x1080+0+0, while DSI1 overlaps at 800x1280+0+0; desktop bounds are 1920x1280. No framebuffer tool was written or run. This candidate uses an exact 1920x1080 borderless Tk window on that desktop, without stopping lightdm or changing xrandr/DRM modes. Overlap means part of the same window can also appear on DSI; the tool records that boundary instead of silently changing monitor layouts.

`tools/hdmi_colour_pattern.py` SHA-256: `b2c83b2a1fca4608cdfee39a45858a1aee0728ee0d5b28c169946c5df91f96cc`.

Root can copy it to the RK and run with a fresh output directory:

```sh
DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 python3 /path/hdmi_colour_pattern.py \
  --output HDMI-1 --geometry 1920x1080+0+0 \
  --control /tmp/hdmi_control.json --out /tmp/hdmi_pattern_unique \
  --capture-xwd --seconds 600 > /tmp/hdmi_pattern.log 2>&1 &
```

The initial chart has nine large patches: RED/GREEN/BLUE, WHITE/GRAY/BLACK, ORANGE/CYAN/MAGENTA. Every rectangle, explicit integer RGB tuple and central measurement ROI comes from one shared specification used by both Tk `#RRGGBB` fill and the RGB24 reference PNG writer. Orange is (255,128,0), gray (128,128,128). Large labels are confined to the upper portion; centre 30–70% sample ROIs exclude text. Reference PNGs intentionally contain patch pixels without Tk text, and their metadata says so. Optional actual X11 window `.xwd` snapshots include text and record process return code and whether the command generation remained unchanged during capture. They are not claimed to prove HDMI wire signalling or panel colourimetry.

Atomically replace the control file with one JSON object. Examples:

```json
{"mode":"solid","colour":"RED","id":"red_epoch_1"}
{"mode":"solid","colour":"#00ff00","label":"GREEN","id":"green_epoch_2"}
{"mode":"chart","id":"chart_epoch_3"}
{"mode":"quit"}
```

Only one object belongs in the file at a time; the examples above show independent commands. A changed command is polled every 100 ms. Named colours, exact hex RGB and three-integer RGB arrays are supported. Bad commands leave the previous valid pattern and produce an error event. `ready.json` identifies the current generation/command, reference PNG hash, window ID, screen bounds and per-patch ROIs; `events.jsonl` records renders/XWD results. Wait for the intended command ID in ready.json and a stable successful actual snapshot before treating an acquisition as that colour epoch. An actual camera response is still needed to validate the FPGA image pipeline.

Escape, SIGTERM, the quit command or the duration limit destroys only this process's window, exposing the existing desktop. The tool saves its exact PID and never matches or stops unrelated background processes.

Local `python ... --self-test` passed PNG signature/chunk CRC/RGB channels, all nine sample ROIs, colour parsing and geometry rejection. `py_compile` also passed. No board/X11 execution was performed by this subagent; root's actual rendering/snapshot/camera verification is pending.
