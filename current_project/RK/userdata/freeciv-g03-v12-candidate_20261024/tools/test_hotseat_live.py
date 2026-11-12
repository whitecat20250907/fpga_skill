"""Real start-page and two-native-human handover test, using semantic UDP."""
import argparse,json,time
from pathlib import Path
from test_live_input import Link,need
from test_campaign_live import screenshot

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--resume-native',action='store_true');args=ap.parse_args()
    need(not args.output.exists(),'Keep prior actual results');args.output.mkdir()
    link=Link();events=[];cases=[];result=dict(test='ACTUAL_RK_START_MENU_TWO_HUMAN_TURNS',human_gaze_accepted=False,
        full_battle_accepted=False,cases=cases,events=events)
    def wait(predicate,seconds=20):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            try:s=link.state(timeout=.7)
            except RuntimeError:continue
            if predicate(s):return s
            time.sleep(.04)
        raise RuntimeError('Actual native state transition timed out')
    def event(name):
        link.sequence+=1;link.raw(f'event {link.sequence} {name}')
        s=wait(lambda s:int(s['last_event'])==link.sequence)
        events.append(dict(event=name,state=s));return s
    def choose(kind,identifier=None):
        s=event('wake');targets=[t for t in s['targets'] if t['kind']==kind and (identifier is None or t['id']==identifier)]
        need(targets,f'Missing actual semantic target {kind}/{identifier}')
        link.point(targets[0],s,seconds=.4);return event('confirm')
    def handover(player):
        s=wait(lambda s:s.get('handoff')==player)
        need(not s['awake'],'Handover must start asleep')
        event('confirm');need(link.state()['player']!=player,'Asleep confirmation must not transfer ownership')
        choose(8,player)
        s=wait(lambda s:s.get('player')==player and s.get('handoff')==-1)
        need(not s['awake'],'New native owner must start asleep');return s
    try:
        s=link.state();link.sequence=int(s['last_event'])
        if not args.resume_native:
            need(s['phase']=='menu','Start page must appear before gameplay')
            screenshot(args.output/'start_page.png')
            link.raw('gaze .5 .5');event('confirm');need(link.state()['phase']=='menu','Gaze must not start game')
            s=choose(10,1);need(s['mode']=='hotseat' and not s['awake'],'Mode choice must sleep without starting')
            screenshot(args.output/'hotseat_selected.png')
            s=event('wake');t=next(t for t in s['targets'] if t['id']==2);link.point(t,s,seconds=.4)
            link.sequence+=1;link.raw(f'event {link.sequence} confirm')
            s=wait(lambda s:s.get('phase')!='menu' and s.get('hotseat') is True,seconds=30)
            cases.append(dict(name='explicit_start_page_selection_launches_native_hotseat',passed=True))
        link.sequence=int(s['last_event']);result['native_initial']=s
        need(s['player']==0 and s['phase']==0 and len(s['cities'])==2 and len(s['army'])==6,'First human scenario must have symmetric army and base/outpost')
        screenshot(args.output/'player1_turn1.png')
        event('end');s=handover(1);result['player2_initial']=s
        need(len(s['cities'])==2 and len(s['army'])==6,'Second native human must own its actual cities and army')
        screenshot(args.output/'player2_turn1.png')
        s=event('wake');target=next((t for t in s['targets'] if t['kind']==7),None)
        need(target,'Second player must have native multi-step reachable targets')
        uid=s['unit'];before=next(u for u in s['army'] if u['id']==uid)
        link.point(target,s,seconds=.4);event('confirm')
        s=wait(lambda s:any(u['id']==uid and u['tile']==target['arg'] for u in s['army']))
        need(not s['awake'],'Movement must sleep after native route')
        cases.append(dict(name='second_human_controls_own_native_unit',passed=True,before=before,
            after=next(u for u in s['army'] if u['id']==uid)))
        event('end');s=handover(0);need(s['turn']==2,'Both human phases must complete before next round')
        cases.append(dict(name='two_deliberate_handoffs_and_native_round2',passed=True))
        screenshot(args.output/'player1_round2.png');result.update(passed=True,final=s)
    except BaseException as error:result.update(passed=False,error=repr(error));raise
    finally:
        link.socket.close();(args.output/'result.json').write_text(json.dumps(result,indent=2))
        print(json.dumps({k:v for k,v in result.items() if k not in ('events','native_initial','player2_initial','final')}),flush=True)
if __name__=='__main__':main()
