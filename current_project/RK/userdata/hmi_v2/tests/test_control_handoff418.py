from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from tests.test_locked_rotation295 import locked, ack
from tests.test_dual_zoom_v95 import hands
from tests.test_interaction import healthy, message
from tests.test_gesture_trajectory import result
from vision.bootstrap import install_vendor_resolver
from vision.gesture_flow import GestureTrajectory


def pair(x, count):
    for _ in range(count):
        x.t+=50_000_000;x.seq+=1;healthy(x.e,x.t)
        rows=hands()
        rows[0]['track_id']=2;rows[1]['track_id']=1
        x.e.feed('vision.hands',message(x.t,x.seq,hands=rows),x.t)


@pytest.mark.parametrize('frames',[1,2])
def test_brief_dual_index_does_not_erase_locked_rotation_proposal(frames):
    x=locked();x.e.bindings['static']['DEMO']['Victory']='demo.rotate'
    pointer=deepcopy(x.e.cursor)
    x.frames('Closed_Fist');x.frames('Victory')
    pending=deepcopy(x.e.shortcut);generation=x.e.gesture_generation
    pair(x,frames)
    assert x.e.shortcut==pending and x.e.gesture_generation==generation
    assert not x.e.out
    x.frames('Closed_Fist');ack(x)
    assert [a['name'] for a in x.e.out]==['demo.rotate']
    assert x.d.state['rotating'] and x.e.cursor==pointer


def test_third_dual_index_frame_replaces_proposal_once_without_click():
    x=locked();x.e.bindings['static']['DEMO']['Victory']='demo.rotate'
    x.frames('Closed_Fist');x.frames('Victory');pair(x,3)
    assert x.e.shortcut is None and x.e.zoom.active
    assert [a['name'] for a in x.e.out]==['demo.zoom']
    ack(x);pair(x,3)
    assert len(x.e.out)==1


@pytest.mark.parametrize('engine_preparing',[False,True])
def test_recorder_pauses_incomplete_zoom_instead_of_losing_stroke(engine_preparing):
    install_vendor_resolver();flow=GestureTrajectory()
    state=dict(state='WRITING',context='DEMO',epoch=7,active_hand_ids=[9,10])
    for i,pose in enumerate(['Closed_Fist']*4+['Pointing_Up']*8):
        flow.update(result(pose),i+1,10+i*.1,10+i*.1,640,360,state)
    recorder=flow.recorders[9];assert recorder.state=='REC'
    both=result('Pointing_Up');left=result('Pointing_Up',x=.7,track=10)
    both.track_ids+=left.track_ids;both.hand_landmarks+=left.hand_landmarks
    both.gestures+=left.gestures;both.handedness+=[[NS(category_name='Left',score=.95)]]
    if engine_preparing:state['zoom_control']={'preparing':True,'active':False}
    assert flow.update(both,13,11.2,11.2,640,360,state)==[]
    assert flow.recorders.get(9) is recorder and recorder.state=='REC'
    state['zoom_control']={'preparing':False,'active':False}
    flow.update(result('Pointing_Up'),14,11.3,11.3,640,360,state)
    assert flow.recorders.get(9) is recorder and recorder.state=='REC'
    state['zoom_control']={'active':True};state['gesture_generation']=1
    assert flow.update(both,15,11.4,11.4,640,360,state)==[] and not flow.recorders
