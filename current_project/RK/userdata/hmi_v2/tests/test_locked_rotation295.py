from copy import deepcopy
import pytest
from tests.test_gesture_contract_v92 import Driver
from tests.test_interaction import message,healthy
from tests.test_gesture_trajectory import result
from vision.bootstrap import install_vendor_resolver
from vision.gesture_flow import GestureTrajectory
from core.targets import demo_targets,center,resolve_medical_click
from adapters.policy import ActionGate

def locked():
    x=Driver();x.e.calibrated=True;x.e._state('IDLE',x.t)
    x.d.state['page']=2
    target=demo_targets(x.d.state,[1920,1080])[0]
    x.e.target_session=dict(phase='LOCKED',lock_id='lock',target=target,
                           cursor=dict(xy=center(target),screen_size=[1920,1080]),locked_ns=x.t)
    x.e.cursor=dict(xy=center(target),screen_size=[1920,1080],valid=True,locked=True,frozen=True,src_ns=x.t)
    x.e.target_catalog=message(x.t,context='DEMO',targets=demo_targets(x.d.state,[1920,1080]))
    return x

def ack(x):
    a=x.e.out[-1]
    x.e.target_catalog['src_ns']=x.t
    assert ActionGate().accept(a,x.e.snapshot(x.t),x.t)[0]
    result=x.d.on_action(a)
    x.e.feed('hmi.ack',message(x.t+1,id=a['id'],ok=True,detail=result['detail']),x.t+1)
    return a

def test_locked_click_fist_can_prepare_static_rotation_without_extra_fist():
    x=locked();x.e.bindings['static']['DEMO']['Victory']='demo.rotate'
    x.frames('Open_Palm',1);x.frames('Closed_Fist');assert x.e.out[-1]['name']=='demo.click';ack(x)
    pointer=deepcopy(x.e.cursor)
    x.frames('Victory');assert x.e.shortcut and x.e.shortcut['target']=='demo.rotate'
    x.frames('Closed_Fist');assert ack(x)['name']=='demo.rotate'
    assert x.d.state['rotating'] and x.e.cursor==pointer
    n=len(x.e.out);x.frames('Closed_Fist',10);assert len(x.e.out)==n

def test_lock_ending_fist_continues_directly_to_trajectory_and_rotate():
    install_vendor_resolver();flow=GestureTrajectory()
    x=locked();x.e.bindings['stroke']['DEMO']['L_rev']='demo.rotate'
    x.frames('Closed_Fist');x.e._consume_right()
    seq=0;now=x.t/1e9
    for _ in range(7):
        seq+=1;now+=.1
        state=x.e.snapshot(int(now*1e9));state['active_hand_ids']=[1]
        flow.update(result('Pointing_Up',track=1),seq,now,now,640,360,state)
    assert flow.recorders[1].state=='REC'
    x.frames('Pointing_Up',2,recorder={'1':{'state':'REC'}})
    stamp=x.t+1
    x.e.feed('vision.stroke',message(stamp,9999,track_id=1,source_side='Right',ending_gesture='Closed_Fist',gesture_generation=x.e.gesture_generation,label='L_rev',confidence=.95,accepted=True),stamp)
    x.t=stamp
    assert ack(x)['name']=='demo.rotate' and x.d.state['rotating']

def test_palm_click_reservation_cannot_block_recorder_fist():
    install_vendor_resolver();flow=GestureTrajectory()
    state=dict(state='IDLE',context='DEMO',epoch=7,active_hand_ids=[9],reserved_hand_ids=[9],target_session={'phase':'LOCKED'})
    for i,pose in enumerate(['Open_Palm']+['Closed_Fist']*4+['Pointing_Up']*8):
        now=10+i*.1
        if pose=='Pointing_Up':state['reserved_hand_ids']=[]
        flow.update(result(pose),i+1,now,now,640,360,state)
    assert flow.recorders[9].state=='REC'

def test_old_confirmation_cannot_rearm_after_generation_change():
    install_vendor_resolver();flow=GestureTrajectory()
    state=dict(state='IDLE',context='DEMO',epoch=7,active_hand_ids=[9],gesture_generation=2,
               confirmed_fist=dict(epoch=7,src_ns=10**10,track_id=9,context='DEMO',generation=1))
    for i in range(9):flow.update(result('Pointing_Up'),i+1,10.1+i*.1,10.1+i*.1,640,360,state)
    assert flow.recorders[9].state=='IDLE'

def test_geometry_changes_keep_semantic_click_and_case_change_rejects():
    x=locked();target=deepcopy(x.e.target_session['target']);moved=deepcopy(target);moved['rect']=[10,20,80,60]
    assert resolve_medical_click(target,[moved])==moved
    x.e.target_catalog['targets']=[moved]
    assert x.e._action('demo.click','Closed_Fist',x.t,x.t)
    assert ActionGate().accept(x.e.out[-1],x.e.snapshot(x.t),x.t)[0]
    moved['case_id']='different'
    with pytest.raises(ValueError):resolve_medical_click(target,[moved])

def test_page_change_keeps_pointer_and_allows_rotate_but_no_stale_click():
    x=locked();pointer=deepcopy(x.e.cursor)
    assert x.e._action('demo.next','console',x.t,x.t);ack(x)
    assert x.e.cursor==pointer and not x.e.target_session['target']
    assert not x.e._action('demo.click','Closed_Fist',x.t,x.t)
    assert x.e._action('demo.rotate','console',x.t,x.t);ack(x)
    assert x.d.state['page']==2 and x.d.state['rotating']

def test_rotation_palm_stop_then_zoom_and_undo_without_moving_lock():
    x=locked();pointer=deepcopy(x.e.cursor)
    x.e.input_hand=1;x.e.input_side='Right'
    assert x.e._action('demo.rotate','stroke',x.t,x.t)
    x.e.out[-1]['confirmation']='trajectory_fist';ack(x)
    x.e.input_hand=x.e.input_side=None;x.t=x.d.rotation_tick
    for _ in range(5):x.frames('Open_Palm',1);x.d.tick(x.t,x.e.snapshot(x.t))
    assert not x.d.state['rotating']
    assert x.e._action('demo.zoom','dual_index',x.t,x.t);x.e.out[-1]['args']={'ratio':1.5};ack(x)
    assert x.d.state['zoom']==1.5
    x.e._undo_last(x.t,x.t);ack(x)
    assert x.d.state['zoom']==1 and x.e.cursor==pointer

def test_maintenance_keeps_case_calibration_and_pointer_without_action_replay():
    from core.maintenance_resume import restore_engine,restore_demo
    x=locked();x.d.state.update(zoom=1.7,orbit=[0,38,0],rotating=True)
    record={'state':x.e.snapshot(x.t),'demo':deepcopy(x.d.state)}
    y=Driver();assert restore_engine(y.e,record,y.t)
    assert restore_demo(y.d,record)
    assert y.e.calibrated and y.e.cursor==x.e.cursor and not y.e.out and not y.e.pending
    assert y.d.state['zoom']==1.7 and y.d.state['orbit']==[0,38,0] and not y.d.state['rotating']
    record['state']['epoch']+=1;assert not restore_engine(y.e,record,y.t)

def test_maintenance_waits_for_hand_startup_before_restoring_calibration():
    from core.maintenance_resume import restore_engine
    x=locked();record={'state':x.e.snapshot(x.t)};y=Driver()
    y.e.broken=['hand'];assert not restore_engine(y.e,record,y.t)
    assert not y.e.calibrated
    y.e.broken=[];assert restore_engine(y.e,record,y.t) and y.e.calibrated
