"""Byte-exact full-row reference for the four-engine RTL packetizer."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rk"))
from line_codec import encode_gray_row, decode_gray_row  # noqa: E402


def main() -> None:
    rows = [
        bytes(1920),
        bytes((i * 37 + (i // 17) * 11) & 255 for i in range(1920)),
        bytes((i // 32 * 13) & 255 for i in range(1920)),
    ]
    containers = []
    for row_id, gray in enumerate(rows):
        container, info = encode_gray_row(gray, 1, row_id, quant_bits=4)
        restored, decoded = decode_gray_row(container)
        assert restored == bytes(v & 0xF0 for v in gray)
        assert decoded["quant_bits"] == 4
        containers.append(container)
        print(row_id, info)
    out = ROOT / "tb" / "generated"
    out.mkdir(exist_ok=True)
    (out / "lz4_gray_row.hex").write_text(
        "".join(f"{v:02x}\n" for gray in rows for v in gray), encoding="ascii")
    (out / "lz4_expected_row.hex").write_text(
        "".join(f"{v:02x}\n" for container in containers for v in container),
        encoding="ascii")


if __name__ == "__main__":
    main()
