"""Install the optional user-authorized hand module in a separate /userdata env."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time
import urllib.request

MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task'
MODEL_SHA='97952348cf6a6a4915c2ea1496b4b37ebabc50cbbf80571435643c455f2b0482'
SAMPLE_BASE = 'https://storage.googleapis.com/mediapipe-tasks/gesture_recognizer/'
SAMPLES = ('thumbs_down.jpg', 'victory.jpg', 'thumbs_up.jpg', 'pointing_up.jpg')
PACKAGES = ('mediapipe==0.10.18', 'numpy==1.26.4', 'jax==0.4.35',
            'jaxlib==0.4.35', 'opencv-contrib-python==4.10.0.84')
SAMPLE_COMMIT='1675dd30f602848d0674de5c88dbc395f0877e59'
SOURCE_PINS={
    'official_example.ipynb':('examples/gesture_recognizer/python/gesture_recognizer.ipynb','a5723f6fa34cd35ca2b469165cbc1f45c1aa6249050ec46134e8fe5fabde963d'),
    'LICENSE':('LICENSE','e2d17c15aaea3a55ff77279e3d895dcbd68baa1b128e4ac9086126ab1d7235f6')}

def download(url, path):
    with urllib.request.urlopen(url, timeout=45) as response:
        value = response.read()
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_bytes(value); temp.replace(path)
    return dict(url=url, bytes=len(value), sha256=hashlib.sha256(value).hexdigest())

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prefix',type=Path,required=True)
    ap.add_argument('--complete-provenance',action='store_true',help='Verify already transferred official source; preserve the original failed installation record')
    args=ap.parse_args()
    prefix=args.prefix.resolve()
    if platform.machine()!='aarch64' or not prefix.is_relative_to('/userdata') or prefix==Path('/userdata'):
        raise RuntimeError('Requires the actual ARM64 board and a dedicated directory below /userdata')
    if args.complete_provenance:
        output=json.loads((prefix/'installation.json').read_text())
        target=prefix/'installation.completed.json'
        if output['status']!='FAILED_PRESERVED' or target.exists():raise RuntimeError('Requires an unrepaired retained failure')
        for name,(path,digest) in SOURCE_PINS.items():
            value=(prefix/'assets'/name).read_bytes()
            if hashlib.sha256(value).hexdigest()!=digest:raise RuntimeError('Official source pin mismatch')
            output['assets'][name]=dict(url=f'https://raw.githubusercontent.com/google-ai-edge/mediapipe-samples/{SAMPLE_COMMIT}/{path}',sha256=digest,bytes=len(value))
        output['freeze']=subprocess.check_output([str(prefix/'venv/bin/python'),'-m','pip','freeze'],text=True)
        output['official_samples_commit']=SAMPLE_COMMIT
        output['retained_initial_failure']='installation.json'
        output['status']='INSTALLED_SEPARATE_ENV_SOURCE_RECOVERED'
        output['source_recovery_unix']=time.time()
        target.write_text(json.dumps(output,indent=2)+'\n')
        print(json.dumps(dict(status=output['status'],prefix=str(prefix))));return
    if prefix.exists():raise RuntimeError('Install destination exists; preserve it and choose a new version')
    prefix.mkdir()
    (prefix/'tmp').mkdir(); (prefix/'assets').mkdir()
    output=dict(start_unix=time.time(),architecture=platform.machine(),packages=PACKAGES,
                original_main_environment_modified=False,backend='CPU MediaPipe Tasks; original gaze remains RKNN NPU')
    try:
        subprocess.run(['/usr/bin/python3','-m','venv',str(prefix/'venv')],check=True)
        import os
        env=dict(os.environ,TMPDIR=str(prefix/'tmp'),PIP_NO_CACHE_DIR='1',
                 OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        with (prefix/'install.log').open('w') as log:
            lockfile=Path(__file__).resolve().parents[1]/'requirements-gesture-rk3576.txt'
            requested=['-r',str(lockfile)] if lockfile.is_file() else list(PACKAGES)
            subprocess.run([str(prefix/'venv/bin/python'),'-m','pip','install','--only-binary=:all:',
                            *requested],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
        output['freeze']=subprocess.check_output([str(prefix/'venv/bin/python'),'-m','pip','freeze'],text=True)
        output['assets']={}
        output['assets']['gesture_recognizer.task']=download(MODEL_URL,prefix/'assets/gesture_recognizer.task')
        if output['assets']['gesture_recognizer.task']['sha256']!=MODEL_SHA:raise RuntimeError('Official version-1 model hash changed')
        for name in SAMPLES:
            output['assets'][name]=download(SAMPLE_BASE+name,prefix/'assets'/name)
        for name in ('fist.jpg','right_hands.jpg'):
            output['assets'][name]=download('https://storage.googleapis.com/mediapipe-assets/'+name,prefix/'assets'/name)
        output['official_samples_commit']=SAMPLE_COMMIT
        base='https://raw.githubusercontent.com/google-ai-edge/mediapipe-samples/'+SAMPLE_COMMIT+'/'
        for name,(path,digest) in SOURCE_PINS.items():
            row=download(base+path,prefix/'assets'/name)
            if row['sha256']!=digest:raise RuntimeError('Official source pin mismatch')
            output['assets'][name]=row
        output['status']='INSTALLED_SEPARATE_ENV_PENDING_ACTUAL_INFERENCE'
    except BaseException as error:
        output['status']='FAILED_PRESERVED';output['error']=repr(error)
        raise
    finally:
        output['end_unix']=time.time()
        (prefix/'installation.json').write_text(json.dumps(output,indent=2)+'\n')
        print(json.dumps(dict(status=output['status'],prefix=str(prefix))))

if __name__=='__main__': main()
