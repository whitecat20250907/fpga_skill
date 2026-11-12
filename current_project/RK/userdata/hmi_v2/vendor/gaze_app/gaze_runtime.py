"""Local adapter for the upstream MGazeNet, face alignment and calibration modules."""
from __future__ import annotations

import ctypes
import json
import os
import threading
import time
import traceback
import uuid

# New process identity; never associate separate hand/face numeric track IDs.
UI_SOURCE_INSTANCE = uuid.uuid4().hex
from collections import deque
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import cv2
import numpy as np
from gazefollower.calibration import MultivariateRidgeCalibration, SVRCalibration
import sys
sys.path.insert(0, '/userdata/fpga_detector_inputs_20261023')
from gaze_bridge import NPUFaceAlignment as MediaPipeFaceAlignment
from gazefollower.filter import HeuristicFilter, OneEuroFilter
from gaze_model import GazeModel as RKNNGazeEstimator
from pcie_capture import PcieCapture

from ridge_isotonic_calibration import RidgeIsotonicCalibration
from region8 import dwell_cell_vote
from overlap_worker import OverlapRunner
from eye_quality import eyes_ready

ROOT = Path(__file__).resolve().parent
REPO = ROOT / "GazeFollower"
MODEL_DIR = REPO / "gazefollower" / "res" / "model_weights"


def load_settings(overrides=None):
    with (ROOT / "settings.json").open(encoding="utf-8-sig") as stream:
        settings = json.load(stream)
    if overrides:
        settings.update(overrides)
    # 必须在返回前设置：calibration_points() 依赖这个全局布局
    set_calibration_grid(settings.get("calibration_grid", 3))
    return settings


def screen_size():
    # Keep calibration pixels and Windows cursor pixels in the same coordinate system.
    if os.name == "nt":
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()
        return (ctypes.windll.user32.GetSystemMetrics(0),
                ctypes.windll.user32.GetSystemMetrics(1))
    from screeninfo import get_monitors
    monitors = get_monitors()
    monitor = next((m for m in monitors if m.is_primary), monitors[0])
    return monitor.width, monitor.height


def open_camera(settings):
    return PcieCapture(settings)


def _source_is_current(timestamp, settings):
    # Use the existing monotonic source-age budget; never replace source time.
    return (type(timestamp) is int and timestamp > 0
            and 0 <= (time.monotonic_ns()-timestamp)/1e9 < settings.get('max_sample_age', .5))


def _source_seconds(timestamp):
    # Only the legacy UI arithmetic needs a numeric sentinel for absent time.
    # timestamp_ns and FaceInfo.timestamp retain None; zero is never fresh.
    return timestamp/1e9 if type(timestamp) is int else 0.


def _empty_source_face(timestamp, rgb, capture_sequence):
    from gazefollower.misc import FaceInfo
    face = FaceInfo(timestamp=timestamp, img_w=rgb.shape[1], img_h=rgb.shape[0])
    face.capture_sequence = capture_sequence
    face.track_id = None
    face.additional_faces = []
    return face


def _publish_people(face, records, *, source_rejected=False):
    # This is the existing latest-result producer, not a second stream/UUID.
    packet=dict(timestamp_ns=face.timestamp, completed_ns=time.monotonic_ns(), people=records,
                source_instance=UI_SOURCE_INSTANCE, primary_track_id=getattr(face,'track_id',None),
                capture_sequence=getattr(face,'capture_sequence',None),
                calibrated_cursor_person='primary_only', track_ids_are_identity=False)
    if source_rejected:
        packet.update(valid=False, reason='stale_or_invalid_source')
    target=Path('/dev/shm')/('gaze_npu_people_'+str(os.getpid())+'.json')
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(packet));temp.replace(target)


def _reject_source(estimator, face):
    from gazefollower.misc import GazeInfo
    estimator.last_timings = dict(prepare_ms=0., npu_ms=0., npu_called=False,
                                  stale_source=True, people_count=0, all_people_npu_ms=0.)
    _publish_people(face, [], source_rejected=True)
    return GazeInfo(timestamp=face.timestamp)


