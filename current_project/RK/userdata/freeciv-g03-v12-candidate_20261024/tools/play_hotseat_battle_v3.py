"""Bounded two-native-human battle through semantic centers/five UDP actions.

The second scripted seat counter-raids with cavalry and defends its base.
These are software inputs, not two tested human gaze/calibration profiles.
"""
import argparse,json,os,time
from pathlib import Path
from run_on_desktop import environment
from test_live_input import Link,need
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--rounds',type=int,default=24);a=ap.parse_args()
    a.output.mkdir(exist_ok=False);env,_=environment(1721);os.environ.update(env)
    link=Link();begin=time.monotonic();events=[];cases=[];report=dict(test='ACTUAL_TWO_NATIVE_HUMAN_BATTLE_V3',human_gaze_accepted=False,cases=cases,events=events)
    def save():(a.output/'progress.json').write_text(json.dumps(report,indent=2))
    def shot(name):
        import gi;gi.require_version('Gdk','3.0');from gi.repository import Gdk
        w=Gdk.get_default_root_window();Gdk.pixbuf_get_from_window(w,0,0,w.get_width(),w.get_height()).savev(str(a.output/(name+'.png')),'png',[],[])
    def wait(predicate,seconds=25):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            try:s=link.state(.8)
            except RuntimeError:continue
            if predicate(s):return s
            time.sleep(.04)
        raise RuntimeError('Two-seat native state transition timed out')
    def event(name):
        s=link.event(name);events.append(dict(t=round(time.monotonic()-begin,3),action=name,player=s.get('player'),turn=s['turn'],unit=s['unit']));return s
    def wake():
        s=link.state()
        if s['awake']:event('cancel')
        return event('wake')
    def choose(target):
        s=wake();target=next((t for t in s['targets'] if (t['kind'],t['id'],t['arg'])==(target['kind'],target['id'],target['arg'])),None)
        if target is None:event('cancel');return None
        link.point(target,s,.4);after=event('confirm');need(not after['awake'],'Confirmation must sleep');time.sleep(.12);return link.state()
    def kind(k,arg=None,identifier=None):
        s=wake();t=next((t for t in s['targets'] if t['kind']==k and (arg is None or t['arg']==arg) and (identifier is None or t['id']==identifier)),None)
        if t is None:event('cancel');return None
        # Confirm in the already-awake context: Escape would close an open
        # recruitment panel before its production/buy target can execute.
        link.point(t,s,.4);after=event('confirm');need(not after['awake'],'Confirmation must sleep');time.sleep(.12);return link.state()
    def focus(uid):
        s=link.state()
        if s['unit']==uid:return s
        if kind(1,identifier=uid):
            s=link.state()
            if s['unit']==uid:return s
        seen=set()
        for _ in range(12):
            s=link.state()
            if s['unit']==uid:return s
            if s['unit'] in seen:return None
            seen.add(s['unit']);event('next')
        return None
    def distance(tile,goal):return max(abs(tile%24-goal%24),abs(tile//24-goal//24))+.04*(abs(tile%24-goal%24)+abs(tile//24-goal//24))
    try:
        s=link.state();link.sequence=int(s['last_event'])
        if s.get('phase')!='menu':
            need(s.get('outcome',0)!=0 or s.get('game_over'),'Only finish an actual completed game')
            s=wake();t=next(t for t in s['targets'] if t['kind']==9);link.point(t,s,.4);link.sequence+=1;link.raw(f'event {link.sequence} confirm')
            s=wait(lambda s:s.get('phase')=='menu');link.sequence=int(s['last_event']);cases.append(dict(name='five_action_return_to_start_page_after_outcome',passed=True))
        shot('01_start_page');s=kind(10,arg=1);need(s['mode']=='hotseat','Explicit hotseat choice');shot('02_hotseat_selected')
        s=wake();t=next(t for t in s['targets'] if t['id']==2);link.point(t,s,.4);link.sequence+=1;link.raw(f'event {link.sequence} confirm')
        s=wait(lambda s:s.get('hotseat') is True and s.get('phase')!='menu');link.sequence=int(s['last_event']);report['initial']=s
        need(s['player']==0 and len(s['army'])==7 and len(s['cities'])==2,'Actual first native human army/base required');shot('03_player1')
        guards={0:next(u['id'] for u in s['army'] if u['role']==0 and u['tile']==463)};last=None;rounds=[];combats=[];handoffs=0
        while time.monotonic()-begin<900:
            s=link.state()
            if s.get('outcome',0)!=0 or s.get('game_over') or s['turn']>a.rounds:break
            if (a.output/'stop.request').exists():break
            key=(s['turn'],s['player']);player=s['player'];home=463 if player==0 else 473;enemy=473 if player==0 else 463
            if key!=last:
                rounds.append(dict(turn=s['turn'],player=player,army=s['army'],cities=s['cities'],gold=s['gold'],known_cities=s.get('known_cities',[])));report.update(phases=rounds,handoffs=handoffs,combats=combats);save()
                print(json.dumps(dict(turn=s['turn'],player=player,army=len(s['army']),gold=s['gold'])),flush=True)
                if player==1 and 1 not in guards:
                    need(len(s['army'])==7 and len(s['cities'])==2,'Actual second native human army/base required');shot('04_player2')
                    guards[1]=next(u['id'] for u in s['army'] if u['role']==0 and u['tile']==473)
                    cases.append(dict(name='two_distinct_native_human_armies_and_treasuries',passed=True))
                if s['turn']>=2 and s['gold']>=120 and ((player==0 and s['turn']<7) or (player==1 and s['turn']==2)):
                    kind(5);kind(3,arg=3 if player==0 else 0);kind(4);event('cancel')
                last=key
            s=link.state();units=sorted((u for u in s['army'] if u['moves']>0),key=lambda u:({2:0,0:1,3:2,1:3}.get(u['role'],4),u['id']))
            for unit in units:
                if unit['id']==guards.get(player):continue
                # The demonstrator's second seat is a counter-raid/one-base
                # defense, not another AI benchmark or a hidden rule change.
                if player==1 and unit['role']!=1:continue
                for step in range(3):
                    state=focus(unit['id'])
                    if not state or state.get('outcome',0)!=0:break
                    actual=next((u for u in state['army'] if u['id']==unit['id']),None)
                    if not actual or actual['moves']<=0:break
                    s=wake();targets=[t for t in s['targets'] if t['kind'] in (0,6,7)];event('cancel')
                    shots=[t for t in targets if t['kind']==6]
                    fights=[t for t in targets if t['kind']==0 and t.get('defender',-1)>=0 and t['win_chance']>=.35]
                    if shots:target=min(shots,key=lambda t:distance(t['tile'],enemy));combats.append(dict(kind='native_bombard',player=player,actor=actual,target=target))
                    elif fights:target=max(fights,key=lambda t:t['win_chance']);combats.append(dict(kind='native_attack',player=player,actor=actual,target=target))
                    else:
                        moves=[t for t in targets if t.get('tile',-1)>=0 and t.get('defender',-1)<0 and distance(t['tile'],enemy)<distance(actual['tile'],enemy)-.001]
                        if not moves:break
                        target=min(moves,key=lambda t:distance(t['tile'],enemy))
                    after=choose(target)
                    if after and shots:
                        actor_after=next((u for u in after['army'] if u['id']==actual['id']),None)
                        combats[-1].update(after_actor=actor_after,after_enemies=after.get('known_enemies',[]))
                    if not after:break
                    if after.get('outcome',0)!=0 or after.get('game_over'):break
                    current=next((u for u in after['army'] if u['id']==unit['id']),None)
                    if not current or (current['tile']==actual['tile'] and current['moves']==actual['moves']):break
            s=link.state()
            if s.get('outcome',0)!=0 or s.get('game_over'):break
            previous=s['player'];event('end');s=wait(lambda s:s.get('handoff',-1)>=0 or s.get('game_over') or s.get('outcome',0)!=0)
            if s.get('outcome',0)!=0 or s.get('game_over'):break
            destination=s['handoff'];need(not s['awake'],'Handoff starts asleep')
            event('confirm');need(link.state()['player']==previous,'Asleep confirm must not transfer the human seat')
            if handoffs<2:shot('handoff_'+str(handoffs+1))
            kind(8,identifier=destination);s=wait(lambda s:s.get('player')==destination and s.get('handoff')==-1)
            need(not s['awake'],'New seat starts asleep');handoffs+=1
        s=link.state()
        if s.get('outcome',0)!=0 and not s.get('game_over'):
            event('end');s=wait(lambda s:s.get('game_over'),15)
            cases.append(dict(name='fifth_action_finishes_native_scenario_settlement',passed=True))
        shot('05_final');log=(ROOT/'logs/server.log').read_text();(a.output/'server.log').write_text(log)
        victory=[line for line in log.splitlines() if 'Scenario victory' in line];capture=[line for line in log.splitlines() if 'CAMPAIGN_CAPTURE' in line]
        need(handoffs>=2 and combats,'Actual two-seat handoff and native combat required')
        report.update(passed=bool(s.get('game_over') and victory),native_full_battle_accepted=bool(s.get('game_over') and victory),final=s,
            handoffs=handoffs,combats=combats,phases=rounds,victory_log=victory,capture_log=capture)
        (a.output/'result.json').write_text(json.dumps(report,indent=2));save();print(json.dumps(dict(passed=report['passed'],turn=s['turn'],handoffs=handoffs,combats=len(combats),victory=victory)),flush=True)
    except BaseException as e:
        report.update(passed=False,error=repr(e));(a.output/'result.json').write_text(json.dumps(report,indent=2));save();raise
    finally:link.socket.close()
if __name__=='__main__':main()
