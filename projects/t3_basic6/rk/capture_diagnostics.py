#!/usr/bin/env python3
"""Capture the PH1A90 CSI-2 stream and diagnose frame content on RK3576.

The elapsed time includes V4L2 startup and file I/O. It is a link smoke test,
not the FPGA physical latency required by contest item 6.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--device", default="/dev/video22")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--frames", type=int, default=30)
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--timeout", type=int, default=35)
    p.add_argument("--json", type=Path)
    args = p.parse_args()
    if args.frames < 1:
        p.error("--frames must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = ["v4l2-ctl", "-d", args.device, "--stream-mmap=4",
               f"--stream-count={args.frames}", f"--stream-to={args.output}"]
    start = time.perf_counter()
    proc = subprocess.run(command, capture_output=True, text=True,
                          timeout=args.timeout)
    elapsed = time.perf_counter() - start
    if proc.returncode:
        raise RuntimeError(f"v4l2-ctl failed ({proc.returncode}): {proc.stderr}")
    frame_bytes = args.width * args.height * 2
    total_bytes = args.output.stat().st_size
    if total_bytes % frame_bytes:
        raise RuntimeError(f"Truncated YUYV data: {total_bytes} bytes")
    count = total_bytes // frame_bytes
    data = np.memmap(args.output, dtype=np.uint8, mode="r",
                     shape=(count, args.height, args.width, 2))
    luma = data[:, :, :, 0]
    chroma = data[:, :, :, 1]
    # Sample separated rows to avoid hashing gigabytes for a simple smoke test.
    samples = luma[:, ::64, ::64]
    hashes = [hashlib.sha256(samples[i].tobytes()).hexdigest()[:16]
              for i in range(count)]
    means = np.mean(samples, axis=(1, 2))
    result = {
        "device": args.device, "format": "YUYV", "width": args.width,
        "height": args.height, "requested_frames": args.frames,
        "received_frames": count, "elapsed_s_including_io": round(elapsed, 3),
        "effective_capture_fps_including_io": round(count / elapsed, 3),
        "frame_bytes": frame_bytes, "total_bytes": total_bytes,
        "unique_sampled_frame_hashes": len(set(hashes)),
        "first_sampled_hash": hashes[0] if hashes else None,
        "last_sampled_hash": hashes[-1] if hashes else None,
        "luma_mean_first": round(float(means[0]), 3) if count else None,
        "luma_mean_last": round(float(means[-1]), 3) if count else None,
        "luma_std_first": round(float(np.std(samples[0])), 3) if count else None,
        "chroma_mean_first": round(float(np.mean(chroma[0, ::64, ::64])), 3)
        if count else None,
        "v4l2_stderr_tail": proc.stderr.strip().splitlines()[-5:],
    }
    text = json.dumps(result, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
