"""Temporal votes over actual application targets, one vote per source sample."""
from collections import deque
from copy import deepcopy
from core.targets import select_target,valid_target,same_target

class TargetVote:
    def __init__(self):
        self.reset()
    def reset(self):
        self.votes=deque(maxlen=6);self.selected=None;self.leader=None;self.streak=0
        self.last_stamp=0;self.last_seq=-1;self.details={};self.catalog={}
    def pause(self):
        # A missing sample is neither a vote nor evidence of a new target.
        self.leader=None;self.streak=0
        self.details=dict(self.details,streak=0)
    def update(self,xy,rows,size,stamp,seq):
        catalog={r['id']:r for r in rows if valid_target(r,size)}
        changed={key for key,old in self.catalog.items() if not same_target(old,catalog.get(key))}
        self.catalog=deepcopy(catalog)
        if self.leader in changed:self.pause()
        if self.selected and not same_target(self.selected,catalog.get(self.selected['id'])):
            self.selected=None
        self.votes=deque((key for key in self.votes if key in catalog and key not in changed),maxlen=6)
        if type(stamp) is not int or type(seq) is not int or stamp<=self.last_stamp or seq<=self.last_seq:
            return deepcopy(self.selected)
        if self.last_stamp and stamp-self.last_stamp>500_000_000:
            self.votes.clear();self.pause()
        self.last_stamp=stamp;self.last_seq=seq
        # Spatial scoring proposes one target. Temporal voting owns switching;
        # do not also apply the former per-frame distance hysteresis.
        candidate=select_target(xy,list(catalog.values()),size)
        if not candidate:
            self.votes.clear();self.pause();self.details={};return None
        self.votes.append(candidate['id']);scores={}
        for age,key in enumerate(reversed(self.votes)):
            scores[key]=scores.get(key,0.)+.85**age
        ranked=sorted(scores,key=lambda key:-scores[key]);first=ranked[0]
        total=sum(scores.values());second=scores[ranked[1]] if len(ranked)>1 else 0.
        ratio=scores[first]/total;margin=(scores[first]-second)/total
        self.streak=self.streak+1 if self.leader==first else 1;self.leader=first
        ready=self.streak>=2 and ratio>=.55 and margin>=.08
        if ready and (not self.selected or self.selected['id']!=first):
            self.selected=deepcopy(catalog[first])
        self.details=dict(samples=len(self.votes),candidate_id=first,candidate_label=catalog[first].get('label','目标'),
                          streak=self.streak,share=ratio,margin=margin,ready=ready,
                          selected_id=self.selected['id'] if self.selected else None,
                          window=6,decay=.85,required_streak=2,required_share=.55,required_margin=.08)
        return deepcopy(self.selected)
