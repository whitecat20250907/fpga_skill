"""A successful action belongs to its confirmation hand until that hand leaves."""
from copy import deepcopy
from .fist_latch import FistLatch
from core.clock import fresh


class RepeatCycle:
    def __init__(self, config):
        self.latch=FistLatch(config);self.clear()

    def clear(self):
        self.session=None;self.latch.reset()

    def begin(self,action,hand,side,context,now):
        self.clear()
        self.session=dict(action=deepcopy(action),hand=hand,side=side,context=context,
                          last_seen=now,released=False,ready=False,progress=0.,pending_id=action['id'],undone=False)

    def acknowledge(self,identity,ok,undo=False):
        s=self.session
        if not s or s.get('pending_id')!=identity:return
        s['pending_id']=None;s['ready']=bool(ok)
        if undo and ok:s['undone']=True
        if not ok:self.clear()

    def observe(self,message,rows,now,context):
        s=self.session
        if not s:return None
        if s['context']!=context or not fresh(message.get('src_ns'),350,now):self.clear();return None
        hand=next((h for h in rows if h.get('track_id')==s['hand'] and h.get('in_bounds',True)),None)
        if hand is None:
            self.latch.observe(dict(message,hands=[]),now,confirming=True)
            if now-s['last_seen']>600_000_000:self.clear()
            return None
        s['last_seen']=now
        # Observe the palm immediately; no second open pose or extra hold is required.
        if hand.get('gesture')=='Open_Palm' and hand.get('score',0)>=.5:
            s['released']=True
        commits=self.latch.observe(dict(message,hands=[hand] if s['released'] else []),now,confirming=True)
        s['progress']=max((p['progress'] for p in self.latch.progress.values()),default=0.)
        if not s['ready'] or s.get('pending_id'):return None
        for _,event,_ in commits:
            if event in ('confirm','cancel'):
                s['released']=False;s['progress']=0.
                return 'repeat' if event=='confirm' else 'undo'
        return None

    def snapshot(self):
        s=self.session
        if not s:return None
        return {k:s[k] for k in ('hand','side','released','ready','progress','undone')} | {'action':s['action']['name'],'pending':bool(s.get('pending_id'))}
