import json,sys
from pathlib import Path
ROOT=Path('/userdata/cpu_model_reuse_lifecycle_20261022')
seq=max([int(x.stem.split('_')[1]) for x in ROOT.glob('request_*.json')]+[0])+1
if seq>1 and not (ROOT/f'response_{seq-1:04d}.json').exists():raise RuntimeError('Previous request pending')
d=dict(action=sys.argv[1])
if d['action']=='benchmark':d['args']=sys.argv[2:];d['label']='benchmark_'+str(seq)
if d['action']=='start':
    d.update(app=sys.argv[2],label=sys.argv[3])
    if len(sys.argv)>4:d['seconds']=int(sys.argv[4])
if d['action']=='job':d.update(__import__('json').loads(sys.argv[2]))
p=ROOT/f'request_{seq:04d}.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d)+'\n');tmp.replace(p);print(p)
