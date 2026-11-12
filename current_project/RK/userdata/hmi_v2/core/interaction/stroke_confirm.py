"""A classified stroke is a proposal, confirmed by the opposite live hand."""
from .fist_latch import FistLatch
from core.clock import fresh


class StrokeConfirm:
    def __init__(self,config):
        self.latch=FistLatch(config);self.pending=None;self.released=set();self.last_seen={}

    def clear(self):
        self.pending=None;self.released.clear();self.last_seen.clear();self.latch.reset()

    def begin(self,stroke,target,source,context,now,peers=()):
        self.clear()
        side=source.get('side')
        if side not in ('Left','Right') or source.get('side_score',0)<.55:return False
        self.pending=dict(label=stroke['label'],target=target,source_track=source['track_id'],
            source_side=side,confirm_side='Left' if side=='Right' else 'Right',
            source_ns=stroke['src_ns'],source_seq=stroke['seq'],context=context,
            expires_ns=now+30_000_000_000,progress=0.,reason='waiting_hand')
        # The other hand may already be open while the drawing hand finishes.
        # Seed preparation from the engine's current fresh, owner-filtered
        # hands; never demand a second open gesture after showing the result.
        others=[h for h in peers if h['track_id']!=source['track_id']
                and h.get('side')==self.pending['confirm_side']
                and h.get('side_score',0)>=.55 and h.get('in_bounds',True)]
        if len(others)==1:
            h=others[0];name=h.get('gesture')
            threshold=.5 if name=='Open_Palm' else self.latch.config.get('confidence_by_gesture',{}).get(name,self.latch.config['confidence'])
            if name in ('Open_Palm','Pointing_Up','Victory','Thumb_Up','ILoveYou') and h.get('score',0)>=threshold:
                self.released.add(h['track_id']);self.last_seen[h['track_id']]=now
                self.pending.update(other_hand_ready=True,reason='make_fist')
        return True

    def observe(self,message,rows,now):
        p=self.pending
        if not p or p.get('confirmed') or p.get('cancelled'):return False
        if not fresh(message.get('src_ns'),350,now):
            self.released.clear();self.last_seen.clear();self.latch.reset()
            p.update(progress=0.,other_hand_ready=False,reason='waiting_hand');return False
        candidates=[h for h in rows if h['track_id']!=p['source_track']
                    and ((h.get('side')==p['confirm_side'] and h.get('side_score',0)>=.55)
                         or h['track_id'] in self.released and now-self.last_seen.get(h['track_id'],0)<=350_000_000)
                    and h.get('in_bounds',True)]
        if len(candidates)!=1:candidates=[]
        # A one-frame detection gap must not erase an observed release. Keep
        # only the same track for at most 350 ms; never replay a missing pose
        # or transfer release permission to a replacement track.
        self.last_seen={k:t for k,t in self.last_seen.items() if now-t<=350_000_000}
        self.released.intersection_update(self.last_seen)
        for h in candidates:self.last_seen[h['track_id']]=now
        for h in candidates:
            name=h.get('gesture');key=h['track_id']
            threshold=.5 if name=='Open_Palm' else self.latch.config.get('confidence_by_gesture',{}).get(name,self.latch.config['confidence'])
            if name in ('Open_Palm','Pointing_Up','Victory','Thumb_Up','ILoveYou') and h.get('score',0)>=threshold:
                self.released.add(key)
        rows=[h for h in candidates if h['track_id'] in self.released]
        commits=self.latch.observe(dict(message,hands=rows),now,confirming=True)
        progress=max((v for v in self.latch.progress.values() if v['name'] in ('Closed_Fist','Thumb_Down')),key=lambda v:v['progress'],default={})
        p['progress']=progress.get('progress',0.)
        p['other_hand_ready']=bool(rows)
        p['reason']='waiting_hand' if not candidates else 'release_first' if not rows else 'holding_fist' if p['progress']>0 else 'make_fist'
        if rows and p['progress']>0 and progress.get('name')=='Thumb_Down':p['reason']='holding_cancel'
        if candidates and not rows and candidates[0].get('gesture')=='Open_Palm':p['reason']='prepare_palm'
        if candidates and candidates[0].get('gesture')=='None':p['reason']='unrecognized'
        for key,event,_ in commits:
            if event=='cancel':p.update(cancelled=True,confirm_track=key);return False
            if event=='confirm':p['confirm_track']=key
        confirmed=any(event=='confirm' for _,event,_ in commits)
        if confirmed:p['confirmed']=True
        return confirmed
