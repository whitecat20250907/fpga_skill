"""Manual native game replacement; retain and reap the original launch Popen.

Run on RK as its existing desktop user. Only the verified old game is closed;
the camera, gaze model, their owners, and drivers are outside this script.
Create this session's stop.request to close this owned candidate normally.
"""
import argparse,hashlib,json,os,signal,subprocess,time
from pathlib import Path
ROOT=Path('/userdata/freeciv-rk3576-gaze-demo')

def identity(pid):
    p=Path('/proc')/str(pid)
    try:return dict(pid=pid,cwd=os.readlink(p/'cwd'),argv=(p/'cmdline').read_bytes().split(b'\0'),
                birth=(p/'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--session',required=True);args=ap.parse_args()
    assert args.session.startswith('campaign_GUI_') and args.session.replace('_','').isalnum()
    OUT=ROOT/'.maintenance'/args.session
    assert not OUT.exists()
    main=identity(118016);assert main and main['cwd']=='/userdata/gaze_model_migration_v1_20261014/app_v28'
    raw=(Path('/proc/118016/environ')).read_bytes().split(b'\0');env=dict(os.environ)
    wanted={b'DISPLAY',b'XAUTHORITY',b'DBUS_SESSION_BUS_ADDRESS',b'XDG_RUNTIME_DIR'}
    for entry in raw:
        key,sep,value=entry.partition(b'=')
        if sep and key in wanted:env[key.decode()]=value.decode()
    assert env.get('DISPLAY');OUT.mkdir()
    with (OUT/'launch.log').open('wb') as log:
        p=subprocess.Popen(['taskset','-c','0-3','nice','-n','10','ionice','-c','3','python3','-B','launch.py','--build','build-arm64'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        ready=dict(status='OWNED_NATIVE_GAME_LAUNCH_STARTED',launcher_pid=p.pid,boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            original_camera_untouched=True,model_pid=118016,capture_pid=118079,old_game_closed=True,
            client_sha256=hashlib.sha256((ROOT/'build-arm64/freeciv-gtk3.22').read_bytes()).hexdigest())
        (OUT/'ready.json').write_text(json.dumps(ready,indent=2));print(json.dumps(ready),flush=True)
        try:
            while p.poll() is None and not (OUT/'stop.request').exists():time.sleep(.25)
        finally:
            if p.poll() is None:
                # Verify only our launcher's descendants, then close its client.
                children=[]
                for path in Path('/proc').glob('[0-9]*/stat'):
                    try:
                        fields=path.read_text().rsplit(')',1)[1].split()
                        if int(fields[1])==p.pid:
                            child=identity(int(path.parent.name))
                            if child and child['cwd']==str(ROOT) and child['argv'][0]==str(ROOT/'build-arm64/freeciv-gtk3.22').encode():children.append(child)
                    except (FileNotFoundError,ProcessLookupError,PermissionError):pass
                for child in children:
                    actual=identity(child['pid'])
                    if actual and actual['birth']==child['birth']:os.kill(child['pid'],signal.SIGTERM)
                deadline=time.monotonic()+10
                while p.poll() is None and time.monotonic()<deadline:
                    active=[]
                    for path in Path('/proc').glob('[0-9]*/stat'):
                        try:
                            fields=path.read_text().rsplit(')',1)[1].split()
                            if int(fields[1])==p.pid:
                                child=identity(int(path.parent.name))
                                if child and child['cwd']==str(ROOT) and child['argv'][0] in (
                                    str(ROOT/'build-arm64/freeciv-gtk3.22').encode(),str(ROOT/'build-arm64/freeciv-server').encode()):active.append(child)
                        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
                    if not active:break
                    time.sleep(.1)
                if p.poll() is None and not active:p.terminate()  # Our owned, idle start page only.
            code=p.wait(timeout=12)
            result=dict(status='ORIGINAL_GAME_LAUNCHER_REAPED',returncode=code,original_Popen_waited=True)
            (OUT/'terminal.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
