import hashlib,json,shutil,subprocess,tarfile,time
from pathlib import Path
ROOT=Path('/userdata/freeciv-rk3576-gaze-demo');OUT=ROOT/'.maintenance/semantic_selection_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
def run(name,command):
    with (OUT/(name+'.log')).open('xb') as log:
        result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    print(name,result.returncode,flush=True)
    if result.returncode:print((OUT/(name+'.log')).read_text(errors='replace')[-8000:],flush=True)
    result.check_returncode()
def main():
    with tarfile.open('/home/linaro/pcie_fix_20261003/semantic_selection_v1.tar') as archive:
        rows=json.loads(archive.extractfile('manifest.json').read())
        for row in rows:
            path=ROOT/row['path'];assert path.resolve().is_relative_to(ROOT) and not path.is_symlink()
            assert (sha(path.read_bytes())==row['old']) if path.exists() else row['old'] is None,row['path']
            assert sha(archive.extractfile(row['path']).read())==row['new']
        OUT.mkdir(exist_ok=False);(OUT/'before').mkdir()
        shutil.copy2(ROOT/'build-arm64/freeciv-gtk3.22',OUT/'before/freeciv-gtk3.22')
        for row in rows:
            path=ROOT/row['path'];backup=OUT/'before'/row['path'];backup.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():shutil.copy2(path,backup)
            temporary=path.with_suffix(path.suffix+'.semantic.tmp');temporary.write_bytes(archive.extractfile(row['path']).read());temporary.replace(path)
        (OUT/'manifest.json').write_text(json.dumps(rows,indent=2))
    run('native_tests',['python3','-B','tools/test_semantic_native.py'])
    for name in ['test_semantic_selection.py','test_start_menu.py','test_screen_bridge.py']:
        run(name,['python3','-B','-m','unittest','discover','-s','tests','-p',name,'-v'])
    start=time.monotonic()
    run('build',['taskset','-c','0-3','nice','-n','15','ionice','-c','3','ninja','-C',str(ROOT/'build-arm64'),'-j','1','freeciv-gtk3.22'])
    report=dict(status='PASS_ARM_BUILD_AND_SELECTION_REGRESSIONS',build_seconds=time.monotonic()-start,
        client_sha256=sha((ROOT/'build-arm64/freeciv-gtk3.22').read_bytes()),main_model_restarted=False)
    (OUT/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
