import sys,json,time,os
from pathlib import Path
import numpy as np
ROOT=Path('/home/linaro/pcie_fix_20261003/hmi_v34_validation');sys.path.insert(0,str(ROOT))
from vision.bootstrap import activate
activate()
os.environ.pop('NPU_REQUIRE_FPGA_DETECTOR',None)  # Offline photograph fixture only.
from vision_pipeline import LandmarkPipeline
from vision.fused_hand import Backend
out=Path('/home/linaro/pcie_fix_20261003/optimization61')
z=np.load('/home/linaro/pcie_fix_20261003/fixtures61.npz');rows=[]
a=LandmarkPipeline(True,tracking=False,roi_cores=[0,0]);b=LandmarkPipeline(True,backend=Backend(),tracking=False,roi_cores=[0,0])
try:
 for key in z.files:
  if key.startswith('face'):continue
  x=z[key];r=a.process(x);s=b.process(x)
  errors=[]
  assert len(r)==len(s),(key,len(r),len(s))
  for left,right in zip(sorted(r,key=lambda h:h['landmarks'][0,0]),sorted(s,key=lambda h:h['landmarks'][0,0])):
   errors.append(float(np.max(np.abs(left['probabilities']-right['probabilities']))))
   assert left['gesture']==right['gesture']
   assert np.array_equal(left['landmarks'],right['landmarks'])
  rows.append(dict(fixture=key,hands=len(r),gestures=[h['gesture'] for h in r],max_probability_error=max(errors,default=0)))
 result=dict(status='PASS',scope='Actual NPU on existing static hand photographs and four-hand composite; original vs fused adapter with unchanged geometry.',rows=rows)
 (out/'fixture_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
finally:a.close();b.close()
