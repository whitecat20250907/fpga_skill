#!/usr/bin/env python3
"""Live FPGA CSI-2 container -> parallel decode -> RK3576 NPU detections.

The appsink drops old frames while inference is slower than the 60 Hz camera.
Use capture_decode.py separately for lossless link/frame-count verification.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
from rknnlite.api import RKNNLite

from fast_decode import decode_frame
from vendor_yolov5s_relu import CLASS_NAMES, letterbox, postprocess_yolov5s


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--device", default="/dev/video22")
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--frames", type=int, default=30)
    p.add_argument("--warmup", type=int, default=1,
                   help="discard initial V4L2 buffers before decode/inference")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--json", type=Path)
    a = p.parse_args()
    if a.frames < 1 or a.warmup < 0:
        p.error("--frames must be positive and --warmup nonnegative")
    fmt = subprocess.run(
        ["v4l2-ctl", "-d", a.device,
         "--set-fmt-video=width=1280,height=1080,pixelformat=YUYV"],
        capture_output=True, text=True, timeout=10)
    if fmt.returncode:
        raise RuntimeError("Cannot set FPGA container format: " + fmt.stderr)
    pipeline = (f"v4l2src device={a.device} io-mode=2 ! "
                "video/x-raw,format=YUY2,width=1280,height=1080 ! "
                "appsink max-buffers=1 drop=true sync=false")
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    if not cap.isOpened():
        raise RuntimeError("Cannot open raw V4L2/GStreamer CSI capture")
    npu = RKNNLite()
    records = []
    overflow_baseline = None
    try:
        if npu.load_rknn(str(a.model)):
            raise RuntimeError("Cannot load RKNN model")
        if npu.init_runtime(core_mask=RKNNLite.NPU_CORE_0):
            raise RuntimeError("Cannot initialize RK3576 NPU")
        for _ in range(a.warmup):
            ok, _discard = cap.read()
            if not ok:
                raise RuntimeError("V4L2 failed during warmup")
        loop_start = time.perf_counter()
        for index in range(a.frames):
            read_start = time.perf_counter()
            ok, container = cap.read()
            capture_ms = (time.perf_counter() - read_start) * 1000
            if not ok or container.shape != (1080, 1280, 2):
                raise RuntimeError(f"Unexpected raw V4L2 frame: {None if not ok else container.shape}")
            gray, meta = decode_frame(container, workers=a.workers)
            if meta["error_flags"] & ~8 or meta.get("overlap_count", 0):
                raise RuntimeError(f"FPGA reported error on frame {meta['frame_id']}: {meta}")
            overflow_words = meta.get("bridge_overflow_words")
            if overflow_words is None:
                raise RuntimeError("Final FPGA overflow counter is absent")
            if overflow_baseline is None:
                overflow_baseline = overflow_words
            elif overflow_words != overflow_baseline:
                raise RuntimeError(
                    f"FPGA bridge dropped new words during live inference: "
                    f"{overflow_baseline} -> {overflow_words}")
            t0 = time.perf_counter()
            rgb = np.repeat(gray[:, :, None], 3, axis=2)
            padded, ratio, dw, dh = letterbox(rgb, 640)
            input_data = np.expand_dims(padded, axis=0)
            preprocess_ms = (time.perf_counter() - t0) * 1000
            t1 = time.perf_counter()
            outputs = npu.inference(inputs=[input_data])
            npu_ms = (time.perf_counter() - t1) * 1000
            if outputs is None:
                raise RuntimeError("NPU returned no outputs")
            t2 = time.perf_counter()
            boxes, scores, classes = postprocess_yolov5s(
                outputs, ratio, dw, dh, 1920, 1080)
            postprocess_ms = (time.perf_counter() - t2) * 1000
            detections = [{"class_id": int(cid),
                           "class_name": CLASS_NAMES[int(cid)]
                           if int(cid) < len(CLASS_NAMES) else str(cid),
                           "score": round(float(score), 4),
                           "xyxy": box.tolist()}
                          for box, score, cid in zip(boxes, scores, classes)]
            record = {"rk_index": index, **meta,
                      "capture_wait_ms": round(capture_ms, 3),
                      "preprocess_ms": round(preprocess_ms, 3),
                      "npu_ms": round(npu_ms, 3),
                      "postprocess_ms": round(postprocess_ms, 3),
                      "detections": detections}
            records.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
        loop_s = time.perf_counter() - loop_start
    finally:
        cap.release()
        npu.release()
    summary = {
        "source": "live_fpga_csi2_compressed",
        "frames_decoded_and_inferred": len(records),
        "warmup_buffers_discarded": a.warmup,
        "bridge_overflow_words_at_first_verified_frame": overflow_baseline,
        "bridge_overflow_words_added_during_run": 0,
        "frame_ids": [r["frame_id"] for r in records],
        "total_detections": sum(len(r["detections"]) for r in records),
        "median_decode_ms": round(statistics.median(r["decode_ms"] for r in records), 3),
        "median_npu_ms": round(statistics.median(r["npu_ms"] for r in records), 3),
        "median_processing_ms": round(statistics.median(
            r["decode_ms"] + r["preprocess_ms"] + r["npu_ms"]
            + r["postprocess_ms"] for r in records), 3),
        "effective_app_fps": round(len(records) / loop_s, 3),
        "records": records,
    }
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "records"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
