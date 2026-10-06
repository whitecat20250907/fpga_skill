#!/usr/bin/env python3
"""Run the supplied RK3576 YOLOv5s model on a captured FPGA CSI-2 frame.

This is an R2 smoke/latency test. A TPG frame validates the data path and NPU
runtime; face/person detection needs real camera frames from F1/R1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

import cv2
import numpy as np
from rknnlite.api import RKNNLite
from vendor_yolov5s_relu import letterbox, postprocess_yolov5s


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered)-1, round((len(ordered)-1)*p))]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--frame", type=Path,
                        help="raw YUYV frame or decoded gray frame")
    source.add_argument("--image", type=Path,
                        help="offline RGB/JPEG/PNG model fixture; not FPGA evidence")
    parser.add_argument("--gray", action="store_true",
                        help="--frame is WIDTH*HEIGHT grayscale bytes")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    if args.image:
        if args.gray:
            parser.error("--gray cannot be combined with --image")
        bgr = cv2.imread(str(args.image))
        if bgr is None:
            parser.error(f"Cannot read image: {args.image}")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        input_format = "RGB_IMAGE_OFFLINE"
    else:
        frame = args.frame.read_bytes()
        needed = args.width * args.height * (1 if args.gray else 2)
        if len(frame) != needed:
            parser.error(f"Expected exactly {needed} bytes, got {len(frame)}")
        if args.gray:
            gray = np.frombuffer(frame, dtype=np.uint8).reshape(
                args.height, args.width)
        else:
            gray = np.frombuffer(frame, dtype=np.uint8).reshape(
                args.height, args.width, 2)[:, :, 0]
        rgb = np.repeat(gray[:, :, None], 3, axis=2)
        height, width = args.height, args.width
        input_format = "GRAY8" if args.gray else "YUYV"
    t0 = time.perf_counter()
    padded, ratio, dw, dh = letterbox(rgb, 640)
    input_data = np.expand_dims(padded, axis=0)
    preprocess_ms = (time.perf_counter() - t0) * 1000

    npu = RKNNLite()
    try:
        if npu.load_rknn(str(args.model)):
            raise RuntimeError("RKNN model failed to load")
        if npu.init_runtime(core_mask=RKNNLite.NPU_CORE_0):
            raise RuntimeError("RK3576 NPU runtime failed to initialize")
        # First call includes cache/setup overhead, so report it separately.
        durations = []
        outputs = None
        for _ in range(args.runs + 1):
            t1 = time.perf_counter()
            outputs = npu.inference(inputs=[input_data])
            durations.append((time.perf_counter()-t1)*1000)
            if outputs is None or any(x is None for x in outputs):
                raise RuntimeError("NPU returned no output")
        t2 = time.perf_counter()
        boxes, scores, classes = postprocess_yolov5s(outputs, ratio, dw, dh,
                                                       width, height)
        postprocess_ms = (time.perf_counter()-t2)*1000
    finally:
        npu.release()

    steady = durations[1:]
    result = {
        "source": str(args.image or args.frame), "model": str(args.model),
        "input_file_sha256": hashlib.sha256(
            (args.image or args.frame).read_bytes()).hexdigest(),
        "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
        "width": width, "height": height, "runs": args.runs,
        "input_format": input_format,
        "preprocess_ms": round(preprocess_ms, 3),
        "first_inference_ms": round(durations[0], 3),
        "npu_ms_median": round(statistics.median(steady), 3),
        "npu_ms_p95": round(percentile(steady, 0.95), 3),
        "postprocess_ms": round(postprocess_ms, 3),
        "output_shapes": [list(x.shape) for x in outputs],
        "detections": [
            {"xyxy": box.tolist(), "score": round(float(score), 4),
             "class_id": int(class_id)}
            for box, score, class_id in zip(boxes, scores, classes)
        ],
    }
    body = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(body+"\n", encoding="utf-8")
    print(body)


if __name__ == "__main__":
    main()
