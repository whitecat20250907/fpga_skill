from core.config import load
from core.bindings import options,validate
from core.interaction.engine import Engine
from tests.test_interaction import healthy,face
from tests.test_calibration_entry import ready


def test_all_app_and_person_controls_bind_in_each_context():
    required={'system.app_demo','system.app_game','system.app_desktop','system.mode_next','system.single','system.dual','system.calibrate','system.calibrate_person1','system.calibrate_person2'}
    for c in ('DEMO','GAME','DESKTOP'):assert required<=set(options(c))
    e=Engine(load());t=10**10;healthy(e,t)
    for target in ('app_game','app_demo','app_desktop'):
        e.bindings['static'][e.context]['Victory']='system.'+target
        e.event('next','Victory',t,t);assert e.shortcut and not e.out
        e.event('confirm','Closed_Fist',t+1,t+1)
        assert e.context==target[4:].upper().replace('DEMO','DEMO') and not e.out
        t+=100_000_000;healthy(e,t)


def test_person1_calibration_waits_for_readiness_and_starts_once():
    e=Engine(load());t=10**10;healthy(e,t);e.system('calibrate_person1',t)
    assert e.calibration_intent and not e.calibration_request
    for i in range(8):
        now=t+(i+1)*100_000_000;healthy(e,now);face(e,now,i+1);e.tick(now)
    assert e.state=='CALIBRATING' and e.calibration_intent is None
    assert len([c for c in e.commands if c['command']=='calibrate'])==1


def test_person2_requires_dual_and_never_reuses_person1_registration():
    e,t=ready();e.system('calibrate_person2',t)
    assert not e.calibration_intent and '双人' in e.toast
    e.system('dual',t+1);e.system('calibrate_person2',t+2)
    assert e.people.pending['slot']==2 and e.calibration_intent['slot']==2
    assert not e.calibration_request
    e.event('cancel','button',t+3,t+3)
    assert not e.calibration_intent and not e.people.pending


def test_calibration_reservation_cancelled_by_app_switch_and_estop():
    for cmd in ('app_game','estop','menu'):
        e,t=ready();e.system('calibrate_person1',t);e.system(cmd,t+1)
        assert not e.calibration_intent and not e.calibration_request
