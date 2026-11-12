"""Single RKNN submission for the unchanged embedding and classifier graphs.

The frozen ROI geometry still runs verbatim. Each ROI worker owns its runtime
and one-use intermediate result; no cross-hand or cross-thread result cache.
"""
import hashlib,json,threading
from core.config import ROOT
from npu_runtime import Model
from vision_pipeline import HandRecognizer, LandmarkPipeline


class FusedEmbedding(Model):
    def __init__(self,core):
        from rknnlite.api import RKNNLite
        self.name='gesture_fused';self.path=ROOT/'models'/self.name/(self.name+'.rknn')
        self.io=json.loads(self.path.with_suffix('.io.json').read_text())
        receipt=json.loads(self.path.with_suffix('.build.json').read_text())
        if hashlib.sha256(self.path.read_bytes()).hexdigest()!=receipt['rknn_sha256']:
            raise RuntimeError('Fused model provenance mismatch')
        self.runtime=RKNNLite(verbose=False);self.calls=0;self.milliseconds=[];self.pending=None
        try:
            if self.runtime.load_rknn(str(self.path))!=0:raise RuntimeError('load fused gesture')
            if self.runtime.init_runtime(core_mask=core)!=0:raise RuntimeError('init fused gesture')
        except BaseException:self.close();raise
    def __call__(self,*arrays):
        self.pending=None
        embedding,probability=super().__call__(*arrays)
        self.pending=(embedding,probability)
        return [embedding]
    def consume(self,embedding):
        pending=self.pending;self.pending=None
        if pending is None or pending[0] is not embedding:
            raise RuntimeError('Fused classifier must consume its own immediately preceding embedding')
        return [pending[1]]
    def close(self):
        self.pending=None
        super().close()


class ClassifierResult:
    def __init__(self,embedding):self.embedding=embedding
    def __call__(self,value):return self.embedding.consume(value)
    def close(self):pass  # The embedding owns and releases the shared RKNN context.


class Backend:
    def __init__(self):self.local=threading.local()
    def __call__(self,name,core=0):
        if name=='gesture_embedder':
            value=FusedEmbedding(core);self.local.embedding=value;return value
        if name=='canned_gesture_classifier':
            value=self.local.embedding;del self.local.embedding;return ClassifierResult(value)
        return Model(name,core)


class FusedHandRecognizer(HandRecognizer):
    def __init__(self,num_hands,core,roi_cores):
        self.pipeline=LandmarkPipeline(True,num_hands,backend=Backend(),core=core,roi_cores=roi_cores)
