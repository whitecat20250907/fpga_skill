"""Offline conversion in the EXISTING RK toolkit venv; never imports the webcam demo."""
import ast
import hashlib
import json
import os
from pathlib import Path
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import torch
import torch.nn as nn
import numpy as np
import onnx
import onnxruntime as ort
from rknn.api import RKNN
from trajectory import trajectory_to_image

ROOT = Path(__file__).resolve().parent
out = ROOT/'model'
out.mkdir(exist_ok=False)
torch.set_num_threads(1)
# Extract only the architecture from the frozen original, no top-level imports
# or camera/MediaPipe code is executed.
tree = ast.parse((ROOT/'original/infer.py').read_text(encoding='utf-8-sig'))
node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GestureNet')
namespace = dict(nn=nn)
exec(compile(ast.Module(body=[node], type_ignores=[]), 'original/GestureNet', 'exec'), namespace)
classes = json.loads((ROOT/'original/gesture_classes.json').read_text())['class_names']
model = namespace['GestureNet'](len(classes))
model.load_state_dict(torch.load(ROOT/'original/gesture_8class.pth', map_location='cpu', weights_only=True))
model.eval()
torch.onnx.export(model, torch.zeros(1,1,28,28), str(out/'gesture8.onnx'),
                  input_names=['trajectory'], output_names=['logits'], opset_version=13,
                  do_constant_folding=True)
onnx.checker.check_model(onnx.load(str(out/'gesture8.onnx')))
opts = ort.SessionOptions(); opts.intra_op_num_threads=1; opts.inter_op_num_threads=1
session = ort.InferenceSession(str(out/'gesture8.onnx'), opts, providers=['CPUExecutionProvider'])
paths = [([(10,10),(10,90),(70,90)]), ([(70,10),(70,90),(10,90)]),
         ([(10,90),(10,10),(70,10)]), ([(70,90),(70,10),(10,10)]),
         ([(10,90),(10,10),(40,60),(70,10),(70,90)]),
         ([(10,10),(25,90),(40,40),(55,90),(70,10)]),
         ([(10,10),(70,10),(10,90),(70,90)]),
         ([(50+40*np.cos(t),50+40*np.sin(t)) for t in np.linspace(0,2*np.pi,80)])]
images = [np.zeros((28,28),np.uint8), np.full((28,28),255,np.uint8)]
images += [trajectory_to_image(p) for p in paths]
rng = np.random.default_rng(3576)
images += [rng.integers(0,256,(28,28),dtype=np.uint8) for _ in range(16)]
images = np.stack(images)
with torch.no_grad():
    expected = model(torch.from_numpy(images[:,None].astype(np.float32)/255.)).numpy()
actual = np.concatenate([session.run(None, {'trajectory':im[None,None].astype(np.float32)/255.})[0] for im in images])
np.testing.assert_allclose(actual, expected, atol=2e-5, rtol=2e-5)
np.savez_compressed(out/'vectors.npz', images=images, torch_logits=expected)
compiler = RKNN(verbose=False)
try:
    for name, call in [('config',lambda:compiler.config(target_platform='rk3576',float_dtype='float16',optimization_level=3)),
                       ('load',lambda:compiler.load_onnx(model=str(out/'gesture8.onnx'))),
                       ('build',lambda:compiler.build(do_quantization=False)),
                       ('export',lambda:compiler.export_rknn(str(out/'gesture8_fp16.rknn')))]:
        if call() != 0: raise RuntimeError(name+' failed')
finally:
    compiler.release()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
report = dict(classes=classes, source_sha256=sha(ROOT/'original/gesture_8class.pth'),
              rknn_sha256=sha(out/'gesture8_fp16.rknn'), onnx_sha256=sha(out/'gesture8.onnx'),
              parameters=sum(p.numel() for p in model.parameters()),
              torch_onnx_max_abs=float(np.abs(expected-actual).max()), test_vectors=len(images),
              input='float32 NHWC 1x28x28x1, /255 exactly once; no mean/std',
              synthetic_vectors=True, human_accuracy_tested=False)
(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report), flush=True)
