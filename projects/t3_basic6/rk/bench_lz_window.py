"""Estimate whether a larger LZ77 window justifies extra FPGA comparators."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from line_codec import WIDTH, delta_encode


def size_lz(src: bytes, window: int, max_length: int = 18) -> int:
    size = 0
    i = 0
    while i < len(src):
        best = 0
        max_off = min(window, i)
        for off in range(1, max_off + 1):
            if src[i] != src[i - off]:
                continue
            n = 1
            while (n < max_length and i + n < len(src) and
                   src[i + n] == src[i + n - off]):
                n += 1
            if n > best:
                best = n
                if best == max_length:
                    break
        if best >= 3:
            size += 3  # escape, length, offset
            i += best
        else:
            size += 2 if src[i] == 0xFF else 1
            i += 1
    return min(size, len(src))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("frame", type=Path)
    p.add_argument("--rows", type=int, default=50)
    a = p.parse_args()
    gray = np.frombuffer(a.frame.read_bytes(), dtype=np.uint8)
    gray = gray.reshape(1080, WIDTH, 2)[:, :, 0]
    gauss = cv2.GaussianBlur(gray, (3, 3), 0,
                             borderType=cv2.BORDER_REPLICATE)
    eq = cv2.equalizeHist(gauss)
    for name, image in (("camera", gray), ("gauss", gauss), ("histeq", eq)):
        rows = image[:a.rows]
        for quant in (1, 4):
            original = 0
            totals = {1: 0, 4: 0, 16: 0, 64: 0}
            for row in rows:
                if quant != 1:
                    row = (row // quant) * quant
                raw = row.tobytes()
                original += len(raw)
                for lane in range(4):
                    delta = delta_encode(raw[lane::4])
                    for window in totals:
                        totals[window] += size_lz(delta, window)
            print(name, f"quant={quant}",
                  {window: round(original / size, 3)
                   for window, size in totals.items()})


if __name__ == "__main__":
    main()
