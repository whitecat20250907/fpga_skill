"""Observe live bus latency for a bounded duration; no hardware/action writes."""
import argparse,json,time,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from core.config import load
from core.hmibus import Subscriber
def main():
 p=argparse.ArgumentParser();p.add_argument('--seconds',type=float,default=60);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if not 1<=a.seconds<=3600:p.error('seconds must be 1..3600')
 c=load();topics=['frame.meta','vision.gaze','vision.hands','hmi.state','sys.metrics'];sub=Subscriber(topics,run=c['paths']['run']);rows={};epochs=set();start=time.monotonic();last={}
 try:
  while time.monotonic()-start<a.seconds:
   for topic,msg in sub.poll(50).items():
    now=time.monotonic_ns();epochs.add(msg['epoch'])
    r=rows.setdefault(topic,{'age_ms':[],'count':0,'out_of_order':0});r['count']+=1;r['age_ms'].append((now-msg['src_ns'])/1e6)
    if msg['src_ns']<=last.get(topic,0):r['out_of_order']+=1
    last[topic]=msg['src_ns']
 finally:sub.close()
 for r in rows.values():
  ages=sorted(r.pop('age_ms'));r['observed_hz']=r['count']/a.seconds;r['p50_ms']=ages[int((len(ages)-1)*.5)];r['p95_ms']=ages[int((len(ages)-1)*.95)];r['max_ms']=ages[-1]
 result={'duration_s':a.seconds,'epochs':sorted(epochs),'topics':rows,'source':'live IPC observation; inference accuracy not measured','status':'PASS' if rows and all(t in rows for t in topics[:-1]) else 'NO_DATA'}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));return result['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
