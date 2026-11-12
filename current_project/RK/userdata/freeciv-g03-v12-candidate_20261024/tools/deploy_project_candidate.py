"""Guarded local-board candidate overlay and one real incremental ARM build."""
import hashlib,io,json,shlex,subprocess,sys,tarfile
from pathlib import Path
R=Path(__file__).resolve().parents[1];H=R.parent/'tmp/freeciv_rk.py';O=R/'evidence/project_candidate_v1'
def digest(data):return hashlib.sha256(data).hexdigest()
def normalized(data):return digest(data.replace(b'\r\n',b'\n'))
def call(args,**kwargs):return subprocess.run([sys.executable,'-X','utf8','-B',str(H),*args],check=True,**kwargs)
def main():
    assert not O.exists();O.mkdir(parents=True)
    names=['AGENTS.md','make_scenario.py','scenario/border-keep.sav','scenario/campaign.lua','project_features.py','project_twin.py',
        'tools/run_mediapipe_gestures.py','tools/run_project_twin.py','tools/run_main_feature_export.py',
        'upstream/freeciv-3.2.6/client/gui-gtk-3.22/demo_control.inc']
    names+=[p.relative_to(R).as_posix() for p in (R/'upstream/freeciv-3.2.6/data/gaze_war').rglob('*') if p.is_file()]
    rows=[];archive=O/'candidate.tar'
    with tarfile.open(archive,'w') as tar:
        for name in names:
            p=R/name;data=p.read_bytes();old=subprocess.run(['git','show','54e7b3f:'+name],cwd=R,capture_output=True)
            rows.append(dict(path=name,sha256=digest(data),old_normalized_sha256=normalized(old.stdout) if old.returncode==0 else None))
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;tar.addfile(info,io.BytesIO(data))
        blob=json.dumps(rows).encode();info=tarfile.TarInfo('candidate_manifest.json');info.size=len(blob);tar.addfile(info,io.BytesIO(blob))
    (O/'candidate_manifest.json').write_text(json.dumps(rows,indent=2))
    remote='/home/linaro/pcie_fix_20261003/project_candidate_v1.tar'
    call(['--put',str(archive),remote])
    body=r'''
import hashlib,json,os,shutil,subprocess,tarfile,time
from pathlib import Path
root=Path('/userdata/freeciv-rk3576-gaze-demo');out=root/'.maintenance/project_candidate_v1'
assert not out.exists();assert subprocess.check_output(['git','-C',str(root),'rev-parse','--short','HEAD'],text=True).strip()=='54e7b3f'
digest=lambda b:hashlib.sha256(b).hexdigest()
with tarfile.open('/home/linaro/pcie_fix_20261003/project_candidate_v1.tar') as archive:
 rows=json.loads(archive.extractfile('candidate_manifest.json').read())
 for row in rows:
  p=root/row['path'];assert p.resolve().is_relative_to(root) and not p.is_symlink()
  if p.exists():assert row['old_normalized_sha256'] is not None and digest(p.read_bytes().replace(b'\r\n',b'\n'))==row['old_normalized_sha256'],row['path']
  else:assert row['old_normalized_sha256'] is None,row['path']
  assert digest(archive.extractfile(row['path']).read())==row['sha256']
 out.mkdir(parents=True);backup=out/'before';backup.mkdir()
 for binary in ('freeciv-gtk3.22','freeciv-server'):
  shutil.copy2(root/'build-arm64'/binary,backup/binary)
 for row in rows:
  p=root/row['path'];saved=backup/row['path']
  if p.exists():saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,saved)
  p.parent.mkdir(parents=True,exist_ok=True)
  temp=p.with_name(p.name+'.candidate.tmp');temp.write_bytes(archive.extractfile(row['path']).read());temp.replace(p)
  assert digest(p.read_bytes())==row['sha256']
 (out/'manifest.json').write_text(json.dumps(rows,indent=2))
started=time.monotonic()
with (out/'build.log').open('wb') as log:
 child=subprocess.Popen(['taskset','-c','0-3','nice','-n','15','ionice','-c','3','ninja','-C',str(root/'build-arm64'),'-j','1'],cwd=root,stdout=log,stderr=subprocess.STDOUT)
 print('ORIGINAL_ARM_INCREMENTAL_BUILD',child.pid,flush=True);code=child.wait()
result=dict(status='PASS_ACTUAL_ARM_NATIVE_BUILD' if code==0 else 'FAILED_ACTUAL_ARM_NATIVE_BUILD',returncode=code,seconds=time.monotonic()-started,
 original_Popen_waited=True,model_or_camera_restarted=False,old_game_not_stopped=True,board_gameplay_accepted=False,
 binaries={b:digest((root/'build-arm64'/b).read_bytes()) for b in ('freeciv-gtk3.22','freeciv-server')})
(out/'build_result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
raise SystemExit(code)
'''
    (O/'board_install_build.py').write_text(body,encoding='utf8')
    call(['--put',str(O/'board_install_build.py'),'/home/linaro/pcie_fix_20261003/project_candidate_v1.py'])
    with (O/'actual.stdout').open('xb') as log:
        call(['--command','python3 -B /home/linaro/pcie_fix_20261003/project_candidate_v1.py','--timeout','900'],stdout=log,stderr=subprocess.STDOUT)
    print((O/'actual.stdout').read_text(encoding='utf8'),flush=True)
if __name__=='__main__':main()
