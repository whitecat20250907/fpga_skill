from copy import deepcopy
import pytest
from core.config import load
from core.bindings import options, validate
from core.interaction.engine import Engine
from adapters.demo import DemoAdapter
from adapters.policy import ActionGate
from tests.test_interaction import healthy, message, observation, catalog
from tests.test_eye_takeover_v49 import selecting, lock


def poses(e, t, names, side='Left', key=2, seq=100):
    for i, name in enumerate(names):
        t += 100_000_000
        healthy(e, t)
        m = observation(t, seq+i, name)
        m['hands'][0].update(track_id=key, side=side, side_score=.8, score=.6)
        e.feed('vision.hands', m, t)
    return t


def acknowledged(e, adapter, name, t):
    healthy(e, t)
    assert e._action(name, 'console', t, t)
    action = e.out[-1]
    adapter.on_action(action)
    e.feed('hmi.ack', message(t+1, id=action['id'], ok=True), t+1)
    return action


@pytest.mark.parametrize('phase', ['IDLE', 'ONBOARD', 'STANDBY', 'MENU', 'WRITING', 'CALIBRATING', 'POINTING'])
def test_left_palm_thumb_undo_works_without_repeat_session_in_all_interaction_modes(phase):
    e=Engine(load());t=10**10;healthy(e,t);e._state('ONBOARD',t);d=DemoAdapter()
    a=acknowledged(e,d,'demo.zoom_in',t)
    e._state(phase,t+1);e.repeat.clear()
    t=poses(e,t,['Open_Palm']+['Thumb_Down']*8)
    undo=[a for a in e.out if a['name']=='demo.undo']
    assert len(undo)==1 and undo[0]['args']['undo_id']==a['id']
    # Validate at the actual action source time; later held frames do not resend.
    action=undo[0];assert ActionGate().accept(action,e.snapshot(action['src_ns']),action['src_ns'])[0]
    d.on_action(action);assert d.state['zoom']==1


def test_undo_survives_hand_departure_and_can_walk_back_multiple_acknowledged_actions():
    e=Engine(load());t=10**10;healthy(e,t);e._state('ONBOARD',t);d=DemoAdapter()
    first=acknowledged(e,d,'demo.zoom_in',t)
    second=acknowledged(e,d,'demo.next',t+10)
    for seq,key,identity in [(100,2,second['id']),(200,9,first['id'])]:
        t=poses(e,t,['Open_Palm']+['Thumb_Down']*4,key=key,seq=seq)
        action=e.out[-1];assert action['name']=='demo.undo' and action['args']['undo_id']==identity
        d.on_action(action);e.feed('hmi.ack',message(t+1,id=action['id'],ok=True),t+1)
    assert d.state['page']==0 and d.state['zoom']==1


def test_eye_lock_then_right_palm_fist_clicks_repeatedly_without_restarting_gaze():
    e,t=selecting();lock(e,t);frozen=deepcopy(e.cursor)
    t=poses(e,t,['Closed_Fist']*4,side='Right',key=1)
    assert not e.out
    for seq in (200,300):
        t=poses(e,t,['Open_Palm']+['Closed_Fist']*5,side='Right',key=1,seq=seq)
        assert len(e.out)==(1 if seq==200 else 2)
        a=e.out[-1];assert a['name']=='demo.click'
        e.feed('hmi.ack',message(t+1,id=a['id'],ok=True),t+1)
    assert e.cursor==frozen and e.target_session['phase']=='LOCKED'
    assert e.snapshot(t)['budget']['gaze_hz']==0 and not e.repeat.session


def test_old_click_mappings_migrate_to_one_eye_entry_and_no_public_click_option():
    b=load()['bindings']
    for context in ('DEMO','DESKTOP','GAME'):
        assert context.lower()+'.click' not in options(context)
        b['static'][context]['Victory']=context.lower()+'.click'
    b=validate(b)
    assert all(b['static'][c]['Victory']=='system.eye_takeover' for c in ('DEMO','DESKTOP','GAME'))


def test_eye_click_allows_same_medical_content_to_expand_without_moving_locked_cursor():
    e,t=selecting();lock(e,t)
    target=e.target_session['target'];target.update(id='demo:control:3:ct_axial',action='demo.inspect',page=3,content='axial',part=None)
    e.target_catalog['targets']=[dict(target,rect=[500,200,800,600])]
    assert e._action('demo.click','Closed_Fist',t,t)
    assert ActionGate().accept(e.out[-1],e.snapshot(t),t)[0]
    e.target_catalog['targets'][0]['page']=2
    assert e._action('demo.click','Closed_Fist',t+1,t+1)
    assert not ActionGate().accept(e.out[-1],e.snapshot(t+1),t+1)[0]


def test_pointing_countdown_is_point_three_seconds_and_duplicate_frames_do_not_start_it():
    pytest.importorskip('cv2')
    from vision.bootstrap import install_vendor_resolver
    from vision.gesture_flow import GestureTrajectory
    from tests.test_gesture_trajectory import result
    install_vendor_resolver();flow=GestureTrajectory(load()['gestures'])
    state=dict(state='ONBOARD',epoch=7,people='single',active_hand_ids=[9])
    for i,name in enumerate(['Closed_Fist']*3+['Pointing_Up']*2):
        t=10+i*.05;flow.update(result(name),i+1,t,t,640,360,state)
    r=flow.recorders[9];start=r.since;assert r.state=='COUNTDOWN'
    flow.update(result('Pointing_Up'),6,start+.29,start+.29,640,360,state);assert r.state=='COUNTDOWN'
    flow.update(result('Pointing_Up'),6,start+.29,start+.31,640,360,state);assert r.state=='COUNTDOWN'
    flow.update(result('Pointing_Up'),7,start+.31,start+.31,640,360,state);assert r.state=='REC'


def test_undo_generation_discards_the_unfinished_recorder_instead_of_reentering_writing():
    pytest.importorskip('cv2')
    from vision.bootstrap import install_vendor_resolver
    from vision.gesture_flow import GestureTrajectory
    from tests.test_gesture_trajectory import result
    install_vendor_resolver();flow=GestureTrajectory(load()['gestures'])
    state=dict(state='ONBOARD',epoch=7,people='single',active_hand_ids=[9],gesture_generation=0)
    for i in range(3):flow.update(result('Closed_Fist'),i+1,10+i*.1,10+i*.1,640,360,state)
    assert flow.recorders[9].state=='ARMED'
    flow.update(result('Pointing_Up'),4,10.4,10.4,640,360,dict(state,gesture_generation=1))
    assert flow.recorders[9].state=='IDLE'
