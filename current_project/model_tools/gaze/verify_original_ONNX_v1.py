"""Run actual original MNN Module/NHWC against converted ONNX/NCHW offline."""
import argparse,hashlib,importlib.metadata,json,time
from pathlib import Path
import numpy as np
import MNN
import onnxruntime as ort
M=Path(__file__).resolve().parents[1];ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);ap.add_argument('--mnn-precision',choices=['low','high'],default='low');a=ap.parse_args();assert a.attempt.startswith('ONNX_numeric_v') and a.attempt.removeprefix('ONNX_numeric_v').isdigit();O=M/'evidence'/a.attempt;O.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();model=M/'source_mouse3/GazeFollower/gazefollower/res/model_weights/base.mnn';converted=M/'evidence/ONNX_conversion_v2/original_gaze.onnx'
rt=MNN.nn.create_runtime_manager(({'precision':a.mnn_precision,'backend':0,'numThread':2},));mod=MNN.nn.load_module_from_file(str(model),['face','left','right','rect'],['output_0'],runtime_manager=rt)
config=ort.SessionOptions();config.intra_op_num_threads=2;config.inter_op_num_threads=1;config.log_severity_level=3
session=ort.InferenceSession(str(converted),sess_options=config,providers=['CPUExecutionProvider'])
variables=[MNN.expr.placeholder((1,n,n,3),MNN.expr.NHWC) for n in (224,112,112)]+[MNN.expr.placeholder((1,12))]
rng=np.random.default_rng(3576415);results=[];stored={};atol=5e-5;rtol=3e-4
cases=['black','white','red','green','blue','gradient','checker','asymmetric_eyes']+[f'random_{i}' for i in range(8)]
for case in cases:
 data={}
 for name,n in [('face',224),('left',112),('right',112)]:
  if case=='black':x=np.zeros((n,n,3),np.float32)
  elif case=='white':x=np.ones((n,n,3),np.float32)
  elif case in ('red','green','blue'):x=np.zeros((n,n,3),np.float32);x[:,:,('red','green','blue').index(case)]=1
  elif case=='gradient':
   yy,xx=np.meshgrid(np.linspace(0,1,n,dtype=np.float32),np.linspace(0,1,n,dtype=np.float32),indexing='ij');x=np.stack([xx,yy,(xx+yy)/2],axis=-1)
  elif case=='checker':x=np.repeat(((np.indices((n,n)).sum(0)//7)%2).astype(np.float32)[...,None],3,axis=-1)
  elif case=='asymmetric_eyes':x=np.full((n,n,3),{'face':0.5,'left':0.05,'right':0.95}[name],np.float32)
  else:x=rng.random((n,n,3),dtype=np.float32)
  # Already-model-input test. Actual ROI/cv2 resize/flip chain is a separate gate.
  data[name]=x[None]
 rect=np.array([[.4,.6,.3,.2,.08,.07,.4,.4,.08,.07,.54,.4]],np.float32)
 if case.startswith('random_'):rect+=rng.uniform(-.02,.02,rect.shape).astype(np.float32)
 data['rect']=rect
 for var,name in zip(variables,('face','left','right','rect')):var.write(np.ascontiguousarray(data[name]))
 start=time.perf_counter();reference=np.array(mod.onForward(variables)[0].read(),dtype=np.float32).reshape(1,258);mnn_ms=(time.perf_counter()-start)*1000
 feed={name:np.ascontiguousarray(x.transpose(0,3,1,2)) if x.ndim==4 else x for name,x in data.items()}
 start=time.perf_counter();actual=session.run(['output_0'],feed)[0];onnx_ms=(time.perf_counter()-start)*1000
 assert actual.shape==reference.shape==(1,258)
 error=np.abs(reference-actual);valid=np.isfinite(reference).all() and np.isfinite(actual).all();passed=bool(valid and np.allclose(actual,reference,atol=atol,rtol=rtol))
 results.append({'case':case,'passed':passed,'max_abs_error':float(error.max()),'mean_abs_error':float(error.mean()),'raw_xy_error':error[0,:2].tolist(),'MNN_ms':mnn_ms,'ONNX_ms':onnx_ms})
 for k,x in data.items():stored[case+'_'+k]=x
 stored[case+'_MNN']=reference;stored[case+'_ONNX']=actual
 print(json.dumps(results[-1]),flush=True)
np.savez_compressed(O/'vectors.npz',**stored)
ok=all(x['passed'] for x in results)
r={'status':'PASS_ORIGINAL_MNN_VS_STATIC_ONNX_OFFLINE_16_CASES' if ok else 'FAIL_ORIGINAL_MNN_VS_STATIC_ONNX_OFFLINE','cases':results,'absolute_tolerance':atol,'relative_tolerance':rtol,'MNN_backend':f'CPU backend0 precision {a.mnn_precision},2threads','original_wrapper_precision':a.mnn_precision=='low','ONNX_backend':session.get_providers(),'model':{'path':str(model),'sha256':sha(model)},'ONNX':{'path':str(converted),'sha256':sha(converted)},'vectors':{'path':str(O/'vectors.npz'),'sha256':sha(O/'vectors.npz')},'source':{'path':str(Path(__file__)),'sha256':sha(__file__)},'versions':{n:importlib.metadata.version(n) for n in ('MNN','onnx','onnxruntime','numpy')},'scope':'16 deterministic full four-input tensors using NHWC MNN Module versus translated NCHW ONNX. All258 outputs. High precision is a diagnostic reference and does not replace original low-precision-wrapper acceptance. Synthetic inputs, not real camera crops, calibration, RKNN or RK3576 NPU. Timings include first call and are host-only; no device performance acceptance.','RK_NPU_executed':False,'full_migration_complete':False}
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(r['status']);assert ok
