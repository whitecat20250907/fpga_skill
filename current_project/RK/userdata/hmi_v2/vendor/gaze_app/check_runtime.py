import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'GazeFollower'))
import cv2,numpy as np
from gaze_runtime import Pipeline,load_settings
p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();a.output.mkdir(exist_ok=False)
settings=load_settings();pipeline=Pipeline(settings);rows=[];data={}
try:
 for i,name in enumerate(['example.jpg','1718417729052.jpg']):
  image=cv2.imread(str(ROOT/'GazeFollower/tests/asset'/name));assert image is not None
  t=time.perf_counter();face,gaze,valid,rgb=pipeline.infer(image,time.monotonic_ns());ms=(time.perf_counter()-t)*1000
  row={'file':name,'face_detected':bool(face.status),'gaze_valid':valid,'pipeline_ms':ms,'face_rect':np.asarray(face.face_rect).tolist(),'left_rect':np.asarray(face.left_rect).tolist(),'right_rect':np.asarray(face.right_rect).tolist(),'eye_openness':[float(face.left_eye_openness),float(face.right_eye_openness)]};rows.append(row)
  if gaze.status:data['image'+str(i)+'_NPU']=gaze.features;data['image'+str(i)+'_RGB']=rgb;data['image'+str(i)+'_rects']=np.asarray([face.face_rect,face.left_rect,face.right_rect])
 r={'status':'PASS_TWO_REPOSITORY_IMAGES_MEDIAPIPE_AND_NPU' if all(x['gaze_valid'] for x in rows) else 'FAIL_REPOSITORY_IMAGE_PIPELINE','cases':rows,'backend':pipeline.estimator.backend,'model_sha256':pipeline.estimator.model_sha256,'MediaPipe_tasks_api':pipeline.aligner.use_tasks_api,'camera_opened':False,'calibration_accepted':False}
 np.savez_compressed(a.output/'image_outputs.npz',**data);(a.output/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
finally:pipeline.close()
