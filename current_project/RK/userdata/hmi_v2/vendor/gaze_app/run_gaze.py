"""Fixed-head gaze cursor demo using the original GazeFollower components."""
from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import importlib.metadata
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import cv2
import numpy as np
import pygame

sys.path.insert(0,str(Path(__file__).resolve().parent / "GazeFollower"))
from desktop_input import X11Input, DwellClick, display_geometry, chinese_font

from gaze_runtime import (ROOT, REPO, MODEL_DIR, CameraWorker, Pipeline,
                          calibration_points, validation_points, validation_metrics,
                          load_settings, make_calibration, make_filter, open_camera, screen_size)
from region8 import RegionDecider, to_cell
from shared_preview import PreviewSelector

TITLE = "MGazeNet - Fixed Head Gaze Cursor"

# 「头不动、尽量精确」模式：不改 settings.json，用 --precise / start_precise.cmd 切进来。
# 相对默认配置只动三处：
#   calibration_grid            3 -> 5   13 点 -> 25 点（边距 3%，把屏幕四角纳入标定）
#   calibration_samples_per_point 30 -> 90  每点多采 3 倍，压低逐点抖动
#   region_mode            true -> false  关掉 8x8 吸附，直接输出连续坐标
# 注意：25 点 x 90 帧，标定一次约 2 分钟（每点 1.5s 稳定 + 约 3s 采样），请保持头部不动。
PRECISE_OVERRIDES = {
    "calibration_grid": 5,
    "calibration_samples_per_point": 90,
    "region_mode": False,
}


def model_metadata(settings):
    model = Path(settings["model_path"]) if settings["model_path"] else MODEL_DIR / "original_gaze_fp16.rknn"
    if not model.is_absolute():
        model = ROOT / model
    return {"path": str(model), "bytes": model.stat().st_size,
            "sha256": hashlib.sha256(model.read_bytes()).hexdigest()}


def self_check(settings, report_path):
    report = {"python": sys.version, "executable": sys.executable,
              "packages": {name: importlib.metadata.version(name)
                           for name in ("rknn-toolkit-lite2", "mediapipe", "numpy", "opencv-contrib-python", "pygame")},
              "model": model_metadata(settings), "display": display_geometry(settings.get("monitor", "HDMI-1")),
              "settings": settings}
    image = cv2.imread(str(REPO / "tests" / "asset" / "example.jpg"))
    if image is None:
        raise RuntimeError("Upstream test image is missing.")
    pipeline = Pipeline(settings)
    durations = []
    try:
        for index in range(25):
            start = time.perf_counter()
            _, gaze, valid, _ = pipeline.infer(image, time.monotonic_ns())
            elapsed = (time.perf_counter() - start) * 1000
            if not valid or gaze.features.shape != (258,):
                raise RuntimeError("Image inference did not produce 258 valid gaze features.")
            if index >= 5:
                durations.append(elapsed)
        report["offline_image_pipeline"] = {
            "passed": True, "feature_dimensions": len(gaze.features),
            "mean_ms": float(np.mean(durations)), "p90_ms": float(np.percentile(durations, 90)),
            "note": "Repeated repository image; excludes camera capture, calibration, filtering and display."}
    finally:
        pipeline.close()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def camera_check(settings, report_path):
    cap = open_camera(settings)
    pipeline = None
    records = []
    start = time.perf_counter()
    try:
        ok, first = cap.read()
        if not ok:raise RuntimeError("Camera failed before NPU initialization")
        del first
        pipeline = Pipeline(settings)
        for _ in range(15):
            ok, image = cap.read()
            if not ok or image is None:
                raise RuntimeError("Camera opened but did not provide a readable frame.")
            image = cv2.resize(image, (settings["camera_width"], settings["camera_height"]))
            before = time.perf_counter()
            _, gaze, valid, _ = pipeline.infer(image, cap.last_metadata["timestamp_ns"])
            records.append({"valid_gaze": valid, "image_size": list(image.shape),
                            "inference_ms": (time.perf_counter() - before) * 1000})
        report = {"camera": settings["camera"], "backend": cap.getBackendName(),
                  "readable_frames": len(records), "valid_gaze_frames": sum(r["valid_gaze"] for r in records),
                  "elapsed_seconds": time.perf_counter() - start,
                  "image_size": records[-1]["image_size"],
                  "mean_inference_ms": float(np.mean([r["inference_ms"] for r in records])),
                  "note": "No camera image was saved. This check does not measure gaze accuracy."}
    finally:
        try:cap.release()
        finally:
            if pipeline is not None:pipeline.close()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


