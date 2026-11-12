"""On-board stage profile of a repeated repository face image, not camera FPS."""
import argparse,json,time,hashlib
from pathlib import Path
import cv2
import numpy as np
from run_gaze import Pipeline,load_settings,REPO,model_metadata

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--face-mode',choices=['image','video'],required=True)
a=p.parse_args()
assert not a.output.exists()
settings=load_settings({"face_running_mode":a.face_mode})
image_path=REPO/'tests/asset/example.jpg'
image=cv2.imread(str(image_path));assert image is not None
image=cv2.resize(image,(settings['camera_width'],settings['camera_height']))
pipeline=Pipeline(settings);records=[]
try:
 for index in range(25):
  started=time.perf_counter()
  face,gaze,valid,rgb=pipeline.infer(image,time.monotonic_ns())
  record={**pipeline.last_timings,'total_ms':(time.perf_counter()-started)*1000,'valid':bool(valid)}
  assert face.status and gaze.status and record['npu_called'] and len(gaze.features)==258
  if index>=5:records.append(record)
 backend=pipeline.estimator.backend
finally:pipeline.close()
assert backend=='RK3576_NPU_RKNNLite'
stats={key:{'p50':float(np.percentile([r[key] for r in records],50)),'p95':float(np.percentile([r[key] for r in records],95))} for key in records[0] if key.endswith('_ms')}
report={'status':'PASS_REAL_RK3576_NPU_REPEATED_IMAGE_STAGE_PROFILE_ONLY','backend':backend,'face_mode':a.face_mode,'model':model_metadata(settings),'source_image_sha256':hashlib.sha256(image_path.read_bytes()).hexdigest(),'input_shape':list(image.shape),'timing_ms':stats,'records':records,'camera_fps_measured':False,'accuracy_accepted':False}
a.output.write_text(json.dumps(report,indent=2));print(json.dumps(stats,indent=2))
