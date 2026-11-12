"""Actual RK3576 NPU worker ABBA on one repeated photo; no camera/game FPS."""
import argparse,hashlib,json,os,sys,threading,time
from pathlib import Path
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent/'GazeFollower'))
import gaze_runtime as runtime

ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();assert not a.output.exists()
image_path=runtime.REPO/'tests/asset/example.jpg';image=cv2.imread(str(image_path));assert image is not None
image=cv2.resize(image,(640,360));settings=runtime.load_settings();assert settings['face_cpu_threads']==4
original_camera=runtime.open_camera;original_estimator=runtime.RKNNGazeEstimator
instances=[]
def estimator(*args,**kwargs):
 value=original_estimator(*args,**kwargs);instances.append(value);return value
class PhotoCapture:
 def __init__(self,_):self.closed=False;self.last_metadata=None;self.counter=0
 def read(self):
  if self.closed:return False,None
  self.counter+=1;stamp=time.monotonic_ns();self.last_metadata=dict(timestamp_ns=stamp,dequeue_ns=stamp,sequence=self.counter)
  return True,image.copy()
 def request_stop(self):self.closed=True
 def release(self):self.closed=True
runtime.open_camera=PhotoCapture;runtime.RKNNGazeEstimator=estimator
rows=[]
try:
 for overlap in (False,True,True,False):
  instances.clear();cfg=dict(settings,overlap_inference=overlap);worker=runtime.CameraWorker(cfg);records=[];seen=0
  worker.start();deadline=time.monotonic()+90
  try:
   while len(records)<25:
    samples,_,error=worker.drain()
    if error:raise RuntimeError(error)
    for s in samples:
     seen+=1
     assert s['valid'] and s['face_detected'] and s['timings']['npu_called'] and len(s['features'])==258
     if seen<=5:continue
     assert not records or s['timestamp_ns']>records[-1]['timestamp_ns']
     records.append(dict(timestamp_ns=s['timestamp_ns'],observed_ns=time.monotonic_ns(),infer_ms=s['infer_ms'],timings=s['timings'],features=s['features'].tolist(),
                         capture_to_observed_ms=(time.monotonic_ns()-s['timestamp_ns'])/1e6))
     if len(records)==25:break
    if time.monotonic()>deadline:raise TimeoutError('Actual photo/NPU worker progress stalled')
    time.sleep(.002)
   assert len(instances)==1 and instances[0].backend=='RK3576_NPU_RKNNLite'
   assert instances[0].model_sha256=='9eeeaedd671d6cab7c7a637175e8c540b8649d315d2cd25d085a35a4c0801ad2'
   model_hash=instances[0].model_sha256
  finally:worker.close()
  assert not worker.thread.is_alive() and (worker.engine is None or not worker.engine.target_thread.is_alive())
  duration=(records[-1]['observed_ns']-records[0]['observed_ns'])/1e9
  row=dict(overlap=overlap,CPU_threads=cfg['face_cpu_threads'],face_mode=cfg['face_running_mode'],samples=len(records),
           completed_photo_samples_per_s=(len(records)-1)/duration,
           age_p50_ms=float(np.percentile([s['capture_to_observed_ms'] for s in records],50)),
           age_p95_ms=float(np.percentile([s['capture_to_observed_ms'] for s in records],95)),
           stage_ms={k:float(np.median([s['timings'][k] for s in records])) for k in ('face_ms','color_ms','estimator_ms','npu_ms')},
           backend='RK3576_NPU_RKNNLite',model_SHA256=model_hash,records=records)
  rows.append(row);print('PHOTO_ROUND',overlap,row['completed_photo_samples_per_s'],row['age_p95_ms'],flush=True)
finally:
 runtime.open_camera=original_camera;runtime.RKNNGazeEstimator=original_estimator
serial=[r for r in rows if not r['overlap']];parallel=[r for r in rows if r['overlap']]
rate_ratio=float(np.mean([r['completed_photo_samples_per_s'] for r in parallel])/np.mean([r['completed_photo_samples_per_s'] for r in serial]))
age_ratio=float(np.mean([r['age_p95_ms'] for r in parallel])/np.mean([r['age_p95_ms'] for r in serial]))
passed=rate_ratio>=1.10 and age_ratio<=1.15
out=dict(status='MEASURED_PHOTO_OVERLAP_FASTER_WITHIN_AGE_GATE' if passed else 'MEASURED_PHOTO_OVERLAP_DID_NOT_PASS_RATE_AND_AGE_GATE',rows=rows,
 throughput_ratio=rate_ratio,p95_age_ratio=age_ratio,criterion=dict(minimum_rate_ratio=1.10,maximum_age_ratio=1.15),
 input_photo_sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),actual_NPU_executed=True,physical_camera_used=False,
 camera_FPS_live_face_accuracy_control_gameplay_or_deployment_accepted=False,
 scope='Single fixed photo repeated through actual candidate CameraWorker, original MediaPipe and original MGazeNet RK3576 NPU; serial baseline uses unchanged Pipeline.infer. ABBA, CPU4/default face mode, one NPU owner per round. Measures worker capacity/age for this input only.')
a.output.write_text(json.dumps(out,indent=2)+'\n');print(out['status'],rate_ratio,age_ratio,flush=True)
