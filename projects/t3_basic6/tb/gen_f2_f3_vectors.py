"""Independent 3x3 Gaussian + line codec vectors for final-row integration."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rk"))
from line_codec import encode_gray_row  # noqa: E402


def main() -> None:
    rows = [bytes((x * 7) & 255 for x in range(1920)),
            bytes((x * 5 + 30) & 255 for x in range(1920))]
    gaussian = []
    for y in range(2):
        out = bytearray()
        for x in range(1920):
            total = 0
            for dy, wy in ((-1, 1), (0, 2), (1, 1)):
                sy = min(1, max(0, y + dy))
                for dx, wx in ((-1, 1), (0, 2), (1, 1)):
                    sx = min(1919, max(0, x + dx))
                    total += wy * wx * rows[sy][sx]
            out.append((total + 8) >> 4)
        gaussian.append(bytes(out))
    containers = [encode_gray_row(gray, 1, row, 4)[0]
                  for row, gray in enumerate(gaussian)]
    out = ROOT / "tb" / "generated"
    out.mkdir(exist_ok=True)
    (out / "f2_f3_input.hex").write_text(
        "".join(f"{v:02x}\n" for row in rows for v in row), encoding="ascii")
    (out / "f2_f3_expected.hex").write_text(
        "".join(f"{v:02x}\n" for row in containers for v in row),
        encoding="ascii")


if __name__ == "__main__":
    main()
