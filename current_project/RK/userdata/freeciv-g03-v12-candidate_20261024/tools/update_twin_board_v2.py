"""Guarded feature-viewer update; keep prior source and fixture evidence."""
import hashlib,io,json,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];HELPER=ROOT.parent/'tmp/freeciv_rk.py'
OUT=ROOT/'evidence/twin_board_v2'
def call(*args,**kwargs):return subprocess.run([sys.executable,'-X','utf8','-B',str(HELPER),*args],check=True,**kwargs)
def main():
    assert not OUT.exists();OUT.mkdir()
    previous={r['path']:r['sha256'] for r in json.loads((ROOT/'evidence/project_candidate_v1/candidate_manifest.json').read_text())}
    names=['project_twin.py','tools/run_project_twin.py','tools/render_board_twin_fixture.py']
    rows=[]
    with tarfile.open(OUT/'update.tar','w') as t:
        for name in names:
            body=(ROOT/name).read_bytes();rows.append(dict(path=name,old=previous.get(name),new=hashlib.sha256(body).hexdigest()))
            info=tarfile.TarInfo(name);info.size=len(body);t.addfile(info,io.BytesIO(body))
        body=json.dumps(rows).encode();info=tarfile.TarInfo('manifest.json');info.size=len(body);t.addfile(info,io.BytesIO(body))
    call('--put',str(OUT/'update.tar'),'/home/linaro/pcie_fix_20261003/twin_board_v2.tar')
    body=r'''
import hashlib,json,os,shutil,subprocess,tarfile
from pathlib import Path
r=Path('/userdata/freeciv-rk3576-gaze-demo');o=r/'.maintenance/twin_board_v2';assert not o.exists()
h=lambda b:hashlib.sha256(b).hexdigest()
with tarfile.open('/home/linaro/pcie_fix_20261003/twin_board_v2.tar') as t:
 rows=json.loads(t.extractfile('manifest.json').read())
 for row in rows:
  p=r/row['path'];assert p.resolve().is_relative_to(r) and not p.is_symlink()
  assert (h(p.read_bytes()) if p.exists() else None)==row['old'],row['path']
  assert h(t.extractfile(row['path']).read())==row['new']
 o.mkdir()
 for row in rows:
  p=r/row['path'];b=o/'before'/row['path']
  if p.exists():b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,b)
  temp=p.with_name(p.name+'.update.tmp');temp.write_bytes(t.extractfile(row['path']).read());temp.replace(p)
 (o/'manifest.json').write_text(json.dumps(rows,indent=2))
subprocess.run([str(r/'.gesture-v1/venv/bin/python'),'-B',str(r/'tools/render_board_twin_fixture.py')],cwd=r,check=True)
shutil.copy2(r/'logs/project_twin_fixture_render_v1/actual_fixture_xyz.png','/home/linaro/pcie_fix_20261003/twin_fixture_actual_v1.png')
for pid in (73828,73824,118016,118079):
 p=Path('/proc')/str(pid)
 print(json.dumps(dict(pid=pid,exists=p.exists(),cwd=os.readlink(p/'cwd') if p.exists() else None,
  argv=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace') if p.exists() else None)))
'''
    script=OUT/'board.py';script.write_text(body,encoding='utf8')
    call('--put',str(script),'/home/linaro/pcie_fix_20261003/twin_board_v2.py')
    with (OUT/'actual.stdout').open('xb') as log:
        call('--command','python3 -B /home/linaro/pcie_fix_20261003/twin_board_v2.py','--timeout','20',stdout=log,stderr=subprocess.STDOUT)
    print((OUT/'actual.stdout').read_text(encoding='utf8'))
    call('--get','/home/linaro/pcie_fix_20261003/twin_fixture_actual_v1.png',str(OUT/'actual_fixture_xyz.png'))
if __name__=='__main__':main()
