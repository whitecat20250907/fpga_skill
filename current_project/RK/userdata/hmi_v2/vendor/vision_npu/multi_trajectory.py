"""Four independent bounded stroke states keyed by transient spatial tracks.

Loss cancels a stroke; we never associate strokes by array position, handedness
alone, or a guessed person identity. No shortcut mapping or actions.
"""
import sys
from types import SimpleNamespace
sys.path.insert(0,'/userdata/gesture8_rk3576_20261021')
from trajectory import TrajectoryRecorder,observations

class MultiTrajectory:
    def __init__(self):self.recorders={}
    def tick(self,now):
        for r in self.recorders.values():r.tick(now)
    def update(self,result,sequence,source_time,now,width,height):
        ids=result.track_ids
        if len(ids)!=len(set(ids)) or len(ids)!=len(result.hand_landmarks) or len(ids)>4:raise ValueError('Invalid track IDs')
        # Retiring a lost ID destroys its unfinished stroke. New ID starts neutral.
        self.recorders={k:v for k,v in self.recorders.items() if k in ids};finished=[]
        for i,key in enumerate(ids):
            sample=SimpleNamespace(hand_landmarks=[result.hand_landmarks[i]],gestures=[result.gestures[i]],handedness=[result.handedness[i]])
            obs=observations(sample)
            if key not in self.recorders:self.recorders[key]=TrajectoryRecorder()
            image=self.recorders[key].update(obs,sequence,source_time,now,width,height)
            if image is not None:finished.append((key,image))
        return finished