def _estimate_one_with_eye_gate(estimator, rgb, face, settings):
    # Same eye-area threshold as the old post-NPU validity check; no new metric.
    # Invalid/dense-missing faces still follow the estimator's original checks.
    if face.status and face.can_gaze_estimation and not eyes_ready(face, settings):
        from gazefollower.misc import GazeInfo
        estimator.last_timings = dict(prepare_ms=0., npu_ms=0., npu_called=False,
                                      eye_quality_rejected=True)
        return GazeInfo(timestamp=face.timestamp)
    result = estimator.detect(rgb, face)
    estimator.last_timings['eye_quality_rejected'] = False
    return result


def estimate_with_eye_gate(estimator, rgb, face, settings):
    # One MGazeNet evaluation per person, using that person's own face + 2 eyes.
    # Only the primary result enters the existing personal calibration/cursor.
    people = [face] + list(getattr(face, 'additional_faces', []))
    primary = None
    primary_timings = None
    records = []
    total_npu_ms = 0.
    for index, person in enumerate(people):
        if not 0 <= (time.monotonic_ns()-person.timestamp)/1e9 < settings.get('max_sample_age', .5):
            from gazefollower.misc import GazeInfo
            result = GazeInfo(timestamp=person.timestamp)
            estimator.last_timings = dict(prepare_ms=0., npu_ms=0., npu_called=False, stale_source=True)
        else:
            result = _estimate_one_with_eye_gate(estimator, rgb, person, settings)
        timings = dict(estimator.last_timings)
        total_npu_ms += timings.get('npu_ms', 0.)
        records.append(dict(track_id=getattr(person, 'track_id', None), valid=bool(result.status),
            raw=np.asarray(result.raw_gaze_coordinates).tolist() if result.status else None,
            eye_openness=[float(person.left_eye_openness),float(person.right_eye_openness)], timings=timings))
        if index == 0:
            primary = result
            primary_timings = timings
    estimator.last_timings = dict(primary_timings, all_people_npu_ms=total_npu_ms, people_count=len(people))
    # Small atomic latest sample on tmpfs, no disk history or stale replay.
    _publish_people(face, records)
    return primary


class Pipeline:
    def __init__(self, settings):
        self.aligner = MediaPipeFaceAlignment(
            model_path=str(MODEL_DIR / "face_landmarker.task"), enable_filter=False,
            running_mode=settings.get("face_running_mode", "image"),
            cpu_threads=settings.get("face_cpu_threads", 0))
        self.estimator = None
        try:
            model = settings.get("model_path", "")
            model_path = Path(model) if model else MODEL_DIR / "original_gaze_fp16.rknn"
            if not model_path.is_absolute():
                model_path = ROOT / model_path
            self.estimator = RKNNGazeEstimator(model_path=str(model_path))
        except Exception:
            self.aligner.release()
            raise
        self.settings = settings

    def infer(self, bgr, timestamp, *, color_order="bgr", capture_sequence=None):
        # Compatibility callers may supply BGR; the live owner supplies native RGB.
        # One RGB array is shared by alignment and the original NPU preprocessor.
        started = time.perf_counter()
        if color_order not in ('bgr','rgb'):
            raise ValueError('Explicit BGR or RGB required')
        rgb = bgr if color_order == 'rgb' else cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        converted = time.perf_counter()
        source_rejected = not _source_is_current(timestamp, self.settings)
        face = (_empty_source_face(timestamp, rgb, capture_sequence) if source_rejected else
                self.aligner.detect(timestamp, rgb, color_order='rgb', capture_sequence=capture_sequence))
        face_done = time.perf_counter()
        if source_rejected or not _source_is_current(timestamp, self.settings):
            face = _empty_source_face(timestamp, rgb, capture_sequence)
            gaze = _reject_source(self.estimator, face)
        else:
            gaze = estimate_with_eye_gate(self.estimator, rgb, face, self.settings)
        self.last_timings = {"face_ms": 0. if source_rejected else (face_done-converted)*1000,
                             "face_npu_skipped": source_rejected,
                             "color_ms": (converted-started)*1000,
                             "estimator_ms": (time.perf_counter()-face_done)*1000,
                             **self.estimator.last_timings}
        valid = bool(gaze.status and gaze.features is not None
                     and np.isfinite(gaze.features).all()
                     and eyes_ready(face, self.settings))
        return face, gaze, valid, rgb

    def close(self):
        if self.estimator is not None:
            self.estimator.release()
        self.aligner.release()


