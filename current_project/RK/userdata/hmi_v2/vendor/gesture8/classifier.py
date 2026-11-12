"""RK3576 NPU classifier; loaded once and called only when a stroke completes."""
import hashlib
import json
from pathlib import Path
import numpy as np


class Classifier:
    def __init__(self, root):
        root = Path(root)
        info = json.loads((root/'model/manifest.json').read_text())
        model = root/'model/gesture8_fp16.rknn'
        if hashlib.sha256(model.read_bytes()).hexdigest() != info['rknn_sha256']:
            raise RuntimeError('Gesture model hash mismatch')
        self.classes = info['classes']
        from rknnlite.api import RKNNLite
        self.runtime = RKNNLite(verbose=False)
        try:
            if self.runtime.load_rknn(str(model)) != 0:
                raise RuntimeError('Cannot load gesture RKNN')
            if self.runtime.init_runtime(core_mask=RKNNLite.NPU_CORE_AUTO) != 0:
                raise RuntimeError('Cannot initialize RK3576 NPU')
        except BaseException:
            self.close()
            raise

    def predict(self, image):
        if image.shape != (28, 28) or image.dtype != np.uint8:
            raise ValueError('Expected uint8 28x28 training raster')
        x = np.ascontiguousarray(image[None, :, :, None].astype(np.float32)/255.)
        output = self.runtime.inference(inputs=[x], data_format=['nhwc'])
        if not isinstance(output, list) or len(output) != 1:
            raise RuntimeError('Unexpected classifier output')
        logits = np.asarray(output[0], dtype=np.float32).reshape(-1)
        if logits.size != 8 or not np.isfinite(logits).all():
            raise RuntimeError('Expected 8 finite logits')
        probs = np.exp(logits-logits.max()); probs /= probs.sum()
        index = int(probs.argmax())
        return dict(label=self.classes[index], confidence=float(probs[index]),
                    accepted=bool(probs[index] >= .60), probabilities=probs.tolist())

    def close(self):
        if self.runtime is not None:
            self.runtime.release()
            self.runtime = None
