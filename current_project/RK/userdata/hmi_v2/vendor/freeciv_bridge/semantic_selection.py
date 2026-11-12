"""Time-weighted selection of current semantic targets, never screen grid cells.

Confidence measures temporal target support, not model accuracy. Coordinates
are already smoothed by the model; only legacy mouse samples get a 45ms EMA.
The matching native implementation is demo_selection.h, exercised by parity tests.
"""
import math

class Selection:
    def __init__(self):
        self.targets=[];self.reset()
    def reset(self):
        self.scores=[0.]*len(self.targets);self.mass=0.;self.stamp=None
        self.pick=-1;self.hover=-1;self.candidate=-1;self.since=0.;self.count=0
        self.confidence=self.margin=0.;self.ready=False;self.x=self.y=0.
    @staticmethod
    def key(t):return (t.get('kind',0),t['id'],t.get('arg',0))
    def sync(self,targets):
        old={self.key(t):i for i,t in enumerate(self.targets)}
        changed=len(targets)!=len(old) or any(self.key(t) not in old or
            abs(t['x']-self.targets[old[self.key(t)]]['x'])>2 or
            abs(t['y']-self.targets[old[self.key(t)]]['y'])>2 for t in targets)
        if changed:self.targets=[dict(t) for t in targets];self.reset();return
        scores=[self.scores[old[self.key(t)]] for t in targets]
        def remap(index):
            if index<0:return -1
            key=self.key(self.targets[index])
            return next(i for i,t in enumerate(targets) if self.key(t)==key)
        self.pick,self.candidate,self.hover=remap(self.pick),remap(self.candidate),remap(self.hover)
        self.targets=[dict(t) for t in targets];self.scores=scores
    def sample(self,x,y,targets,stamp,now,filtered=True):
        self.sync(targets)
        if not all(math.isfinite(v) for v in (x,y,stamp,now)) or not 0<=now-stamp<=.25:
            self.reset();return
        if self.stamp is not None and stamp<=self.stamp:return
        if self.stamp is not None and stamp-self.stamp>.25:self.reset()
        dt=0. if self.stamp is None else stamp-self.stamp
        if self.stamp is None or filtered:self.x,self.y=x,y
        else:
            a=-math.expm1(-dt/.045);self.x+=a*(x-self.x);self.y+=a*(y-self.y)
        self.stamp=stamp;self.ready=False
        distances=sorted(((t['x']-self.x)**2+(t['y']-self.y)**2,i) for i,t in enumerate(self.targets))
        if not distances:self.reset();return
        best,winner=distances[0];second=distances[1][0] if len(distances)>1 else 1e30
        spatial=(second-best)/(second+1.)
        target=self.targets[winner]
        spacing=min((math.hypot(t['x']-target['x'],t['y']-target['y']) for i,t in enumerate(self.targets) if i!=winner),default=200.)
        radius=max(36.,min(180.,spacing*.9))
        usable=spatial>=.08 and best<=radius*radius
        self.hover=winner if usable else -1
        # Give the first observation a bounded prior weight. It is still just
        # one source frame: duration and three-frame confirmation gates remain.
        decay=math.exp(-dt/.18);weight=-math.expm1(-(dt if dt else 1/30)/.18)
        self.scores=[v*decay for v in self.scores];self.mass=self.mass*decay+weight
        if usable:self.scores[winner]+=weight
        self.confidence=self.scores[winner]/self.mass if self.mass>0 else 0.
        runner=max((v for i,v in enumerate(self.scores) if i!=winner),default=0.)
        self.margin=(self.scores[winner]-runner)/self.mass if self.mass>0 else 0.
        eligible=usable and self.confidence>=.60 and self.margin>=.12
        if not eligible:self.candidate=-1;self.count=0;return
        if self.candidate!=winner:self.candidate=winner;self.since=stamp;self.count=1
        else:self.count+=1
        if self.count>=3 and stamp-self.since>=.12-1e-9:
            self.pick=winner;self.ready=True
    def confirmable(self,now):
        return self.ready and self.pick>=0 and self.stamp is not None and 0<=now-self.stamp<=.25
    def preview(self,now):
        return self.hover if self.stamp is not None and 0<=now-self.stamp<=.25 else -1
