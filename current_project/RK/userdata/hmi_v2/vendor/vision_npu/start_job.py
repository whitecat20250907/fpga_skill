"""Start an isolated finite job with all SSH descriptors closed."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('script');p.add_argument('args',nargs='*');p.add_argument('--toolkit',action='store_true');a=p.parse_args()
py='/userdata/gaze_model_migration_v1_20261014/'+('venv' if a.toolkit else 'app_venv')+'/bin/python'
with (ROOT/(Path(a.script).stem+'.job.log')).open('w') as f:
    child=subprocess.Popen([py,'-u','-B',str(ROOT/a.script),*a.args],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
print(child.pid)
