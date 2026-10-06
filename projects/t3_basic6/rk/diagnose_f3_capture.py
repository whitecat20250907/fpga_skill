#!/usr/bin/env python3
"""Audit a raw FPGA container capture, including incomplete startup buffers."""

from __future__ import annotations

import argparse
import json
import struct
from collections import Counter
from pathlib import Path

from line_codec import CONTAINER_ROW_BYTES, HEADER, WIDTH, decode_gray_row


def invalid_literals(row: bytes, modes: tuple[int, ...],
                     lengths: tuple[int, ...], quant_bits: int) -> list[dict]:
    bad = []
    for lane in range(4):
        stream = b"".join(
            row[32 + pair*8 + lane*2:34 + pair*8 + lane*2]
            for pair in range(WIDTH // 8))[:lengths[lane]]
        if not modes[lane]:
            values = enumerate(stream)
        else:
            literals = []
            pos = 0
            while pos < len(stream):
                if stream[pos] == 0xFF:
                    pos += 2
                else:
                    literals.append((pos, stream[pos]))
                    pos += 1
            values = literals
        for pos, value in values:
            if value & ((1 << quant_bits) - 1):
                bad.append({"lane": lane, "offset": pos,
                            "value": value, "low_bits": value & ((1 << quant_bits) - 1)})
    return bad


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    data = args.capture.read_bytes()
    if len(data) % CONTAINER_ROW_BYTES:
        parser.error("Capture length is not an integer number of container rows")
    frames: dict[str, dict] = {}
    bad_examples = []
    corrupt_bits = Counter()
    jumps = []
    previous = None
    for index in range(len(data) // CONTAINER_ROW_BYTES):
        row = data[index*CONTAINER_ROW_BYTES:(index+1)*CONTAINER_ROW_BYTES]
        header = HEADER.unpack_from(row)
        frame_id, row_id = header[4], header[3]
        key = str(frame_id)
        summary = frames.setdefault(key, {"rows": 0, "crc_pass": 0,
                                           "crc_fail": 0, "row_first": row_id,
                                           "row_last": row_id})
        summary["rows"] += 1
        summary["row_last"] = row_id
        if previous is not None and ((frame_id == previous[0] and row_id != previous[1]+1)
                                     or (frame_id != previous[0] and row_id != 0)):
            jumps.append({"capture_row": index, "previous": previous,
                          "current": [frame_id, row_id]})
        previous = [frame_id, row_id]
        try:
            decode_gray_row(row)
            summary["crc_pass"] += 1
        except ValueError as exc:
            summary["crc_fail"] += 1
            violations = invalid_literals(row, header[7:11], header[11:15],
                                          header[2] >> 4)
            for item in violations:
                corrupt_bits[(item["lane"], item["offset"], item["low_bits"])] += 1
            if len(bad_examples) < 16:
                bad_examples.append({"capture_row": index,
                                     "frame_id": frame_id,
                                     "row_id": row_id,
                                     "error": str(exc),
                                     "invalid_literals": violations[:4]})
    result = {"source": str(args.capture),
              "capture_origin": "board_file_requires_user_assertion",
              "rows_total": len(data) // CONTAINER_ROW_BYTES,
              "frames": frames, "row_sequence_jumps": jumps[:16],
              "bad_examples": bad_examples,
              "invalid_literal_patterns": [
                  {"lane": lane, "offset": offset, "low_bits": low, "count": count}
                  for (lane, offset, low), count in sorted(corrupt_bits.items())]}
    body = json.dumps(result, indent=2)
    if args.json:
        args.json.write_text(body + "\n", encoding="utf-8")
    print(body)


if __name__ == "__main__":
    main()
