"""Play the actual native campaign through five-action semantic UDP only.

Uses read-only client-known tiles and legal targets. No save/HP/gold mutation,
server console commands, model calls, camera access or fixed screen grid.
"""
import argparse,json,os,sys,time,traceback
from pathlib import Path
from test_live_input import Link,need
from run_on_desktop import environment
from profile_linux import snapshot
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--turns',type=int,default=28);ap.add_argument('--resume',action='store_true');a=ap.parse_args()
    a.output.mkdir(exist_ok=False);env,_=environment(1721);os.environ.update(env)
    link=Link();events=[];cases=[];begin=time.monotonic();resources=[]
    result=dict(test='ACTUAL_NATIVE_CAMPAIGN_FULL_BATTLE_V3',human_input=False,camera_or_inference_started=False,events=events,cases=cases)
    def save():
        (a.output/'progress.json').write_text(json.dumps(result,indent=2))
    def capture(name):
        import gi;gi.require_version('Gdk','3.0');from gi.repository import Gdk
        root=Gdk.get_default_root_window();pix=Gdk.pixbuf_get_from_window(root,0,0,root.get_width(),root.get_height());pix.savev(str(a.output/(name+'.png')),'png',[],[])
    def wait(predicate,seconds=20):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            try:s=link.state(.8)
            except RuntimeError:continue
            if predicate(s):return s
            time.sleep(.05)
        raise RuntimeError('Native state transition timed out')
    def event(name):
        s=link.event(name);events.append(dict(t=round(time.monotonic()-begin,3),action=name,turn=s['turn'],unit=s['unit'],gold=s['gold'],army=len(s.get('army',[]))));return s
    def choose(target,state):
        # Refresh the real target identity after wake, never use a screen grid.
        if state['awake']:event('cancel')
        s=event('wake');t=next((t for t in s['targets'] if (t['kind'],t['id'],t['arg'])==(target['kind'],target['id'],target['arg'])),None)
        if t is None:return None
        link.point(t,s,.38);ready=link.state()
        if not ready['selection_ready']:
            link.point(t,s,.25);ready=link.state()
        need(ready['selection_ready'],'Actual target center did not become confirmable')
        after=event('confirm');need(not after['awake'],'Confirmed native action must sleep');time.sleep(.12)
        return link.state()
    def choose_kind(kind,arg=None):
        s=link.state()
        if s['awake']:event('cancel')
        s=event('wake');t=next((t for t in s['targets'] if t['kind']==kind and (arg is None or t['arg']==arg)),None)
        if t is None:event('cancel');return None
        link.point(t,s,.4);after=event('confirm');need(not after['awake'],'Confirmed selection must sleep');time.sleep(.1);return link.state()
    def focus(uid):
        # Tab advances native idle units and can skip a unit marked done by a
        # completed goto. Prefer its actual semantic unit target when present.
        s=link.state()
        if s['unit']==uid:return s
        if s['awake']:event('cancel')
        s=event('wake');target=next((t for t in s['targets'] if t['kind']==1 and t['id']==uid),None)
        if target is not None:
            link.point(target,s,.4);s=event('confirm')
            if s['unit']==uid:return s
        event('cancel');seen=set()
        for _ in range(12):
            s=link.state()
            if s['unit']==uid:return s
            if not any(u['id']==uid and u['moves']>0 for u in s.get('army',[])):return None
            if s['unit'] in seen:return None
            seen.add(s['unit'])
            event('next')
        return None
    def end_turn():
        s=link.state();old=s['turn'];event('end')
        return wait(lambda s:s.get('game_over') or s.get('outcome',0)!=0 or s['turn']>old,12)
    def distance(tile,goal):
        x,y=tile%24,tile//24;gx,gy=goal%24,goal//24
        return max(abs(x-gx),abs(y-gy))+.04*(abs(x-gx)+abs(y-gy))
    def metrics(label,before,start):
        after=snapshot();elapsed=time.monotonic()-start;hz=os.sysconf('SC_CLK_TCK');rows=[]
        for pid,old in before.items():
            new=after.get(pid)
            if new and new['start']==old['start']:
                rows.append(dict(name=new['name'],pid=pid,cpu_one_core_percent=(new['ticks']-old['ticks'])/hz/elapsed*100,rss_mib=new['rss_bytes']/2**20))
        resources.append(dict(phase=label,seconds=elapsed,processes=rows));result['resources']=resources
    try:
        s=link.state();link.sequence=int(s['last_event'])
        if not a.resume:
            if s.get('phase')!='menu':
                need(s.get('game_over'),'Only leave a native completed match through its return target')
                s=event('wake');t=next(t for t in s['targets'] if t['kind']==9);link.point(t,s,.4)
                link.sequence+=1;link.raw(f'event {link.sequence} confirm')
                s=wait(lambda state:state.get('phase')=='menu');link.sequence=int(s['last_event'])
                cases.append(dict(name='five_action_return_after_native_game_over',passed=True))
            need(s.get('phase')=='menu','Start at the real GTK menu');capture('01_start_page')
            s=choose_kind(10,0);need(s and s['mode']=='campaign','Explicit campaign selection')
            s=event('wake');t=next(t for t in s['targets'] if t['id']==2);link.point(t,s,.4)
            link.sequence+=1;link.raw(f'event {link.sequence} confirm')
            s=wait(lambda s:s.get('phase')!='menu' and s.get('campaign')==2,30);link.sequence=int(s['last_event'])
        need(s.get('hotseat') is False,'Single-player campaign required');result['initial']=s
        before=snapshot();start=time.monotonic();time.sleep(8);metrics('idle',before,start);capture('02_campaign_start')
        choose_kind(5);capture('03_recruitment')
        for role in range(4):
            s=choose_kind(3,role);need(s is not None,'All four native role cards available')
        cases.append(dict(name='four_native_recruitment_roles_selected',passed=True));choose_kind(3,3)
        before=snapshot();start=time.monotonic();s=event('wake');t=next(t for t in s['targets'] if t['kind']==3)
        link.point(t,s,8);metrics('steady_selection',before,start);event('cancel')
        start=time.monotonic();before=snapshot();last_turn=-1;visited={};purchases=0;attacks=0;bombards=0
        while time.monotonic()-begin<900:
            if (a.output/'stop.request').exists():break
            s=link.state();turn=s['turn']
            if s.get('game_over') or s.get('outcome',0)!=0:break
            if turn>a.turns:break
            if turn!=last_turn:
                summary=dict(turn=turn,gold=s['gold'],income=s['point_income'],army=s['army'],cities=s['cities'],enemies=s.get('known_enemies',[]),known_cities=s.get('known_cities',[]))
                result.setdefault('turns',[]).append(summary);save();print(json.dumps(dict(turn=turn,gold=s['gold'],income=s['point_income'],army=len(s['army']),enemies=len(s.get('known_enemies',[])))),flush=True)
                if turn in (3,5,8,12,18):capture('turn_'+str(turn))
                if turn>=2 and s['gold']>=90:
                    choose_kind(5)
                    # Native prices and treasury enforce affordability.
                    role=3 if sum(u['role']==3 for u in s['army'])<3 else 0
                    choose_kind(3,role);s=choose_kind(4)
                    if s is not None:purchases+=1
                    event('cancel')
                last_turn=turn
            s=link.state();order=sorted([u for u in s['army'] if u['moves']>0],key=lambda u:({2:0,3:1,0:2,1:3}.get(u['role'],4),u['id']))
            for unit in order:
                for _ in range(4):
                    state=focus(unit['id'])
                    if not state:break
                    actual=next((u for u in state['army'] if u['id']==unit['id']),None)
                    if not actual or actual['moves']<=0 or state.get('game_over'):break
                    s=event('wake');targets=[t for t in s['targets'] if t['kind'] in (0,6,7)];event('cancel')
                    sites={c['tile'] for c in s['cities']}
                    keeps=[c['tile'] for c in s.get('known_cities',[]) if c['name']=='Border Keep']
                    goal=keeps[0] if keeps else 470
                    if actual['role']==1:
                        goal=370 if 370 not in sites else (542 if 542 not in sites else 470)
                    elif actual['id']==106 and 370 not in sites:goal=370
                    elif actual['id']==111:goal=463
                    if actual['hp']<=3:goal=463
                    shots=[t for t in targets if t['kind']==6]
                    enemy_hp={e['id']:e['hp'] for e in s.get('known_enemies',[])}
                    if shots:
                        target=min(shots,key=lambda t:distance(t['tile'],goal));after=choose(target,s)
                        if after:
                            reduced=[e for e in after.get('known_enemies',[]) if e['id'] in enemy_hp and e['hp']<enemy_hp[e['id']]]
                            bombards+=1;cases.append(dict(name='native_bombard',target=target,actual_hp_reduced=bool(reduced),before=enemy_hp,after=after.get('known_enemies',[])))
                        break
                    attacks_here=[t for t in targets if t['kind']==0 and t.get('defender',-1)>=0]
                    good=[t for t in attacks_here if t['win_chance']>=.38 and actual['hp']>=5]
                    if good:
                        target=max(good,key=lambda t:t['win_chance']+(1 if distance(t['tile'],463)<3 else 0))
                        after=choose(target,s)
                        if after:attacks+=1;result.setdefault('combats',[]).append(dict(actor=actual,target=target,after_army=after['army'],after_enemies=after.get('known_enemies',[])))
                        continue
                    moves=[t for t in targets if t['kind'] in (0,7) and t.get('tile',-1)>=0 and t.get('defender',-1)<0]
                    old_distance=distance(actual['tile'],goal)
                    moves=[t for t in moves if distance(t['tile'],goal)<old_distance-.001 and (turn,actual['id'],t['tile']) not in visited]
                    if not moves:break
                    target=min(moves,key=lambda t:distance(t['tile'],goal));visited[(turn,actual['id'],target['tile'])]=True
                    after=choose(target,s)
                    if not after:break
                    new=next((u for u in after['army'] if u['id']==actual['id']),None)
                    if not new or new['tile']==actual['tile']:break
            s=link.state()
            if s.get('game_over') or s.get('outcome',0)!=0:break
            end_turn()
        if s.get('outcome')==1 and not s.get('game_over'):
            event('end')
            s=wait(lambda state:state.get('game_over'),15)
        metrics('selection_and_battle',before,start);result.update(final=s,purchases=purchases,attack_commands=attacks,bombard_commands=bombards)
        capture('04_final')
        log=(ROOT/'logs/server.log').read_text(errors='replace');(a.output/'server.log').write_text(log)
        captures=[line for line in log.splitlines() if 'CAMPAIGN_CAPTURE' in line];victories=[line for line in log.splitlines() if 'victory' in line.lower()]
        accepted=bool(s.get('game_over') and s.get('outcome')==1 and victories)
        result.update(captures=captures,victory_log=victories,passed=accepted,full_battle_accepted=accepted)
        save();(a.output/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(passed=result['passed'],turn=s['turn'],purchases=purchases,attacks=attacks,bombards=bombards,captures=captures,victory=victories)),flush=True)
    except BaseException as e:
        result.update(passed=False,error=repr(e),traceback=traceback.format_exc());save();(a.output/'result.json').write_text(json.dumps(result,indent=2));raise
    finally:link.socket.close()
if __name__=='__main__':main()
