from copy import deepcopy
import pytest
from tests.test_eye_takeover_v49 import selecting,lock
from tests.test_interaction import healthy,face,message,catalog,observation
from adapters.policy import ActionGate


def locked():
    e,t=selecting();face(e,t,1);e.people.slots[1]=11;e.people.calibrated[1]=True;e.calibration_track=11
    lock(e,t);return e,t


def lose_face(e,t):
    now=t+5_100_000_000;healthy(e,now)
    e.feed('vision.face',message(now,2,faces=[]),now)
    return now


@pytest.mark.parametrize('action',['demo.focus','demo.click','desktop.click','game.click','game.confirm'])
def test_locked_action_survives_face_loss_without_live_gaze(action):
    e,t=locked();e.context=action.split('.')[0].upper();e.target_session['context']=e.context;e.target_session['target']['action']=e.context.lower()+'.click'
    original=deepcopy(e.cursor);identity=e.target_session['lock_id'];now=lose_face(e,t);catalog(e,now)
    assert e.calibrated and e.target_session['lock_id']==identity
    e.calibrated=False  # An already frozen target also works after an explicit calibration loss.
    for i in range(3):
        stamp=now+i*100_000_000;healthy(e,stamp);catalog(e,stamp)
        assert e._action(action,'Victory',stamp,stamp)
        assert ActionGate().accept(e.out[-1],e.snapshot(stamp),stamp)==(True,'')
        assert e.cursor==original and e.snapshot(stamp)['budget']['gaze_hz']==0


def test_pending_static_click_survives_face_loss_then_confirm_executes():
    e,t=locked();e.bindings['static']['DEMO']['Victory']='demo.click'
    e.input_hand=1;e.event('next','Victory',t+1,t+1);assert e.shortcut
    now=lose_face(e,t);assert e.shortcut
    e.event('confirm','Closed_Fist',now+1,now+1);catalog(e,now+1)
    assert e.out[-1]['name']=='demo.click'
    assert ActionGate().accept(e.out[-1],e.snapshot(now+1),now+1)[0]


def test_pending_trajectory_focus_survives_face_loss_and_other_hand_confirmation():
    e,t=locked();e.bindings['stroke']['DEMO']['Z']='demo.focus'
    e._state('WRITING',t+1)
    m=observation(t+1,1,'Closed_Fist');m['hands'][0].update(side='Right',side_score=.99)
    e.latest['vision.hands']=m;e.last_hand=t+1
    e.feed('vision.stroke',message(t+2,track_id=1,label='Z',confidence=.99,accepted=True),t+2)
    assert e.stroke_confirm.pending
    now=lose_face(e,t);assert e.stroke_confirm.pending and e._stroke_invalid_reason(now) is None
    for i,name in enumerate(['Open_Palm']*2+['Closed_Fist']*9):
        stamp=now+i*100_000_000;healthy(e,stamp);catalog(e,stamp)
        m=observation(stamp,i+2,name);m['hands'][0].update(track_id=2,side='Left',side_score=.99)
        e.feed('vision.hands',m,stamp)
        if e.out:break
    assert len(e.out)==1 and e.out[-1]['name']=='demo.focus'
    assert e.out[-1]['confirmation']=='opposite_hand'
    assert ActionGate().accept(e.out[-1],e.snapshot(stamp),stamp)[0]


def test_gaze_restart_keeps_frozen_point_but_invalidates_eye_calibration():
    e,t=locked();original=deepcopy(e.cursor)
    for i,instance in enumerate(['old','new']):e.feed('sys.metrics',message(t+i+1,producer='gaze',instance=instance,ok=True),t+i+1)
    assert not e.calibrated and e.cursor==original and e.target_session['phase']=='LOCKED'


def test_hand_health_gap_pauses_actions_and_recovers_same_lock():
    e,t=locked();identity=e.target_session['lock_id']
    e.feed('sys.metrics',message(t+1,producer='hand',ok=False),t+1);e.tick(t+1)
    assert e.state=='DEGRADED' and not e._action('demo.click','Victory',t+1,t+1)
    healthy(e,t+2);catalog(e,t+2)
    assert e.target_session['lock_id']==identity and e._action('demo.click','Victory',t+2,t+2)
    assert ActionGate().accept(e.out[-1],e.snapshot(t+2),t+2)[0]


def test_dual_loss_and_explicit_boundaries_still_clear_lock():
    e,t=locked();e.people.mode='dual';lose_face(e,t);assert not e.target_session
    for command in ('app_game','dual','estop','calibrate_person1'):
        e,t=locked();e.system(command,t+1);assert not e.target_session
    e,t=locked();e.feed('sys.metrics',dict(message(t+1,producer='fpga-io',ok=True),epoch=8),t+1)
    assert not e.target_session


def test_missing_or_changed_lock_never_bypasses_gate_when_uncalibrated():
    e,t=locked();now=lose_face(e,t);catalog(e,now)
    assert e._action('demo.click','Victory',now,now)
    a=e.out[-1];s=e.snapshot(now);s['target_session']['lock_id']='replacement'
    assert not ActionGate().accept(a,s,now)[0]
    e._clear_target();assert not e._action('demo.click','Victory',now,now)
