# RGB chart measurements on every V4L2 frame

`tools/capture_colour_verify.c` is an independent MMAP RGB24 capture tool; existing `capture_verify.c` is unchanged. It accepts the same six arguments plus one manual ROI text file:

```sh
gcc -O2 -std=c11 -Wall -Wextra -Werror -o capture_colour_verify capture_colour_verify.c -lm
./capture_colour_verify --self-test
CAPTURE_SAVE_MODE=bounded COLOUR_STABLE_FRAMES=30 ./capture_colour_verify \
  /dev/videoX 1280 720 1000 evidence/FRESH_RUN/frame 90 manual720_roi.txt \
  >evidence/FRESH_RUN/frames.jsonl 2>evidence/FRESH_RUN/capture.stderr.log
```

Root must choose the actual dynamically identified V4L2 node, current supported dimensions and real chart centre boxes. The parent output directory must already exist, and the filename prefix must be fresh. The tool uses V4L2 S_FMT RGB24 and verifies exact negotiated dimensions, byte stride and sizeimage before four-buffer allocation/queue/STREAMON. It does not write BARs, change the bit, substitute frames, correct colours or interpolate missing frames.

## Manual ROI format

Each line is `NAME x0 y0 x1 y1`, with half-open pixel coordinates on the original camera frame. Blank lines and `#` comments are allowed. Names are RED/GREEN/BLUE/WHITE/GRAY/BLACK/ORANGE/CYAN/MAGENTA. The default requires all nine once; unknown/duplicate/out-of-bounds/overlapping boxes, fewer than16 pixels or fewer than3 rows are rejected. Coordinates are parsed with checked integer conversion. Explicit `COLOUR_ALLOW_PARTIAL=1` permits a measured subset and labels its scope EXPLICIT_PARTIAL_ROIS; it is never a full-chart acceptance.

Choose uniform patch centres after observing the **actual** camera image at the corresponding video mode. Do not use monitor-side coordinates in the camera image or invent boxes for patches outside view. Tilting/rotation requires only that the centre boxes remain inside the actual patch, excluding labels/borders. If the chart moves out of those boxes, flags are measurements of that changed scene rather than proof of a DMA colour failure.

## JSON measurements and flags

A metadata record states dimensions, explicit byte order R,G,B, ROI scope, thresholds and row-field schema. Every dequeued frame has its own record: index, V4L2 sequence/delta/gap, bytesused/exact expected length, ERROR flag, elapsed time, warmup, transport_bad, suspicious and inconclusive. Sequence repeats/skips/backward changes are marked (normal uint32 wrap is accepted). Invalid-size/ERROR frames have `rois:null` rather than measuring stale/partial bytes as valid RGB. No whole-frame green/purple fraction is calculated or used as a verdict.

Every valid frame measures **all pixels in each selected ROI**. Each ROI includes RGB mean, exact zero/255 clipping counts, contrary-order rows, inconclusive rows, adjacent severe-jump rows and maximum temporal mean-channel delta. All ROI rows are retained as compact arrays:

```text
[absolute_y, R_mean, G_mean, B_mean, expected_order_score,
 adjacent_max_channel_jump, dominant, order_status]
```

Dominant codes are R/G/B, Y (R≈G>B), C (G≈B>R), M (R≈B>G), N (near-neutral) and ? (mixed/ambiguous). Expected order scores are min(R−G,R−B) for RED, min(G−R,G−B) for GREEN, min(B−R,B−G) for BLUE, min(R−G,G−B) for ORANGE, min(G−R,B−R) for CYAN, and min(R−G,B−G) for MAGENTA. Positive scores beyond the margin support that row's expected order. Negative scores beyond the margin mark contrary order. Low brightness/chroma or a score within the margin are inconclusive. WHITE/GRAY/BLACK have order_status N: this tool records their RGB/clipping/jumps without pretending to calibrate their luminance/chroma accuracy. Row status E/W/I means expected/contrary/inconclusive.

A selected ROI is suspicious when contrary-order rows reach the explicit threshold, any adjacent-row maximum channel jump reaches its threshold, or a valid previous-frame ROI mean differs sufficiently in one channel. Default one contrary row detects one-/two-line green stripes inside a RED or ORANGE centre; natural green, cyan and magenta patches match their own expected channel orders. Temporal/row jumps can also arise from real scene/exposure changes; the JSON preserves numerical evidence and the flag is not a root-cause assertion.

Default thresholds and controls (all validated and included in metadata):

| Environment | Default | Meaning |
|---|---:|---|
| COLOUR_ORDER_MARGIN | 5 RGB8 levels | Minimum channel-order separation |
| COLOUR_MIN_BRIGHTNESS | 8 | Minimum row maximum RGB8 to interpret colour order |
| COLOUR_MIN_CHROMA | 8 | Minimum row max−min RGB8 to interpret colour order |
| COLOUR_ROW_JUMP | 40 | Adjacent-row maximum absolute channel-mean change |
| COLOUR_TEMPORAL_JUMP | 40 | Successive valid-frame ROI maximum mean-channel change |
| COLOUR_MIN_BAD_ROWS | 1 | Contrary rows that flag an ROI |
| COLOUR_STABLE_FRAMES | 30 | Initial frames labelled warmup, still fully measured/logged/saved |
| COLOUR_SAVE_EVERY | 250 | Periodic raw save interval;0 disables periodic saves |
| COLOUR_ALLOW_PARTIAL | 0 | Explicitly permit incomplete manual chart coverage |

Warmup never deletes or hides frames. Summary separately records all/stable suspicious and inconclusive counts. An entirely dark or fully clipped colour ROI remains inconclusive even if no opposite dominant colour is found.

## Evidence, cleanup and interpretation

CAPTURE_SAVE_MODE defaults bounded: exact first/last dequeued raw frames, periodic raw frames and the first eight flagged raw frames. `all` additionally saves every flagged frame; `none` disables all raw saves but retains every frame's JSON measurements. Save filenames cannot silently overwrite existing evidence. Raw bytes are saved as captured, including a declared bad short packet, with its JSON length/flags. Unexpected driver index or bytesused beyond mapped memory causes a clear failure without reading out of bounds. Deadline/signal/IO failure always attempts STREAMOFF, unmap, buffer release and close; early end retains the last actually captured raw frame when saving is enabled.

Exit0 means **CAPTURE_COMPLETE_MEASUREMENTS_ONLY**: complete requested acquisition without structural transport/sequence/IO errors. It is deliberately not a colour PASS; flags/inconclusive counts and every frame must be reviewed. Missing frames/no data, deadline, signal interruption, packet/sequence errors or IO/save/cleanup failure exit2. No dark/incomplete/unmeasured result is promoted to a complete colour proof.

## Local software validation

Actual Windows MinGW GCC compiles the same portable measurement/ROI functions with `-O2 -std=c11 -Wall -Wextra -Werror -DCOLOUR_SELFTEST_ONLY`; `--self-test` passes28 checks. Fixtures include exact nominal nine-colour chart (natural GREEN/CYAN/MAGENTA not flagged), ORANGE becoming G-dominant, temporal change, one-/two-row green stripes inside RED, low light, all-channel saturation, smooth illumination/tilt gradients, colour borders outside manually selected centres, ROI parser acceptance/negative cases and sequence wrap arithmetic. Selftest-only binaries explicitly refuse actual capture.

Windows lacks Linux V4L2 headers, so this local compile does **not** compile/validate the Linux acquisition backend or count as hardware acceptance. Root must run the stated full GCC command on RK, then selftest and real acquisition. The subagent performs no UART/board operations. Current source hash is recorded in the companion tool manifest supplied to root.
