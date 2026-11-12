"""Strict RKNNLite backend. CPU reference is never a fallback."""
import hashlib,json,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
class Model:
    def __init__(self,name,core=0):
        from rknnlite.api import RKNNLite
        self.name=name;self.path=ROOT/'models'/(name+'.rknn')
        self.io=json.loads(self.path.with_suffix('.io.json').read_text())
        receipt=self.path.with_suffix('.build.json')
        if not receipt.is_file():raise RuntimeError('Missing model provenance receipt: '+name)
        if hashlib.sha256(self.path.read_bytes()).hexdigest()!=json.loads(receipt.read_text())['rknn_sha256']:
            raise RuntimeError('Model hash mismatch: '+name)
        self.runtime=RKNNLite(verbose=False);self.calls=0;self.milliseconds=[]
        try:
            if self.runtime.load_rknn(str(self.path))!=0:raise RuntimeError('load '+name)
            if self.runtime.init_runtime(core_mask=core)!=0:raise RuntimeError('init '+name)
        except BaseException:self.runtime.release();raise
    def __call__(self,*arrays):
        if len(arrays)!=len(self.io['inputs']):raise ValueError('input count '+self.name)
        args=[]
        for x,meta in zip(arrays,self.io['inputs']):
            # Eliminated ONNX inputs have no runtime consumer.
            if not meta.get('active',True):continue
            x=np.ascontiguousarray(x,dtype=np.float32)
            if list(x.shape)!=meta['shape']:raise ValueError((self.name,x.shape,meta))
            if not np.isfinite(x).all():raise ValueError('nonfinite input '+self.name)
            if meta.get('active',True):args.append(x)
        t=time.perf_counter()
        # Conventional NCHW ONNX image input, native NHWC RKNN buffer.
        out=self.runtime.inference(inputs=args,data_format=[d.get('format','nchw') for d in self.io['inputs'] if d.get('active',True)])
        ms=(time.perf_counter()-t)*1000;self.calls+=1;self.milliseconds.append(ms)
        if len(self.milliseconds)>4096:del self.milliseconds[:2048]
        if out is None or len(out)!=len(self.io['outputs']):raise RuntimeError('outputs '+self.name)
        result=[np.asarray(x).reshape(meta['shape']) for x,meta in zip(out,self.io['outputs'])]
        if any(not np.isfinite(x).all() for x in result):raise RuntimeError('nonfinite output '+self.name)
        return result
    def close(self):
        if self.runtime is not None:self.runtime.release();self.runtime=None

class ReferenceModel:
    """Explicit test-only TFLite backend, not selected automatically."""
    def __init__(self,name,core=0):
        import sys
        sys.path.insert(0,str(ROOT/'reference_packages'))
        from tflite_runtime.interpreter import Interpreter
        self.name=name;self.runtime=Interpreter(model_path=str(ROOT/'models'/(name+'.tflite')),num_threads=1);self.runtime.allocate_tensors()
        self.calls=0;self.milliseconds=[]
    def __call__(self,*arrays):
        t=time.perf_counter()
        for d,x in zip(self.runtime.get_input_details(),arrays):self.runtime.set_tensor(d['index'],np.asarray(x,dtype=np.float32))
        self.runtime.invoke();out=[self.runtime.get_tensor(d['index']) for d in self.runtime.get_output_details()]
        self.calls+=1;self.milliseconds.append((time.perf_counter()-t)*1000);return out
    def close(self):self.runtime=None
