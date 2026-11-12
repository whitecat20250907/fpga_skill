import json,sys,time,resource
from pathlib import Path
import numpy as np
from rknnlite.api import RKNNLite
sys.path.insert(0,'/userdata/hmi_v2/vendor/vision_npu')
from npu_runtime import Model
root=Path('/home/linaro/pcie_fix_20261003/optimization61')
a=Model('gesture_embedder');b=Model('canned_gesture_classifier');f=RKNNLite(verbose=False)
assert f.load_rknn(str(root/'models/gesture_fused.rknn'))==0
assert f.init_runtime(core_mask=0)==0
inputs=[];fixture=Path('/userdata/all_models_npu_20261022/fixture_final/fixtures.npz')
if fixture.exists():
 with np.load(fixture) as z:
  for key in z.files:
   if 'gesture_embedder' in key and z[key].shape==(1,21,3):inputs.append(z[key].astype(np.float32))
fixture_count=len(inputs);rng=np.random.default_rng(61)
for _ in range(256):
 x=rng.normal(size=(1,21,3)).astype(np.float32);x-=x[:,:1];x/=max(np.ptp(x[:,:,0]),np.ptp(x[:,:,1]))+1e-5;inputs.append(x)
errors=[];different=0
def fused(x):return f.inference(inputs=[x],data_format=['nchw'])
try:
 for x in inputs:
  emb=a(x,None,None)[0];prob=b(emb)[0];got=fused(x)
  errors.append([float(np.max(np.abs(emb-got[0].reshape(emb.shape)))),float(np.max(np.abs(prob-got[1].reshape(prob.shape))))]);different+=int(np.argmax(prob)!=np.argmax(got[1]))
 rows=[]
 # Alternate order reduces monotonic warmup bias. Keep runtime services unchanged.
 for mode in ('original','fused','fused','original'):
  t=time.monotonic();cpu=resource.getrusage(resource.RUSAGE_SELF);ct=cpu.ru_utime+cpu.ru_stime;times=[];n=0
  while time.monotonic()-t<8:
   x=inputs[n%len(inputs)];s=time.perf_counter_ns()
   if mode=='original':b(a(x,None,None)[0])
   else:fused(x)
   times.append((time.perf_counter_ns()-s)/1e6);n+=1
  duration=time.monotonic()-t;cpu=resource.getrusage(resource.RUSAGE_SELF)
  rows.append(dict(mode=mode,calls=n,duration_s=duration,mean_ms=float(np.mean(times)),p95_ms=float(np.percentile(times,95)),cpu_ms_per_call=1000*(cpu.ru_utime+cpu.ru_stime-ct)/n))
 result=dict(fixture_count=fixture_count,total_inputs=len(inputs),max_abs_embedding=max(x[0] for x in errors),max_abs_probability=max(x[1] for x in errors),class_mismatches=different,rows=rows,scope='Actual NPU; fixed tensors under live-service contention, not end-to-end live hand accuracy.')
 result['pass']=result['max_abs_probability']<=.01 and different==0
 (root/'fused_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
finally:a.close();b.close();f.release()
