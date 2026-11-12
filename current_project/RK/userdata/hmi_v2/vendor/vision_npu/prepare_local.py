"""Create an isolated CPU optimization candidate from the measured app33 package."""
import json,re,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'npu_dualcore_20261022'
names=['vision_pipeline.py','npu_runtime.py','gaze_bridge.py','gaze_model.py','runtime_policy.py','policy.json','roi_workers.py',
       'multi_trajectory.py','run_hands.py','fixture_test.py','benchmark.py','benchmark_dual.py','start_job.py','test_contracts.py','test_roi_workers.py']
for name in names:
    assert not (ROOT/name).exists(),name
    shutil.copy2(OLD/name,ROOT/name)
def edit(name,old,new):
    p=ROOT/name;s=p.read_text();assert s.count(old)==1,(name,old);p.write_bytes(s.replace(old,new).encode())
edit('npu_runtime.py',"        for x,meta in zip(arrays,self.io['inputs']):\n            x=np.ascontiguousarray(x,dtype=np.float32)",
     "        for x,meta in zip(arrays,self.io['inputs']):\n            # Eliminated ONNX inputs have no runtime consumer.\n            if not meta.get('active',True):continue\n            x=np.ascontiguousarray(x,dtype=np.float32)")
edit('vision_pipeline.py',"        except BaseException:self.close();raise\n    def __call__", 
     "        except BaseException:self.close();raise\n        self.embed_active=[x.get('active',True) for x in self.embed.io['inputs']] if hand and hasattr(self.embed,'io') else [True]*3\n    def __call__")
edit('vision_pipeline.py',"            tensors=[normalize_object(p,w,h),np.array([[right]],np.float32),normalize_object(world)]",
     "            tensors=[normalize_object(p,w,h),\n                     np.array([[right]],np.float32) if self.embed_active[1] or record else None,\n                     normalize_object(world) if self.embed_active[2] or record else None]")
edit('vision_pipeline.py',"        tensor=crop(rgb,rect,size).astype(np.float32)/255", "        tensor=crop(rgb,rect,size).astype(np.float32);tensor/=255")
edit('vision_pipeline.py',"h,w=rgb.shape[:2];side=max(h,w);tensor=crop(rgb,[w/2,h/2,side,side,0],self.size,True).astype(np.float32)/255\n        if not self.hand:tensor=tensor*2-1",
     "h,w=rgb.shape[:2];side=max(h,w);tensor=crop(rgb,[w/2,h/2,side,side,0],self.size,True).astype(np.float32);tensor/=255\n        if not self.hand:tensor*=2;tensor-=1")
edit('gaze_bridge.py',"app_v33_dualcore_20261022","app_v34_cpu_reuse_20261022")
edit('gaze_bridge.py',"        self.landmarker.value=[points(p)] if p is not None else []\n        self.last_video_timestamp_ms=None\n        return super().detect(timestamp,rgb,color_order='rgb',capture_sequence=sequence)",
     "        from geometry_array import from_array\n        return from_array(self,p,rgb.shape,timestamp,sequence)")
edit('run_hands.py',"app_v33_dualcore_20261022","app_v34_cpu_reuse_20261022")
edit('run_hands.py','from pcie_preview_reader import ExistingPreview','from model_frame_reader import ExistingModelFrame as ExistingPreview')
# Preserve all approved geometric math/thresholds, replacing only conversion wrappers.
p=ROOT/'baseline/OriginalGeometry.py';source=p.read_text();body=source[source.index('        coordinates = np.asarray([(p.x,p.y,p.z) for p in raw_landmarks]'):source.index('\n    def release(self):',source.index('    def detect(self,'))]
body=body.replace('        coordinates = np.asarray([(p.x,p.y,p.z) for p in raw_landmarks], dtype=np.float64)','        coordinates = np.asarray(p, dtype=np.float64)')
body=body.replace('        _face_mesh = np.array([[p.x, p.y, p.z] for p in scaled_landmarks], dtype=np.int16)',
                  '        precise_pixels = coordinates * [image_width,image_height,image_width]\n        scaled_landmarks = np.rint(precise_pixels)\n        _face_mesh = scaled_landmarks.astype(np.int16)')
body=body.replace('        precise_pixels = coordinates * [image_width,image_height,image_width]\n        face_info.left_eye_ear', '        face_info.left_eye_ear')
body=re.sub(r'scaled_landmarks\[(\d+)\]\.([xy])',lambda m:'scaled_landmarks['+m[1]+','+str('xy'.index(m[2]))+']',body)
body='\n'.join(line[4:] if line.startswith('    ') else line for line in body.splitlines())
header='''"""Array-only geometry derived from the pinned deployed MediaPipeFaceAlignment.
Keep its rounding, eye gates and ROI definitions; no neural call or mp.Image.
Original GazeFollower attribution/license remain in the app and baseline source.
"""
import math
import numpy as np
from gazefollower.misc import FaceInfo

def from_array(self,p,image_shape,timestamp,sequence=None):
    if int(timestamp)!=timestamp or timestamp<0:raise ValueError('Nonnegative integer timestamp required')
    face_info=FaceInfo();face_info.timestamp=timestamp;face_info.capture_sequence=sequence
    image_height,image_width=image_shape[:2];face_info.img_w=image_width;face_info.img_h=image_height
    if p is None:
        self.reset_filters();return face_info
'''
(ROOT/'geometry_array.py').write_bytes((header+body+'\n').encode())
(ROOT/'source_derivation.json').write_bytes((json.dumps(dict(baseline=str(p),baseline_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),changes='Array wrappers only; original ROI math, precision, quality gates and thresholds retained.'),indent=2)+'\n').encode())
print('CREATED_ISOLATED_CPU_CANDIDATE')