class _OverlapFaceSource:
    """Camera/MediaPipe owner; each packet holds its own image and face result."""
    def __init__(self, worker):
        self.worker = worker
        self.settings = worker.settings
        self.cap = worker.cap = open_camera(self.settings)
        self.aligner = None
        self.failed_reads = 0
        try:
            ok, first_frame = self.cap.read_rgb()
            if not ok or first_frame is None:
                raise RuntimeError('Camera failed before NPU initialization')
            del first_frame
            self.aligner = MediaPipeFaceAlignment(
                model_path=str(MODEL_DIR / 'face_landmarker.task'), enable_filter=False,
                running_mode=self.settings.get('face_running_mode', 'image'),
                cpu_threads=self.settings.get('face_cpu_threads', 0))
        except BaseException:
            self.cap.release()
            raise

    def next(self):
        ok, bgr = self.cap.read_rgb()
        if not ok or bgr is None:
            self.failed_reads += 1
            if self.failed_reads >= 30:
                raise RuntimeError('Camera stopped providing frames.')
            return None
        self.failed_reads = 0
        meta = dict(self.cap.last_metadata)
        meta.setdefault('timestamp_ns', None)
        read_done = time.perf_counter()
        if not _source_is_current(meta['timestamp_ns'], self.settings):
            face = _empty_source_face(meta['timestamp_ns'], bgr, meta['sequence'])
            return dict(meta=meta, face=face, rgb=bgr, read_done=read_done,
                        before=read_done, face_done=read_done, converted=read_done,
                        input_rejected=True)
        if bgr.shape[:2] != (self.settings['camera_height'], self.settings['camera_width']):
            bgr = cv2.resize(bgr, (self.settings['camera_width'], self.settings['camera_height']))
        before = time.perf_counter()
        # Resizing can consume the remaining budget; check at NPU admission too.
        source_rejected = not _source_is_current(meta['timestamp_ns'], self.settings)
        face = (_empty_source_face(meta['timestamp_ns'], bgr, meta['sequence']) if source_rejected else
                self.aligner.detect(meta['timestamp_ns'], bgr, color_order='rgb', capture_sequence=meta['sequence']))
        face_done = time.perf_counter()
        rgb = bgr
        return dict(meta=meta, face=face, rgb=rgb, read_done=read_done,
                    before=before, face_done=face_done, converted=time.perf_counter(),
                    input_rejected=source_rejected)

    def interrupt(self):
        self.cap.request_stop()

    def close(self):
        try:
            self.cap.release()
        finally:
            if self.aligner is not None:
                self.aligner.release()


class _OverlapGazeTarget:
    """Single NPU owner; no concurrent calls or model/input changes."""
    def __init__(self, settings):
        self.settings = settings
        model = settings.get('model_path', '')
        model_path = Path(model) if model else MODEL_DIR / 'original_gaze_fp16.rknn'
        if not model_path.is_absolute():
            model_path = ROOT / model_path
        self.estimator = RKNNGazeEstimator(model_path=str(model_path))
        self.last_timestamp = None

    def process(self, packet):
        face, rgb, meta = packet['face'], packet['rgb'], packet['meta']
        timestamp = meta['timestamp_ns']
        if face.timestamp != timestamp:
            raise RuntimeError('Face/image capture timestamps differ or repeat')
        started = time.perf_counter()
        stale = packet.get('input_rejected', False) or not _source_is_current(timestamp, self.settings)
        if stale:
            face = _empty_source_face(timestamp, rgb, meta['sequence'])
            gaze = _reject_source(self.estimator, face)
        else:
            if self.last_timestamp is not None and timestamp <= self.last_timestamp:
                raise RuntimeError('Face/image capture timestamps differ or repeat')
            # Rejected future/missing input must not poison the next good frame.
            self.last_timestamp = timestamp
            gaze = estimate_with_eye_gate(self.estimator, rgb, face, self.settings)
        ended = time.perf_counter()
        valid = bool(gaze.status and gaze.features is not None
                     and np.isfinite(gaze.features).all()
                     and eyes_ready(face, self.settings))
        captured_at = _source_seconds(timestamp)
        sample = dict(t=captured_at, timestamp_ns=timestamp, capture_sequence=meta['sequence'], valid=valid,
                      source_instance=UI_SOURCE_INSTANCE,track_id=getattr(face,'track_id',None),
                      features=gaze.features.copy() if valid else None,
                      raw=np.asarray(gaze.raw_gaze_coordinates).copy() if valid else None,
                      timings=dict(face_ms=(packet['face_done']-packet['before'])*1000,
                                   face_npu_skipped=packet.get('input_rejected', False),
                                   color_ms=(packet['converted']-packet['face_done'])*1000,
                                   estimator_ms=(ended-started)*1000,
                                   resize_ms=(packet['before']-packet['read_done'])*1000,
                                   input_age_ms=(packet['read_done']-captured_at)*1000 if type(timestamp) is int else None,
                                   capture_to_dequeue_ms=(meta['dequeue_ns']-timestamp)/1e6 if type(timestamp) is int else None,
                                   dequeue_to_input_ms=(packet['read_done']-meta['dequeue_ns']/1e9)*1000,
                                   face_to_npu_queue_ms=(started-packet['converted'])*1000,
                                   **self.estimator.last_timings),
                      infer_ms=(ended-packet['before'])*1000, stage_overlap=True,
                      face_detected=bool(face.status),
                      reason=('源帧已过期或时间无效' if stale else '有效' if valid else '未检测到人脸' if not face.status else '闭眼或眼睛开合度不足' if self.estimator.last_timings.get('eye_quality_rejected') else '眼区越界或模型输入无效' if not gaze.status else '闭眼或眼睛开合度不足'),
                      eye_left=float(face.left_eye_openness), eye_right=float(face.right_eye_openness),
                      eye_left_ear=getattr(face,'left_eye_ear',None),eye_right_ear=getattr(face,'right_eye_ear',None))
        if face.status:
            rgb = rgb.copy()  # Only the display overlay needs writable pixels.
            for rect in (face.face_rect, face.left_rect, face.right_rect):
                x, y, w, h = map(int, rect)
                cv2.rectangle(rgb, (x, y), (x+w, y+h), (80, 220, 130), 1)
        return sample, rgb

    def close(self):
        self.estimator.release()


