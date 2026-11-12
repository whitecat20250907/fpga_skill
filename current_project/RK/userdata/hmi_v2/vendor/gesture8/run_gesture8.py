"""Optional bounded eight-trajectory recognizer sharing the current PCIe RGB.

Uses the same gesture.lock as the existing five-action sampler. No OS keys or
game actions are sent: class-to-shortcut mapping must be supplied by the user.
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

ROOT = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--game-dir', type=Path, default=Path('/userdata/freeciv-rk3576-gaze-demo'))
    ap.add_argument('--app-dir', type=Path, default=Path('/userdata/gaze_model_migration_v1_20261014/app_v34_cpu_reuse_20261022'))
    ap.add_argument('--model-pid', type=int, required=True)
    ap.add_argument('--seconds', type=float, default=30)
    ap.add_argument('--fps', type=float, default=0, help='0 = process every available new frame')
    ap.add_argument('--cpu-threads',type=int,choices=(0,1,2,4),default=2)
    ap.add_argument('--num-hands',type=int,choices=(1,2,3,4),default=4,
                    help='Capacity up to four hands; ambiguous single-stroke ownership is rejected')
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if not 0 < args.seconds <= 300 or not __import__('math').isfinite(args.fps) or args.fps<0:
        ap.error('seconds in (0,300], fps >=0 (0 uncapped)')
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.game_dir.resolve()))
    from hand_runtime import create_frame_reader
    from trajectory import TrajectoryRecorder, observations
    from classifier import Classifier
    from hand_runtime import create_recognizer,SampleClock
    stop = False
    def terminate(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, terminate); signal.signal(signal.SIGINT, terminate)
    report = dict(status='RUNNING', pid=os.getpid(), samples=0, npu_calls=0, results=[],
                  camera_opened=False, actions_sent=False, live_gesture_acceptance=False,
                  cpu_threads=args.cpu_threads,num_hands=args.num_hands,requested_fps=args.fps,
                  boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    begin, cpu_begin = time.monotonic(), time.process_time()
    try:
        with ExitStack() as stack:
            lock = stack.enter_context((args.game_dir/'logs/gesture.lock').open('a+'))
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
            reader = create_frame_reader(args.app_dir, args.model_pid)
            stack.callback(reader.close)
            report['owners'] = dict(model=reader.model,capture=reader.capture)
            import mediapipe as mp
            asset = args.game_dir/'.gesture-v1/assets/gesture_recognizer.task'
            if hashlib.sha256(asset.read_bytes()).hexdigest() != '97952348cf6a6a4915c2ea1496b4b37ebabc50cbbf80571435643c455f2b0482':
                raise RuntimeError('Existing MediaPipe asset hash changed')
            recognizer = stack.enter_context(create_recognizer(asset,num_hands=args.num_hands,cpu_threads=args.cpu_threads))
            classifier = Classifier(ROOT); stack.callback(classifier.close)
            recorder = TrajectoryRecorder()
            rows = stack.enter_context((args.output/'samples.jsonl').open('w',buffering=1))
            started, cpu_started = time.monotonic(), time.process_time()
            schedule = SampleClock(args.fps)
            while not stop and time.monotonic()-started < args.seconds:
                recorder.tick(time.monotonic())
                wait=schedule.delay(time.monotonic())
                if wait:
                    time.sleep(min(.02,wait))
                    continue
                item = reader.read()
                if item is None:
                    schedule.busy(time.monotonic());continue
                schedule.accepted(time.monotonic())
                rgb, meta = item
                t0 = time.monotonic()
                prediction = recognizer.recognize_for_video(rgb,meta['timestamp_ns']//1_000_000)
                reader.check_owners()
                hands = observations(prediction)
                now = time.monotonic()
                raster = recorder.update(hands,meta['sequence'],meta['timestamp_ns']/1e9,now,rgb.shape[1],rgb.shape[0])
                row = dict(**meta,hand_count=len(hands),state=recorder.state,reason=recorder.reason,
                           point_count=len(recorder.points),hand_ms=(now-t0)*1000,source_age_ms=(now-meta['timestamp_ns']/1e9)*1000)
                if raster is not None:
                    npu_start = time.monotonic()
                    result = classifier.predict(raster)
                    reader.check_owners()
                    result.update(npu_ms=(time.monotonic()-npu_start)*1000,capture_sequence=meta['sequence'],timestamp_ns=meta['timestamp_ns'])
                    if time.monotonic()-meta['timestamp_ns']/1e9 > .35:
                        result.update(accepted=False,rejection='expired_after_npu')
                    report['npu_calls'] += 1
                    report['results'].append(result); row['result'] = result
                    import cv2
                    cv2.imwrite(str(args.output/('trajectory_%03d.png'%report['npu_calls'])),raster)
                    print(json.dumps(result),flush=True)
                rows.write(json.dumps(row)+'\n');report['samples'] += 1
            reader.check_owners()
            elapsed = time.monotonic()-started
            report.update(status='COMPLETED_SHARED_PCIE_OBSERVATION',reader_stats=reader.stats,
                          steady_seconds=elapsed,steady_cpu_one_core_percent=100*(time.process_time()-cpu_started)/elapsed)
    except BaseException as error:
        report.update(status='FAILED_PRESERVED',error=repr(error))
        raise
    finally:
        report.update(seconds=time.monotonic()-begin,cpu_seconds=time.process_time()-cpu_begin,
                      max_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
        (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report),flush=True)


if __name__ == '__main__':
    main()
