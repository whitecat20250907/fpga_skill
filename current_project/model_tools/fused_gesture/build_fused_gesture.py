"""Compose existing FP16 graphs without changing learned parameters."""
import json,hashlib,time,os
from pathlib import Path
os.environ['OMP_NUM_THREADS']='1'
os.environ['OPENBLAS_NUM_THREADS']='1'
import onnx
from onnx import compose,helper
from rknn.api import RKNN
root=Path('/userdata/hmi_v2/vendor/vision_npu/models')
out=Path('/home/linaro/pcie_fix_20261003/optimization61/models');out.mkdir(parents=True,exist_ok=True)
a=onnx.load(root/'gesture_embedder.onnx');b=onnx.load(root/'canned_gesture_classifier.onnx')
print('inputs',[(x.name,str(x.type.tensor_type.shape)) for x in a.graph.input],flush=True)
aa=compose.add_prefix(a,'embed_');bb=compose.add_prefix(b,'head_')
edge=(aa.graph.output[0].name,bb.graph.input[0].name)
# Keep the embedding output for independent same-input A/B and original adapter contract.
merged=compose.merge_models(aa,bb,io_map=[edge],outputs=[aa.graph.output[0].name,bb.graph.output[0].name])
onnx.checker.check_model(merged)
path=out/'gesture_fused.onnx';onnx.save(merged,path)
io=json.loads((root/'gesture_embedder.io.json').read_text());io['outputs']+=json.loads((root/'canned_gesture_classifier.io.json').read_text())['outputs']
for row in io['inputs']:row['name']='embed_'+row['name']
for row,name in zip(io['outputs'],[edge[0],bb.graph.output[0].name]):row['name']=name
(out/'gesture_fused.io.json').write_text(json.dumps(io,indent=2))
r=RKNN(verbose=False);t=time.monotonic()
try:
 for stage,fn in [('config',lambda:r.config(target_platform='rk3576',float_dtype='float16',optimization_level=3)),('load',lambda:r.load_onnx(model=str(path))),('build',lambda:r.build(do_quantization=False)),('export',lambda:r.export_rknn(str(path.with_suffix('.rknn'))))]:
  rc=fn();print(stage,rc,flush=True)
  if rc:raise RuntimeError((stage,rc))
 report={'rknn_sha256':hashlib.sha256(path.with_suffix('.rknn').read_bytes()).hexdigest(),'onnx_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sources':{n:hashlib.sha256((root/(n+'.onnx')).read_bytes()).hexdigest() for n in ('gesture_embedder','canned_gesture_classifier')},'seconds':time.monotonic()-t,'format':'FP16','weights_changed':False}
 path.with_suffix('.build.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
finally:r.release()
