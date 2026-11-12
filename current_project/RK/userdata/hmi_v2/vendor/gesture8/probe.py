import importlib.util
import importlib.metadata
import json
import sys
print(json.dumps(dict(python=sys.executable, modules={x:bool(importlib.util.find_spec(x)) for x in ['torch','onnx','onnxruntime','mediapipe','rknnlite','cv2','rknn']})),flush=True)
