"""Reuse approved eye quality/ROI geometry without constructing CPU networks."""
import os,sys,time
from pathlib import Path
from types import SimpleNamespace
import cv2,numpy as np
APP=Path(os.environ.get('GAZE_APP_DIR','/userdata/gaze_model_migration_v1_20261014/app_v34_cpu_reuse_20261022'))
sys.path.insert(0,str(APP));sys.path.insert(0,str(APP/'GazeFollower'))
from gazefollower.face_alignment.MediaPipeFaceAlignment import MediaPipeFaceAlignment as OriginalGeometry
from gazefollower.misc import OneEuroFilter,FaceInfo
from vision_pipeline import LandmarkPipeline,points
from npu_runtime import Model
from runtime_policy import POLICY

class Selected:
    def __init__(self):self.value=[]
    def detect_for_video(self,*args):return SimpleNamespace(face_landmarks=self.value)
    def detect(self,*args):return SimpleNamespace(face_landmarks=self.value)
    def close(self):pass

class Geometry(OriginalGeometry):
    def __init__(self):
        # Intentionally do not call the parent initializer: it constructs
        # MediaPipe CPU graphs. Only its verified detect()/eye geometry is reused.
        self.running_mode='video';self.last_video_timestamp_ms=None
        self.enable_filter=False;self.cpu_threads=0;self.use_tasks_api=True
        self.face_mesh=None;self.landmarker=Selected();self._fallback_blazeface=None
        self.face_rect_filter=OneEuroFilter(timestamp_unit='ns');self.left_rect_filter=OneEuroFilter(timestamp_unit='ns')
        self.right_rect_filter=OneEuroFilter(timestamp_unit='ns');self.landmarks_filter=OneEuroFilter(timestamp_unit='ns')
        self.lip_vertices_index=[61,91,14,178,402,324,95]
        self.left_vertices_index=[33,246,161,160,159,158,157,173,133,155,154,153,145,144,163,7,33]
        self.right_vertices_index=[362,388,384,385,386,387,388,466,263,249,380,373,374,380,381,382,362]
    def from_points(self,p,rgb,timestamp,sequence=None):
        from geometry_array import from_array
        return from_array(self,p,rgb.shape,timestamp,sequence)
    def _get_fallback_blazeface(self):return None

class NPUFaceAlignment:
    def __init__(self,*args,num_faces=None,core=None,backend=Model,**kwargs):
        count=num_faces if num_faces is not None else int(os.environ.get('NPU_MAX_FACES','1'))
        if core is None:core=int(os.environ.get('NPU_FACE_CORE',str(POLICY.get('face_core',0))))
        self.pipeline=LandmarkPipeline(False,count,backend=backend,core=core);self.geometries={};self.empty=Geometry()
        self.primary_id=None
    def detect_all(self,timestamp,image,*,color_order='bgr',capture_sequence=None):
        if color_order not in ('rgb','bgr'):raise ValueError('color_order')
        rgb=image if color_order=='rgb' else cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
        raw=self.pipeline.process(rgb,timestamp/1e9);faces=[]
        for r in raw:
            if r['id'] not in self.geometries:self.geometries[r['id']]=Geometry()
            g=self.geometries[r['id']]
            f=g.from_points(r['landmarks'],rgb,timestamp,capture_sequence);f.track_id=r['id'];faces.append(f)
        active={r['id'] for r in raw};self.geometries={k:v for k,v in self.geometries.items() if k in active}
        return faces
    def detect(self,timestamp,image,*,color_order='bgr',capture_sequence=None):
        faces=self.detect_all(timestamp,image,color_order=color_order,capture_sequence=capture_sequence)
        if faces:
            selected=next((f for f in faces if f.track_id==self.primary_id),faces[0]);self.primary_id=selected.track_id
            selected.additional_faces=[f for f in faces if f is not selected];return selected
        rgb=image if color_order=='rgb' else cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
        f=self.empty.from_points(None,rgb,timestamp,capture_sequence);f.additional_faces=[];return f
    def release(self):self.pipeline.close();self.geometries.clear()
    def reset_filters(self):
        self.pipeline.reset();self.geometries.clear();self.primary_id=None

class GazePipeline:
    def __init__(self,faces=2,core=None,backend=Model):
        from gaze_runtime import load_settings
        from gaze_model import GazeModel as RKNNGazeEstimator
        self.settings=load_settings();self.face=NPUFaceAlignment(num_faces=faces,core=core,backend=backend)
        try:self.estimator=RKNNGazeEstimator(str(APP/self.settings['model_path']))
        except BaseException:self.face.release();raise
    def process(self,rgb,stamp=None):
        from gaze_runtime import estimate_with_eye_gate
        stamp=time.monotonic_ns() if stamp is None else stamp;t=time.perf_counter()
        faces=self.face.detect_all(stamp,rgb,color_order='rgb');detected=time.perf_counter();rows=[]
        for face in faces:
            if not 0<=(time.monotonic_ns()-stamp)/1e9<self.settings.get('max_sample_age',.5):
                rows.append(dict(id=face.track_id,valid=False,stale=True));continue
            gaze=estimate_with_eye_gate(self.estimator,rgb,face,self.settings)
            rows.append(dict(id=face.track_id,valid=bool(gaze.status),stale=False,raw=np.asarray(gaze.raw_gaze_coordinates).tolist() if gaze.status else None,
                eye_openness=[float(face.left_eye_openness),float(face.right_eye_openness)],timings=dict(self.estimator.last_timings)))
        return dict(faces=len(faces),people=rows,face_ms=(detected-t)*1000,total_ms=(time.perf_counter()-t)*1000,age_ms=(time.monotonic_ns()-stamp)/1e6)
    def close(self):self.face.release();self.estimator.release()
