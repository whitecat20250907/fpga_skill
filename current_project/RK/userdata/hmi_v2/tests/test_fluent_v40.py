from core.config import load
from core.interaction.engine import Engine
from core.interaction.calibration_entry import readiness
from tests.test_interaction import healthy,face


def test_single_mode_reselection_preserves_valid_calibration():
    e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e.people.calibrated[1]=True
    e.people.slots[1]=50;e._state('IDLE',t)
    e.system('single',t+1)
    assert e.calibrated and e.people.slots[1]==50 and not e.commands


def test_explicit_app_switch_cancels_incomplete_calibration_and_opens_app():
    e=Engine(load());t=10**10;healthy(e,t);e._state('CALIBRATING',t)
    e.system('app_game',t+1)
    assert e.context=='GAME' and e.state=='ONBOARD'
    assert [c['command'] for c in e.commands]==['preview','hide_window']
    assert e.application_request['context']=='GAME' and not e.out


def test_calibration_request_waits_for_face_then_starts_without_second_command():
    e=Engine(load());t=10**10;healthy(e,t);e.system('calibrate',t)
    assert e.calibration_intent and not e.calibration_request
    for i in range(1,6):healthy(e,t+i*1_000_000_000)
    assert e.calibration_intent
    for i in range(4):
        now=t+5_100_000_000+i*100_000_000;healthy(e,now);face(e,now,i+1);e.tick(now)
    assert e.state=='CALIBRATING' and e.calibration_request
    assert sum(c['command']=='calibrate' for c in e.commands)==1


def test_clear_eyes_away_from_exact_center_are_allowed():
    e=Engine(load());t=10**10;healthy(e,t);face(e,t,1)
    e.latest['vision.face']['faces'][0]['face_rect']=[100,80,100,100]
    ready,key,reason=readiness(e.latest['vision.face'],e.people,t)
    assert not reason and all(ready.values())
    e.latest['vision.face']['faces'][0]['can_gaze']=False
    assert readiness(e.latest['vision.face'],e.people,t)[2]
