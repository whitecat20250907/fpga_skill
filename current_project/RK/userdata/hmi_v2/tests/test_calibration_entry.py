import pytest
from core.config import load
from core.interaction.engine import Engine
from tests.test_interaction import healthy,message,face


def ready():
    e=Engine(load());t=10**10;healthy(e,t)
    for i in range(7):face(e,t+i*100_000_000,i+1);e.tick(t+i*100_000_000)
    return e,t+600_000_000


def test_empty_console_calibrate_has_feedback_and_no_calibration_request():
    e=Engine(load());t=10**10;healthy(e,t);e.system('calibrate',t)
    assert not e.commands and not e.calibration_request and e.state!='CALIBRATING'
    assert '完整人脸' in e.toast


@pytest.mark.parametrize('route',['console','menu','button','gesture'])
def test_all_entry_routes_start_once_only_after_same_readiness(route):
    e,t=ready()
    if route=='console':e.system('calibrate',t)
    elif route=='menu':e._state('MENU',t);e.menu_index=4;e.event('confirm','button',t,t)
    elif route=='gesture':e._bound('system.calibrate','Thumb_Up',t,t)
    else:e._state('ONBOARD',t);e.event('confirm','button',t,t)
    assert e.state=='CALIBRATING'
    request=e.calibration_request;commands=len(e.commands)
    e.system('calibrate',t+1)
    assert e.calibration_request==request and len(e.commands)==commands
    assert '先取消' in e.toast


@pytest.mark.parametrize('change',['stale','no_eyes','too_far','off_center','replacement','unregistered','wrong_selected','pending'])
def test_not_ready_never_starts_calibration(change):
    e,t=ready();f=e.latest['vision.face'];primary=f['faces'][0]
    if change=='stale':t+=351_000_000
    if change=='no_eyes':primary['can_gaze']=False
    if change=='too_far':primary['face_rect'][2]=30
    if change=='off_center':primary['face_rect'][0]=0
    if change=='replacement':primary['track_id']=22
    if change=='two_faces':f['faces'].append(dict(primary,track_id=22,primary=False))
    if change in ('unregistered','wrong_selected','pending'):
        e.people.mode='dual'
        if change=='wrong_selected':e.people.slots[1]=22
        if change=='pending':e.people.request(1)
    e.system('calibrate',t)
    assert e.state!='CALIBRATING' and not e.calibration_request
    assert not any(c['command']=='calibrate' for c in e.commands)
    assert '尚未开始' in e.toast


def test_bad_sample_and_track_change_restart_stability_window():
    e,t=ready();e.latest['vision.face']['faces'][0]['can_gaze']=False;e.tick(t)
    assert e.onboard_since==0
    face(e,t+1,8);e.tick(t+1);e.system('calibrate',t+1)
    assert not e.calibration_request
    e.latest['vision.face']['faces'][0]['track_id']=22;e.tick(t+2)
    assert e.onboard_since==t+2


def test_estop_clears_registration_stroke_and_commands_until_explicit_resume():
    from ui.feedback import feedback
    e,t=ready();e.system('dual',t);e.system('person1',t)
    e.writing={'state':'REC'};e.stroke={'accepted':True};e.shortcut={'target':'demo.next'}
    e.system('estop',t+1)
    assert e.people.pending is None and not e.writing and not e.stroke and not e.shortcut
    assert not e.out and not e.pending
    assert [c['command'] for c in e.commands]==['preview','hide_window']
    assert feedback(e.snapshot(t+1))['title']=='已暂停'
    for name in ('single','person2','calibrate','confirm','demo_next'):
        e.system(name,t+2)
        assert e.estop and e.state=='STANDBY' and e.people.mode=='dual' and e.people.pending is None
    e.system('menu',t+3)
    assert not e.estop and e.state=='MENU'


def test_service_loss_cancels_unconfirmed_registration():
    e,t=ready();e.system('dual',t);e.system('person1',t)
    assert e.people.pending
    e.feed('sys.metrics',message(t+1,producer='hand',ok=False),t+1);e.tick(t+1)
    assert e.state=='DEGRADED' and e.people.pending is None
