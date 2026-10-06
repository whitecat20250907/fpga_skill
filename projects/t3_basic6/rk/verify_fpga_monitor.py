#!/usr/bin/env python3
"""Check FPGA frame counters/timing embedded in a raw V4L2 YUYV capture."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from parse_fpga_header import FRAME_BYTES, parse


def verify(capture: Path) -> dict:
    size = capture.stat().st_size
    if size % FRAME_BYTES:
        raise ValueError(f"capture truncated: {size} bytes")
    count = size // FRAME_BYTES
    if count < 2:
        raise ValueError("at least two frames required for period/geometry checks")
    headers = []
    with capture.open("rb") as stream:
        for _ in range(count):
            header = stream.read(64)
            headers.append(parse(header))
            stream.seek(FRAME_BYTES - 64, 1)
    # First frame after programming has no previous-frame statistics.
    bad_geometry = [i for i, h in enumerate(headers[1:], start=1)
                    if h["previous_rows"] != 1080 or
                    h["previous_64bit_words"] != 518400]
    lost = []
    for i in range(1, count):
        delta = (headers[i]["frame_id"] - headers[i-1]["frame_id"]) & 0xFFFFFFFF
        if delta != 1:
            lost.append({"rk_index": i, "fpga_frame_id_gap": delta})
    periods = [h["previous_sof_period_ticks"] for h in headers[1:]
               if h["previous_sof_period_ticks"]]
    hz = headers[0]["nominal_rx_clock_hz"]
    result = {
        "received_frames": count,
        "first_fpga_frame_id": headers[0]["frame_id"],
        "last_fpga_frame_id": headers[-1]["frame_id"],
        "lost_or_duplicated_frames": lost,
        "bad_previous_frame_geometry_indices": bad_geometry,
        "lane_error_frames": [i for i, h in enumerate(headers)
                              if h["lane_error_sticky"]],
        "bridge_overflow_frames": [i for i, h in enumerate(headers)
                                   if h["bridge_overflow_sticky"]],
        "processing_error_frames": [i for i, h in enumerate(headers)
                                    if h["processing_error_sticky"]],
        "median_sof_period_ticks": round(statistics.median(periods)) if periods else None,
        "median_fpga_fps_from_nominal_clock":
            round(hz / statistics.median(periods), 4) if periods else None,
        "nominal_rx_clock_hz": hz,
        "caveat": "RX clock value is from sensor mode table, not instrument-calibrated",
    }
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("capture", type=Path)
    p.add_argument("--json", type=Path)
    a = p.parse_args()
    result = verify(a.capture)
    body = json.dumps(result, ensure_ascii=False, indent=2)
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(body + "\n", encoding="utf-8")
    print(body)
    if (result["lost_or_duplicated_frames"] or
        result["bad_previous_frame_geometry_indices"] or
        result["lane_error_frames"] or result["bridge_overflow_frames"] or
        result["processing_error_frames"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
