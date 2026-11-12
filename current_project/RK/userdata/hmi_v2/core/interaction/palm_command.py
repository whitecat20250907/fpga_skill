"""Fresh palm-to-pose command; independent of the previous confirmation hand."""
from .fist_latch import FistLatch

class PalmCommand:
    def __init__(self, config, side, pose):
        self.latch=FistLatch(config);self.side=side;self.pose=pose;self.context=None;self.clear()

    def clear(self):
        self.hand=None;self.released=False;self.seen=0;self.latch.reset()

    def observe(self, message, rows, now, context):
        if context!=self.context:self.clear();self.context=context
        candidates=[h for h in rows if h.get('side')==self.side and h.get('side_score',1)>=.45 and h.get('in_bounds',True)]
        if len(candidates)!=1:
            if now-self.seen>600_000_000:self.clear()
            self.latch.observe(dict(message,hands=[]),now,confirming=True)
            return False
        h=candidates[0]
        if h['track_id']!=self.hand:self.clear();self.hand=h['track_id']
        self.seen=now;name=h.get('gesture')
        threshold=self.latch.config.get('confidence_by_gesture',{}).get(name,self.latch.config['confidence'])
        if h.get('score',0)>=threshold:
            if name=='Open_Palm':self.released=True
            elif name not in (self.pose,None,'None'):self.released=False
        commits=self.latch.observe(dict(message,hands=[h] if self.released else []),now,confirming=True)
        if any(name==self.pose for _,_,name in commits):
            self.released=False;return True
        return False
