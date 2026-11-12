"""Replay classified labels through the hand policy into the real native game.

This changes the current demo turn and moves one unit. Labels/timestamps and
gaze are software test inputs, NOT live model or human-control acceptance.
"""
import argparse
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gesture_control import GestureLatch,send_game_action
from screen_bridge import FreecivScreenInput

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists():ap.error('Preserve previous evidence')
    link=FreecivScreenInput();latch=GestureLatch();events=[]
    result=dict(source='SOFTWARE_CLASSIFIED_LABEL_AND_GAZE_REPLAY_INTO_REAL_GAME',human_test=False,
                inference_started=False,camera_started=False,events=events)
    def state(predicate=lambda _:True):
        limit=time.monotonic()+2
        while time.monotonic()<limit:
            value=link.update()
            if value is not None and predicate(value):return value
            time.sleep(.01)
        raise RuntimeError('Actual game state acknowledgement timeout')
    def samples(name,seconds,score=1.,hand=True,target=None):
        found=[];limit=time.monotonic()+seconds
        while time.monotonic()<limit:
            link.update() # Pump the existing nonblocking transport as the real worker does.
            if target:
                value=state()
                link.gaze(target['x']/value['map'][2],target['y']/value['map'][3])
            stamp=time.monotonic()
            action=latch.observe(name,score,hand,stamp,stamp)
            if action:found.append(action)
            time.sleep(.05)
        return found
    def release():
        assert samples(None,.4,1.,False)==[]
    def action(label,expected,target=None):
        release()
        actions=samples(label,1.1,.99,True,target)
        if actions!=[expected]:raise RuntimeError('Held action did not fire exactly once: '+str(actions))
        if target:
            picked=state(lambda s:s['pick']>=0 and s['targets'][s['pick']]['kind']==0)
            result['pre_confirm_target']=picked['targets'][picked['pick']]
        if not send_game_action(link,expected):raise RuntimeError('Transport refused expected action')
        sequence=link.sequence
        current=state(lambda s:int(s['last_event'])==sequence)
        if samples(label,.3,.99,True,target):raise RuntimeError('Held action repeated')
        events.append(dict(label=label,action=expected,sequence=sequence,acknowledged=True,
                           awake=current['awake'],unit=current['unit'],moves=current['moves'],turn=current['turn']))
        return current
    try:
        initial=state();result['initial']=initial
        if initial['awake']:raise RuntimeError('Start with the actual game asleep')
        release()
        if samples('Open_Palm',1.,.60):raise RuntimeError('Below-threshold real fixture score was accepted')
        unchanged=state()
        if unchanged['last_event']!=initial['last_event']:raise RuntimeError('Low-confidence sample sent an action')
        awake=action('Pointing_Up','wake')
        if not awake['awake']:raise RuntimeError('Native game did not wake')
        targets=[t for t in awake['targets'] if t['kind']==0]
        target=max(targets,key=lambda t:t['x'])
        action('Closed_Fist','confirm',target)
        # The UDP sequence acknowledges client dispatch; the real server's
        # movement/turn update is asynchronous and must be observed separately.
        moved=state(lambda s:not s['awake'] and (s['unit']!=awake['unit'] or s['moves']<awake['moves']))
        result['movement_effect']=moved
        action('Victory','next')
        next_unit=state(lambda s:s['unit']!=moved['unit'])
        result['next_effect']=next_unit
        action('Thumb_Up','end')
        ended=state(lambda s:s['turn']>next_unit['turn'])
        result['end_effect']=ended
        action('Pointing_Up','wake')
        cancelled=action('Thumb_Down','cancel')
        if cancelled['awake']:raise RuntimeError('Native cancel did not sleep')
        result.update(status='PASS_FIVE_ACTION_POLICY_TO_REAL_NATIVE_GAME_SOFTWARE_REPLAY_ONLY',
                      low_confidence_refusal=True,final=cancelled)
    except BaseException as error:
        result.update(status='FAILED_PRESERVED',error=repr(error));raise
    finally:
        link.close();args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(status=result['status'],actions=len(events))))

if __name__=='__main__':main()
