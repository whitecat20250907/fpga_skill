"""Deploy exact owned candidate files and perform another native ARM build."""
import argparse,hashlib,io,json,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];HELPER=ROOT.parent/'tmp/freeciv_rk.py'
def call(*args,**kwargs):return subprocess.run([sys.executable,'-X','utf8','-B',str(HELPER),*args],check=True,**kwargs)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tag',default='campaign_client_v6');ap.add_argument('--previous',default='campaign_client_v5');args=ap.parse_args()
    assert (args.tag,args.previous) in (('campaign_client_v5','campaign_client_v4'),('campaign_client_v6','campaign_client_v5'));OUT=ROOT/'evidence'/args.tag
    assert not OUT.exists();OUT.mkdir()
    previous={r['path']:r['sha256'] for r in json.loads((ROOT/'evidence/project_candidate_v1/candidate_manifest.json').read_text())}
    with tarfile.open(ROOT/'evidence/twin_board_v2/update.tar') as old:
        previous.update({r['path']:r['new'] for r in json.loads(old.extractfile('manifest.json').read())})
    previous.update({r['path']:r['new'] for r in json.loads((ROOT/'evidence/campaign_client_v3/manifest.json').read_text())})
    previous.update({r['path']:r['new'] for r in json.loads((ROOT/'evidence'/args.previous/'manifest.json').read_text())})
    names=['upstream/freeciv-3.2.6/client/gui-gtk-3.22/demo_control.inc','tools/test_live_input.py',
        'scenario/campaign.lua','scenario/border-keep.sav','scenario/duel-hotseat.sav','make_scenario.py',
        'tools/run_project_twin.py','tools/run_mediapipe_gestures.py','project_twin.py','AGENTS.md','launch.py','start_menu.py']
    if args.tag=='campaign_client_v6':names=['launch.py','start_menu.py']
    rows=[]
    with tarfile.open(OUT/'update.tar','w') as t:
        for name in names:
            old=previous.get(name)
            if old is None:
                original=subprocess.run(['git','show','54e7b3f:'+name],cwd=ROOT,capture_output=True)
                old=hashlib.sha256(original.stdout.replace(b'\r\n',b'\n')).hexdigest() if original.returncode==0 else None
            body=(ROOT/name).read_bytes();rows.append(dict(path=name,old=old,new=hashlib.sha256(body).hexdigest()))
            info=tarfile.TarInfo(name);info.size=len(body);t.addfile(info,io.BytesIO(body))
        body=json.dumps(rows).encode();info=tarfile.TarInfo('manifest.json');info.size=len(body);t.addfile(info,io.BytesIO(body))
    (OUT/'manifest.json').write_text(json.dumps(rows,indent=2))
    call('--put',str(OUT/'update.tar'),'/home/linaro/pcie_fix_20261003/'+args.tag+'.tar')
    body=r'''
import hashlib,json,shutil,subprocess,tarfile,time
from pathlib import Path
r=Path('/userdata/freeciv-rk3576-gaze-demo');o=r/'.maintenance/campaign_client_v4';assert not o.exists()
h=lambda b:hashlib.sha256(b).hexdigest()
with tarfile.open('/home/linaro/pcie_fix_20261003/campaign_client_v4.tar') as t:
 rows=json.loads(t.extractfile('manifest.json').read())
 for row in rows:
  p=r/row['path'];assert p.resolve().is_relative_to(r) and not p.is_symlink()
  assert (h(p.read_bytes())==row['old'] or h(p.read_bytes().replace(b'\r\n',b'\n'))==row['old']) if p.exists() else row['old'] is None,row['path']
  assert h(t.extractfile(row['path']).read())==row['new']
 o.mkdir()
 for binary in ('freeciv-gtk3.22','freeciv-server'):
  (o/'before').mkdir(exist_ok=True);shutil.copy2(r/'build-arm64'/binary,o/'before'/binary)
 for row in rows:
  p=r/row['path'];b=o/'before'/row['path'];b.parent.mkdir(parents=True,exist_ok=True)
  if p.exists():shutil.copy2(p,b)
  temp=p.with_name(p.name+'.update.tmp');temp.write_bytes(t.extractfile(row['path']).read());temp.replace(p)
 (o/'manifest.json').write_text(json.dumps(rows,indent=2))
start=time.monotonic()
with (o/'build.log').open('wb') as log:
 child=subprocess.Popen(['taskset','-c','0-3','nice','-n','15','ionice','-c','3','ninja','-C',str(r/'build-arm64'),'-j','1'],cwd=r,stdout=log,stderr=subprocess.STDOUT)
 print('ORIGINAL_NATIVE_BUILD',child.pid,flush=True);code=child.wait()
result=dict(returncode=code,seconds=time.monotonic()-start,original_Popen_waited=True,
 main_or_camera_restarted=False,client_sha256=h((r/'build-arm64/freeciv-gtk3.22').read_bytes()))
(o/'build_result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if code:print((o/'build.log').read_text(errors='replace')[-8000:],flush=True)
raise SystemExit(code)
'''.replace('campaign_client_v4',args.tag)
    script=OUT/'board.py';script.write_text(body,encoding='utf8')
    call('--put',str(script),'/home/linaro/pcie_fix_20261003/'+args.tag+'.py')
    with (OUT/'actual.stdout').open('xb') as log:
        call('--command','python3 -B /home/linaro/pcie_fix_20261003/'+args.tag+'.py','--timeout','120',stdout=log,stderr=subprocess.STDOUT)
    print((OUT/'actual.stdout').read_text(encoding='utf8'))
if __name__=='__main__':main()
