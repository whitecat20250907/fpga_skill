"""Bounded actual shared-camera hand inference plus read-only twin renderer."""
import argparse,json,os,subprocess,time
from pathlib import Path
ROOT=Path('/userdata/freeciv-rk3576-gaze-demo')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tag',default='project_twin_live_v2');args=ap.parse_args()
    assert args.tag=='project_twin_live_v2';OUT=ROOT/'logs'/args.tag
    assert not OUT.exists();OUT.mkdir()
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    python=str(ROOT/'.gesture-v1/venv/bin/python')
    viewer=None;hands=None
    with (OUT/'viewer.stdout').open('wb') as view_log,(OUT/'hands.stdout').open('wb') as hand_log:
        try:
            viewer=subprocess.Popen(['taskset','-c','0-3','nice','-n','15',python,'-B','tools/run_project_twin.py',
                '--seconds','16','--output',str(OUT/'viewer')],cwd=ROOT,env=env,stdout=view_log,stderr=subprocess.STDOUT)
            time.sleep(.7)
            hands=subprocess.Popen(['taskset','-c','4','nice','-n','15',python,'-B','tools/run_mediapipe_gestures.py',
                '--app-dir','/userdata/gaze_model_migration_v1_20261014/app_v28','--model-pid','118016',
                '--seconds','10','--fps','6','--feature-port','29802','--output',str(OUT/'hands')],
                cwd=ROOT,env=env,stdout=hand_log,stderr=subprocess.STDOUT)
            print(json.dumps(dict(owned_viewer_pid=viewer.pid,owned_hand_pid=hands.pid)),flush=True)
            hands.wait(timeout=45);viewer.wait(timeout=45)
        finally:
            for child in (hands,viewer):
                if child is not None:
                    if child.poll() is None:child.terminate()
                    child.wait(timeout=6)
    result=dict(hand_returncode=hands.returncode,viewer_returncode=viewer.returncode,
                original_Popen_both_waited=True,camera_or_model_restarted=False,human_motion_accepted=False,
                hand=json.loads((OUT/'hands/result.json').read_text()),viewer=json.loads((OUT/'viewer/result.json').read_text()))
    (OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
    assert hands.returncode==0 and viewer.returncode==0
if __name__=='__main__':main()
