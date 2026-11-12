import threading
import time
from types import SimpleNamespace

from core.config import load
from core.interaction.engine import Engine
from core.interaction.model_demand import demand
from vision.inference_demand import InferenceDemand
from vision.ring_capture import RingCapture
from vision.resume_tracking import resume_spatial_track
from tests.test_interaction import healthy, message


def test_normal_states_keep_head_display_without_eye_inference():
    for state in ('STANDBY','PRESENT','ONBOARD','IDLE','MENU','WRITING'):
        assert demand(state)['gaze_hz']==0 and demand(state)['face_hz']==15
        assert demand(state,head_display_hz=0)['face_hz']==0
    assert demand('IDLE',dual=True)==dict(gaze_hz=0,face_hz=10,reason='dual_hand_ownership')
    assert demand('MENU',registration=True)['face_hz']==15
    assert demand('MENU',registration=True)['gaze_hz']==0
    assert demand('POINTING')['gaze_hz']==32
    assert demand('POINTING',target_phase='LOCKED')['gaze_hz']==0
    assert demand('CALIBRATING')['gaze_hz']==30
    assert demand('CALIBRATING',calibration_phase='RESULT')['gaze_hz']==0
    assert demand('POINTING',estop=True)['gaze_hz']==0


def test_hands_not_capped_by_onboarding_or_missing_calibration():
    e=Engine(load());t=10**10;healthy(e,t)
    for state in ('STANDBY','ONBOARD','IDLE','WRITING','MENU','POINTING','CALIBRATING'):
        e._state(state,t)
        b=e.snapshot(t)['budget']
        assert b['hand_hz']>0 and b['hand_unlimited']
    e._state('DEGRADED',t)
    assert not e.snapshot(t)['budget']['hand_unlimited']


def test_paused_face_does_not_invent_loss_or_erase_calibration():
    e=Engine(load());t=10**10;healthy(e,t)
    e.tuning['head_display_hz']=0
    e.calibrated=True;e.people.calibrated[1]=True;e.people.slots[1]=11
    e.calibration_track=11;e._state('IDLE',t)
    for i in range(1,60):healthy(e,t+i*1_000_000_000)
    assert e.calibrated and e.people.calibrated[1] and e.state=='IDLE'
    assert not e.snapshot(t+60_000_000_000)['cursor']['valid']


def test_pointer_wakes_without_old_gaze_then_cancel_stops_immediately():
    e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e._state('IDLE',t)
    e.system('pointer',t+1)
    assert e.state=='POINTING' and e.snapshot(t+1)['budget']['gaze_hz']==32
    assert not e.cursor['valid']
    e.system('cancel',t+2)
    assert e.snapshot(t+2)['budget']['gaze_hz']==0


def test_registration_discovers_faces_after_idle_pause():
    e=Engine(load());t=10**10;healthy(e,t);e.people.mode='dual'
    e.system('person1',t)
    assert not e.people.pending['choices']
    e.feed('vision.face',message(t+1,faces=[dict(track_id=5,valid=True,face_rect=[10,20,100,100])]),t+1)
    assert e.people.pending['choices']==[5]


def test_demand_expires_and_never_reuses_a_pre_activation_frame():
    d=InferenceDemand();t=10**10
    s=message(t,budget=dict(face_hz=32,gaze_hz=32,reason='target_selection'))
    d.update(s,7,t)
    assert not d.accepts(t-1,now=t+1)
    assert d.accepts(t+1,now=t+1)
    assert not d.accepts(t+400_000_000,now=t+400_000_000)
    d.update(dict(s,src_ns=t+1_000_000_000,estop=True),7,t+1_000_000_000)
    assert d.rate(now=t+1_000_000_001)==0
    d.update(dict(s,src_ns=t+2_000_000_000),7,t+2_000_000_000)
    assert not d.accepts(t+1_000_000_000,now=t+2_000_000_001)


def test_deliberate_pause_retains_only_spatial_seeds_and_forces_real_redetection():
    tracks=[{'id':11,'rect':[300,180,150,150,0]}]
    pipeline=SimpleNamespace(last_stamp=10.,last_detection=10.,tracks=tracks,next_id=12)
    aligner=SimpleNamespace(pipeline=pipeline)
    assert resume_spatial_track(aligner,20_000_000_000,20_010_000_000)
    assert pipeline.last_stamp is None and pipeline.last_detection==-float('inf')
    assert pipeline.tracks is tracks and pipeline.next_id==12
    # The next source timestamp is written by the real frozen pipeline; no
    # old observation is assigned the new frame's time or made valid here.
    pipeline.last_stamp=20.01;pipeline.last_detection=20.01
    assert not resume_spatial_track(aligner,20_000_000_000,20_020_000_000)


def test_unplanned_long_frame_gap_still_uses_original_tracker_reset():
    pipeline=SimpleNamespace(last_stamp=10.,last_detection=10.,tracks=[{'id':11}])
    assert not resume_spatial_track(SimpleNamespace(pipeline=pipeline),9_000_000_000,20_000_000_000)
    assert pipeline.last_stamp==pipeline.last_detection==10.


def test_zero_rate_blocks_without_copying_or_reporting_camera_failure_and_resumes_latest():
    class Ring:
        def __init__(self):self.reads=0
        def check_owner(self):pass
        def latest(self,serial):
            self.reads+=1
            return SimpleNamespace(serial=100,meta={'sequence':100},rgb='latest_frame')
    cap=RingCapture.__new__(RingCapture)
    cap.stop=threading.Event();cap.ring=Ring();cap.serial=0;cap.bootstrap=False
    cap.hz=0;cap.deadline=0;cap.admission=None
    result=[];thread=threading.Thread(target=lambda:result.append(cap.read_rgb()));thread.start()
    try:
        time.sleep(1.1)
        assert thread.is_alive() and cap.ring.reads==0 and not result
        cap.hz=30;thread.join(1)
        assert result==[(True,'latest_frame')] and cap.ring.reads==1
        cap.hz=0;thread=threading.Thread(target=lambda:result.append(cap.read_rgb()));thread.start()
        cap.request_stop();thread.join(1)
        assert not thread.is_alive() and result[-1]==(False,None)
    finally:cap.request_stop();thread.join(1)
