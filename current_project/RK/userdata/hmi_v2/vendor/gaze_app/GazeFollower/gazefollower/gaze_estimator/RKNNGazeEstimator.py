"""MGazeNet preprocessing and on-device RK3576 RKNN execution.

Preprocessing follows GazeFollower MGazeNetGazeEstimator (GC Zhu), retained in
source_mouse3 with its original license. MNN is never a runtime fallback.
"""
import hashlib
import platform
import time
from pathlib import Path
import cv2
import numpy as np
from .GazeEstimator import GazeEstimator
from ..misc import GazeInfo, TrackingState, clip_patch


def prepare_inputs(image, face):
    """RGB8 full processed image -> left, face, rect, right native NHWC image tensors (rect unchanged)."""
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError('Expected RGB uint8 HxWx3')
    if (face.img_h, face.img_w) != image.shape[:2]:
        raise ValueError('Face rectangles and image dimensions differ')
    boxes = [np.asarray(r) for r in (face.face_rect, face.left_rect, face.right_rect)]
    if any(r.shape != (4,) or not np.isfinite(r).all() or
           not np.equal(r, r.astype(np.int64)).all() for r in boxes):
        raise ValueError('Face alignment must provide integer pixel rectangles')
    boxes = [r.astype(np.int64) for r in boxes]
    patches = [clip_patch(image, r) for r in boxes]
    if any(p is None or not p.size for p in patches):
        return None
    # Preserve original requested rectangles in rect12 even when clip_patch
    # clips the right/bottom edge; this matches the original implementation.
    rect = np.array([v for x,y,w,h in boxes for v in (w,h,x,y)], np.float32)
    rect = (rect / np.array([face.img_w,face.img_h]*6,np.float32)).reshape(1,12)
    resized = [cv2.resize(p, (n,n)).astype(np.float32)/255.0
               for p,n in zip(patches,(224,112,112))]
    resized[2] = cv2.flip(resized[2],1)
    tensors = [np.ascontiguousarray(p[None]) for p in resized]
    return [tensors[1],tensors[0],rect,tensors[2]]


class RKNNGazeEstimator(GazeEstimator):
    def __init__(self, model_path):
        super().__init__()
        self.model_path = Path(model_path).resolve()
        if platform.machine() != 'aarch64' or not self.model_path.is_file():
            raise RuntimeError('RK3576 and an explicit compiled RKNN model are required')
        compatible = Path('/sys/firmware/devicetree/base/compatible').read_bytes()
        driver = Path('/sys/bus/platform/devices/27700000.npu/driver')
        if b'rockchip,rk3576' not in compatible or driver.resolve().name != 'RKNPU':
            raise RuntimeError('RK3576 RKNPU driver is unavailable')
        from rknnlite.api import RKNNLite
        self.runtime = RKNNLite(verbose=False)
        try:
            if self.runtime.load_rknn(str(self.model_path)) != 0:
                raise RuntimeError('Cannot load RKNN gaze model')
            if self.runtime.init_runtime(core_mask=RKNNLite.NPU_CORE_AUTO) != 0:
                raise RuntimeError('Cannot initialize on-device RK3576 NPU')
        except Exception:
            self.release()
            raise
        self.backend = 'RK3576_NPU_RKNNLite'
        self.model_sha256 = hashlib.sha256(self.model_path.read_bytes()).hexdigest()

    def detect(self, image, face_info):
        self.last_timings = {"prepare_ms": 0.0, "npu_ms": 0.0, "npu_called": False}
        gaze = GazeInfo(timestamp=face_info.timestamp)
        if not face_info.status:
            gaze.tracking_state = TrackingState.FACE_MISSING
            return gaze
        if not face_info.can_gaze_estimation:
            gaze.tracking_state = TrackingState.OUT_OF_BOUNDARIES
            return gaze
        started = time.perf_counter()
        inputs = prepare_inputs(image,face_info)
        self.last_timings["prepare_ms"] = (time.perf_counter()-started)*1000
        if inputs is None:
            gaze.tracking_state = TrackingState.OUT_OF_BOUNDARIES
            return gaze
        started = time.perf_counter()
        result = self.runtime.inference(inputs=inputs,data_format=['nhwc','nhwc','nchw','nhwc'])
        self.last_timings.update(npu_ms=(time.perf_counter()-started)*1000, npu_called=True)
        if not isinstance(result,list) or len(result) != 1:
            raise RuntimeError('Invalid RKNN model output list')
        output = np.asarray(result[0],dtype=np.float32).reshape(-1).copy()
        if output.size != 258 or not np.isfinite(output).all():
            raise RuntimeError('RKNN model must produce 258 finite features')
        gaze.features = output
        gaze.raw_gaze_coordinates = output[:2].copy()
        gaze.status = True
        gaze.left_openness = face_info.left_eye_openness
        gaze.right_openness = face_info.right_eye_openness
        gaze.tracking_state = TrackingState.SUCCESS
        return gaze

    def release(self):
        if getattr(self,'runtime',None) is not None:
            self.runtime.release()
            self.runtime = None
