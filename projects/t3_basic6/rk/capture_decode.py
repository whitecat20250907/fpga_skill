#!/usr/bin/env python3
"""Capture PH1A90 four-lane LZ77 CSI container and verify every row CRC.

The CSI format is declared YUYV 1280x1080 only to reuse the RK V4L2 driver;
its bytes are a custom packet stream and must be decoded before inference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np

from line_codec import CONTAINER_ROW_BYTES, WIDTH, decode_gray_row

try:
    from fast_decode import decode_frame as fast_decode_frame
except (ImportError, OSError):
    fast_decode_frame = None


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--device", default="/dev/video22")
    p.add_argument("--frames", type=int, default=3)
    p.add_argument("--warmup", type=int, default=0,
                   help="discard this many initial V4L2 buffers before CRC checks")
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--gray", type=Path, required=True)
    p.add_argument("--json", type=Path)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--decode-only", action="store_true",
                   help="decode an existing --capture file without opening V4L2")
    p.add_argument("--hardware-captured", action="store_true",
                   help="with --decode-only, assert file came from a real board capture")
    p.add_argument("--python-decoder", action="store_true",
                   help="use slow reference decoder even if C++ library is present")
    a = p.parse_args()
    if a.frames < 1 or a.height < 1 or a.warmup < 0:
        p.error("frames and height must be positive; warmup nonnegative")
    if a.hardware_captured and not a.decode_only:
        p.error("--hardware-captured only applies to --decode-only")
    a.capture.parent.mkdir(parents=True, exist_ok=True)
    a.gray.parent.mkdir(parents=True, exist_ok=True)
    if a.decode_only:
        capture_s = 0.0
        stderr_tail = []
    else:
        fmt = subprocess.run(
            ["v4l2-ctl", "-d", a.device,
             "--set-fmt-video=width=1280,height=1080,pixelformat=YUYV"],
            capture_output=True, text=True, timeout=10)
        if fmt.returncode:
            raise RuntimeError("V4L2 format setup failed: " + fmt.stderr)
        t0 = time.perf_counter()
        proc = subprocess.run(
            ["v4l2-ctl", "-d", a.device, "--stream-mmap=4",
             f"--stream-count={a.frames+a.warmup}", f"--stream-to={a.capture}"],
            capture_output=True, text=True, timeout=a.timeout)
        capture_s = time.perf_counter() - t0
        if proc.returncode:
            raise RuntimeError("V4L2 capture failed: " + proc.stderr)
        stderr_tail = proc.stderr.strip().splitlines()[-5:]
    frame_bytes = CONTAINER_ROW_BYTES * a.height
    data = a.capture.read_bytes()
    if len(data) != frame_bytes * (a.frames+a.warmup):
        raise ValueError(
            f"expected {frame_bytes*(a.frames+a.warmup)} bytes, got {len(data)}")
    t1 = time.perf_counter()
    last_gray = bytearray()
    frame_ids = []
    packed_bytes = []
    monitors = []
    for frame in range(a.frames):
        if fast_decode_frame and not a.python_decoder:
            base = (frame+a.warmup) * frame_bytes
            view = np.frombuffer(memoryview(data)[base:base + frame_bytes],
                                 dtype=np.uint8)
            gray_array, info = fast_decode_frame(view, height=a.height)
            gray = gray_array.tobytes()
            row_packed = info["packed_bytes"]
            frame_id = info["frame_id"]
            monitors.append(info if "clock_hz" in info else None)
        else:
            gray = bytearray()
            row_packed = 0
            frame_id = None
            for row in range(a.height):
                base = ((frame+a.warmup) * frame_bytes
                        + row * CONTAINER_ROW_BYTES)
                restored, info = decode_gray_row(
                    data[base:base + CONTAINER_ROW_BYTES])
                if info["row_id"] != row:
                    raise ValueError(f"frame {frame} row {row}: row ID mismatch")
                if frame_id is None:
                    frame_id = info["frame_id"]
                    monitors.append(info.get("fpga_monitor"))
                elif frame_id != info["frame_id"]:
                    raise ValueError(f"frame {frame}: frame ID changed within frame")
                row_packed += info["packed_bytes"]
                gray.extend(restored)
        assert len(gray) == WIDTH * a.height
        frame_ids.append(frame_id)
        packed_bytes.append(row_packed)
        last_gray = gray
    decode_s = time.perf_counter() - t1
    if any(b != a + 1 for a, b in zip(frame_ids, frame_ids[1:])):
        raise ValueError(f"FPGA frame IDs are not consecutive: {frame_ids}")
    overflow_values = [m["bridge_overflow_words"] for m in monitors
                       if m and "bridge_overflow_words" in m]
    a.gray.write_bytes(last_gray)
    result = {
        "capture_origin": ("board_file" if a.hardware_captured else
                           "offline_file") if a.decode_only else "rk_v4l2",
        "decoder": "parallel_cpp" if fast_decode_frame and not a.python_decoder
        else "python_reference",
        "device": None if a.decode_only else a.device,
        "frames_verified": a.frames,
        "warmup_buffers_discarded": a.warmup,
        "frame_ids": frame_ids,
        "row_crc_verified": a.frames * a.height,
        "raw_gray_bytes_per_frame": WIDTH * a.height,
        "packed_bytes_per_frame": packed_bytes,
        "fpga_monitors": monitors,
        "bridge_overflow_words_first": overflow_values[0] if overflow_values else None,
        "bridge_overflow_words_last": overflow_values[-1] if overflow_values else None,
        "bridge_overflow_words_added_during_capture":
            overflow_values[-1] - overflow_values[0] if overflow_values else None,
        "compression_ratio_vs_gray": [
            round(WIDTH * a.height / n, 4) for n in packed_bytes],
        "wire_bytes_per_frame": frame_bytes,
        "wire_savings_vs_original_yuyv": round(
            1 - frame_bytes / (WIDTH * a.height * 2), 4),
        "capture_s_including_file_io": round(capture_s, 4),
        "decode_s": round(decode_s, 4),
        "gray_output": str(a.gray),
        "last_gray_sha256": hashlib.sha256(last_gray).hexdigest(),
        "v4l2_stderr_tail": stderr_tail,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if a.json:
        a.json.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
