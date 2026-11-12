"""One deliberate fist arms one gesture; pointing belongs to the stroke recorder."""
from dataclasses import dataclass
from core.clock import fresh
from .latch import GESTURES


@dataclass
class Hand:
    name: str = ''
    since: int = 0
    count: int = 0
    armed_until: int = 0
    consumed: bool = False
    last_seen: int = 0
    elapsed_ns: int = 0
    continuous: bool = False


class FistLatch:
    def __init__(self, config, max_age_ms=350):
        self.config=config;self.max_age_ms=max_age_ms
        self.epoch=None;self.seq=-1;self.stamp=0;self.reset()

    def reset(self):
        self.hands={};self.progress={};self.conflict=False

    def arm_confirmed(self,key,stamp):
        # The deliberate closing fist can also prepare the next pose. Holding
        # it emits nothing; a later static pose still needs its own confirmation.
        self.hands[key]=Hand(name='Closed_Fist',since=stamp,last_seen=stamp,
                            consumed=True,armed_until=stamp+int(self.config.get('armed_s',4.)*1e9))

    def observe(self, message, now, layer='POINT', calibrating=False, confirming=False, locking=False):
        stamp=message.get('src_ns');seq=message.get('seq')
        if message.get('epoch')!=self.epoch:
            self.reset();self.epoch=message.get('epoch');self.seq=-1;self.stamp=0
        if not fresh(stamp,self.max_age_ms,now) or type(seq) is not int:
            self.reset();return []
        if seq<=self.seq or stamp<=self.stamp:return []
        if self.stamp and stamp-self.stamp>self.max_age_ms*1_000_000:self.reset()
        self.seq=seq;self.stamp=stamp;self.progress={};self.conflict=False
        rows=message.get('hands',[]);ids=[r.get('track_id') for r in rows]
        if len(rows)>4 or any(type(k) is not int for k in ids) or len(set(ids))!=len(ids):
            self.reset();return []
        gap_ns=int(self.config.get('pose_gap_s',.45)*1e9)
        self.hands={k:v for k,v in self.hands.items() if k in ids or stamp-v.last_seen<=gap_ns};commits=[]
        prior_armed={k:h.armed_until for k,h in self.hands.items()}
        for key,h in self.hands.items():
            if key not in ids:h.continuous=False
        for row in rows:
            key=row['track_id'];h=self.hands.setdefault(key,Hand())
            name=row.get('gesture');score=row.get('score',0)
            if not row.get('in_bounds',True) or type(score) not in (int,float) or not 0<=score<=1:
                self.hands[key]=Hand();continue
            threshold=self.config.get('confidence_by_gesture',{}).get(name,self.config['confidence'])
            if locking and name=='Closed_Fist':threshold=self.config.get('eye_lock_confidence',.55)
            if score<threshold or name in (None,'None'):
                # A short undecided frame is not a deliberate release and does
                # not erase arming or add hold time. Only real poses count.
                h.continuous=False
                if h.last_seen and stamp-h.last_seen<=gap_ns:continue
                self.hands[key]=Hand();continue
            if name!=h.name:
                h.name=name;h.since=stamp;h.count=0;h.consumed=False;h.elapsed_ns=0;h.continuous=False
            if h.continuous:h.elapsed_ns+=stamp-h.last_seen
            h.last_seen=stamp;h.continuous=True
            h.count+=1
            if layer=='WRITE':continue  # The original recorder owns the ending fist.
            if name=='Open_Palm' and confirming and not calibrating:
                continue  # An open resting hand is preparation, not modal cancel.
            if name=='Closed_Fist':
                hold=self.config['hold_s']['Closed_Fist'] if confirming else self.config.get('arm_s',.25)
                if locking:hold=self.config.get('eye_lock_hold_s',.22)
                event='confirm' if confirming else None
                phase='CONFIRMING' if confirming else 'ARMING'
            elif (h.armed_until>=stamp or confirming or calibrating) and not h.consumed and name in GESTURES:
                if name=='Pointing_Up':
                    self.progress[key]=dict(hand=key,name=name,progress=0.,phase='TRAJECTORY');continue
                hold=self.config.get('cancel_hold_s',1.) if calibrating and name=='Open_Palm' else self.config['hold_s'][name]
                event=GESTURES[name];phase='GESTURE'
            else:
                if h.armed_until>=stamp:self.progress[key]=dict(hand=key,name='Closed_Fist',progress=1.,phase='ARMED')
                continue
            progress=min(1.,h.elapsed_ns/(hold*1e9))
            self.progress[key]=dict(hand=key,name=name,progress=progress,phase=phase)
            if progress>=1 and h.count>=self.config['min_frames'] and not h.consumed:
                h.consumed=True
                if event:commits.append((key,event,name));h.armed_until=0
                else:h.armed_until=stamp+int(self.config.get('armed_s',4.)*1e9)
            if name=='Closed_Fist' and not confirming and h.consumed:
                # A visible, valid held fist is still preparation, not inactivity.
                h.armed_until=stamp+int(self.config.get('armed_s',4.)*1e9)
                self.progress[key]['phase']='ARMED'
        active={p['name'] for p in self.progress.values() if p['phase'] in ('GESTURE','CONFIRMING') and p['progress']>.5}
        if len(active)>1:
            # Pause conflicting commitments, retain the observed preparation.
            # The remaining hand can finish without repeating its arming fist.
            for key,_,_ in commits:
                self.hands[key].consumed=False;self.hands[key].armed_until=prior_armed.get(key,0)
            self.conflict=True;return []
        return commits[:1]
