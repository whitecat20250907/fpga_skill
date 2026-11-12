"""Bounded raw-network concurrency benchmark, never a live perception FPS claim."""
import argparse,concurrent.futures,hashlib,json,os,re,threading,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]

def summary(values):
    if not values:return None
    a=sorted(values)
    return dict(mean=sum(a)/len(a),p95=a[int((len(a)-1)*.95)],max=a[-1],samples=len(a))

class Network:
    def __init__(self,name,core,rows):
        from rknnlite.api import RKNNLite
        self.name=name;self.times=[];self.calls=0;self.core=core
        if name=='MGazeNet':
            path=ROOT/'vendor/gaze_app/GazeFollower/gazefollower/res/model_weights/original_gaze_fp16.rknn'
            shapes=[(1,112,112,3),(1,224,224,3),(1,12),(1,112,112,3)];formats=['nhwc','nhwc','nchw','nhwc']
        elif name=='GestureNet8':
            path=ROOT/'vendor/gesture8/model/gesture8_fp16.rknn'
            shapes=[(1,28,28,1)];formats=['nhwc']
        elif name=='gesture_fused':
            path=ROOT/'models/gesture_fused/gesture_fused.rknn'
            meta=json.loads(path.with_suffix('.io.json').read_text())
            inputs=[v for v in meta['inputs'] if v.get('active',True)]
            shapes=[v['shape'] for v in inputs];formats=[v.get('format','nchw') for v in inputs]
        else:
            path=ROOT/'vendor/vision_npu/models'/f'{name}.rknn'
            meta=json.loads(path.with_suffix('.io.json').read_text())
            inputs=[v for v in meta['inputs'] if v.get('active',True)]
            shapes=[v['shape'] for v in inputs];formats=[v.get('format','nchw') for v in inputs]
        expected=(json.loads(path.with_suffix('.build.json').read_text())['rknn_sha256'] if name=='gesture_fused'
                  else next(v['sha256'] for v in rows if v['path']==path.relative_to(ROOT).as_posix()))
        self.sha=hashlib.sha256(path.read_bytes()).hexdigest();assert self.sha==expected,name
        rng=np.random.default_rng(20261025)
        self.inputs=[rng.random(s,dtype=np.float32) for s in shapes];self.formats=formats
        self.runtime=RKNNLite(verbose=False)
        try:
            if self.runtime.load_rknn(str(path)) or self.runtime.init_runtime(core_mask=core):raise RuntimeError('RKNN load/init '+name)
            self.call(False);self.call(False)
        except BaseException:self.runtime.release();raise
    def call(self,record=True):
        start=time.perf_counter_ns();output=self.runtime.inference(inputs=self.inputs,data_format=list(self.formats))
        elapsed=(time.perf_counter_ns()-start)/1e6
        if not isinstance(output,list) or not output:raise RuntimeError('Missing inference output '+self.name)
        if not record and any(not np.isfinite(v).all() for v in output):raise RuntimeError('Nonfinite '+self.name)
        if record:
            self.calls+=1
            if len(self.times)<10000:self.times.append(elapsed)
    def reset(self):self.times.clear();self.calls=0
    def close(self):self.runtime.release()

def ticks():
    v=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
    return sum(v),v[3]+v[4]

