"""Package candidate and a retained-parent lifecycle; no credentials included."""
import ast,shutil,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'npu_dualcore_20261022';REPO=ROOT.parents[1]
s=(OLD/'lifecycle.py').read_text()
s=s.replace('/userdata/npu_dualcore_lifecycle_20261022','/userdata/cpu_model_reuse_lifecycle_20261022')
s=s.replace('/userdata/twb_ui_trial_20261022_v6/lifecycle/selected.json','/userdata/npu_dualcore_lifecycle_20261022/selected.json')
s=s.replace('/userdata/twb_ui_trial_20261022_v6/lifecycle/restored_2_closed.json','/userdata/npu_dualcore_lifecycle_20261022/lifecycle/selected_uncapped_closed.json')
s=s.replace("        elif action=='benchmark':", "        elif action in ('benchmark','job'):")
s=s.replace("str(ROOT/'benchmark_dual.py')", "str(Path(cmd.get('package',str(ROOT)))/cmd.get('script','benchmark_dual.py'))")
s=s.replace("cwd=ROOT,env=dict(env,NPU_LOAD_FILE=str(loadfile))", "cwd=ROOT,env=dict(env,NPU_LOAD_FILE=str(loadfile),GAZE_APP_DIR=cmd.get('app','/userdata/gaze_model_migration_v1_20261014/app_v34_cpu_reuse_20261022'))")
(ROOT/'lifecycle.py').write_text(s)
s=(OLD/'request.py').read_text().replace('/userdata/npu_dualcore_lifecycle_20261022','/userdata/cpu_model_reuse_lifecycle_20261022')
s=s.replace("p=ROOT/f'request_", "if d['action']=='job':d.update(__import__('json').loads(sys.argv[2]))\np=ROOT/f'request_")
(ROOT/'request.py').write_text(s)
game=ROOT/'game_adapter';game.mkdir(exist_ok=True)
for name in ['hand_runtime.py','tools/run_mediapipe_gestures.py','start-gestures-rk3576.sh']:
    shutil.copy2(REPO.parent/'freeciv-rk3576-gaze-demo'/name,game/Path(name).name)
shutil.copy2(ROOT.parent/'gesture8_rk3576_20261021/run_gesture8.py',game/'run_gesture8.py')
for p in ROOT.rglob('*.py'):ast.parse(p.read_text(encoding='utf8'),filename=str(p))
out=REPO.parent/'tmp/cpu_model_reuse_20261022.tar.gz'
with tarfile.open(out,'w:gz') as tar:
    for p in ROOT.rglob('*'):
        if p.is_file() and '__pycache__' not in str(p):tar.add(p,arcname=str(p.relative_to(ROOT)))
print(out)
