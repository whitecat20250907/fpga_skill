"""Bounded actual-board A/B sample; only starts and reaps its own hand process."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from profile_existing_main import process

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid',type=int,required=True)
    ap.add_argument('--csv',type=Path,required=True)
    ap.add_argument('--app-dir',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--cpu',default='4')
    ap.add_argument('--fps',type=float,default=3)
    ap.add_argument('--send-actions',action='store_true')
    args=ap.parse_args()
    if args.output.exists():ap.error('Preserve previous measurement')
    args.output.mkdir(parents=True)
    original=process(args.pid)
    owned=None
    result=dict(test='ACTUAL_BOARD_HAND_MAIN_NO_FACE_AB',human_test=False,actual_NPU_latency_measured=False)
    def measure(label):
        subprocess.run([sys.executable,str(ROOT/'tools/profile_existing_main.py'),
            '--pid',str(args.pid),'--csv',str(args.csv),'--seconds','20',
            '--label',label,'--output',str(args.output/(label+'.json'))],check=True,
            stdout=subprocess.DEVNULL,timeout=25)
    try:
        measure('baseline_game_main')
        command=['taskset','-c',args.cpu,'nice','-n','15',str(ROOT/'.gesture-v1/venv/bin/python'),'-B',
            str(ROOT/'tools/run_mediapipe_gestures.py'),'--app-dir',str(args.app_dir),
            '--model-pid',str(args.pid),'--seconds','40','--fps',str(args.fps),
            '--output',str(args.output/'hand')]
        if args.send_actions:command.append('--send-actions')
        env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        with (args.output/'hand.log').open('w') as log:
            owned=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT)
            limit=time.monotonic()+20
            while not (args.output/'hand/ready.json').exists():
                if owned.poll() is not None:raise RuntimeError('Owned hand process failed before ready')
                if time.monotonic()>limit:raise RuntimeError('Owned hand process readiness timeout')
                time.sleep(.05)
            time.sleep(1)
            measure('parallel_game_main_hand')
            owned.send_signal(signal.SIGTERM)
            code=owned.wait(timeout=10)
            if code:raise RuntimeError(f'Owned hand process exit {code}')
        if process(args.pid)['start_ticks']!=original['start_ticks']:raise RuntimeError('Main instance changed')
        result.update(status='PASS_SCOPED_REAL_BOARD_NO_FACE_AB',original_main_preserved=True,
                      owned_hand_pid=owned.pid,owned_hand_reaped=True,cpu=args.cpu,fps=args.fps)
    except BaseException as error:
        result.update(status='FAILED_PRESERVED',error=repr(error));raise
    finally:
        if owned is not None and owned.poll() is None:
            owned.terminate()
            try:owned.wait(timeout=10)
            except subprocess.TimeoutExpired:
                owned.kill();owned.wait(timeout=5)
        (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))

if __name__=='__main__':main()
