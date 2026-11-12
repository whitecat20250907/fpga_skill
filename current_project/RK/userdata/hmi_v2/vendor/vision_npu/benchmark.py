"""Bounded concurrent real-model still replay; never opens any camera.

Both pipeline throughput (batches/s) and per-person valid gaze rate are reported.
Two faces means 2 MGazeNet calls, 4 hands means 4 landmark/embed/classifier calls.
All threads retain their own contexts and are joined before releasing models.
"""
import argparse,collections,hashlib,json,os,queue,resource,threading,time,traceback
from pathlib import Path
import cv2,numpy as np
from npu_runtime import ROOT,Model
from fixture_test import fixtures
from vision_pipeline import LandmarkPipeline
from gaze_bridge import APP,NPUFaceAlignment,Geometry

def stats(x):return dict(n=len(x),median=float(np.median(x)),p95=float(np.percentile(x,95)),max=float(max(x))) if x else None
def cpu_ticks(pid):
    try:
        f=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();return int(f[11])+int(f[12])
    except OSError:return None
class CPUFace:
    def __init__(self,n):
        import mediapipe as mp
        from gazefollower.face_alignment.MediaPipeFaceAlignment import _cpu_base_options
        self.mp=mp;self.geometry=Geometry()
        self.task=mp.tasks.vision.FaceLandmarker.create_from_options(mp.tasks.vision.FaceLandmarkerOptions(
            base_options=_cpu_base_options(mp.tasks,4,model_asset_path=str(APP/'GazeFollower/gazefollower/res/model_weights/face_landmarker.task')),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,num_faces=n,min_face_detection_confidence=.5,min_face_presence_confidence=.5,min_tracking_confidence=.5))
    def detect_all(self,stamp,rgb,**kwargs):
        raw=self.task.detect_for_video(self.mp.Image(image_format=self.mp.ImageFormat.SRGB,data=rgb),stamp//1000000)
        result=[]
        for i,landmarks in enumerate(raw.face_landmarks):
            p=np.array([[x.x,x.y,x.z] for x in landmarks]);f=self.geometry.from_points(p,rgb,stamp);f.track_id=i;result.append(f)
        return result
    def release(self):self.task.close()
class CPUHand:
    def __init__(self,n):
        import mediapipe as mp
        self.mp=mp
        class Options(mp.tasks.BaseOptions):
            def to_pb2(self):
                p=super().to_pb2();p.acceleration.Clear();p.acceleration.xnnpack.num_threads=2;return p
        self.task=mp.tasks.vision.GestureRecognizer.create_from_options(mp.tasks.vision.GestureRecognizerOptions(
            base_options=Options(model_asset_path='/userdata/freeciv-rk3576-gaze-demo/.gesture-v1/assets/gesture_recognizer.task'),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,num_hands=n,min_hand_detection_confidence=.6,min_hand_presence_confidence=.6,min_tracking_confidence=.6))
    def process(self,rgb,stamp=None):return self.task.recognize_for_video(self.mp.Image(image_format=self.mp.ImageFormat.SRGB,data=rgb),time.monotonic_ns()//1000000).hand_landmarks
    def close(self):self.task.close()
def run_case(label,nfaces,nhands,cpu=False,core_face=0,core_hand=0,hand_hz=0,seconds=12,cnn=True,blend=False,hand_cores=(),face_cores=(),core_gaze=0,gaze_cores=()):
    from gaze_runtime import load_settings,_estimate_one_with_eye_gate as estimate_with_eye_gate
    from gaze_model import GazeModel,GazeBatch
    sys_path='/userdata/gesture8_rk3576_20261021'
    import sys
    sys.path.insert(0,sys_path);from classifier import Classifier
    os.environ['NPU_FACE_CORES']=','.join(map(str,face_cores))
    images={n:rgb for n,rgb,_,_ in fixtures()};face_rgb=images['face_one' if nfaces==1 else 'face_two']
    hand_rgb=images[{1:'thumbs_up',2:'right_hands',4:'four_hands'}[nhands]] if nhands else None
    bindings={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'models').glob('*.rknn') if p.stem!='palm_debug'}
    settings=load_settings();stop=threading.Event();ready=[threading.Event() for _ in range(4)];errors=[];q=queue.Queue(1);rows=[];hands=[];events=[];loads=[];replaced=[0]
    def face_worker():
        model=None
        try:
            model=CPUFace(nfaces) if cpu else NPUFaceAlignment(num_faces=nfaces,core=core_face)
            ready[0].set()
            while not stop.is_set():
                if 'backpressure' in label and q.full():stop.wait(.001);continue
                stamp=time.monotonic_ns();t=time.perf_counter();out=model.detect_all(stamp,face_rgb,color_order='rgb');packet=(stamp,out,(time.perf_counter()-t)*1000)
                try:q.put_nowait(packet)
                except queue.Full:
                    try:q.get_nowait();replaced[0]+=1
                    except queue.Empty:pass
                    try:q.put_nowait(packet)
                    except queue.Full:pass
        except BaseException:errors.append(traceback.format_exc());stop.set();ready[0].set()
        finally:
            if model:model.release()
    def gaze_worker():
        model=None
        try:
            path=str(APP/settings['model_path'])
            model=GazeBatch(path,cores=gaze_cores) if gaze_cores else GazeModel(path,core=core_gaze);ready[1].set()
            while not stop.is_set():
                try:stamp,faces,face_ms=q.get(timeout=.1)
                except queue.Empty:continue
                valid=0;dur=[];ages=[]
                if gaze_cores:
                    for gaze,timings,done in model.estimate_many(face_rgb,faces,settings):
                        valid+=int(bool(gaze.status));dur.append(timings);ages.append((done-stamp)/1e6)
                    rows.append(dict(done=time.monotonic(),faces=len(faces),valid=valid,age_ms=(time.monotonic_ns()-stamp)/1e6,person_ages=ages,face_ms=face_ms,stages=dur))
                    continue
                for face in faces:
                    if (time.monotonic_ns()-stamp)/1e9>=settings['max_sample_age']:continue
                    gaze=estimate_with_eye_gate(model,face_rgb,face,settings);valid+=int(bool(gaze.status));dur.append(dict(model.last_timings));ages.append((time.monotonic_ns()-stamp)/1e6)
                rows.append(dict(done=time.monotonic(),faces=len(faces),valid=valid,age_ms=(time.monotonic_ns()-stamp)/1e6,person_ages=ages,face_ms=face_ms,stages=dur))
        except BaseException:errors.append(traceback.format_exc());stop.set();ready[1].set()
        finally:
            if model:model.release()
    def hand_worker():
        model=None
        try:
            model=CPUHand(nhands) if cpu else LandmarkPipeline(True,nhands,core=core_hand,roi_cores=hand_cores);ready[2].set()
            while not stop.is_set():
                t=time.monotonic();result=model.process(hand_rgb);hands.append(dict(done=time.monotonic(),count=len(result),ms=(time.monotonic()-t)*1000))
                if hand_hz:stop.wait(max(0,1/hand_hz-(time.monotonic()-t)))
        except BaseException:errors.append(traceback.format_exc());stop.set();ready[2].set()
        finally:
            if model:model.close()
    def event_worker():
        model=None;extra=None
        try:
            model=Classifier(Path(sys_path))
            raster=np.zeros((28,28),np.uint8);cv2.line(raster,(5,3),(5,22),255,2);cv2.line(raster,(5,22),(22,22),255,2)
            if blend:extra=Model('face_blendshapes');sample=np.load(ROOT/'models/face_blendshapes.reference.npz')['in_0_0']
            ready[3].set()
            while not stop.is_set():
                t=time.monotonic()
                for _ in range(4 if nhands==4 else 1):model.predict(raster)
                if extra:
                    for _ in range(nfaces):extra(sample)
                events.append(dict(done=time.monotonic(),ms=(time.monotonic()-t)*1000));stop.wait(max(0,1-(time.monotonic()-t)))
        except BaseException:errors.append(traceback.format_exc());stop.set();ready[3].set()
        finally:
            if model:model.close()
            if extra:extra.close()
    workers=[]
    for fn,enabled in [(face_worker,nfaces),(gaze_worker,nfaces),(hand_worker,nhands),(event_worker,cnn)]:
        if enabled:
            t=threading.Thread(target=fn);t.start();workers.append(t)
    try:
        for i,enabled in enumerate([nfaces,nfaces,nhands,cnn]):
            if enabled and not ready[i].wait(30):raise RuntimeError('init timeout')
        if errors:raise RuntimeError(str(errors))
        stop.wait(2);begin=time.monotonic();cpu_begin=time.process_time()
        while time.monotonic()-begin<seconds and not stop.wait(.5):
            try:load=Path('/sys/kernel/debug/rknpu/load').read_text().strip()
            except OSError:
                try:load=Path(os.environ['NPU_LOAD_FILE']).read_text().strip()
                except (OSError,KeyError):load=None
            loads.append(dict(at=time.monotonic(),load=load))
        end=time.monotonic();cpu_end=time.process_time()
    finally:
        stop.set()
        for t in workers:t.join(30)
    if errors or any(t.is_alive() for t in workers):raise RuntimeError(str(errors))
    rows=[r for r in rows if begin<=r['done']<=end];hands=[r for r in hands if begin<=r['done']<=end];events=[r for r in events if begin<=r['done']<=end];duration=end-begin
    result=dict(label=label,backend='CPU_MediaPipe_plus_NPU_gaze_trajectory' if cpu else 'ALL_NPU',faces=nfaces,hands=nhands,
        model_sha256=bindings,core_face=core_face,core_hand=core_hand,hand_roi_cores=list(hand_cores),face_roi_cores=list(face_cores),core_gaze=core_gaze,gaze_cores=list(gaze_cores),hand_target_hz=hand_hz,seconds=duration,gaze_batch_hz=len(rows)/duration,
        all_people_valid_hz=sum(r['valid']==nfaces for r in rows)/duration,valid_person_outputs_hz=sum(r['valid'] for r in rows)/duration,
        face_counts=dict(collections.Counter(r['faces'] for r in rows)),valid_counts=dict(collections.Counter(r['valid'] for r in rows)),
        age_ms=stats([r['age_ms'] for r in rows]),person_age_ms=stats([a for r in rows for a in r['person_ages']]),
        stale_over250ms=sum(r['age_ms']>250 for r in rows),face_ms=stats([r['face_ms'] for r in rows]),
        gaze_npu_ms=stats([s['npu_ms'] for r in rows for s in r['stages'] if s.get('npu_called')]),
        hand_batch_hz=len(hands)/duration,all_hands_valid_hz=sum(h['count']==nhands for h in hands)/duration,
        hand_counts=dict(collections.Counter(h['count'] for h in hands)),hand_ms=stats([h['ms'] for h in hands]),
        event_batches_hz=len(events)/duration,event_ms=stats([r['ms'] for r in events]),
        cpu_one_core_percent=100*(cpu_end-cpu_begin)/duration,rss_peak_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        latest_slot_replacements_including_warmup=replaced[0],npu_load=loads,blend_synthetic_stress=blend)
    return dict(summary=result,gaze=rows,hand=hands,events=events)
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',default='benchmark_v1');p.add_argument('--seconds',type=float,default=12);p.add_argument('--case',default='all');a=p.parse_args()
    cv2.setNumThreads(1);out=ROOT/a.out;out.mkdir(exist_ok=True)
    cases=[('cpu_single',1,2,True,0,0,10),('npu_single',1,2,False,0,0,10),('cpu_dual4',2,4,True,0,0,10),('npu_dual4',2,4,False,0,0,10),
        ('npu_dual4_20hz',2,4,False,0,0,20),('npu_dual4_split',2,4,False,1,2,20),('npu_eye1',1,0,False,0,0,20),('npu_eye2',2,0,False,0,0,20),
        ('npu_hand1',0,1,False,0,0,60),('npu_hand2',0,2,False,0,0,60),('npu_hand4',0,4,False,0,0,60),('npu_dual4_backpressure',2,4,False,0,0,10)]
    summaries=[]
    for label,nf,nh,cpu,cf,ch,hz in cases:
        if a.case!='all' and label not in a.case.split(','):continue
        result=run_case(label,nf,nh,cpu,cf,ch,hz,a.seconds,cnn=bool(nf and nh));(out/(label+'.json')).write_text(json.dumps(result,indent=2)+'\n')
        summaries.append(result['summary']);print(json.dumps(result['summary']),flush=True)
        (out/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
if __name__=='__main__':main()
