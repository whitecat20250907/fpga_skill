#!/usr/bin/env python3
"""Reference wire format for four parallel, line-local LZ77 encoders.

Each engine sees every fourth gray pixel, applies an 8-bit row delta and may
emit offset-one LZ77 matches (3..130 bytes). 0xFF is the escape byte: 0xFF,0
encodes a literal 0xFF and 0xFF,0x80|(length-3) encodes a match at offset 1.
This first hardware-friendly profile deliberately has only offset 1.
Rows fall back to stored mode when LZ77 would expand. A 2560-byte YUYV row
carries a 32-byte header plus four 480-byte striped lanes and zero padding.
Each 8-byte stripe contains two bytes from each lane, matching the FPGA's
four two-byte/cycle readers. Header flag bit 0 identifies this layout.
"""

from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path

WIDTH = 1920
CONTAINER_ROW_BYTES = 1280 * 2
HEADER = struct.Struct("<4sBBHIHH4B4HI")
assert HEADER.size == 32
MONITOR = struct.Struct("<4sBBHIQQIII")
assert MONITOR.size == 40


def delta_encode(src: bytes) -> bytes:
    prev = 0
    out = bytearray()
    for value in src:
        out.append((value - prev) & 255)
        prev = value
    return bytes(out)


def delta_decode(src: bytes) -> bytes:
    value = 0
    out = bytearray()
    for d in src:
        value = (value + d) & 255
        out.append(value)
    return bytes(out)


def lz1_encode(src: bytes) -> bytes:
    """Greedy offset-one LZ77 subset, with 0xFF escape for token/literal."""
    out = bytearray()
    i = 0
    while i < len(src):
        match = 0
        if i and i + 2 < len(src) and src[i] == src[i - 1] == src[i + 1] == src[i + 2]:
            match = 3
            while match < 130 and i + match < len(src) and src[i + match] == src[i + match - 1]:
                match += 1
        if match:
            out.extend((0xFF, 0x80 | (match - 3)))
            i += match
        else:
            out.append(src[i])
            if src[i] == 0xFF:
                out.append(0)
            i += 1
    return bytes(out)


def lz1_decode(src: bytes, expected: int) -> bytes:
    out = bytearray()
    i = 0
    while i < len(src):
        value = src[i]
        i += 1
        if value == 0xFF:
            if i >= len(src):
                raise ValueError("truncated escape")
            ctrl = src[i]
            i += 1
            if ctrl == 0:
                out.append(0xFF)
            elif ctrl & 0x80 and out:
                out.extend(bytes((out[-1],)) * ((ctrl & 0x7F) + 3))
            else:
                raise ValueError("invalid LZ77 token")
        else:
            out.append(value)
        if len(out) > expected:
            raise ValueError("decoded lane too long")
    if len(out) != expected:
        raise ValueError("decoded lane has wrong length")
    return bytes(out)


