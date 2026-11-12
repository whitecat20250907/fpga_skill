"""Opt-in, bounded latest-sample export at the real filtered production point."""
import json
import math
import os
from pathlib import Path
import time


class CalibrationBinding:
    """Observe which transient face supplied this personal calibration.

    This never changes calibration, filtering, cursor or game behavior. If any
    accepted CALIBRATE sample changes track/session, UI projection is disabled.
    """
    def __init__(self):self.reset()
    def reset(self):self.actor=None;self.mixed=False
    @staticmethod
    def actor_of(sample):
        source=sample.get('source_instance');track=sample.get('track_id')
        return (source,track) if isinstance(source,str) and source and type(track) is int and track>0 else None
    def observe(self,sample,phase):
        if phase=='CALIBRATE' and sample.get('valid'):
            actor=self.actor_of(sample)
            if actor is None:self.mixed=True
            elif self.actor is None:self.actor=actor
            elif actor!=self.actor:self.mixed=True
    def matches(self,sample):return not self.mixed and self.actor is not None and self.actor==self.actor_of(sample)


def filtered_packet(sample,phase,filtered,has_calibrated,screen_size,binding,now_ns):
    stamp=sample.get('timestamp_ns');actor=binding.actor_of(sample)
    fresh=type(stamp) is int and 0<=now_ns-stamp<=350_000_000
    calibrated=bool(has_calibrated and binding.matches(sample))
    size=[int(v) for v in screen_size]
    if len(size)!=2 or any(v<=0 for v in size):raise ValueError('screen size')
    xy=[float(v) for v in filtered] if filtered is not None else None
    valid=bool(fresh and sample.get('valid') and phase=='TRACK' and calibrated and xy is not None
               and len(xy)==2 and all(math.isfinite(v) for v in xy)
               and 0<=xy[0]<size[0] and 0<=xy[1]<size[1])
    return dict(version=1,kind='filtered_gaze_ui',timestamp_ns=stamp,capture_sequence=sample.get('capture_sequence'),
        source_instance=actor[0] if actor else None,track_id=actor[1] if actor else None,
        mode=phase,valid=valid,filtered=xy if valid else None,screen_size=size,
        calibration_valid_for_track=calibrated,calibration_track_id=binding.actor[1] if calibrated else None,
        projection_valid=valid,ray_is_physical_3d=False,track_ids_are_person_identity=False)


class FilteredUIExport:
    def __init__(self,*,path=None,clock=time.monotonic_ns):
        self.path=Path(path) if path is not None else Path('/dev/shm')/('gaze_ui_filtered_'+str(os.getpid())+'.json')
        self.clock=clock;self.binding=CalibrationBinding();self.last_write=-1;self.last_valid=None
        self.errors=0;self.writes=0
    def reset_binding(self):self.binding.reset()
    def observe(self,sample,phase,filtered,has_calibrated,screen_size):
        # Optional UI failure never replaces the application's exception policy.
        try:
            self.binding.observe(sample,phase);now=self.clock()
            packet=filtered_packet(sample,phase,filtered,has_calibrated,screen_size,self.binding,now)
            valid=packet['valid']
            if self.last_write>=0 and now-self.last_write<100_000_000 and valid==self.last_valid:return False
            temporary=self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(packet,separators=(',',':'),allow_nan=False),encoding='utf8');temporary.replace(self.path)
            self.last_write=now;self.last_valid=valid;self.writes+=1;return True
        except (OSError,ValueError,TypeError,IndexError):self.errors+=1;return False