class CameraWorker:
    """Acquire and infer off the UI thread; emit each physical frame once."""
    def __init__(self, settings):
        self.settings = settings
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.samples = deque(maxlen=256)
        self.preview = None
        self.error = None
        self.ready = False
        self.dropped_samples = 0
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.cap = None
        self.engine = None

    def start(self):
        self.thread.start()

    def _run(self):
        if self.settings.get('overlap_inference', False):
            self._run_overlap()
            return
        pipeline = None
        try:
            self.cap = open_camera(self.settings)
            # Reserve the contiguous DMA buffers before loading NPU models.
            # Opening the async adapter alone does not guarantee allocation.
            ok, first_frame = self.cap.read_rgb()
            if not ok or first_frame is None:
                raise RuntimeError("Camera failed before NPU initialization")
            del first_frame
            pipeline = Pipeline(self.settings)
            self.ready = True
            failed_reads = 0
            while not self.stop_event.is_set():
                ok, bgr = self.cap.read_rgb()
                if not ok or bgr is None:
                    failed_reads += 1
                    if failed_reads >= 30:
                        raise RuntimeError("Camera stopped providing frames.")
                    self.stop_event.wait(0.03)
                    continue
                timestamp = self.cap.last_metadata.get('timestamp_ns')
                captured_at = _source_seconds(timestamp)
                failed_reads = 0
                read_done = time.perf_counter()
                if bgr.shape[:2] != (self.settings["camera_height"], self.settings["camera_width"]):
                    bgr = cv2.resize(bgr, (self.settings["camera_width"], self.settings["camera_height"]))
                before = time.perf_counter()
                face, gaze, valid, rgb = pipeline.infer(bgr, timestamp, color_order='rgb', capture_sequence=self.cap.last_metadata['sequence'])
                infer_ms = (time.perf_counter() - before) * 1000
                sample = {"t": captured_at, "timestamp_ns": timestamp, "capture_sequence": self.cap.last_metadata["sequence"], "valid": valid,
                          "source_instance": UI_SOURCE_INSTANCE,"track_id":getattr(face,"track_id",None),
                          "features": gaze.features.copy() if valid else None,
                          "raw": np.asarray(gaze.raw_gaze_coordinates).copy() if valid else None,
                          "timings": {**pipeline.last_timings,
                                      "resize_ms": (before-read_done)*1000,
                                      "input_age_ms": (read_done-captured_at)*1000 if type(timestamp) is int else None,
                                      "capture_to_dequeue_ms": (self.cap.last_metadata['dequeue_ns']-timestamp)/1e6 if type(timestamp) is int else None,
                                      "dequeue_to_input_ms": (read_done-self.cap.last_metadata['dequeue_ns']/1e9)*1000},
                          "infer_ms": infer_ms, "face_detected": bool(face.status),
                          "reason": ("源帧已过期或时间无效" if pipeline.estimator.last_timings.get("stale_source") else "有效" if valid else "未检测到人脸" if not face.status else "闭眼或眼睛开合度不足" if pipeline.estimator.last_timings.get("eye_quality_rejected") else "眼区越界或模型输入无效" if not gaze.status else "闭眼或眼睛开合度不足"),
                          "eye_left": float(face.left_eye_openness), "eye_right": float(face.right_eye_openness),
                          "eye_left_ear": getattr(face,"left_eye_ear",None),"eye_right_ear": getattr(face,"right_eye_ear",None)}
                if face.status:
                    rgb = rgb.copy()  # Only the display overlay needs writable pixels.
                    for rect in (face.face_rect, face.left_rect, face.right_rect):
                        x, y, w, h = map(int, rect)
                        cv2.rectangle(rgb, (x, y), (x + w, y + h), (80, 220, 130), 1)
                with self.lock:
                    if len(self.samples) == self.samples.maxlen:
                        self.dropped_samples += 1
                    self.samples.append(sample)
                    self.preview = rgb
        except Exception:
            with self.lock:
                self.error = traceback.format_exc()
        finally:
            try:
                if self.cap is not None:
                    self.cap.release()
            except Exception:
                with self.lock:
                    self.error = (self.error or "") + traceback.format_exc()
            finally:
                if pipeline is not None:
                    pipeline.close()

    def _run_overlap(self):
        def publish(result):
            sample, rgb = result
            with self.lock:
                if len(self.samples) == self.samples.maxlen:
                    self.dropped_samples += 1
                sample['overlap_skipped_face_packets'] = self.engine.slot.replaced
                self.samples.append(sample)
                self.preview = rgb

        def ready():
            with self.lock:
                self.ready = True

        def error(detail):
            with self.lock:
                self.ready = False
                self.error = (self.error or '') + detail

        self.engine = OverlapRunner(lambda: _OverlapFaceSource(self),
                                    lambda: _OverlapGazeTarget(self.settings),
                                    publish, ready, error, self.stop_event)
        self.engine.run()

    def drain(self):
        with self.lock:
            samples = list(self.samples)
            self.samples.clear()
            return samples, self.preview, self.error

    def close(self):
        self.stop_event.set()
        if self.settings.get('overlap_inference', False):
            if self.engine is not None:
                self.engine.request_stop()
            self.thread.join(timeout=15)
            if self.thread.is_alive():
                raise RuntimeError('Camera/inference owners did not stop cleanly')
            return
        self.thread.join(timeout=5)
        if self.thread.is_alive() and self.cap is not None:
            self.cap.release()
            self.thread.join(timeout=2)