def encode_gray_row(gray: bytes, frame_id: int, row_id: int,
                    quant_bits: int = 0) -> tuple[bytes, dict]:
    if len(gray) != WIDTH:
        raise ValueError(f"expected {WIDTH} gray pixels")
    if not 0 <= quant_bits <= 7:
        raise ValueError("quant_bits must be 0..7")
    gray = bytes(value & (0xFF << quant_bits) for value in gray)
    streams = []
    modes = []
    for lane in range(4):
        delta = delta_encode(gray[lane::4])
        packed = lz1_encode(delta)
        use_lz = len(packed) < len(delta)
        modes.append(int(use_lz))
        streams.append(packed if use_lz else delta)
    lengths = [len(s) for s in streams]
    packed_bytes = sum(lengths)
    header = HEADER.pack(b"LZ4R", 1, 1 | quant_bits << 4,
                         row_id, frame_id,
                         WIDTH, packed_bytes, *modes, *lengths,
                         zlib.crc32(gray))
    padded = [stream.ljust(WIDTH // 4, b"\0") for stream in streams]
    body = header + b"".join(
        padded[lane][pair * 2:pair * 2 + 2]
        for pair in range(WIDTH // 8) for lane in range(4))
    if len(body) > CONTAINER_ROW_BYTES:
        raise ValueError("compressed row exceeds 1280-pixel YUYV container")
    info = {"frame_id": frame_id, "row_id": row_id,
            "raw_gray_bytes": WIDTH, "packed_bytes": packed_bytes,
            "wire_bytes": CONTAINER_ROW_BYTES, "lane_modes": modes,
            "lane_lengths": lengths, "crc32": zlib.crc32(gray),
            "quant_bits": quant_bits}
    return body.ljust(CONTAINER_ROW_BYTES, b"\0"), info


def decode_gray_row(container: bytes) -> tuple[bytes, dict]:
    if len(container) != CONTAINER_ROW_BYTES:
        raise ValueError("wrong container row size")
    unpacked = HEADER.unpack_from(container)
    (magic, version, flags, row_id, frame_id, raw_bytes, packed_bytes,
     *tail) = unpacked
    modes, lengths, crc32 = tail[:4], tail[4:8], tail[8]
    if (magic != b"LZ4R" or version != 1 or flags & 15 != 1
            or raw_bytes != WIDTH):
        raise ValueError("invalid row header")
    if sum(lengths) != packed_bytes or any(n > WIDTH // 4 for n in lengths):
        raise ValueError("invalid lane lengths")
    if HEADER.size + WIDTH > len(container):
        raise ValueError("truncated striped payload")
    lanes = []
    striped = container[HEADER.size:HEADER.size + WIDTH]
    for lane, (mode, length) in enumerate(zip(modes, lengths)):
        stream = b"".join(striped[pair * 8 + lane * 2:
                                  pair * 8 + lane * 2 + 2]
                          for pair in range(WIDTH // 8))[:length]
        if mode == 1:
            delta = lz1_decode(stream, WIDTH // 4)
        elif mode == 0 and length == WIDTH // 4:
            delta = stream
        else:
            raise ValueError("unsupported lane mode or stored length")
        lanes.append(delta_decode(delta))
    gray = bytearray(WIDTH)
    for lane, stream in enumerate(lanes):
        gray[lane::4] = stream
    if zlib.crc32(gray) != crc32:
        raise ValueError("row CRC32 mismatch")
    info = {"frame_id": frame_id, "row_id": row_id,
            "packed_bytes": packed_bytes,
            "lane_modes": list(modes), "quant_bits": flags >> 4}
    monitor_offset = HEADER.size + WIDTH
    if row_id == 0 and container[monitor_offset:monitor_offset + 4] == b"TICK":
        (magic, monitor_version, error_flags, _reserved, monitor_frame_id,
         sof_tick, packet_tick, prev_period, clock_hz,
         overlap_count) = MONITOR.unpack_from(container, monitor_offset)
        if monitor_version != 1 or monitor_frame_id != frame_id:
            raise ValueError("invalid FPGA monitor record")
        info["fpga_monitor"] = {
            "sensor_csi_sof_tick": sof_tick,
            "packet_start_tick": packet_tick,
            "previous_frame_period_ticks": prev_period,
            "clock_hz": clock_hz,
            "overlap_count": overlap_count,
            "error_flags": error_flags,
            "fpga_pipeline_us": round((packet_tick - sof_tick) * 1e6 / clock_hz, 3)
            if packet_tick >= sof_tick and clock_hz else None,
            "measured_input_fps": round(clock_hz / prev_period, 3)
            if prev_period else None,
        }
        if container[1992:1996] == b"OVFL":
            info["fpga_monitor"]["bridge_overflow_words"] = (
                struct.unpack_from("<I", container, 2000)[0])
    return bytes(gray), info


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--yuyv", type=Path, help="one 1920x1080 YUYV camera frame")
    p.add_argument("--rows", type=int, default=1080)
    p.add_argument("--quant-bits", type=int, default=4)
    p.add_argument("--output", type=Path,
                   help="write encoded CSI container rows for decoder tests")
    a = p.parse_args()
    if not a.yuyv:
        p.error("--yuyv is required")
    frame = a.yuyv.read_bytes()
    if len(frame) != WIDTH * 1080 * 2:
        p.error("YUYV frame size is not 1920x1080")
    packed = 0
    output = a.output.open("wb") if a.output else None
    for row in range(min(a.rows, 1080)):
        yuyv = frame[row * WIDTH * 2:(row + 1) * WIDTH * 2]
        gray = yuyv[0::2]
        container, stats = encode_gray_row(gray, 1, row, a.quant_bits)
        restored, decoded = decode_gray_row(container)
        expected = bytes(value & (0xFF << a.quant_bits) for value in gray)
        assert restored == expected and decoded["row_id"] == row
        if output:
            output.write(container)
        packed += stats["packed_bytes"]
    if output:
        output.close()
    rows = min(a.rows, 1080)
    print(json.dumps({"rows": rows, "raw_gray_bytes": rows * WIDTH,
                      "packed_bytes": packed,
                      "compression_ratio": round(rows * WIDTH / packed, 4),
                      "wire_bytes": rows * CONTAINER_ROW_BYTES,
                      "wire_savings_vs_yuyv": round(
                          1 - CONTAINER_ROW_BYTES / (WIDTH * 2), 4)},
                     indent=2))


if __name__ == "__main__":
    main()