class App:
    def __init__(self, settings):
        self.settings = settings
        self.geometry = display_geometry(settings.get("monitor", "HDMI-1"))
        self.size = np.asarray([self.geometry["width"],self.geometry["height"]], dtype=int)
        os.environ["SDL_VIDEO_WINDOW_POS"] = f'{self.geometry["x"]},{self.geometry["y"]}'
        pygame.display.init()
        pygame.font.init()
        self.window = pygame.display.set_mode(tuple(self.size), pygame.FULLSCREEN)
        if self.window.get_size() != tuple(self.size):
            actual = self.window.get_size()
            pygame.quit()
            raise RuntimeError(f"Fullscreen size {actual} differs from screen pixels {tuple(self.size)}. "
                               "Check the primary monitor resolution before calibrating.")
        pygame.display.set_caption(TITLE)
        font_path = Path(chinese_font())
        self.font = pygame.font.Font(str(font_path) if font_path.exists() else None,
                                     max(24, int(self.size[0] / 80)))
        self.pointer = X11Input(self.geometry)
        self.dwell = DwellClick(settings.get("dwell_seconds",1.0))
        self.click_enabled = False
        self.pointer_clicks = 0
        self.clock = pygame.time.Clock()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.session = Path(settings.get("output_root", str(ROOT / "data"))) / stamp
        self.session.mkdir(parents=True)
        metadata = {"display": self.geometry, "backend": "RK3576_NPU_RKNNLite", "screen_px": self.size.tolist(), "settings": settings,
                    "model": model_metadata(settings), "calibration_points": calibration_points(),
                    "validation_points": validation_points()}
        (self.session / "session.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        self.csv_stream = (self.session / "gaze.csv").open("w", newline="", encoding="utf-8")
        self.writer = csv.writer(self.csv_stream)
        self.writer.writerow(["timestamp_ns", "phase", "point", "valid", "target_x_px", "target_y_px",
                              "model_x", "model_y", "calibrated_x_px", "calibrated_y_px",
                              "filtered_x_px", "filtered_y_px", "inference_ms", "sample_age_ms", "reason", "mouse_enabled", "eye_left", "eye_right", 'input_age_ms', 'resize_ms', 'face_ms', 'color_ms', 'estimator_ms', 'prepare_ms', 'npu_ms', 'npu_called', 'capture_to_dequeue_ms', 'dequeue_to_input_ms', 'capture_sequence', 'eye_left_ear', 'eye_right_ear', 'eye_quality_metric'])
        self.ui_filtered_export=None
        if os.environ.get('TWB_UI_FILTERED_EXPORT')=='1':
            from filtered_ui_export import FilteredUIExport
            self.ui_filtered_export=FilteredUIExport()
        self.worker = CameraWorker(settings)
        self.calibration = None
        self.gaze_filter = make_filter(settings)
        self.phase = "PREVIEW"
        self.running = True
        self.mouse_enabled = False
        self.latest_sample = None
        self.last_status_write = 0
        self.hotkeys = {}
        self.last_gaze = None
        self.last_valid_at = 0
        self.last_sample_at = 0
        self.timestamps = []
        self.preview = None
        self.preview_selector = PreviewSelector(int(settings.get("preview_fps",20)))
        self.preview_note = "高清预览等待：模型640×360"
        self.sequence = 0
        self.round = 0
        self.report_message = ""
        self.report_coverage = ""
        self.point_index = 0
        self.point_start = 0
        self.point_samples = []
        self.point_frames = 0
        self.features, self.labels, self.point_ids = [], [], []
        self.validation_records = []
        # 8x8 区域模式：把逐帧坐标收敛成一个稳定区域，再吸附到格心。
        self.region_grid = int(settings.get("region_grid", 8))
        self.region_mode = bool(settings.get("region_mode", True))
        self.region = RegionDecider(grid=self.region_grid,
                                   window=int(settings.get("region_window", 12)),
                                   hysteresis=int(settings.get("region_hysteresis", 3)),
                                   min_confidence=float(settings.get("region_min_confidence", 0.6)))
        self.region_cell = None
        self.worker.start()

    def text(self, text, y, color=(220, 230, 240)):
        image = self.font.render(text, True, color)
        self.window.blit(image, (28, y))

    def begin(self, phase):
        self.mouse_enabled = False
        self.click_enabled = False
        self.dwell.reset()
        self.phase = phase
        self.point_index = 0
        self.point_start = time.perf_counter()
        self.point_samples = []
        self.point_frames = 0
        self.last_gaze = None
        self.gaze_filter = make_filter(self.settings)
        self.region.reset()
        self.region_cell = None
        if phase == "CALIBRATE":
            if self.ui_filtered_export:self.ui_filtered_export.reset_binding()
            self.round += 1
            self.features, self.labels, self.point_ids = [], [], []
            self.calibration = None
        else:
            self.validation_records = []

    def global_pressed(self, key):
        return self.pointer.pressed(key)

    def apply_pointer(self, point, sample_time, enabled):
        fresh = 0 <= time.perf_counter() - sample_time < self.settings.get("max_sample_age", 0.5)
        active = bool(enabled and fresh and self.phase == "TRACK")
        if active:self.pointer.move(*point)
        if self.dwell.update(point, sample_time, active and self.click_enabled):
            self.pointer.click();self.pointer_clicks += 1


    def controls(self):
        if self.global_pressed(0x75) and self.phase == "TRACK":
            self.click_enabled = not self.click_enabled
            self.dwell.reset()
        if self.global_pressed(0x79):  # F10 always stops this app, including while minimized.
            self.running = False
        if self.global_pressed(0x77):  # F8 works immediately after calibration too.
            if self.phase in ("READY", "RESULT") and self.calibration is not None and self.calibration.has_calibrated:
                self.phase = "TRACK"
            if self.phase == "TRACK":
                self.mouse_enabled = not self.mouse_enabled
                self.dwell.reset()
        if self.global_pressed(0x76) and self.phase == "TRACK":  # F7 区域模式 / 连续模式
            self.region_mode = not self.region_mode
            self.region.reset()
            self.region_cell = None
        if self.global_pressed(0x78):  # F9
            handle = pygame.display.get_wm_info().get("window")
            if handle:
                self.pointer.restore(handle)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    if self.phase in ("PREVIEW", "FAILED") and self.worker.ready:
                        self.begin("CALIBRATE")
                    elif self.phase in ("READY", "RESULT"):
                        self.phase = "TRACK"
                elif event.key == pygame.K_r and self.worker.ready:
                    self.begin("CALIBRATE")
                elif event.key == pygame.K_v and self.calibration is not None and self.calibration.has_calibrated:
                    self.begin("VALIDATE")
                elif event.key == pygame.K_h and self.phase == "TRACK":
                    pygame.display.iconify()

    def process(self, samples):
        for sample_index, sample in enumerate(samples):
            # Reject stale/future results before calibration, filtering and region votes.
            if not 0 <= time.perf_counter() - sample["t"] < self.settings.get("max_sample_age", .5):
                sample = dict(sample, valid=False, reason="源帧已过期或时间无效")
            self.sequence += 1
            self.last_sample_at = sample["t"]
            self.latest_sample = sample
            self.timestamps.append(sample["t"])
            self.timestamps = self.timestamps[-60:]
            cal, filtered, target = None, None, None
            if self.phase in ("CALIBRATE", "VALIDATE"):
                points = calibration_points() if self.phase == "CALIBRATE" else validation_points()
                target = np.asarray(points[self.point_index]) * self.size
            if sample["valid"]:
                self.last_valid_at = sample["t"]
                if self.calibration is not None and self.calibration.has_calibrated:
                    _, normalized = self.calibration.predict(sample["features"], sample["raw"])
                    cal = np.asarray(normalized, dtype=float) * self.size
                    filtered = np.asarray(self.gaze_filter.filter_values(cal, timestamp=sample["t"]), dtype=float)
                    if not np.isfinite(filtered).all() or not np.isfinite(cal).all():
                        cal, filtered = None, None
                        self.dwell.reset()
                    else:
                        self.last_gaze = filtered
                        point = None
                        if self.region_mode:
                            if self.phase == "TRACK":
                                norm = np.clip(np.asarray(filtered, dtype=float) / self.size, 0.0, 1.0)
                                cell = self.region.update(float(norm[0]), float(norm[1]))
                                if cell is not None and self.region.decided:
                                    self.region_cell = cell
                                    point = ((cell[0]+.5)/self.region_grid*self.size[0],
                                             (cell[1]+.5)/self.region_grid*self.size[1])
                        else:
                            point = tuple(np.clip(filtered,(0,0),self.size-1))
                        # Preserve every sample for calibration/filtering/logging,
                        # but never replay a batch of old cursor movements/clicks.
                        if sample_index == len(samples)-1:
                            self.apply_pointer(point, sample["t"], self.mouse_enabled and point is not None)

            else:
                self.dwell.reset()
                self.last_gaze = None
                self.gaze_filter = make_filter(self.settings)
                # Invalid frames end this fixation: old region votes must not
                # steer the cursor after a blink/occlusion or lost face.
                self.region.reset()
                self.region_cell = None
            elapsed = sample["t"] - self.point_start
            if self.phase in ("CALIBRATE", "VALIDATE") and elapsed >= self.settings["settle_seconds"]:
                self.point_frames += 1
                if self.phase == "CALIBRATE" and sample["valid"]:
                    self.point_samples.append(sample["features"])
                elif self.phase == "VALIDATE" and elapsed < (
                        self.settings["settle_seconds"] + self.settings["validation_seconds_per_point"]):
                    self.validation_records.append({"point": self.point_index, "sequence": self.sequence,
                                                    "calibrated": cal.tolist() if cal is not None else None,
                                                    "filtered": filtered.tolist() if filtered is not None else None})
            if self.ui_filtered_export:
                self.ui_filtered_export.observe(sample,self.phase,filtered,
                    bool(self.calibration is not None and self.calibration.has_calibrated),self.size)
            def values(x):
                return list(x) if x is not None else ["", ""]
            self.writer.writerow([sample["timestamp_ns"], self.phase,
                                  self.point_index + 1 if target is not None else "", int(sample["valid"]),
                                  *values(target), *values(sample["raw"]), *values(cal), *values(filtered), sample["infer_ms"], (time.perf_counter()-sample["t"])*1000, sample["reason"], self.mouse_enabled, sample["eye_left"], sample["eye_right"],
                                  *[sample["timings"][key] for key in ['input_age_ms', 'resize_ms', 'face_ms', 'color_ms', 'estimator_ms', 'prepare_ms', 'npu_ms', 'npu_called', 'capture_to_dequeue_ms', 'dequeue_to_input_ms']],
                                  sample.get('capture_sequence'),sample.get('eye_left_ear'),sample.get('eye_right_ear'),
                                  'EAR' if self.settings.get('eye_ear_threshold') is not None else 'legacy_pixel_area'])
        self.csv_stream.flush()

    def advance(self):
        elapsed = time.perf_counter() - self.point_start
        if self.phase == "CALIBRATE":
            count = self.settings["calibration_samples_per_point"]
            if len(self.point_samples) < count:
                # 90 帧/点时不能再用固定的 15s 超时，按采样数放宽（低帧率下也能采满）
                timeout = max(15.0, self.settings["settle_seconds"] + count / 5.0)
                if elapsed > timeout:
                    self.phase = "FAILED"
                    self.report_message = "有效人脸样本不足，请调整光线和坐姿，按空格重试。"
                return
            point = calibration_points()[self.point_index]
            self.features.extend(self.point_samples[:count])
            self.labels.extend([point] * count)
            self.point_ids.extend([self.point_index] * count)
            self.point_index += 1
            if self.point_index == len(calibration_points()):
                self.fit()
                return
        elif self.phase == "VALIDATE":
            if elapsed < self.settings["settle_seconds"] + self.settings["validation_seconds_per_point"]:
                return
            self.point_index += 1
            if self.point_index == len(validation_points()):
                self.finish_validation()
                return
        else:
            return
        self.point_start = time.perf_counter()
        self.point_samples = []
        self.point_frames = 0
        self.gaze_filter = make_filter(self.settings)

    def fit(self):
        self.window.fill((22, 30, 40))
        self.text("正在完成标定，请稍候……", int(self.size[1] / 2))
        pygame.display.flip()
        features, labels = np.asarray(self.features, dtype=np.float32), np.asarray(self.labels, dtype=np.float32)
        directory = self.session / f"calibration_{self.round:02d}"
        self.calibration = make_calibration(self.settings["calibration"], directory)
        ok, _, predictions = self.calibration.calibrate(features, labels)
        if not ok:
            self.phase = "FAILED"
            self.report_message = "标定失败，按空格重试。"
            return
        np.savez_compressed(directory / "samples.npz", features=features, labels=labels,
                            point_ids=self.point_ids, screen_px=self.size)
        if self.settings["calibration"] == "svr":
            self.calibration.save_model()
        elif self.settings["calibration"] == "ridge_iso":
            # numpy-only 导出：权重 / 标准化参数 / 单调校正断点，可在嵌入式端直接复现
            np.savez(directory / "ridge_iso_model.npz",
                     weights=self.calibration.weights,
                     feature_mean=self.calibration.feature_mean,
                     feature_std=self.calibration.feature_std,
                     iso_x_xs=self.calibration.iso_x.xs, iso_x_ys=self.calibration.iso_x.ys,
                     iso_y_xs=self.calibration.iso_y.xs, iso_y_ys=self.calibration.iso_y.ys)
        else:
            np.save(directory / "ridge_weights.npy", self.calibration.weights)
        self.phase = "READY"
        self.gaze_filter = make_filter(self.settings)
        print(f"Calibration complete: {len(features)} samples. Validate with V; no accuracy claim from fitting data.")

    def finish_validation(self):
        report = validation_metrics(self.validation_records, validation_points(), self.size)
        report["protocol"] = "20 held-out target positions; fixed dwell windows; no closest-to-target selection."
        report["summary_aggregation"] = "Equal-weight mean of per-target metrics; p90 is the mean of target-wise p90 values."
        report["settings"] = self.settings
        report["worker_dropped_samples"] = self.worker.dropped_samples
        report["records"] = self.validation_records
        file = self.session / f"validation_{datetime.now():%H%M%S_%f}.json"
        file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        metrics = report["filtered"]
        if metrics:
            self.report_message = (f"平均逐帧偏差 {metrics['mean_frame_error_px']:.0f} px；"
                                   f"平均各点 P90 {metrics['p90_frame_error_px']:.0f} px；"
                                   f"8×8 命中率 单帧 {metrics['grid_8x8_hit_rate']:.0%}"
                                   f" / 停留投票 {metrics.get('grid_8x8_hit_rate_dwell', 0):.0%}")
        else:
            self.report_message = "评测没有有效样本，请重新调整坐姿和标定。"
        print(f"Validation report: {file}")
        self.report_coverage = (f"有效样本 {report['valid_rate']:.0%}；"
                                f"有效目标 {report['completed_points']}/{report['expected_points']}")
        self.phase = "RESULT"
        self.mouse_enabled = False

    def preview_surface(self, size):
        # Hold the source reference as well as its identity: ndarray ids cannot
        # be reused while cached. CameraWorker publishes a fresh RGB array.
        source = self.preview
        if source is None:
            return None
        if (getattr(self, "_scaled_source", None) is not source
                or getattr(self, "_scaled_size", None) != size):
            if source.shape[:2] == (1080, 1920) and size[0] <= 1920 and size[1] <= 1080:
                # Display uses the original snapshot; the model stays 640x360.
                # 960x540 is an exact 2:1 area reduction, avoiding a full1080
                # pygame surface followed by slow noninteger smoothscale.
                pixels = cv2.resize(source, size, interpolation=cv2.INTER_AREA)
                self._scaled_preview = pygame.surfarray.make_surface(np.transpose(pixels, (1, 0, 2)))
            else:
                image = pygame.surfarray.make_surface(np.transpose(source, (1, 0, 2)))
                self._scaled_preview = pygame.transform.smoothscale(image, size)
            self._scaled_source = source
            self._scaled_size = size
        return self._scaled_preview

    def draw(self):
        self.window.fill((22, 30, 40))
        fresh = time.perf_counter() - self.last_valid_at < 0.5
        sample = self.latest_sample
        age = time.perf_counter()-sample["t"] if sample else 999
        status = "等待摄像头首帧" if sample is None else sample["reason"]
        if sample is not None and age > self.settings.get("max_sample_age",0.5):
            status += f" / 帧延迟 {age*1000:.0f}ms，暂停眼控"
        if time.monotonic()-self.last_status_write > .1:
            state = {"time":time.time(),"phase":self.phase,"mouse_enabled":self.mouse_enabled,
                     "reason":status,"age_ms":age*1000,"region_mode":self.region_mode}
            path=Path('/userdata/gaze_model_migration_v1_20261014/control_status.json')
            temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state),encoding='utf8');temp.replace(path)
            self.last_status_write=time.monotonic()
        fps = ((len(self.timestamps) - 1) / (self.timestamps[-1] - self.timestamps[0])
               if len(self.timestamps) > 1 and self.timestamps[-1] > self.timestamps[0] else 0)
        if self.phase not in ("CALIBRATE", "VALIDATE"):
            self.text("MGazeNet 固定头部定位", 22)
            self.text(f"{status}    处理 {fps:.1f} FPS    鼠标：{'开' if self.mouse_enabled else '关'}    停留点击：{'开' if self.click_enabled else '关'}", 80)
            mode = f"{self.region_grid}×{self.region_grid} 区域模式" if self.region_mode else "连续模式"
            cell = f"{self.region_cell}" if self.region_cell is not None else "待定"
            self.text(f"输出：{mode}    区域 {cell}    置信 {self.region.confidence:.0%}", 135)
            self.text("ESC/F10 退出  F6 停留点击  F7 区域/连续  F8 鼠标开关  R 标定  V 评测  H 隐藏  F9 返回", int(self.size[1]) - 65)
        if self.phase in ("PREVIEW", "FAILED"):
            self.text(f"保持头部稳定、眼睛睁开，让脸居中；准备好后按空格开始 {len(calibration_points())} 点标定。", 190)
            self.text(self.preview_note, 232)
            if self.preview is not None:
                width = min(960, int(self.size[0] * 0.62), int(self.size[1] * 0.9))
                height = round(width * self.preview.shape[0] / self.preview.shape[1])
                image = self.preview_surface((width, height))
                self.window.blit(image, ((int(self.size[0]) - width) // 2, (int(self.size[1]) - height) // 2))
            else:
                self.text("正在打开摄像头和加载模型……", int(self.size[1] / 2))
        elif self.phase in ("CALIBRATE", "VALIDATE"):
            points = calibration_points() if self.phase == "CALIBRATE" else validation_points()
            kind = "标定" if self.phase == "CALIBRATE" else "独立评测"
            self.text(f"{kind} {self.point_index + 1}/{len(points)}：只看白色目标，ESC / F10 退出。", 28)
            pos = tuple((np.asarray(points[self.point_index]) * self.size).astype(int))
            pygame.draw.circle(self.window, (95, 160, 255), pos, 22)
            pygame.draw.circle(self.window, (255, 255, 255), pos, 9)
        elif self.phase == "TRACK":
            self.text(self.preview_note, 232)
            if self.preview is not None:
                self.window.blit(self.preview_surface((320,180)),(int(self.size[0])-330,10))
            for col in range(1, 8):
                x = int(self.size[0] * col / 8)
                pygame.draw.line(self.window, (42, 52, 64), (x, 0), (x, int(self.size[1])))
            for row in range(1, 8):
                y = int(self.size[1] * row / 8)
                pygame.draw.line(self.window, (42, 52, 64), (0, y), (int(self.size[0]), y))
            self.text("绿色圆圈是注视估计；按 V 测试，确认效果后按 F8 开启鼠标跟随。", 190)
            if fresh and self.last_gaze is not None:
                pos = tuple(np.clip(self.last_gaze, (0, 0), self.size - 1).astype(int))
                pygame.draw.circle(self.window, (80, 240, 150), pos, 20, 3)
                pygame.draw.circle(self.window, (80, 240, 150), pos, 4)
        elif self.phase == "READY":
            self.text("标定完成。按 F8 直接开启眼控；V 评测；空格仅查看定位。", int(self.size[1] / 2))
        else:
            self.text(self.report_message, int(self.size[1] / 2))
            if self.phase == "RESULT":
                self.text(self.report_coverage, int(self.size[1] / 2) + 60)
                self.text("报告已保存到 data；按空格返回定位，R 重新标定，V 再测。", int(self.size[1] / 2) + 120)
            else:
                self.text("按空格重试，ESC 退出。", int(self.size[1] / 2) + 60)
        pygame.display.flip()

    def run(self):
        started = time.monotonic()
        try:
            while self.running:
                self.controls()
                # Only an explicitly supplied owner path can request orderly exit.
                if self.settings.get('stop_request') and Path(self.settings['stop_request']).is_file():
                    self.running = False
                if self.settings.get("preview_seconds",0) and time.monotonic()-started >= self.settings["preview_seconds"]:
                    self.running = False
                if not self.running:
                    break
                samples, model_preview, error = self.worker.drain()
                self.preview, self.preview_note = self.preview_selector.select(model_preview,self.worker.cap)
                if error:
                    raise RuntimeError(error)
                self.process(samples)
                self.advance()
                self.draw()
                self.clock.tick(60)
        finally:
            self.mouse_enabled = False
            self.worker.close()
            self.csv_stream.close()
            self.pointer.close()
            pygame.image.save(self.window,str(self.session / "last_ui.png"))
            report = {"status": "PASS_UI_SESSION_CLOSED" if sys.exc_info()[0] is None and not self.worker.error and not self.worker.thread.is_alive() else "FAIL_UI_SESSION",
                      "phase":self.phase,"samples":self.sequence,"pointer_clicks":self.pointer_clicks,
                      "worker_error":self.worker.error,"worker_alive":self.worker.thread.is_alive(),
                      "display":self.geometry,"camera_device":self.worker.cap.device if self.worker.cap else None,
                      "capture_end":self.worker.cap.end_metadata if self.worker.cap else None,
                      "calibration_performed":bool(self.calibration is not None and self.calibration.has_calibrated),
                      "accuracy_accepted":False}
            (self.session / "runtime_result.json").write_text(json.dumps(report,indent=2)+"\n")
            pygame.quit()
            print(f"Session saved: {self.session}")


def main():
    parser = argparse.ArgumentParser(description="MGazeNet fixed-head gaze cursor")
    parser.add_argument("--check", action="store_true", help="Offline model and dependency check; no webcam or GUI")
    parser.add_argument("--probe-camera", action="store_true", help="Capture 15 frames without opening a GUI")
    parser.add_argument("--camera", choices=("fpga-pcie",))
    parser.add_argument("--monitor", default="HDMI-1")
    parser.add_argument("--preview-fps", type=int, choices=(10,15,20), default=20,
                        help="Independent raw HDMI snapshot ceiling; model pixels unchanged")
    parser.add_argument("--preview-seconds", type=float, default=0)
    parser.add_argument("--stop-request", help="Optional exact owner request file for normal shutdown")
    parser.add_argument("--output-root")
    parser.add_argument("--calibration", choices=("ridge_iso", "svr", "ridge"))
    parser.add_argument("--filter", choices=("one_euro", "heuristic"))
    parser.add_argument("--model", help="Explicit compiled .rknn model path")
    parser.add_argument("--precise", action="store_true",
                        help="Head-still precision mode: 25-point grid, 90 samples/point, continuous output")
    parser.add_argument("--continuous", action="store_true",
                        help="Continuous cursor without changing calibration grid or sample count")
    args = parser.parse_args()
    settings = load_settings(PRECISE_OVERRIDES if args.precise else None)
    if args.continuous:
        settings['region_mode'] = False
    settings.update(monitor=args.monitor, preview_seconds=args.preview_seconds,preview_fps=args.preview_fps)
    settings['stop_request'] = args.stop_request
    if args.output_root:settings["output_root"]=args.output_root
    for key in ("camera", "calibration", "filter"):
        value = getattr(args, key)
        if value is not None:
            settings[key] = value
    if args.model:
        settings["model_path"] = args.model
    if args.check:
        self_check(settings, ROOT / "data" / "deployment_check.json")
    elif args.probe_camera:
        report_path = ROOT / "data" / "camera_check.json"
        try:
            camera_check(settings, report_path)
        except Exception as error:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps({"camera": settings["camera"], "passed": False,
                                               "error": str(error),
                                               "note": "Camera and live gaze accuracy are not verified."}, indent=2), encoding="utf-8")
            raise
    else:
        App(settings).run()


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(f"\nError: {error}", file=sys.stderr)
        sys.exit(1)
