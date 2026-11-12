import subprocess
from pathlib import Path
root=Path('/userdata/freeciv-rk3576-gaze-demo')
with (root/'.maintenance/semantic_selection_v1/session_owner.log').open('xb') as stream:
    p=subprocess.Popen(['/userdata/gaze_model_migration_v1_20261014/app_venv/bin/python','-u','-B','/home/linaro/pcie_fix_20261003/semantic_board_session.py'],
        cwd=root,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
print('Started owned semantic test session',p.pid)
