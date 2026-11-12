"""Bounded RK3576 raw forward A/B. No camera, DMA, BAR or OS input access."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if b'rockchip,rk3576' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes():
        raise RuntimeError('Actual RK3576 required')
    from rknnlite.api import RKNNLite
    provenance=json.loads((ROOT/'vendor/PROVENANCE.json').read_text())['files']
    names={'face_detector':1,'face_landmarks_detector':1,'hand_detector':0,
           'hand_landmarks_detector':0,'gesture_embedder':0,'canned_gesture_classifier':0}
    cases=[]
    for name,core in names.items():
        path=ROOT/'vendor/vision_npu/models'/f'{name}.rknn'
        meta=json.loads(path.with_suffix('.io.json').read_text())
        inputs=[v for v in meta['inputs'] if v.get('active',True)]
        cases.append((name,path,[v['shape'] for v in inputs],[v.get('format','nchw') for v in inputs],core))
    cases.append(('MGazeNet',ROOT/'vendor/gaze_app/GazeFollower/gazefollower/res/model_weights/original_gaze_fp16.rknn',
                  [(1,112,112,3),(1,224,224,3),(1,12),(1,112,112,3)],['nhwc','nhwc','nchw','nhwc'],2))
    cases.append(('GestureNet8',ROOT/'vendor/gesture8/model/gesture8_fp16.rknn',[(1,28,28,1)],['nhwc'],0))
    result={'scope':'Actual NPU, original/packaged weights, identical deterministic synthetic inputs; excludes preprocessing, tracking, live FPS and human accuracy',
            'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'camera_opened':False,'fpga_accessed':False,
            'atol':1e-5,'rtol':1e-5,'rows':[],'status':'RUNNING'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    try:
        for name,path,shapes,formats,core in cases:
            entry=next(r for r in provenance if r['path']==path.relative_to(ROOT).as_posix())
            old=Path('/'+entry['source'].removeprefix('board_root/'))
            if sha(path)!=entry['sha256'] or sha(old)!=entry['sha256']:
                raise RuntimeError('Original/integrated model hash mismatch: '+name)
            rng=np.random.default_rng(20261025)
            samples=[[np.zeros(shape,np.float32) for shape in shapes],
                     [rng.random(shape,dtype=np.float32) for shape in shapes]]
            outputs=[];timings=[]
            for model_path,mask in [(old,0),(path,core)]:
                runtime=RKNNLite(verbose=False);runs=[];durations=[]
                try:
                    if runtime.load_rknn(str(model_path))!=0:raise RuntimeError('load '+name)
                    if runtime.init_runtime(core_mask=mask)!=0:raise RuntimeError('init '+name)
                    for sample in samples:
                        # RKNNLite replaces format strings with numeric enums in
                        # the caller's list. Give each invocation a fresh list.
                        start=time.perf_counter_ns();values=runtime.inference(inputs=[v.copy() for v in sample],data_format=list(formats))
                        durations.append((time.perf_counter_ns()-start)/1e6)
                        if not isinstance(values,list) or not values or any(not np.isfinite(v).all() for v in values):
                            raise RuntimeError('Nonfinite/missing outputs: '+name)
                        runs.append([np.array(v,copy=True) for v in values])
                finally:runtime.release()
                outputs.append(runs);timings.append(durations)
            comparisons=[]
            for before,after in zip(*outputs):
                if len(before)!=len(after):raise RuntimeError('Output count mismatch: '+name)
                for x,y in zip(before,after):
                    if x.shape!=y.shape:raise RuntimeError('Output shape mismatch: '+name)
                    comparisons.append({'shape':list(x.shape),'max_abs':float(np.max(np.abs(x-y))),
                                        'exact':bool(np.array_equal(x,y)),'pass':bool(np.allclose(x,y,atol=1e-5,rtol=1e-5))})
            row={'model':name,'sha256':entry['sha256'],'original':str(old),'integrated':str(path),
                 'original_core_mask':0,'integrated_core_mask':core,'comparisons':comparisons,
                 'individual_call_ms_including_first_call':timings,'pass':all(v['pass'] for v in comparisons)}
            result['rows'].append(row);args.output.write_text(json.dumps(result,indent=2))
            print(name, 'PASS' if row['pass'] else 'FAIL',flush=True)
        result['status']='PASS' if all(r['pass'] for r in result['rows']) else 'FAIL'
    except Exception as exc:
        result['status']='FAIL';result['error']=str(exc);raise
    finally:args.output.write_text(json.dumps(result,indent=2))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
