"""Optional RKNN NPU hand recognizer sharing the already-running PCIe RGB.

Default is observation only. --send-actions opts into the game's five UDP
events. This program never opens a camera, supplies gaze, controls the OS
mouse, changes a model/driver, or starts/restarts the main application.
"""
import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gesture_control import GestureLatch,send_game_action
from screen_bridge import FreecivScreenInput
from hand_runtime import create_recognizer,SampleClock

def top(result):
    # Four hands may be observed, but game ownership is not inferred from list
    # order. Ambiguous multi-hand action input is suppressed.
    if len(result.hand_landmarks)>1:return None,0.,True
    if result.gestures and result.gestures[0]:
        c=result.gestures[0][0]
        return c.category_name,float(c.score),bool(result.hand_landmarks)
    return None,1.,bool(result.hand_landmarks)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prefix',type=Path,default=ROOT/'.gesture-v1')
    ap.add_argument('--app-dir',type=Path)
    ap.add_argument('--model-pid',type=int)
    ap.add_argument('--seconds',type=float,default=0,help='0 = until SIGINT/SIGTERM; otherwise <=300')
    ap.add_argument('--fps',type=float,default=0,help='0 = process every available new frame')
    ap.add_argument('--confidence',type=float,default=.7)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--send-actions',action='store_true')
    ap.add_argument('--feature-port',type=int,help='Optional local read-only 3D feature output; no extra inference')
    ap.add_argument('--num-hands',type=int,choices=(1,2,3,4),default=4)
    ap.add_argument('--cpu-threads',type=int,choices=(0,1,2,4),default=2)
    ap.add_argument('--fixtures',action='store_true',help='Official sample stills; never sends game events')
    args=ap.parse_args()
    if args.feature_port is not None and not 1024<=args.feature_port<=65535:ap.error('Invalid local feature port')
    if not __import__('math').isfinite(args.fps) or args.fps<0 or not 0<=args.seconds<=300 or not .7<=args.confidence<=1:
        ap.error('fps >=0 (0 uncapped), seconds in [0,300], confidence in [.7,1]')
    if args.fixtures and args.send_actions:ap.error('Fixture inference cannot send game events')
    if not args.fixtures and args.app_dir is None:ap.error('--app-dir required for existing PCIe preview')
    if args.output.exists():ap.error('Preserve previous output')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.mkdir()
    model=args.prefix/'assets/gesture_recognizer.task'
    provenance=args.prefix/'installation.completed.json'
    if not provenance.exists():provenance=args.prefix/'installation.json'
    installation=json.loads(provenance.read_text())
    if not installation['status'].startswith('INSTALLED_SEPARATE_ENV'):
        raise RuntimeError('Complete and verify the retained installation before starting')
    digest=hashlib.sha256(model.read_bytes()).hexdigest()
    if digest!=installation['assets'][model.name]['sha256']:raise RuntimeError('Model hash changed')
    stop=False
    def terminate(*_):
        nonlocal stop
        stop=True
    signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate)
    result=dict(backend='RK3576 NPU FP16',model_sha256=digest,source='official_still_fixtures' if args.fixtures else 'existing_PCIe_memfd_RGB',
        send_actions=args.send_actions,original_gaze_NPU_unchanged=True,camera_opened=False,
        samples=0,events=[],censored_results=0,human_live_test=False,output_directory=str(args.output.resolve()),
        cpu_threads=args.cpu_threads,num_hands=args.num_hands,requested_fps=args.fps)
    before=time.process_time();start=time.monotonic()
    try:
        with ExitStack() as stack:
            publisher=None
            if args.feature_port is not None:
                from project_features import FeaturePublisher,hand_features
                # Inference already has the requested 2..8 Hz scheduler.
                # A second identical limiter discards jittered completions.
                publisher=FeaturePublisher(('127.0.0.1',args.feature_port),fps=0)
                stack.callback(publisher.close)
            (ROOT/'logs').mkdir(exist_ok=True)
            lock=stack.enter_context((ROOT/'logs/gesture.lock').open('a+'))
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            import mediapipe as mp
            recognizer=stack.enter_context(create_recognizer(model,video=not args.fixtures,
                num_hands=args.num_hands,cpu_threads=args.cpu_threads))
            result['npu_policy']=dict(hand_roi_cores=recognizer.pipeline.roi_cores,uncapped=args.fps==0)
            rows=stack.enter_context((args.output/'samples.jsonl').open('w',buffering=1))
            result['mediapipe_version']=mp.__version__
            if args.fixtures:
                expected={'fist.jpg':'Closed_Fist','pointing_up.jpg':'Pointing_Up','right_hands.jpg':'Open_Palm',
                          'thumbs_down.jpg':'Thumb_Down','thumbs_up.jpg':'Thumb_Up','victory.jpg':'Victory'}
                mapped=0
                for path in sorted((args.prefix/'assets').glob('*.jpg')):
                    image=mp.Image.create_from_file(str(path));begin=time.monotonic()
                    prediction=recognizer.recognize(image)
                    categories=[g[0] for g in prediction.gestures if g]
                    # Still validation checks the expected label among all
                    # detected hands; live multi-hand actions remain suppressed.
                    match=next((c for c in categories if c.category_name==expected.get(path.name)),None)
                    name=match.category_name if match else None
                    score=float(match.score) if match else 0.
                    has_hand=bool(prediction.hand_landmarks)
                    row=dict(file=path.name,gesture=name,score=score,has_hand=has_hand,inference_ms=(time.monotonic()-begin)*1000)
                    if publisher:
                        packet=hand_features(prediction,time.monotonic_ns(),result['samples'])
                        packet['fixture']=True
                        (args.output/(path.stem+'.features.json')).write_text(json.dumps(packet))
                        publisher.send(packet)
                    rows.write(json.dumps(row)+'\n');result['samples']+=1
                    if path.name not in expected or name!=expected[path.name] or not has_hand:
                        raise RuntimeError('Official fixture classification mismatch: '+path.name)
                    if name!='Open_Palm':
                        if score<args.confidence:raise RuntimeError('Mapped fixture below configured threshold: '+path.name)
                        mapped+=1
                if mapped!=5:raise RuntimeError('All five mapped fixture classes required')
                result['five_mapped_fixture_classes_above_threshold']=True
            else:
                from hand_runtime import create_frame_reader
                reader=create_frame_reader(args.app_dir,args.model_pid);stack.callback(reader.close)
                result['frame_source']=getattr(reader,'source','existing_preview_RGB1080_center')
                result['owners']=dict(model=reader.model,capture=reader.capture)
                link=FreecivScreenInput() if args.send_actions else None
                if link:stack.callback(link.close)
                latch=GestureLatch(confidence=args.confidence)
                steady_start=time.monotonic();steady_cpu=time.process_time()
                deadline=steady_start+args.seconds if args.seconds else float('inf')
                (args.output/'ready.json').write_text(json.dumps(dict(pid=os.getpid(),owners=result['owners'],fps=args.fps,confidence=args.confidence)))
                schedule=SampleClock(args.fps)
                while not stop and time.monotonic()<deadline:
                    wait=schedule.delay(time.monotonic())
                    if wait:
                        if link:link.update()
                        time.sleep(min(.02,wait));continue
                    if link:link.update()
                    item=reader.read()
                    if item is None:schedule.busy(time.monotonic());continue
                    schedule.accepted(time.monotonic())
                    rgb,meta=item;begin=time.monotonic()
                    prediction=recognizer.recognize_for_video(rgb,meta['timestamp_ns']//1_000_000)
                    now=time.monotonic();name,score,has_hand=top(prediction)
                    if publisher:publisher.send(hand_features(prediction,meta['timestamp_ns'],result['samples'],capture_sequence=meta['sequence']))
                    reader.check_owners()
                    if link:link.update()
                    age=now-meta['timestamp_ns']/1e9
                    action=latch.observe(name,score,has_hand,meta['timestamp_ns']/1e9,now)
                    row=dict(**meta,gesture=name,score=score,has_hand=has_hand,inference_ms=(now-begin)*1000,
                             age_ms=age*1000,action=action,sent=False)
                    if age>.35:result['censored_results']+=1
                    if action:
                        if link:row['sent']=send_game_action(link,action)
                        result['events'].append(dict(action=action,sent=row['sent'],timestamp_ns=meta['timestamp_ns']))
                    rows.write(json.dumps(row)+'\n');result['samples']+=1
                reader.check_owners();result['reader_stats']=reader.stats
                steady_seconds=time.monotonic()-steady_start
                result['steady_state']=dict(seconds=steady_seconds,samples_per_second=result['samples']/steady_seconds,
                    cpu_one_core_percent=100*(time.process_time()-steady_cpu)/steady_seconds)
                if link:
                    result['transport_counts']=link.counts
                    result['game_communication_verified']=bool(link.counts['replies'])
        result['status']='PASS_ACTUAL_FIXTURE_INFERENCE' if args.fixtures else 'COMPLETED_ACTUAL_SHARED_PCIE_HAND_INFERENCE'
    except BaseException as error:
        result['status']='FAILED_PRESERVED';result['error']=repr(error);raise
    finally:
        elapsed=time.monotonic()-start
        result.update(elapsed_seconds=elapsed,cpu_one_core_percent=100*(time.process_time()-before)/elapsed,
                      max_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
        (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))

if __name__=='__main__':main()
