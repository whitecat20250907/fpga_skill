"""One subprocess per model bounds compiler memory; FP16, no calibration fiction."""
import os
os.environ['OMP_NUM_THREADS']='1'
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse, hashlib, json, time
from pathlib import Path
from rknn.api import RKNN
ROOT=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser();p.add_argument('name');a=p.parse_args()
    src=ROOT/'models'/(a.name+'.tflite');dst=src.with_suffix('.rknn')
    r=RKNN(verbose=False);start=time.monotonic()
    try:
        for stage,fn in [('config',lambda:r.config(target_platform='rk3576',float_dtype='float16',optimization_level=3)),('load_onnx',lambda:r.load_onnx(model=str(src.with_suffix('.onnx')))),('build',lambda:r.build(do_quantization=False)),('export',lambda:r.export_rknn(str(dst)))]:
            print(stage,flush=True)
            rc=fn()
            if rc!=0:raise RuntimeError((stage,rc))
        row=dict(name=a.name,source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),rknn_sha256=hashlib.sha256(dst.read_bytes()).hexdigest(),bytes=dst.stat().st_size,seconds=time.monotonic()-start,format='FP16 RK3576',toolkit='2.3.0',cpu_fallback=False)
        dst.with_suffix('.build.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row),flush=True)
    finally:r.release()
if __name__=='__main__':main()
