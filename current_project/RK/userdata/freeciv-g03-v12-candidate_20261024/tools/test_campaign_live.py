"""Bounded native GUI economy test. Actual UDP centers, no camera control."""
import argparse,json,os,struct,subprocess,time
from pathlib import Path
from test_live_input import Link,need

def screenshot(path):
    from PIL import Image
    proc=Path('/proc/118016/environ');env=dict(os.environ)
    for entry in proc.read_bytes().split(b'\0'):
        key,sep,value=entry.partition(b'=')
        if sep and key in (b'DISPLAY',b'XAUTHORITY'):env[key.decode()]=value.decode()
    rawpath=path.with_suffix('.xwd')
    subprocess.run(['xwd','-display',env['DISPLAY'],'-root','-silent','-out',str(rawpath)],env=env,check=True,timeout=6)
    raw=rawpath.read_bytes();h=struct.unpack_from('>25I',raw)
    need(h[11] in (24,32) and h[7]==0 and tuple(h[14:17])==(0xff0000,0xff00,0xff),'Unsupported desktop XWD encoding')
    pixels=raw[h[0]+h[19]*12:]
    Image.frombytes('RGB',(h[4],h[5]),pixels,'raw','BGR' if h[11]==24 else 'BGRX',h[12],1).save(path)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--resume-turn2',action='store_true');a=ap.parse_args()
    need(not a.output.exists(),'Keep previous actual evidence');a.output.mkdir(parents=True)
    link=Link();events=[];cases=[];result=dict(test='ACTUAL_ARM_CAMPAIGN_GUI_V2',human_input=False,events=events,cases=cases)
    def event(name):
        s=link.event(name);events.append(dict(event=name,state=s));return s
    def choose(kind,arg=None):
        s=event('wake');choices=[t for t in s['targets'] if t['kind']==kind and (arg is None or t['arg']==arg)]
        need(choices,f'Actual semantic target unavailable {kind}/{arg}')
        link.point(choices[0],s,seconds=.4);s=event('confirm');time.sleep(.2);s=link.state()
        need(not s['awake'],'Confirmed action must sleep');return s
    def end():
        old=link.state()['turn'];event('end');limit=time.monotonic()+8
        while time.monotonic()<limit:
            s=link.state(timeout=6)
            if s['turn']!=old:break
            time.sleep(.1)
        need(s['turn']==old+1,'Native turn must advance once');return s
    try:
        initial=link.state();result['initial']=initial;link.sequence=int(initial['last_event'])
        need(initial['campaign']==2 and initial['turn']==(2 if a.resume_turn2 else 1),'Expected expanded native scenario phase required')
        need(sorted(x['role'] for x in initial['army'])==[0,0,1,2,3],'Four native roles required')
        screenshot(a.output/'initial.png')
        event('cancel')
        if not a.resume_turn2:
            s=choose(5);need(s['city']>=0,'Recruitment panel must remain after opening')
            screenshot(a.output/'recruitment.png')
            for role in range(4):
                s=choose(3,role);need(s['city']>=0,'Production choice must leave the map-visible panel')
                need(s['cities'][0]['production_type']==next(u['type_id'] for u in initial['army'] if u['role']==role),'Native production did not change')
            cases.append(dict(name='all_four_native_production_choices',passed=True))
            choose(3,2);end()
        s=choose(5);s=event('wake');need(any(t['kind']==4 for t in s['targets']),'Native purchase must become legal on turn 2')
        before=s['gold'];cost=s['cities'][0]['buy_cost'];event('cancel')
        choose(5);s=choose(4)
        need(s['gold']==before-cost and s['cities'][0]['stock']>0,'Exact native treasury deduction and shield purchase required')
        before_count=sum(u['role']==2 for u in s['army']);s=end()
        need(sum(u['role']==2 for u in s['army'])>=before_count+1,'Purchased archer must actually spawn next turn')
        cases.append(dict(name='native_gold_purchase_and_next_turn_unit',passed=True,spent=cost,before_gold=before,after_gold=s['gold']))
        screenshot(a.output/'after_recruitment.png')
        s=event('wake');targets=[t for t in s['targets'] if t['kind']==7]
        need(targets,'Known native multi-step reachable centers required')
        target=max(targets,key=lambda t:t['x']);uid=s['unit'];before=next(u for u in s['army'] if u['id']==uid)
        link.point(target,s,seconds=.4);s=event('confirm');time.sleep(.3);s=link.state()
        after=next(u for u in s['army'] if u['id']==uid)
        need(not s['awake'] and after['tile']==target['arg'] and after['moves']<before['moves'],
             'Native multi-step path must reach selected tile and sleep')
        cases.append(dict(name='native_current_turn_multi_step_route',passed=True,before=before,after=after))
        screenshot(a.output/'after_movement.png')
        result.update(passed=True,final=link.state(),human_gaze_accepted=False,full_battle_accepted=False,
            movement_range_accepted=True)
    except BaseException as error:
        result.update(passed=False,error=repr(error));raise
    finally:
        link.socket.close();(a.output/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('events','initial','final')}),flush=True)
if __name__=='__main__':main()
