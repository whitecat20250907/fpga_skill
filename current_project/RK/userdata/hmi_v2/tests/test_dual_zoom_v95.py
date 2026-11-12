from copy import deepcopy
import math
import pytest
from core.config import load
from core.bindings import options,validate
from core.interaction.dual_zoom import DualZoom
from core.interaction.engine import Engine
from adapters.demo import DemoAdapter
from adapters.policy import ActionGate
from tests.test_interaction import healthy,message


def hands(distance=.4,pose='Pointing_Up'):
    rows=[]
    for i,side in enumerate(('Left','Right')):
        points=[[.3+i*distance,.5,0] for _ in range(21)]
        rows.append(dict(track_id=i+1,side=side,side_score=.9,gesture=pose,score=.9,image21=points,in_bounds=True))
    return rows


class Run:
    def __init__(self):
        self.e=Engine(load());self.d=DemoAdapter();self.d.state['page']=2;self.t=10**10;self.seq=0
        healthy(self.e,self.t);self.e._state('ONBOARD',self.t)
    def feed(self,distance=.4,rows=None):
        self.t+=50_000_000;self.seq+=1;healthy(self.e,self.t)
        self.e.feed('vision.hands',message(self.t,self.seq,hands=hands(distance) if rows is None else rows),self.t)
        self.d.tick(self.t,self.e.snapshot(self.t))
    def ack(self):
        a=self.e.out[-1];ok,reason=ActionGate().accept(a,self.e.snapshot(self.t),self.t);assert ok,reason
        self.d.on_action(a);self.e.feed('hmi.ack',message(self.t+1,id=a['id'],ok=True),self.t+1)
        return a
    def begin(self,distance=.4):
        for _ in range(3):self.feed(distance)
        assert self.e.zoom.active;return self.ack()


def test_exactly_three_distinct_frames_then_ratio_and_release_hold():
    r=Run();r.feed();r.feed();assert not r.e.out and not r.e.zoom.active
    r.feed();a=r.ack();assert a['confirmation']=='dual_index_sequence'
    for distance in [.5,.6,.4,.2]:
        r.feed(distance);assert r.d.state['zoom']==pytest.approx(distance/.4)
    assert len(r.e.out)==1
    r.feed(rows=[]);assert not r.e.zoom.active and r.d.state['zoom']==pytest.approx(.5)
    r.t+=10**10;r.d.tick(r.t,r.e.snapshot(r.t));assert r.d.state['zoom']==pytest.approx(.5)
    r.begin(.2);r.feed(.3);assert r.d.state['zoom']==pytest.approx(.75)


def test_zoom_is_one_undoable_action_and_repeats_final_ratio():
    r=Run();a=r.begin();r.feed(.6);r.feed(rows=[])
    assert r.e.last_action['args']['ratio']==pytest.approx(1.5)
    assert len(r.d.undo_history)==1
    r.e._repeat_last(r.t,r.t);b=r.ack();assert b['repeated_from']==a['id'] and r.d.state['zoom']==pytest.approx(2.25)
    r.e._undo_last(r.t,r.t);r.ack();assert r.d.state['zoom']==pytest.approx(1.5)
    r.e._undo_last(r.t,r.t);r.ack();assert r.d.state['zoom']==1


def test_missed_or_invalid_sample_restarts_three_frame_preparation():
    z=DualZoom();assert z.observe(hands(),100)=='prepare';assert z.observe(hands(),200)=='prepare'
    assert z.observe([],300) is None
    assert z.observe(hands(),400)=='prepare';assert z.observe(hands(),500)=='prepare';assert z.observe(hands(),600)=='start'
    rows=hands();rows[0]['image21'][8][0]=math.nan
    assert z.observe(rows,700)=='end' and not z.active


def test_duplicate_packet_cannot_count_toward_three_frames():
    r=Run();r.feed();m=deepcopy(r.e.latest['vision.hands'])
    for _ in range(9):r.e.feed('vision.hands',m,r.t)
    assert r.e.zoom.count==1 and not r.e.out


