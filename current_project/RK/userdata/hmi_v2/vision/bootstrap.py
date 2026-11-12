"""Resolve vendor modules without editing frozen algorithm bytes."""
from core.config import ROOT,load
import importlib, importlib.abc, importlib.util, os,sys

FOLDERS=['gaze_app/GazeFollower','gaze_app','vision_npu','ui_support','gesture8','hand_consumer','freeciv_bridge']

class VendorResolver(importlib.abc.MetaPathFinder):
    def __init__(self,vendor):
        self.modules={}
        for folder in FOLDERS:
            for path in (vendor/folder).glob('*.py'):
                if path.stem!='__init__':self.modules[path.stem]=path
        self.package=vendor/'gaze_app/GazeFollower/gazefollower'
    def find_spec(self,fullname,path=None,target=None):
        if '.' in fullname:return None
        if fullname=='gazefollower':
            return importlib.util.spec_from_file_location(fullname,self.package/'__init__.py',submodule_search_locations=[str(self.package)])
        source=self.modules.get(fullname)
        return importlib.util.spec_from_file_location(fullname,source) if source else None

def install_vendor_resolver(vendor=None):
    vendor=vendor or ROOT/'vendor'
    if not any(isinstance(f,VendorResolver) for f in sys.meta_path):sys.meta_path.insert(0,VendorResolver(vendor))

def activate():
    vendor=ROOT/'vendor'
    install_vendor_resolver(vendor)
    os.environ['GAZE_APP_DIR']=str(vendor/'gaze_app')
    os.environ['NPU_VISION_PACKAGE']=str(vendor/'vision_npu')
    os.environ['NPU_REQUIRE_FPGA_DETECTOR']='1'
    os.environ.setdefault('NPU_MAX_FACES','2')
    policy=load()['npu']
    os.environ['NPU_FACE_CORE']=str(policy['face_core']);os.environ['NPU_GAZE_CORE']=str(policy['gaze_core'])
    os.environ['NPU_HAND_CORES']=','.join(map(str,policy['hand_roi_cores']))
    for folder in FOLDERS:
        sys.path.insert(0,str(vendor/folder))
    # Frozen files contain historical sys.path.insert calls. Pin dependencies
    # in sys.modules BEFORE importing those files, so old paths cannot win.
    for name in ['runtime_policy','detector_frame','npu_runtime','roi_workers','vision_pipeline','geometry_array','gaze_model','gaze_bridge']:
        importlib.import_module(name)
    sys.modules['runtime_policy'].POLICY.update(policy)
    for name in ['classifier','trajectory','demo_trajectory','multi_trajectory']:importlib.import_module(name)
    return vendor