def make_calibration(method, directory):
    directory.mkdir(parents=True, exist_ok=True)
    if method == "ridge_iso":
        # 推荐。实测（留一点交叉验证，390 样本 × 258 维）：
        #   SVR(rbf)         8x8 命中率  0%–10%（随机基线 1.6%）
        #   标准化 Ridge      8x8 命中率 20%–34%
        #   + 逐轴单调校正     8x8 命中率 37%–53%（单帧）、46%–62%（停留投票）
        return RidgeIsotonicCalibration(alpha=1.0, use_isotonic=True, standardize=True)
    if method == "ridge":
        return MultivariateRidgeCalibration(alpha=0.1)
    if method == "svr":
        model = SVRCalibration(model_save_path=str(directory))
        # Always fit fresh for this sitting, including when an earlier XML exists.
        model._set_svm_params(model.svr_x)
        model._set_svm_params(model.svr_y)
        model.has_calibrated = False
        return model
    raise ValueError(f"Unknown calibration: {method}")


def make_filter(settings):
    if settings["filter"] == "heuristic":
        return HeuristicFilter(look_ahead=3)
    if settings["filter"] == "one_euro":
        return OneEuroFilter(freq=settings["camera_fps"],
                             min_cutoff=settings["min_cutoff"], beta=settings["beta"])
    raise ValueError(f"Unknown filter: {settings['filter']}")


_CALIBRATION_POINTS = None


