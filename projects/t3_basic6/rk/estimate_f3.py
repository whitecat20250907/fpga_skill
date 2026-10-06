#!/usr/bin/env python3
"""Offline estimate only: OpenCV surrogate F2 + exact F3 codec on camera data.

OpenCV's histogram mapping may differ from the FPGA's fixed-point LUT. Use
this to size the link and inspect image loss, never as an on-board result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from line_codec import (CONTAINER_ROW_BYTES, WIDTH, decode_gray_row,
                        encode_gray_row)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--yuyv", type=Path, required=True)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--quant-bits", type=int, default=4)
    p.add_argument("--json", type=Path)
    a = p.parse_args()
    raw = a.yuyv.read_bytes()
    needed = WIDTH * a.height * 2
    if len(raw) != needed:
        p.error(f"expected {needed} YUYV bytes, got {len(raw)}")
    gray = np.frombuffer(raw, dtype=np.uint8).reshape(a.height, WIDTH, 2)[:, :, 0]
    gauss = cv2.GaussianBlur(gray, (3, 3), 0,
                             borderType=cv2.BORDER_REPLICATE)
    equalized = cv2.equalizeHist(gauss)
    quantized = equalized & np.uint8((0xFF << a.quant_bits) & 0xFF)
    packed = 0
    rows_lz = 0
    for row in range(a.height):
        container, info = encode_gray_row(equalized[row].tobytes(),
                                          1, row, a.quant_bits)
        restored, _ = decode_gray_row(container)
        if restored != quantized[row].tobytes():
            raise AssertionError(f"row {row} did not roundtrip")
        packed += info["packed_bytes"]
        rows_lz += any(info["lane_modes"])
    diff = equalized.astype(np.int16) - quantized.astype(np.int16)
    mse = float(np.mean(diff.astype(np.float32) ** 2))
    result = {
        "measurement_context": "offline_surrogate_not_fpga",
        "source": str(a.yuyv), "height": a.height,
        "quant_bits": a.quant_bits, "max_quant_error": int(diff.max()),
        "mse_vs_hist_eq": round(mse, 4),
        "psnr_vs_hist_eq_db": round(10 * np.log10(255**2 / mse), 3)
        if mse else None,
        "raw_gray_bytes": WIDTH * a.height,
        "packed_bytes": packed,
        "compression_ratio_vs_gray": round(WIDTH * a.height / packed, 4),
        "wire_bytes": CONTAINER_ROW_BYTES * a.height,
        "wire_savings_vs_original_yuyv": round(
            1 - CONTAINER_ROW_BYTES / (WIDTH * 2), 4),
        "rows_with_at_least_one_lz_lane": rows_lz,
    }
    body = json.dumps(result, ensure_ascii=False, indent=2)
    if a.json:
        a.json.write_text(body + "\n", encoding="utf-8")
    print(body)


if __name__ == "__main__":
    main()
