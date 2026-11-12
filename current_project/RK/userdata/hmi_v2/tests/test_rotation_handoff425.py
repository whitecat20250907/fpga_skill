from copy import deepcopy
import pytest
from tests.test_locked_rotation295 import locked, ack
from ui.feedback import feedback


def spinning():
    x=locked();x.frames('Closed_Fist')
    x.e.input_hand=1;x.e.input_side='Right'
    assert x.e._action('demo.rotate','stroke',x.t,x.t)
    x.e.out[-1]['confirmation']='trajectory_fist';ack(x)
    x.e.input_hand=x.e.input_side=None;x.t=x.d.rotation_tick
    x.frames('Closed_Fist',1)
    return x


@pytest.mark.parametrize('phase',['POINTING','CALIBRATING'])
def test_eye_selection_or_calibration_stops_rotation_without_moving_pointer(phase):
    x=spinning();state=x.e.snapshot(x.t);state['state']=phase
    pointer=deepcopy(x.e.cursor);orbit=deepcopy(x.d.state['orbit'])
    x.d.tick(x.t,state)
    assert not x.d.state['rotating']
    assert x.d.state['orbit']==orbit and x.e.cursor==pointer


def test_locked_target_does_not_hide_arm_progress():
    x=locked();x.frames('Closed_Fist')
    state=x.e.snapshot(x.t)
    assert state['gesture']['phase']=='ARMED'
    assert feedback(state)['title']=='手势识别已开启'


def test_zoom_feedback_has_priority_over_locked_target():
    x=locked();state=x.e.snapshot(x.t)
    state['zoom_control']={'active':True,'ratio':1.75}
    f=feedback(state)
    assert f['title']=='双指缩放' and '1.75' in f['hint']


def test_old_observation_cannot_keep_rotation_running():
    x=spinning();state=x.e.snapshot(x.t)
    for i in range(1,10):
        now=x.t+i*100_000_000;state['src_ns']=now
        x.d.tick(now,state)
    assert not x.d.state['rotating']


def test_recycled_track_id_on_other_side_cannot_own_rotation():
    x=spinning()
    for i in range(1,9):
        now=x.t+i*100_000_000;state=x.e.snapshot(x.t)
        state.update(src_ns=now,hand_src_ns=now)
        state['hand_observations']=[dict(track_id=1,side='Left',gesture='Closed_Fist',score=.9)]
        x.d.tick(now,state)
    assert not x.d.state['rotating']


def test_same_side_track_recovery_and_locked_rotation_remain_available():
    x=spinning();pointer=deepcopy(x.e.cursor)
    start=x.d.state['orbit'][1]
    for i in range(1,9):
        now=x.t+i*100_000_000;state=x.e.snapshot(x.t)
        state.update(src_ns=now,hand_src_ns=now)
        state['hand_observations']=[dict(track_id=17,side='Right',gesture='Closed_Fist',score=.9)]
        x.d.tick(now,state)
    assert x.d.state['rotating'] and x.d.state['orbit'][1]>start
    assert x.e.cursor==pointer and x.d.rotation_hand['track_id']==17
