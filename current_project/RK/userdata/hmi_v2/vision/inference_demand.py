"""Fresh engine demand shared by capture and inference threads.

Models stay loaded; suspended demand admits no frame or NPU forward. Keeping
the model objects avoids reinitialization latency on each gesture.
"""
import threading
import time


class InferenceDemand:
    def __init__(self):
        self.lock = threading.Lock()
        self.state_ns = 0
        self.epoch = 0
        self.face_hz = self.gaze_hz = 0
        self.since_ns = 0
        self.reason = 'waiting_engine'
        self.face_calls = self.gaze_calls = self.gaze_npu_calls = 0

    def update(self, state, epoch, now=None):
        now = time.monotonic_ns() if now is None else now
        valid = state.get('epoch') == epoch and 0 <= now-state.get('src_ns', 0) <= 350_000_000
        b = state.get('budget', {}) if valid and not state.get('estop') else {}
        face, gaze = max(0, b.get('face_hz', 0)), max(0, b.get('gaze_hz', 0))
        with self.lock:
            if (face > 0 and self.face_hz <= 0) or (gaze > 0 and self.gaze_hz <= 0) or self.epoch != epoch:
                self.since_ns = now
            self.state_ns = state.get('src_ns', 0) if valid else 0
            self.epoch, self.face_hz, self.gaze_hz = epoch, face, gaze
            self.reason = b.get('reason', 'paused')

    def rate(self, name='face', now=None):
        now = time.monotonic_ns() if now is None else now
        with self.lock:
            if not self.state_ns or not 0 <= now-self.state_ns <= 350_000_000:
                return 0
            return self.face_hz if name == 'face' else self.gaze_hz

    def accepts(self, stamp, name='face', now=None):
        return self.rate(name, now) > 0 and type(stamp) is int and stamp > self.since_ns

    def snapshot(self):
        return dict(face_hz=self.rate('face'), gaze_hz=self.rate('gaze'),
                    reason=self.reason, face_calls=self.face_calls,
                    gaze_calls=self.gaze_calls, gaze_npu_calls=self.gaze_npu_calls)
