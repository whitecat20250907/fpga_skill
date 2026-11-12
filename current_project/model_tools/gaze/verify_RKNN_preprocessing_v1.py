"""Run on RK with installed cv2: compare actual upstream preprocessing code.

The original MNN tensor/backend objects are recording sinks only. This checks
preprocessing equivalence, not model inference, NPU availability or accuracy.
"""
import ast,hashlib,json
from pathlib import Path
from types import SimpleNamespace
import cv2
import numpy as np
O=Path.cwd();src=O/'MGazeNetGazeEstimator.py';target=O/'RKNNGazeEstimator.py';misc=O/'__init__.py'
def definition(path,name):
 tree=ast.parse(path.read_text(encoding='utf8'));node=next(n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name==name)
 return compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec')
ns={'np':np,'cv2':cv2,'GazeEstimator':object,'FaceInfo':object,'GazeInfo':SimpleNamespace,'TrackingState':SimpleNamespace(FACE_MISSING=0,OUT_OF_BOUNDARIES=2,SUCCESS=1,FAILURE=3)}
exec(definition(misc,'clip_patch'),ns)
exec(definition(src,'MGazeNetGazeEstimator'),ns)
exec(definition(target,'prepare_inputs'),ns)
class Tensor:
 def write(self,a):self.a=a.copy()
class Sink:
 def onForward(self,inputs):return [SimpleNamespace(read=lambda:np.zeros(258,np.float32))]
original=object.__new__(ns['MGazeNetGazeEstimator']);original.face_size=(224,224);original.eye_size=(112,112)
for name in ('face','left','right','rect'):setattr(original,name+'_var',Tensor())
original.gaze_module=Sink()
rng=np.random.default_rng(3576415);cases=[]
for case in range(12):
 image=rng.integers(0,256,(96,160,3),dtype=np.uint8)
 if case<4:
  image[:]=0
  if case<3:image[:,:,case]=255
  else:image[:]=255
 face=SimpleNamespace(timestamp=123,status=True,can_gaze_estimation=True,img_w=160,img_h=96,left_eye_openness=20,right_eye_openness=20,
   face_rect=np.array([10,5,120,80]),left_rect=np.array([22,30,33,17]),right_rect=np.array([84,31,35,17]))
 if case>=8:face.face_rect=np.array([20,10,160,96]);face.right_rect=np.array([140,82,36,20])
 output=original.detect(image,face);assert output.status
 actual=ns['prepare_inputs'](image,face);assert len(actual)==4
 for out,name,shape in zip(actual,('left','face','rect','right'),((1,3,112,112),(1,3,224,224),(1,12),(1,3,112,112))):
  gold=getattr(original,name+'_var').a
  if name!='rect':gold=gold.transpose(2,0,1)[None]
  assert out.shape==shape and out.dtype==np.float32 and out.flags.c_contiguous
  assert np.array_equal(out,gold),(case,name,float(np.max(np.abs(out-gold))))
  if case<3 and name!='rect':assert np.all(out[:,case]==1) and np.all(np.delete(out,case,axis=1)==0)
 cases.append({'case':case,'bit_exact_all_four_inputs':True,'clipped_edge':case>=8})
face.face_rect=np.array([-1,0,20,20]);assert ns['prepare_inputs'](image,face) is None
face.face_rect=np.array([0,0,20,20]);face.img_w=161
try:ns['prepare_inputs'](image,face)
except ValueError:pass
else:raise AssertionError('mismatched geometry accepted')
r={'status':'PASS_RK_PREPROCESSING_BIT_EXACT_TO_UPSTREAM_12_CASES','cases':cases,'invalid_rectangle_rejected':True,'mismatched_geometry_rejected':True,'cv2_version':cv2.__version__,'numpy_version':np.__version__,'sources':[{'name':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (src,target,misc,Path(__file__))],'NPU_executed':False,'MNN_executed':False,'camera_opened':False,'scope':'Actual upstream detect/clip_patch code run with recording tensor sinks; compares RGB channels, resize, post-resize right-eye flip, clipped edges, original rect12 normalization, layout and input order. Does not test model or camera.'}
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
