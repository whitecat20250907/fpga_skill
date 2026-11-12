"""Two index tips: three fresh consecutive samples establish a relative baseline."""
import math

class DualZoom:
    def __init__(self):self.reset()
    def reset(self):
        self.count=0;self.baseline=None;self.ratio=1.;self.active=False;self.action_id=None;self.stamp=0
    def stop(self):self.count=0;self.baseline=None;self.active=False
    def observe(self,rows,stamp):
        points=[]
        for side in ('Left','Right'):
            hands=[h for h in rows if h.get('side')==side and h.get('in_bounds',True)]
            if len(hands)!=1:break
            h=hands[0];pts=h.get('image21',[])
            if h.get('gesture')!='Pointing_Up' or h.get('score',0)<.5 or len(pts)!=21:break
            tip=pts[8]
            if len(tip)<2 or not all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in tip[:2]):break
            points.append((tip[0]*640,tip[1]*360))
        distance=math.dist(*points) if len(points)==2 else 0
        if self.stamp and stamp-self.stamp>350_000_000:self.stop()
        if distance<4:
            ended=self.active;self.stop();self.stamp=stamp
            return 'end' if ended else None
        self.stamp=stamp
        if self.active:self.ratio=distance/self.baseline;return 'update'
        if self.count==0:self.action_id=None;self.ratio=1.
        self.count+=1
        if self.count<3:return 'prepare'
        self.baseline=distance;self.ratio=1.;self.active=True;return 'start'
    def snapshot(self):return dict(active=self.active,preparing=0<self.count<3,frames=self.count,ratio=self.ratio,action_id=self.action_id,src_ns=self.stamp)
