"""One shared NPU hand result feeds static gestures, 4 strokes and telemetry."""
import argparse,fcntl,json,os,sys,time
from contextlib import ExitStack
from pathlib import Path
import cv2,numpy as np
from vision_pipeline import HandRecognizer
from multi_trajectory import MultiTrajectory
sys.path.insert(0,'/userdata/freeciv-rk3576-gaze-demo')
sys.path.insert(0,'/userdata/gesture8_rk3576_20261021')
from model_frame_reader import ExistingModelFrame as ExistingPreview
from classifier import Classifier

def main():
    p=argparse.ArgumentParser();p.add_argument('--app-dir',default='/userdata/gaze_model_migration_v1_20261014/app_v34_cpu_reuse_20261022')
    p.add_argument('--model-pid',type=int);p.add_argument('--seconds',type=float,default=30);p.add_argument('--fps',type=float,default=0,help='0 = uncapped');p.add_argument('--output',type=Path,required=True);p.add_argument('--core',type=int,choices=(0,1,2),default=0);a=p.parse_args()
    if not 0<a.seconds<=300 or not np.isfinite(a.fps) or a.fps<0:raise ValueError('bounded seconds, finite nonnegative fps')
    a.output.mkdir(parents=True,exist_ok=False);cv2.setNumThreads(1);rows=[];calls=0
    try:
        with ExitStack() as stack:
            lock=stack.enter_context(open('/userdata/freeciv-rk3576-gaze-demo/logs/gesture.lock','a+'));fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            reader=ExistingPreview(a.app_dir,a.model_pid);stack.callback(reader.close)
            hand=stack.enter_context(HandRecognizer(4,a.core));cnn=Classifier('/userdata/gesture8_rk3576_20261021');stack.callback(cnn.close)
            trajectories=MultiTrajectory();start=time.monotonic();cpu=time.process_time();deadline=0.
            while time.monotonic()-start<a.seconds:
                now=time.monotonic();trajectories.tick(now)
                if now<deadline:time.sleep(min(.01,deadline-now));continue
                item=reader.read()
                if item is None:time.sleep(.005);continue
                rgb,meta=item;deadline=now+(1/a.fps if a.fps else 0);t=time.monotonic()
                result=hand.recognize_for_video(rgb,meta['timestamp_ns']//1000000);finished=trajectories.update(result,meta['sequence'],meta['timestamp_ns']/1e9,time.monotonic(),rgb.shape[1],rgb.shape[0]);events=[]
                for key,raster in finished:
                    event=cnn.predict(raster);calls+=1;event['track_id']=key
                    if (time.monotonic_ns()-meta['timestamp_ns'])/1e9>.35:event.update(accepted=False,rejection='stale')
                    events.append(event)
                reader.check_owners();rows.append(dict(sequence=meta['sequence'],timestamp_ns=meta['timestamp_ns'],hands=len(result.hand_landmarks),track_ids=result.track_ids,
                    gestures=[x[0].category_name for x in result.gestures],ms=(time.monotonic()-t)*1000,age_ms=(time.monotonic_ns()-meta['timestamp_ns'])/1e6,events=events))
            elapsed=time.monotonic()-start;report=dict(status='COMPLETED_NPU_SHARED_PREVIEW',seconds=elapsed,samples=len(rows),batches_hz=len(rows)/elapsed,cpu_one_core_percent=100*(time.process_time()-cpu)/elapsed,
                hands_capacity=4,hand_roi_cores=hand.pipeline.roi_cores,target_fps=a.fps,trajectory_npu_calls=calls,camera_opened=False,actions_sent=False,backend='RK3576 NPU',reader=reader.stats,owners=dict(model=reader.model,capture=reader.capture))
    except BaseException as e:
        report=dict(status='FAILED',error=repr(e),actions_sent=False);raise
    finally:
        (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        (a.output/'samples.json').write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__':main()
