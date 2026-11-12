"""Isolated app34; only downstream Python input preparation changes."""
import hashlib,json,os,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent;BASE=Path('/userdata/gaze_model_migration_v1_20261014')
OLD=BASE/'app_v33_dualcore_20261022';APP=BASE/'app_v34_cpu_reuse_20261022';PKG=Path('/userdata/cpu_model_reuse_20261022')
assert not APP.exists() and not PKG.exists()
shutil.copytree(OLD,APP,ignore=shutil.ignore_patterns('__pycache__'))
PKG.mkdir()
for p in ROOT.glob('*.py'):shutil.copy2(p,PKG/p.name)
shutil.copy2(ROOT/'policy.json',PKG/'policy.json')
(PKG/'models').symlink_to('/userdata/all_models_npu_20261022/models',target_is_directory=True)
def edit(name,before,after):
    p=APP/name;s=p.read_text();assert s.count(before)==1,(name,before);p.write_text(s.replace(before,after))
edit('start.sh','app_v33_dualcore_20261022','app_v34_cpu_reuse_20261022')
edit('gaze_runtime.py',"'/userdata/npu_dualcore_20261022'","'/userdata/cpu_model_reuse_20261022'")
for spaces in (8,16):
    indent=' '*spaces
    edit('gaze_runtime.py',indent+'if face.status:\n'+indent+'    for rect in',
         indent+'if face.status:\n'+indent+'    rgb = rgb.copy()  # Only the display overlay needs writable pixels.\n'+indent+'    for rect in')
shutil.copy2(ROOT/'shared_model_frame.py',APP/'shared_model_frame.py')
edit('pcie_capture.py','from shared_preview import SharedPreview','from shared_preview import SharedPreview\nfrom shared_model_frame import SharedModelFrame')
edit('pcie_capture.py',"        try:\n            self.process=subprocess.Popen", "        self.model_store=None\n        try:\n            if self.reduced_output:self.model_store=SharedModelFrame()\n            self.process=subprocess.Popen")
edit('pcie_capture.py',"        except BaseException:\n            if self.preview_store", "        except BaseException:\n            if self.model_store is not None:self.model_store.close()\n            if self.preview_store")
edit('pcie_capture.py','                # Native RGB3 is RGB.', '                if self.model_store is not None:self.model_store.publish(data,meta)\n                # Native RGB3 is RGB.')
edit('pcie_capture.py','        # One private writable RGB frame, also safe for post-inference drawing.\n        return True,small.copy()',
     '        # Native bytes remain immutable; drawing makes its own copy downstream.\n        return True,small')
edit('pcie_capture.py','        # Child capture/writer has ended before closing the parent snapshot.',
     '        # The Python publisher must finish before its buffer can be unmapped.\n        if self.model_store is not None and not self.thread.is_alive():self.model_store.close()\n        # Child capture/writer has ended before closing the parent snapshot.')
out=ROOT/'app_source';out.mkdir()
names=['gaze_runtime.py','pcie_capture.py','start.sh','settings.json','shared_model_frame.py']
for name in names:shutil.copy2(APP/name,out/name)
unchanged=['capture_native','capture_native.c','async_output.c','async_output.h','preview_snapshot.h','rgb_area3.h','shared_preview.py','settings.json']
evidence=[]
for name in unchanged:
    a=hashlib.sha256((OLD/name).read_bytes()).hexdigest();b=hashlib.sha256((APP/name).read_bytes()).hexdigest()
    assert a==b,name
    evidence.append(dict(name=name,old_sha256=a,new_sha256=b,unchanged=True))
(ROOT/'unchanged_capture.json').write_text(json.dumps(evidence,indent=2)+'\n')
for directory in (APP,PKG):
    for p in [directory,*directory.rglob('*')]:
        if not p.is_symlink():os.chown(p,1000,1000)
print('PREPARED_APP34_CPU_INPUT_REUSE')
