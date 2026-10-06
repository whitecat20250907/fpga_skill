#!/usr/bin/env python3
"""Check every byte of one captured YUYV frame from s0_tx_probe.

Example on RK3576:
  v4l2-ctl -d /dev/video22 --set-fmt-video=width=1920,height=1080,pixelformat=YUYV
  v4l2-ctl -d /dev/video22 --stream-mmap=3 --stream-count=1 --stream-to=frame.yuyv
  python3 verify_tpg.py frame.yuyv --width 1920 --height 1080

Y and chroma byte order is part of the link contract; a visible picture alone
cannot prove that the FPGA-to-RK data stream is byte exact.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def verify(frame: bytes, width: int, height: int, stride: int) -> tuple[int, list[str]]:
    if width <= 0 or width % 2 or height <= 0 or stride < 2 * width:
        raise ValueError("Need even positive width, positive height, and stride >= 2*width")
    required = stride * height
    if len(frame) < required:
        raise ValueError(f"Incomplete frame: {len(frame)} bytes, need {required}")
    errors = 0
    samples: list[str] = []
    for y in range(height):
        row = frame[y * stride : y * stride + 2 * width]
        for x in range(0, width, 2):
            actual = row[2*x : 2*x+4]
            expected = bytes((x & 255, 128, (x + 1) & 255, 128))
            if actual != expected:
                errors += 1
                if len(samples) < 12:
                    samples.append(f"row={y} x={x}: got={actual.hex()} expected={expected.hex()}")
    return errors, samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frame", type=Path)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--stride", type=int, default=0)
    args = parser.parse_args()
    stride = args.stride or args.width * 2
    data = args.frame.read_bytes()
    frame_size = stride * args.height
    if len(data) % frame_size:
        parser.error(f"File size {len(data)} is not a multiple of frame size {frame_size}")
    total_errors = 0
    samples = []
    count = len(data) // frame_size
    for i in range(count):
        errors, found = verify(data[i*frame_size:(i+1)*frame_size],
                               args.width, args.height, stride)
        total_errors += errors
        samples.extend(f"frame={i} {x}" for x in found[:max(0, 12-len(samples))])
    print(f"Checked {count} frames, {count*args.width//2*args.height} YUYV words; "
          f"errors={total_errors}")
    for item in samples:
        print(item)
    raise SystemExit(1 if total_errors else 0)


if __name__ == "__main__":
    main()
