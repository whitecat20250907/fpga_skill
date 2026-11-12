import subprocess,sys
from core.config import ROOT

def test_old_absolute_paths_cannot_override_frozen_project_modules(tmp_path):
    (tmp_path/'region8.py').write_text('raise RuntimeError("historical module selected")')
    code='''import sys
from vision.bootstrap import install_vendor_resolver
from core.config import ROOT
install_vendor_resolver()
sys.path.insert(0,sys.argv[1])
import region8,multi_trajectory,json
from pathlib import Path
assert Path(region8.__file__)==ROOT/'vendor/gaze_app/region8.py'
assert Path(multi_trajectory.__file__)==ROOT/'vendor/ui_support/multi_trajectory.py'
assert 'vendor' not in Path(json.__file__).parts
'''
    subprocess.run([sys.executable,'-c',code,str(tmp_path)],cwd=ROOT,check=True,capture_output=True,text=True)
