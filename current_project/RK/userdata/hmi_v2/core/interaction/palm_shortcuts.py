"""A palm prepares exactly one repeat/undo edge; no action is tied to track lifetime."""
from .fist_latch import FistLatch

class PalmShortcuts:
    def __init__(self, config, side):
        self.side=side;self.latch=FistLatch(config);self.clear()
    def clear(self):
        self.hand=None;self.prepared=False;self.consumed=False;self.seen=0;self.latch.reset()
    @property
    def owns(self):return self.prepared or self.consumed
    def observe(self,message,rows,now):
        candidates=[h for h in rows if h.get('side')==self.side and h.get('in_bounds',True) and h.get('side_score',1)>=.45]
        if len(candidates)!=1:
            if now-self.seen>450_000_000:self.clear()
            self.latch.observe(dict(message,hands=[]),now,confirming=True);return None
        h=candidates[0];self.seen=now
        # One unambiguous same-side hand can continue through a tracker ID change.
        if h['track_id']!=self.hand:self.latch.reset();self.hand=h['track_id']
        name=h.get('gesture');score=h.get('score',0)
        threshold=self.latch.config.get('confidence_by_gesture',{}).get(name,self.latch.config['confidence'])
        if score>=threshold:
            if name=='Open_Palm':self.prepared=True;self.consumed=False
            elif name not in ('Closed_Fist','Thumb_Down',None,'None'):
                self.prepared=False;self.consumed=False
        commits=self.latch.observe(dict(message,hands=[h] if self.prepared else []),now,confirming=True)
        for _,event,name in commits:
            if event in ('confirm','cancel'):
                self.prepared=False;self.consumed=True
                return 'repeat' if name=='Closed_Fist' else 'undo'
        return None
