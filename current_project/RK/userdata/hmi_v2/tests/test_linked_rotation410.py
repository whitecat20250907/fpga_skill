from copy import deepcopy
import pytest
from tests.test_locked_rotation295 import locked, ack
from tests.test_gesture_trajectory import result
from tests.test_interaction import message, healthy
from core.targets import demo_targets, center
from vision.bootstrap import install_vendor_resolver
from vision.gesture_flow import GestureTrajectory


def test_locked_ct_rotation_is_volume_rotation_not_slice_scan():
    x=locked();x.d.state['page']=1
    target=demo_targets(x.d.state,[1920,1080])[0]
    x.e.target_session['target']=target
    x.e.cursor['xy']=center(target)
    pointer=deepcopy(x.e.cursor);crosshair=deepcopy(x.d.state['crosshair'])
    x.e.input_hand=1;x.e.input_side='Right'
    assert x.e._action('demo.rotate','stroke',x.t,x.t)
    x.e.out[-1]['confirmation']='trajectory_fist';ack(x)
    assert x.d.state['page']==2
    x.t=x.d.rotation_tick
    for _ in range(5):
        x.frames('Closed_Fist',1);x.d.tick(x.t,x.e.snapshot(x.t))
    assert x.d.state['orbit'][1]>0 and x.d.state['crosshair']==crosshair
    assert x.e.cursor==pointer


@pytest.mark.parametrize('order',['stroke_first','hands_first'])
def test_live_recorder_to_engine_ending_fist_executes_only_rotation(order):
    install_vendor_resolver();x=locked();flow=GestureTrajectory(x.e.config['gestures'])
    x.e.bindings['stroke']['DEMO']['L_rev']='demo.rotate'
    pointer=deepcopy(x.e.cursor);done_count=0
    poses=['Closed_Fist']*5+['Pointing_Up']*18+['Closed_Fist']*8
    for i,pose in enumerate(poses):
        x.t+=100_000_000;x.seq+=1;healthy(x.e,x.t)
        state=x.e.snapshot(x.t);state['active_hand_ids']=[1]
        finished=flow.update(result(pose,x=.3+min(i,22)*.012,track=1),x.seq,x.t/1e9,x.t/1e9,640,360,state)
        records={str(k):{'state':r.state} for k,r in flow.recorders.items()}
        hands=message(x.t,x.seq,hands=[dict(track_id=1,side='Right',side_score=.95,gesture=pose,score=.95)],recorder=records,gesture_generation=state['gesture_generation'])
        stroke=message(x.t,x.seq,track_id=1,source_side='Right',ending_gesture=pose,gesture_generation=state['gesture_generation'],label='L_rev',confidence=.95,accepted=True)
        if finished and order=='stroke_first':x.e.feed('vision.stroke',stroke,x.t)
        x.e.feed('vision.hands',hands,x.t)
        if finished and order=='hands_first':x.e.feed('vision.stroke',stroke,x.t)
        if finished:ack(x)
        done_count+=len(finished)
    assert done_count==1
    assert [a['name'] for a in x.e.out]==['demo.rotate']
    assert x.d.state['rotating'] and x.e.cursor==pointer


def test_cancel_rotation_proposal_after_open_palm_does_not_undo_previous_action():
    x=locked();x.e.bindings['static']['DEMO']['Victory']='demo.rotate'
    assert x.e._action('demo.zoom','dual_index',x.t,x.t)
    x.e.out[-1]['args']={'ratio':1.4};ack(x)
    x.frames('Closed_Fist');x.frames('Victory');assert x.e.shortcut
    x.frames('Open_Palm',1);x.frames('Thumb_Down')
    assert x.e.shortcut is None
    assert [a['name'] for a in x.e.out]==['demo.zoom']
    assert x.d.state['zoom']==1.4


def test_held_ready_fist_does_not_silently_expire_before_static_rotation():
    x=locked();x.e.bindings['static']['DEMO']['Victory']='demo.rotate'
    x.frames('Closed_Fist',140);x.frames('Victory')
    assert x.e.shortcut and x.e.shortcut['target']=='demo.rotate'
    x.frames('Closed_Fist');ack(x);assert x.d.state['rotating']


def test_held_ready_fist_keeps_trajectory_prepared():
    install_vendor_resolver();flow=GestureTrajectory()
    state=dict(state='IDLE',epoch=7,context='DEMO',active_hand_ids=[1],target_session={'phase':'LOCKED'})
    for i in range(70):
        now=10+i*.1;flow.update(result('Closed_Fist',track=1),i+1,now,now,640,360,state)
        if i>=3:assert flow.recorders[1].state=='ARMED'

