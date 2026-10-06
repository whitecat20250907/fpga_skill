"""Generate independent Python codec vectors for the Verilog lane engine."""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rk"))
from line_codec import delta_encode, lz1_encode  # noqa: E402


def from_delta(values: list[int]) -> bytes:
    out = bytearray()
    value = 0
    for d in values:
        value = (value + d) & 255
        out.append(value)
    return bytes(out)


def write_vectors(n: int, suffix: str) -> None:
    cases = [
        bytes(n),
        bytes(i & 255 for i in range(n)),
        random.Random(4711).randbytes(n),
        from_delta([0] * 10 + [255] + [0] * (n - 11)),
    ]
    out = ROOT / "tb" / "generated"
    out.mkdir(exist_ok=True)
    inputs = b"".join(cases)
    expected = bytearray()
    params = []
    for case in cases:
        delta = delta_encode(case)
        coded = lz1_encode(delta)
        mode = int(len(coded) < n)
        stream = coded if mode else delta
        expected.extend(stream.ljust(n, b"\0"))
        params.append((mode << 9) | len(stream))
    (out / f"lz1_input{suffix}.hex").write_text(
        "".join(f"{x:02x}\n" for x in inputs), encoding="ascii")
    (out / f"lz1_expected{suffix}.hex").write_text(
        "".join(f"{x:02x}\n" for x in expected), encoding="ascii")
    (out / f"lz1_params{suffix}.hex").write_text(
        "".join(f"{x:04x}\n" for x in params), encoding="ascii")
    print(n, [(p >> 9, p & 511) for p in params])


def main() -> None:
    write_vectors(32, "")
    write_vectors(480, "_480")


if __name__ == "__main__":
    main()
