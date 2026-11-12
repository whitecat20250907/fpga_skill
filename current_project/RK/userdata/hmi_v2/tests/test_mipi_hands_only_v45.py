from copy import deepcopy
import pytest
from ui.mipi_composer import compose
from ui.hand_slots import DisplayHandSlots
from hft2_wire import decode
from tests.test_mipi_observation import sample, STAMP


@pytest.mark.parametrize('profile',['legacy','theater'])
def test_hands_and_trace_render_with_eye_service_paused(profile):
    state,face,hands=sample(layer='WRITE',writing={'state':'REC'},active_hand_ids=[1,2])
    hands['seq']=21
    hands['hands'][0].update(gesture='Victory',score=.9)
    right=deepcopy(hands['hands'][0]);right.update(track_id=2,side='Right')
    hands['hands'].append(right)
    hands['recorder']={'2':{'state':'REC','points':[[100,100],[150,100],[150,200]]}}
    result=decode(compose(state,None,hands,STAMP,1,profile,DisplayHandSlots())[0])
    scene=result['scene'];meta=result['metadata']
    assert scene.valid==19  # Both hands plus trace, no face or gaze.
    assert len(scene.vertices)==45 and meta.trajectory_points==3
    assert scene.face_timestamp_ns==0 and scene.hand_timestamp_ns==STAMP
    assert scene.capture_sequence==21
    assert meta.actor_track_id==0xfffffffe and meta.association_flags==7
    assert not meta.ui_status & (7<<13)
    assert (meta.ui_status>>4)&15


def test_hands_only_stale_epoch_and_assignment_still_apply():
    state,face,hands=sample(active_hand_ids=[1])
    render=lambda h:decode(compose(state,None,h,STAMP,1)[0])['scene'].valid
    assert render(hands)==1
    assert render(dict(hands,src_ns=STAMP-351_000_000))==0
    assert render(dict(hands,epoch=8))==0
    state['active_hand_ids']=[]
    assert render(hands)==0
    state.update(people='dual',active_hand_ids=[1])
    assert render(hands)==0


def test_face_pause_and_resume_do_not_reset_anatomical_display_slots():
    state,face,hands=sample(active_hand_ids=[1]);slots=DisplayHandSlots()
    first=decode(compose(state,face,hands,STAMP,1,slotter=slots)[0])
    assert first['scene'].valid==5
    hands['hands'][0].update(side='Right',side_score=.51)
    paused=decode(compose(state,None,hands,STAMP+1,2,slotter=slots)[0])
    resumed=decode(compose(state,face,hands,STAMP+2,3,slotter=slots)[0])
    assert paused['scene'].valid==1 and resumed['scene'].valid==5
