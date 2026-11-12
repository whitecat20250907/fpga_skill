"""Read the existing same-frame FPGA planes only when explicitly requested."""
import base64
import io
import threading
import time


class ModelPreview:
    def __init__(self, run):
        self.path = str(run / 'frames.memfd')
        self.lock = threading.Lock()
        self.ring = None
        self.cached = None
        self.cached_ns = 0

    def close(self):
        if self.ring:
            self.ring.close()
            self.ring = None

    def capture(self):
        from PIL import Image
        from core.frame_ring import FrameRing
        from vision.bootstrap import install_vendor_resolver
        install_vendor_resolver()
        from detector_frame import detector_input
        with self.lock:
            now = time.monotonic_ns()
            if self.ring:
                try:self.ring.check_owner()
                except RuntimeError:self.close();self.cached = None
            if self.cached and 0 <= now - self.cached_ns < 500_000_000 and 0 <= now-self.cached['source_ns'] < 500_000_000:
                return dict(self.cached, age_ms=(now-self.cached['source_ns'])/1e6)
            try:
                if not self.ring:self.ring = FrameRing(self.path)
                frame = self.ring.latest()
                if frame is None:raise ValueError('模型帧尚未就绪')
                now = time.monotonic_ns()
                stamp = frame.meta['timestamp_ns']
                if not 0 <= now - stamp < 500_000_000:raise ValueError('模型帧已过期')
                planes = []
                for size, label in ((128, '人脸检测输入'), (192, '手掌检测输入')):
                    pixels = detector_input(frame.rgb, size)
                    if pixels is None:raise ValueError('缺少实际 FPGA 模型平面')
                    stream = io.BytesIO()
                    Image.fromarray(pixels, 'RGB').save(stream, 'PNG')
                    planes.append(dict(size=size, label=label,
                        image='data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode()))
                self.cached = dict(planes=planes, sequence=frame.meta['sequence'],
                    epoch=str(frame.meta['fpga_epoch']), source_ns=stamp,
                    age_ms=(now-stamp)/1e6, contract=frame.meta['detector_contract'])
                self.cached_ns = now
                return self.cached
            except Exception:
                self.close();self.cached=None
                raise