def _make_calibration_points(grid):
    """grid=3: 中心 + 8 边点 + 4 内点 = 13（原布局，保持顺序不变）。
    grid=5: 5×5 = 25 点，边距收到 3%，把屏幕四角纳入标定。"""
    if int(grid) == 5:
        coords = (0.03, 0.265, 0.5, 0.735, 0.97)
        return [(x, y) for y in coords for x in coords]
    edge = [(x, y) for y in (0.05, 0.5, 0.95) for x in (0.05, 0.5, 0.95)]
    points = [(0.5, 0.5)] + [p for p in edge if p != (0.5, 0.5)]
    return points + [(x, y) for y in (0.25, 0.75) for x in (0.25, 0.75)]


def calibration_points():
    global _CALIBRATION_POINTS
    if _CALIBRATION_POINTS is None:
        _CALIBRATION_POINTS = _make_calibration_points(3)
    return _CALIBRATION_POINTS


def set_calibration_grid(grid):
    """grid=3 -> 沿用原来的 13 点布局；grid=5 -> 25 点，覆盖到屏幕四角。

    实测现象：13 点布局下四角误差 429 px，而内部点只有 231 px——
    四角各只由 1 个标定点支撑，外推代价极高。加密到 25 点（边距 3%）
    是"头不动、要精确"这条路线最直接的收益点。
    """
    global _CALIBRATION_POINTS
    _CALIBRATION_POINTS = _make_calibration_points(int(grid))


def validation_points():
    return [(x, y) for y in (0.15, 0.35, 0.65, 0.85) for x in (0.1, 0.3, 0.5, 0.7, 0.9)]


def validation_metrics(records, points, size):
    """Use all valid frames in fixed dwell windows, without target-based selection."""
    per_point = []
    for index, target_norm in enumerate(points):
        rows = [r for r in records if r["point"] == index]
        valid_rows = [r for r in rows if r.get("filtered") is not None]
        target = np.asarray(target_norm) * np.asarray(size)
        result = {"point": index + 1, "target_px": target.tolist(),
                  "frames": len(rows), "valid_frames": len(valid_rows)}
        if valid_rows:
            for field in ("calibrated", "filtered"):
                xy = np.asarray([r[field] for r in valid_rows])
                errors = np.linalg.norm(xy - target, axis=1)
                consecutive = [(valid_rows[j - 1][field], valid_rows[j][field])
                               for j in range(1, len(valid_rows))
                               if valid_rows[j]["sequence"] == valid_rows[j - 1]["sequence"] + 1]
                jitter = (float(np.sqrt(np.mean([np.sum((np.asarray(b) - a) ** 2)
                                                for a, b in consecutive]))) if consecutive else None)
                predicted_cells = np.minimum(np.floor(xy / size * 8).astype(int), 7)
                target_cell = np.minimum(np.floor(target / size * 8).astype(int), 7)
                # 竞赛关心的不是逐帧误差，而是"盯住一个区域能不能选对"。
                # 对整段注视做滑窗多数投票，得到区域级命中率与置信覆盖率。
                dwell_hit, dwell_coverage = dwell_cell_vote(
                    [tuple(int(c) for c in cell) for cell in predicted_cells],
                    tuple(int(c) for c in target_cell), window=12)
                result[field] = {"mean_frame_error_px": float(np.mean(errors)),
                                 "p90_frame_error_px": float(np.percentile(errors, 90)),
                                 "fixation_mean_error_px": float(np.linalg.norm(xy.mean(axis=0) - target)),
                                 "rms_s2s_px": jitter,
                                 "grid_8x8_hit_rate": float(np.mean(np.all(predicted_cells == target_cell, axis=1))),
                                 "grid_8x8_hit_rate_dwell": float(dwell_hit),
                                 "grid_8x8_dwell_coverage": float(dwell_coverage)}
        per_point.append(result)
    total, valid = len(records), sum(r.get("filtered") is not None for r in records)
    summary = {"frames": total, "valid_frames": valid,
               "valid_rate": valid / total if total else 0,
               "completed_points": sum(p["valid_frames"] > 0 for p in per_point),
               "expected_points": len(points), "per_point": per_point}
    for field in ("calibrated", "filtered"):
        results = [p[field] for p in per_point if field in p]
        summary[field] = {}
        if results:
            for key in results[0]:
                values = [p[key] for p in results if p[key] is not None]
                summary[field][key] = float(np.mean(values)) if values else None
    return summary
