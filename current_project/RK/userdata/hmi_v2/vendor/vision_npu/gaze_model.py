"""Existing MGazeNet math with an explicit RK3576 core assignment."""
import hashlib,os,time
from pathlib import Path
from gazefollower.gaze_estimator import RKNNGazeEstimator as Original
from gazefollower.gaze_estimator.GazeEstimator import GazeEstimator
from runtime_policy import POLICY
class GazeModel(Original):
    def __init__(self,model_path,core=None):
        GazeEstimator.__init__(self)
        self.model_path=Path(model_path).resolve()
        if core is None:core=int(os.environ.get('NPU_GAZE_CORE',str(POLICY.get('gaze_core',0))))
        if core not in (0,1,2,3):raise ValueError('RK3576 core mask')
        if b'rockchip,rk3576' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes():raise RuntimeError('RK3576 required')
        from rknnlite.api import RKNNLite
        self.runtime=RKNNLite(verbose=False)
        try:
            if self.runtime.load_rknn(str(self.model_path))!=0:raise RuntimeError('load gaze')
            if self.runtime.init_runtime(core_mask=core)!=0:raise RuntimeError('init gaze core '+str(core))
        except BaseException:self.release();raise
        self.backend='RK3576_NPU_RKNNLite';self.model_sha256=hashlib.sha256(self.model_path.read_bytes()).hexdigest()

class _PersonGaze:
    def __init__(self,path,core):self.model=GazeModel(path,core)
    def __call__(self,rgb,face,settings):
        from gaze_runtime import _estimate_one_with_eye_gate
        from gazefollower.misc import GazeInfo
        if not 0<=(time.monotonic_ns()-face.timestamp)/1e9<settings.get('max_sample_age',.5):
            gaze=GazeInfo(timestamp=face.timestamp);timings=dict(prepare_ms=0.,npu_ms=0.,npu_called=False,stale_source=True)
        else:
            gaze=_estimate_one_with_eye_gate(self.model,rgb,face,settings);timings=dict(self.model.last_timings)
        return gaze,timings,time.monotonic_ns()
    def close(self):self.model.release()

class GazeBatch:
    """Independent person inference; one frame waits for its at most two results."""
    def __init__(self,model_path,cores=None):
        from roi_workers import OwnerPool
        self.model_path=Path(model_path).resolve()
        default=','.join(map(str,POLICY.get('gaze_cores') or [0,0]))
        cores=cores if cores is not None else [int(c) for c in os.environ.get('NPU_GAZE_CORES',default).split(',')]
        self.pool=OwnerPool(lambda c:_PersonGaze(self.model_path,c),cores)
        self.backend='RK3576_NPU_RKNNLite';self.model_sha256=hashlib.sha256(self.model_path.read_bytes()).hexdigest();self.last_timings={}
    def estimate_many(self,rgb,people,settings):
        if len(people)>2:raise ValueError('At most 2 people')
        return self.pool.map([(rgb,face,settings) for face in people])
    def release(self):self.pool.close()