def test_bimanual_control_cancels_pending_static_and_old_trajectory():
    r=Run();r.e.shortcut={'label':'下一页','hand':2,'expires_ns':10**12};r.e.stroke_owner={'track_id':2};r.e._state('MENU',r.t)
    r.feed();r.feed();assert r.e.shortcut is not None and r.e.stroke_owner is not None and r.e.gesture_generation==0
    r.feed();assert r.e.shortcut is None and r.e.stroke_owner is None and r.e.gesture_generation==1
    r.ack();assert len(r.e.out)==1 and r.e.out[-1]['name']=='demo.zoom'


def test_stale_stream_freezes_size_without_replaying():
    r=Run();r.begin();r.feed(.6);r.t+=400_000_000;healthy(r.e,r.t);r.e.tick(r.t)
    assert not r.e.zoom.active;r.d.tick(r.t,r.e.snapshot(r.t));assert r.d.state['zoom']==pytest.approx(1.5)


def test_old_zoom_mappings_removed_without_resetting_other_choices():
    c=load()['bindings'];c['stroke']['DEMO']={'L':'demo.zoom_in','M':'demo.next','W':'demo.zoom_out'}
    migrated=validate(c)['stroke']['DEMO'];assert migrated=={'L':'','M':'demo.next','W':''}
    assert 'demo.zoom_in' not in options('DEMO') and 'demo.zoom_out' not in options('DEMO')
    with pytest.raises(ValueError):DemoAdapter().on_action({'name':'demo.zoom_in','id':'old','args':{}})


def test_render_model_comparison_keeps_all_legal_targets_clear_of_operation_hud():
    from core.targets import demo_targets,medical_spec
    assert len({r['rect'][1] for r in medical_spec()['pages'][0]['controls']})==1
    for page in range(4):
        for row in demo_targets({'page':page,'case_id':'case_00000','plane':'axial'},[1920,1080]):
            x,y,w,h=row['rect'];assert x+w<=1456 or y+h<=930 or x>=1896 or y>=1056


def test_zoom_hold_fist_does_not_arm_another_gesture():
    r=Run();r.begin();r.feed(.6)
    for _ in range(8):r.feed(rows=hands(pose='Closed_Fist'))
    assert len(r.e.out)==1 and not r.e.latch.progress


def test_ratio_is_not_old_step_zoom_or_old_scale_limit():
    r=Run();r.begin(.05);r.feed(.6);assert r.d.state['zoom']==pytest.approx(12.)
    r.feed(rows=[]);r.begin(.1);r.feed(.2);assert r.d.state['zoom']==pytest.approx(24.)


def test_two_right_hands_or_two_people_are_not_a_two_hand_pair():
    z=DualZoom();rows=hands();rows[0]['side']='Right'
    for t in range(1,6):assert z.observe(rows,t) is None
    assert not z.active


def test_record_confirmation_is_not_offered_twice():
    from core.targets import medical_rows
    assert any(r['key']=='record' for r in medical_rows({'page':3,'case_id':'case_00000'}))
    assert not any(r['key']=='record' for r in medical_rows({'page':3,'case_id':'case_00000','record':{'case_id':'case_00000'}}))


def test_local_trajectory_recorder_yields_before_engine_broadcast():
    from types import SimpleNamespace as NS
    from tests.test_gesture_trajectory import result
    from vision.bootstrap import install_vendor_resolver
    from vision.gesture_flow import GestureTrajectory
    install_vendor_resolver();flow=GestureTrajectory();state=dict(state='ONBOARD',context='DEMO',epoch=7,active_hand_ids=[9,10])
    for i in range(3):flow.update(result('Closed_Fist'),i+1,10+i*.1,10+i*.1,640,360,state)
    assert flow.recorders[9].state=='ARMED'
    both=result('Pointing_Up');left=result('Pointing_Up',x=.7,track=10)
    both.track_ids+=left.track_ids;both.hand_landmarks+=left.hand_landmarks;both.gestures+=left.gestures;both.handedness+=[[NS(category_name='Left',score=.95)]]
    assert flow.update(both,4,10.3,10.3,640,360,state)==[] and flow.recorders[9].state=='ARMED'
    state['zoom_control']={'active':True};state['gesture_generation']=1
    assert flow.update(both,5,10.4,10.4,640,360,state)==[] and not flow.recorders