def run_plan(policy,seconds,rows,parallel_only=False,fused=False,roi_workers=2,roi_cpus=None):
    if roi_workers not in (1,2,4):raise ValueError('ROI workers must be 1, 2 or 4')
    networks=[];release_ok=True
    def network(name,mask):
        n=Network(name,mask,rows);networks.append(n);return n
    try:
        face=[network('face_detector',1),network('face_landmarks_detector',1),network('MGazeNet',2)]
        hand_detector=network('hand_detector',{'current_auto':0,'explicit_split':1,'detector_core1':2}[policy])
        hand_names=('hand_landmarks_detector','gesture_fused') if fused else ('hand_landmarks_detector','gesture_embedder','canned_gesture_classifier')
        hands=[[network(name,mask) for name in hand_names]
               for mask in ([1+(i%2) for i in range(roi_workers)] if policy=='explicit_split' else [0]*roi_workers)]
        cases=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=roi_workers) as rois:
            for label,faces,hand_count in [('face_only',1,0),('one_hand_only',0,1),('one_person_two_hands',1,2),('two_people_four_hands',2,4)]:
                if parallel_only and not (faces and hand_count):continue
                for n in networks:n.reset()
                start_signal=threading.Event();stop=threading.Event();cycles={'face':0,'hand':0};errors=[]
                def roi_batch(worker,indices):
                    if roi_cpus is not None:os.sched_setaffinity(0,set(roi_cpus))
                    for _ in indices:
                        for n in hands[worker]:n.call()
                def face_loop():
                    os.sched_setaffinity(0,{5});start_signal.wait()
                    try:
                        while not stop.is_set():
                            face[0].call()
                            for _ in range(faces):face[1].call();face[2].call()
                            cycles['face']+=1
                    except BaseException as exc:errors.append(repr(exc));stop.set()
                def hand_loop():
                    os.sched_setaffinity(0,{6});start_signal.wait()
                    try:
                        while not stop.is_set():
                            hand_detector.call()
                            pending=[rois.submit(roi_batch,i,range(i,hand_count,roi_workers)) for i in range(min(roi_workers,hand_count))]
                            for p in pending:p.result()
                            cycles['hand']+=1
                    except BaseException as exc:errors.append(repr(exc));stop.set()
                active=[threading.Thread(target=fn) for count,fn in [(faces,face_loop),(hand_count,hand_loop)] if count]
                for thread in active:thread.start()
                cpu0=ticks();start=time.monotonic();loads={0:[],1:[]};start_signal.set()
                while time.monotonic()-start<seconds and not stop.wait(.2):
                    for core,value in re.findall(r'Core(\d+):\s*(\d+)%',Path('/sys/kernel/debug/rknpu/load').read_text()):
                        loads[int(core)].append(int(value))
                stop.set()
                for thread in active:thread.join(10)
                if any(t.is_alive() for t in active):
                    # Never release a runtime underneath its inference call.
                    # Non-daemon workers retain the process for diagnosis.
                    release_ok=False
                    raise RuntimeError('Inference did not return within bounded stop; contexts retained')
                elapsed=time.monotonic()-start;cpu1=ticks()
                if errors:raise RuntimeError(errors)
                case=dict(scenario=label,faces=faces,hands=hand_count,duration_s=elapsed,
                    raw_bundle_hz={k:v/elapsed for k,v in cycles.items()},
                    simultaneous_min_hz=min(v/elapsed for v in cycles.values() if v),
                    cpu_all_core_percent=100*(1-(cpu1[1]-cpu0[1])/(cpu1[0]-cpu0[0])),
                    npu_busy_percent={str(k):summary(v) for k,v in loads.items()},
                    networks=[dict(name=n.name,core_mask=n.core,calls=n.calls,call_ms=summary(n.times),sha256=n.sha) for n in networks])
                cases.append(case);print(policy,label,case['raw_bundle_hz'],flush=True)
        return dict(policy=policy,fused_gesture=fused,roi_workers=roi_workers,roi_cpus=roi_cpus,cases=cases)
    finally:
        if release_ok:
            for n in reversed(networks):n.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=15);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--policies',nargs='+',choices=('current_auto','explicit_split','detector_core1'),default=['current_auto','explicit_split'])
    p.add_argument('--parallel-only',action='store_true');p.add_argument('--fused',action='store_true');a=p.parse_args()
    if not 5<=a.seconds<=60:p.error('seconds 5..60 per case')
    assert b'rockchip,rk3576' in Path('/sys/firmware/devicetree/base/compatible').read_bytes()
    import subprocess
    for s in ('hmi-gaze','hmi-hand'):
        if subprocess.run(['systemctl','is-active','--quiet',s]).returncode==0:raise RuntimeError('Stop live model services before benchmark')
    rows=json.loads((ROOT/'vendor/PROVENANCE.json').read_text())['files']
    report=dict(status='RUNNING',boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        scope='Deterministic synthetic inputs, real RKNN calls; detector runs every bundle, independent face/hand loops, 2 hand ROI workers. No crop, tracking, NMS, gaze calibration, camera latency or app actions. Not end-to-end FPS.',
        excludes='GestureNet8 is event-triggered and excluded from continuous bundles. Blendshape is disabled.',
        baseline='Only gaze/hand services stopped; C capture, preview and other HMI services remain. CPU and NPU load include surviving services.',
        policies=[])
    try:
        for policy in a.policies:
            report['policies'].append(run_plan(policy,a.seconds,rows,a.parallel_only,a.fused));a.output.write_text(json.dumps(report,indent=2))
        report['status']='PASS'
    except BaseException as exc:report['status']='FAIL';report['error']=repr(exc);raise
    finally:a.output.write_text(json.dumps(report,indent=2))
if __name__=='__main__':main()
