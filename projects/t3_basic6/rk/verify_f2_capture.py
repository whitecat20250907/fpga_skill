#!/usr/bin/env python3
"""Inspect the F2 grayscale/Gaussian/hist-equalized live YUYV output.

Geometry, grayscale chroma, frame counters and error bits are hardware checks.
The three algorithms' numeric correctness is checked separately in HDL
simulation against a direct reference; this capture cannot recover their
unknown camera input pixels for a byte-exact algorithm comparison.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from parse_fpga_header import FRAME_BYTES
from verify_fpga_monitor import verify


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("capture", type=Path)
    p.add_argument("--json", type=Path)
    a = p.parse_args()
    monitor = verify(a.capture)
    count = monitor["received_frames"]
    data = np.memmap(a.capture, dtype=np.uint8, mode="r",
                     shape=(count, 1080, 1920, 2))
    summaries = []
    for frame in range(count):
        y = data[frame, :, :, 0].copy()
        c = data[frame, :, :, 1].copy()
        y[0, :32] = y[0, 32]
        c[0, :32] = 128
        summaries.append({
            "frame_id": monitor["first_fpga_frame_id"] + frame,
            "chroma_non_128_bytes": int(np.count_nonzero(c != 128)),
            "luma_mean": round(float(y.mean()), 3),
            "luma_std": round(float(y.std()), 3),
            "distinct_luma_levels": int(np.unique(y).size),
            "luma_p05": int(np.percentile(y, 5)),
            "luma_p95": int(np.percentile(y, 95)),
        })
    result = {"monitor": monitor, "frames": summaries,
              "all_payload_chroma_128": all(
                  f["chroma_non_128_bytes"] == 0 for f in summaries)}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if a.json:
        a.json.write_text(text + "\n", encoding="utf-8")
    print(text)
    if not result["all_payload_chroma_128"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
