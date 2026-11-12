"""Five-action policy for the optional, user-authorized MediaPipe module.

This policy never supplies gaze coordinates. The native game remains the
authority for dynamic targets, fresh gaze, command execution and sleep.
"""
import math

MAPPING = {'Pointing_Up':'wake', 'Closed_Fist':'confirm', 'Thumb_Down':'cancel',
           'Victory':'next', 'Thumb_Up':'end'}
HOLD_SECONDS = {'wake':.4, 'confirm':.6, 'cancel':.4, 'next':.4, 'end':.8}

class GestureLatch:
    def __init__(self, confidence=.7, release_seconds=.3, max_age=.35):
        self.confidence=confidence; self.release_seconds=release_seconds; self.max_age=max_age
        self.armed=False; self.neutral_since=None; self.candidate=None; self.since=None;self.samples=0
        self.last_stamp=-math.inf

    def observe(self, name, score, has_hand, stamp, now):
        """Require fresh advancing source frames, hold, then deliberate release.

        A direct gesture change never rearms. A fresh no-hand or confident
        unrecognised pose sustained for .3s rearms; low-confidence jitter does
        not. Stale/missing frames clear a partial hold and cannot rearm.
        """
        if (not all(math.isfinite(x) for x in (score,stamp,now)) or
            not 0<=score<=1 or not 0<=now-stamp<=self.max_age or stamp<=self.last_stamp):
            self.candidate=None; self.since=None; self.neutral_since=None
            return None
        gap=stamp-self.last_stamp
        self.last_stamp=stamp
        if gap>.75:
            self.candidate=None;self.since=None;self.neutral_since=None
        neutral=not has_hand or (name in ('None',None) and score>=self.confidence)
        if neutral:
            self.candidate=None;self.since=None
            if self.neutral_since is None:self.neutral_since=stamp
            if stamp-self.neutral_since>=self.release_seconds:self.armed=True
            return None
        self.neutral_since=None
        action=MAPPING.get(name) if score>=self.confidence else None
        if not self.armed or action is None:
            self.candidate=None;self.since=None;return None
        if action!=self.candidate:
            self.candidate=action;self.since=stamp;self.samples=0
        self.samples+=1
        if self.samples>=3 and stamp-self.since+1e-9>=HOLD_SECONDS[action]:
            self.armed=False;self.candidate=None;self.since=None
            return action
        return None

def action_allowed(action,state):
    """Do not toggle an already awake game or confirm while it is asleep."""
    if not isinstance(state,dict) or type(state.get('awake')) is not bool:return False
    if action=='wake':return not state['awake']
    if action=='confirm':return state['awake']
    return action in ('cancel','next','end')

def send_game_action(link,action):
    """Synchronize with the game's global event sequence before sending.

    Other optional input producers can have sent events since this process
    started. A UDP send is not an acknowledgement of command execution.
    """
    state=link.update()
    if not action_allowed(action,state):return False
    try:
        last=state['last_event']
        if isinstance(last,str) and last.isascii() and last.isdigit():last=int(last)
        if type(last)!=int or not 0<=last<2**64-1:return False
    except (KeyError,ValueError):return False
    link.sequence=max(link.sequence,last)
    return link.action(action)
