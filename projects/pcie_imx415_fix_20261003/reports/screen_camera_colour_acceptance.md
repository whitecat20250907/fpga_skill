# Actual screen pixels and manual camera colour ROIs

Two independent stages are required: verify the X11 screenshot is the requested RGB pattern, then measure the camera response. Neither reference PNGs nor a successful decoder alone establishes actual screen or camera correctness.

## Tools and local checks

- `tools/xwd_screen_verify.py`: numpy and Python standard library only; no Pillow or cv2 dependency. SHA-256 `d9269d300403e7d495803ea7f6cb169dc25785d19c90c3707f624a3200347661`.
- `tools/camera_chart_roi.py`: numpy/cv2, imports the statistics/ROI helper from the first file. SHA-256 `12345506f21d9920e153c245013c22d8fd01e616d0da4c7ac96b213ac3d49678`.
- XWD decoder self-test passes six synthetic endian/RGB-mask/24-/32-bit/RGB565 fixtures and 30 unsupported/malformed cases. Camera analysis self-test passes nominal colours, detects an R/G swap, all-dark ROIs and neutral colour patches even with zero margins, and rejects silently incomplete full-chart input. Both files pass Python syntax compilation. These are local software tests, not actual board acceptance.

The XWD header layout was checked against `XWDFile.h` in the [official Xorg xproto 7.0.31 source archive](https://www.x.org/archive/individual/proto/xproto-7.0.31.tar.gz), preserved locally as `evidence/XWDFile_upstream_xproto_7_0_31.h`. It declares a 100-byte version-7 header, 12-byte colour records, big-endian header words and an image-data byte-order field. Pixel Z-format byte order is also described in the [official Xlib specification](https://www.x.org/releases/X11R7.6/doc/libX11/specs/libX11/libX11.html). The implementation reads those declarations rather than assuming an ARGB/BGR byte order.

## Screen stage: actual XWD, never the reference PNG

Root's actual RK run is `evidence/hdmi_pattern_colour06`. Its XWD is about 8.3 MB, so run the decoder on the board and retrieve the much smaller lossless PNG and JSON:

```sh
python3 /uploaded/tools/xwd_screen_verify.py \
  --xwd evidence/hdmi_pattern_colour06/actual_000N.xwd \
  --ready evidence/hdmi_pattern_colour06/ready.json \
  --events evidence/hdmi_pattern_colour06/events.jsonl --generation N \
  --out evidence/hdmi_pattern_colour06/check_N
```

Select the actual generation N recorded by the tool, not a guessed filename. Verification requires exactly one rendered event and one matching actual capture event, successful XWD return code, stable command generation, coherent source-session paths and screenshot dimensions equal to the rendered monitor window. Older generations can use their saved rendered event even when ready.json now describes a newer one.

Only TrueColor ZPixmap is supported. The decoder explicitly validates version, pixel depth, masks/non-overlap/contiguity, byte order, row stride, colour-table offset and exact payload length; unsupported planar/palette/DirectColor/nonzero-xoffset formats fail clearly. It supports byte-aligned 8/16/24/32-bit pixels for decoding. Exact nominal RGB8 verification additionally requires eight bits per channel; other depths retain the decoded image but do not receive that exact-RGB pass.

Root's actual board-side decode has now been retrieved and independently inspected locally: `evidence/hdmi_actual_x11_colour.json`, SHA-256 `06b49b827112d3e0a53c98c74177232fca95eeab64822efe907582979170e19b`, records generation1, the successful stable actual XWD capture and **all nine centre ROIs with zero mismatched pixels and [0,0,0] maximum channel error**. Each centre contains36864 actual screenshot pixels. Actual XWD uses little-endian32-bit TrueColor, depth24, masks0x00ff0000/0x0000ff00/0x000000ff and row stride7680. The actual decoded screenshot is `evidence/hdmi_actual_x11_colour.png`, SHA-256 `81952cc3cb550ba0f785206f788341fcf574efa01cfb9f7f12fee74c2fb19f9d`. Its source XWD SHA-256 is `a2e42a754e6d581caacc79ef87718fea52e687f03a1506a3b1bd4698e4864dd1`. This establishes **PASS_X11_WINDOW_PATCH_RGB8 for the actual rendered window**, and does not establish sensor/ISP colour correctness or physical HDMI colourimetry.

`decoded_actual.png` is made solely from decoded XWD bytes. The reference PNG is never opened or substituted as actual pixels. Every centre ROI is compared byte-for-byte against the command's explicit RGB tuple; JSON includes per-channel maxima, mismatch count, means/medians/clipping and actual source/data hashes. Empty/missing ROI evidence, unsuccessful/unstable capture, dimension disagreement or an RGB mismatch cannot pass. `--decode-only` returns the explicitly weaker `DECODED_ACTUAL_UNVERIFIED` status. An accepted screenshot is `PASS_X11_WINDOW_PATCH_RGB8`, not proof of HDMI physical colourimetry or FPGA camera correctness.

## Camera stage: original pixels and manually chosen boxes

Actual `evidence/colour_baseline04_last.png` is 640x360 and shows only the ORANGE/CYAN corner with about 90° viewing rotation. It cannot support nine manually distinct centre ROIs. No automatic chart location or artificial nine-box definition was made. Qualitatively, the green-looking ORANGE and magenta-looking CYAN are consistent with an R/G interchange direction, but that is a hypothesis, not a root-cause or completed repair claim.

Root supplies centre boxes on the actual camera image, in its original orientation:

```json
{"coordinate_system":"pixels_xyxy","patches":[
  {"name":"RED","box":[100,100,140,140]},
  {"name":"ORANGE","box":[200,100,240,140]}
]}
```

Those coordinates are schema examples only, not valid measured boxes for the current image. Names for a full chart are RED/GREEN/BLUE/WHITE/GRAY/BLACK/ORANGE/CYAN/MAGENTA. Nonempty in-bounds boxes must not overlap. Use all nine for full-chart scope, or explicitly `--allow-partial` for measured subsets:

```sh
python camera_chart_roi.py --image actual_camera.png --boxes manual_boxes.json \
  --out fresh_camera_analysis_directory
```

The tool reads ordinary images through cv2 and explicitly converts BGR/BGRA to RGB before measuring. Raw `.rgb` input instead requires exact RGB24 width/height/byte length. It performs no resizing, rotation, white balance or pixel correction. JSON records raw RGB means/medians/std/clipping and channel differences/ratios, plus an explicitly assumed sRGB inverse-transfer statistic; actual camera ISP gamma remains unverified. Annotated PNG is a separate overlay copy, never measurement input.

Expected channel-order checks are R dominant for red, G for green, B for blue, R>G>B for orange, G/B>R for cyan and R/B>G for magenta. Thresholds are explicit, and dark ROIs are inconclusive rather than passing. Neutral colours report chroma and white>gray>black brightness order without pretending a calibrated colour-accuracy score. Full channel-order support is a limited colour-plane sanity result, not whole-system acceptance. Partial measurements are clearly labelled partial.

## Low-impact acceptance sequence

1. Hold a chart or controlled solid command; wait for its matching rendered generation and stable successful actual XWD event. Decode/verify that screenshot and preserve PNG/JSON before changing the command.
2. Capture the camera at the same stable colour epoch, preserving original image dimensions/bytes and the command ID. Avoid interpreting transition frames or label/border pixels as colour samples.
3. Prefer a full visible chart for nine centre boxes. If only a corner is visible, a solid full-monitor command can fill that visible corner with each known colour in turn; root can choose a fixed visible-screen centre ROI and collect separate per-epoch partial measurements. Do not combine missing spatial evidence into a fabricated full-chart pass.
4. Only after actual screen pixels and actual camera channel order agree should the result support image-link colour acceptance; preserve remaining colourimetry/gamma and incomplete framing limits explicitly.

This subagent operated only on local files. Actual decoder/ROI board results remain root-owned.
