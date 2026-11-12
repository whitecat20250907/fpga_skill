from ui.mipi_composer import compose
from ui.hand_slots import DisplayHandSlots
from hft2_wire import decode
from tests.test_mipi_observation import sample,STAMP


def test_held_static_gesture_remains_visible_after_action_latch_consumed():
    state,face,hands=sample(gesture={})
    hands['hands'][0].update(gesture='Victory',score=.91)
    for seq in range(1,5):
        meta=decode(compose(state,face,hands,STAMP,seq)[0])['metadata']
        assert (meta.ui_status>>4)&15==4
    assert not state.get('history')


def test_fist_preparation_does_not_select_trajectory_page_until_index():
    state,face,hands=sample(writing={'state':'ARMED'})
    hands['hands'][0].update(gesture='Closed_Fist',score=.9)
    meta=decode(compose(state,face,hands,STAMP,1)[0])['metadata']
    assert (meta.ui_status>>4)&15==1 and not meta.ui_status&(1<<16)
    state['writing']['state']='COUNTDOWN'
    assert decode(compose(state,face,hands,STAMP,2)[0])['metadata'].ui_status&(1<<16)


def test_right_hand_label_jitter_never_removes_existing_geometry():
    tracker=DisplayHandSlots();left=dict(track_id=1,side='Left',side_score=.99)
    right=dict(track_id=2,side='Right',side_score=.97)
    context=(7,'single',1,10)
    assert tracker.select([right,left],STAMP,context)==[(0,left),(1,right)]
    jitter=dict(right,side='Left',side_score=.51)
    assert tracker.select([jitter,left],STAMP+100_000_000,context)==[(0,left),(1,jitter)]
    assert tracker.select([left],STAMP+200_000_000,context)==[(0,left)]  # No stale right pose.
    assert tracker.select([left,jitter],STAMP+300_000_000,context)==[(0,left),(1,jitter)]
    assert tracker.select([jitter],STAMP+700_000_000,context)==[]  # Expired labels are not replayed.
    assert tracker.select([dict(right,side='Left')],STAMP+800_000_000,(8,'single',1,10))[0][0]==0
