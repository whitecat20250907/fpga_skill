#!/usr/bin/env python3
"""Read F5's 64-byte diagnostic header from one 1920x1080 YUYV frame."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

FRAME_BYTES = 1920 * 1080 * 2
HEADER = struct.Struct("<4sIIIQQQIIIIII")


def parse(frame: bytes) -> dict:
    if len(frame) not in (HEADER.size, FRAME_BYTES):
        raise ValueError(f"frame/header size {len(frame)} is invalid")
    (magic, version, frame_id, flags, sof_ticks, period_ticks,
     prev_span_ticks, rows, words, nominal_hz, header_size,
     reserved0, reserved1) = HEADER.unpack_from(frame)
    if magic != b"FPGA" or version != 1 or header_size != 64:
        raise ValueError("missing/invalid FPGA diagnostic header")
    if reserved0 or reserved1:
        raise ValueError("nonzero reserved fields")
    return {
        "frame_id": frame_id,
        "sof_ticks": sof_ticks,
        "previous_sof_period_ticks": period_ticks,
        "previous_frame_span_ticks": prev_span_ticks,
        "previous_rows": rows,
        "previous_64bit_words": words,
        "lane_error_sticky": flags & 0xF,
        "bridge_overflow_sticky": bool(flags & (1 << 9)),
        "processing_error_sticky": bool(flags & (1 << 10)),
        "nominal_rx_clock_hz": nominal_hz,
        "previous_fps_from_nominal_clock": round(nominal_hz / period_ticks, 3)
        if period_ticks else None,
        "previous_frame_span_us_from_nominal_clock":
            round(prev_span_ticks * 1_000_000 / nominal_hz, 3)
            if nominal_hz and prev_span_ticks else None,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("frame", type=Path)
    a = p.parse_args()
    print(json.dumps(parse(a.frame.read_bytes()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
