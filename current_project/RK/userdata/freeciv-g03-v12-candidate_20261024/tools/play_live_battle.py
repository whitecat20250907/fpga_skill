"""Manual UDP battle acceptance sequence on the real fixed-map game.

Run after test_live_input.py (cavalry advanced once). Uses actual semantic
candidate centers, never a screen grid. Leaves capture outcome for visual
and server-log verification; this script alone cannot certify victory.
"""
import argparse
import json
from pathlib import Path
import time
from test_live_input import Link,need


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--front-unit',type=int,required=True)
    ap.add_argument('--pause',type=float,default=1.)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    if a.output.exists() or not 0<=a.pause<=2:ap.error('Fresh output and pause in [0,2] required')
    link=Link();events=[];begin=time.monotonic()
    result=dict(test='REAL_GAME_UDP_BATTLE_SEQUENCE',human_gaze_test=False,events=events)
    def event(name):
        state=link.event(name)
        events.append(dict(seconds=time.monotonic()-begin,action=name,state=state))
        time.sleep(a.pause)
        return link.state()
    def choose(kind,identifier=None,arg=None,east=False):
        state=event('wake')
        targets=[t for t in state['targets'] if t['kind']==kind and
                 (identifier is None or t['id']==identifier) and (arg is None or t['arg']==arg)]
        need(targets,f'No actual semantic candidate kind={kind}, id={identifier}, arg={arg}')
        target=max(targets,key=lambda t:t['x']) if east else min(targets,key=lambda t:t['x'])
        link.point(target,state)
        result=event('confirm')
        need(not result['awake'],'Confirmation did not complete and sleep')
        return result
    def focus():
        if link.state()['unit']!=a.front_unit:choose(1,identifier=a.front_unit)
        need(link.state()['unit']==a.front_unit,'Wrong frontal unit')
    def end_turn():
        before=link.state()['turn'];state=event('end')
        deadline=time.monotonic()+2
        while state['turn']==before and time.monotonic()<deadline:
            time.sleep(.05);state=link.state()
        need(state['turn']==before+1,'Turn did not advance exactly once')
        return state
    try:
        initial=link.state();result['initial']=initial
        need(initial['turn']==1 and initial['moves']==3 and not initial['awake'],
             'Expected post-input-test cavalry on turn 1')
        link.sequence=int(initial['last_event'])
        choose(0,east=True)                 # Attack the external guard.
        choose(2)                           # Westwatch production management.
        choose(3,arg=0)                     # Actual Legion production order.
        focus();choose(0,east=True)         # Legion moves toward the castle.
        end_turn()
        choose(2)
        before=link.state()['gold']
        after=choose(4)['gold']             # Actual rule-checked treasury buy.
        need(after<before,'Purchase did not deduct treasury gold')
        result['purchase']=dict(before=before,after=after,spent=before-after)
        focus();choose(0,east=True)
        end_turn()
        focus();choose(0,east=True)         # Actual castle guard combat.
        end_turn()
        focus();choose(0,east=True)         # Attempt capture; verify visually.
        result.update(sequence_executed=True,final=link.state(),
                      victory_verified_by_this_script=False,
                      required_next='Capture unmodified desktop, then settle and verify real server victory log')
    except BaseException as error:
        result.update(sequence_executed=False,error=repr(error));raise
    finally:
        link.socket.close();a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(json.dumps(dict(sequence_executed=result.get('sequence_executed',False),
                             event_count=len(events),elapsed=time.monotonic()-begin,
                             error=result.get('error')),ensure_ascii=False))


if __name__=='__main__':main()
