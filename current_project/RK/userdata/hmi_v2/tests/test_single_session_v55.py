from tests.test_eye_takeover_v49 import selecting,lock
from tests.test_interaction import healthy,face,message,catalog,gaze
from core.interaction.people import People
from core.interaction.calibration_entry import readiness


def test_single_track_churn_and_long_absence_preserve_calibration_and_lock():
    e,t=selecting();face(e,t,1);e.people.slots[1]=11;e.calibration_track=11;lock(e,t)
    identity=e.target_session['lock_id']
    for i in range(1,32):
        now=t+i*1_000_000_000;healthy(e,now);e.feed('vision.face',message(now,i+1,faces=[]),now)
    assert e.calibrated and e.target_session['lock_id']==identity
    e.feed('vision.face',message(now+1,40,faces=[dict(track_id=99,primary=True,valid=True,face_rect=[240,130,150,100],can_gaze=True)]),now+1)
    e.feed('vision.gaze',message(now+2,40,track_id=99,valid=False,calib={'done':True}),now+2)
    assert e.calibrated and e.people.slots[1]==99 and e.target_session['lock_id']==identity
    assert not any(c['command']=='invalidate_calibration' for c in e.commands)
    e.system('eye_takeover',now+3);assert e.state=='POINTING'
    assert e.commands[-1]['track_id'] is None


def test_single_hands_and_primary_calibration_do_not_require_face_registration():
    p=People();p.faces=[dict(track_id=1),dict(track_id=2)];hands=[dict(track_id=3),dict(track_id=4)]
    assert p.hands_for_active(hands)==hands
    t=10**10;m=message(t,faces=[dict(track_id=1,valid=True,primary=True,face_rect=[240,130,150,100],can_gaze=True),dict(track_id=2,valid=True)])
    _,key,reason=readiness(m,p,t);assert key==('single',1,1) and not reason


def test_single_person1_button_requests_calibration_without_enrollment():
    e,t=selecting();e.system('person1',t)
    assert not e.people.pending and e.calibration_intent


def test_dual_still_rejects_other_person_gaze():
    e,t=selecting();e.people.mode='dual';e.people.slots[1]=11;e.calibration_track=11
    e.feed('vision.gaze',message(t+1,30,track_id=99,valid=True,filtered_xy=[100,100]),t+1)
    assert 'vision.gaze' not in e.latest


def test_single_calibration_request_waits_until_cancel_instead_of_expiring():
    from core.interaction.engine import Engine
    from core.config import load
    e=Engine(load());t=10**10;healthy(e,t);e.system('calibrate',t)
    for i in range(1,32):healthy(e,t+i*1_000_000_000)
    assert e.calibration_intent and not e.calibration_request
    e.event('cancel','button',t+31_000_000_001,t+31_000_000_001)
    assert not e.calibration_intent
