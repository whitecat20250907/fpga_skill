from dataclasses import dataclass
from core.clock import fresh

GESTURES = {'Pointing_Up':'wake','Closed_Fist':'confirm','Thumb_Down':'cancel',
            'Victory':'next','Thumb_Up':'end','Open_Palm':'sleep','ILoveYou':'menu'}

@dataclass
class Hand:
    armed:bool=False
    neutral:int=0
    name:str=''
    start:int=0
    frames:int=0

class Latch:
    def __init__(self, config, max_age_ms=350):
        self.config=config;self.hands={};self.stamp=0;self.seq=-1;self.epoch=None
        self.max_age_ms=max_age_ms
        self.absent_since=0;self.progress={};self.conflict=False
    def reset(self):
        self.hands.clear();self.absent_since=0;self.progress={}
    def observe(self, message, now, layer='POINT', calibrating=False):
        self.progress={};self.conflict=False
        stamp=message.get('src_ns');seq=message.get('seq');epoch=message.get('epoch')
        if epoch!=self.epoch:self.reset();self.stamp=0;self.seq=-1;self.epoch=epoch
        if not fresh(stamp,self.max_age_ms,now) or type(seq) is not int or seq<=self.seq or stamp<=self.stamp:
            self.reset();return []
        if self.stamp and stamp-self.stamp>self.max_age_ms*1_000_000:self.reset()
        self.stamp=stamp;self.seq=seq
        rows=message.get('hands',[])
        if not isinstance(rows,list) or len(rows)>4:self.reset();return []
        keys=[r.get('track_id') for r in rows]
        if any(type(k) is not int or k<0 for k in keys) or len(set(keys))!=len(keys):self.reset();return []
        if not rows:
            self.absent_since=self.absent_since or stamp
            self.hands.clear();return []
        absent_armed=bool(self.absent_since and stamp-self.absent_since>=self.config['release_s']*1e9)
        self.absent_since=0
        self.hands={k:v for k,v in self.hands.items() if k in keys}
        commits=[]
        for row in rows:
            key=row['track_id'];h=self.hands.setdefault(key,Hand(armed=absent_armed))
            name=row.get('gesture');score=row.get('score',0)
            if type(score) not in (float,int) or not 0<=score<=1 or score<self.config['confidence'] or not row.get('in_bounds',True):
                h.name='';h.start=h.frames=h.neutral=0;h.armed=False;continue
            if name in (None,'None'):
                h.name='';h.start=h.frames=0;h.neutral=h.neutral or stamp
                if stamp-h.neutral>=self.config['release_s']*1e9:h.armed=True
                continue
            h.neutral=0
            if layer=='WRITE' and name not in ('ILoveYou','Open_Palm'):
                h.name='';h.frames=h.start=0;continue
            if name not in GESTURES or not h.armed:continue
            if name!=h.name:h.name=name;h.start=stamp;h.frames=0
            h.frames+=1
            hold=1. if name=='Open_Palm' and (layer=='WRITE' or calibrating) else self.config['hold_s'][name]
            progress=min(1.,(stamp-h.start)/(hold*1e9))
            self.progress[key]={'hand':key,'name':name,'progress':progress,'committed':None}
            if progress>=1 and h.frames>=self.config['min_frames']:commits.append((key,GESTURES[name],name))
        # Resolve conflict BEFORE any hand commits, including commits in this tick.
        active={p['name'] for p in self.progress.values() if p['progress']>0.5}
        if len(active)>1:
            self.reset();self.conflict=True;return []
        for key,_,_ in commits:self.hands[key].armed=False
        # Two hands making the same gesture still produce only one action.
        return commits[:1]
