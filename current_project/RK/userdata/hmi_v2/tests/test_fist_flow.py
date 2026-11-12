from tests.test_interaction import catalog
from core.config import load
from core.interaction.fist_latch import FistLatch
from core.interaction.engine import Engine
from adapters.policy import ActionGate
from tests.test_interaction import healthy,observation,message
from tests.test_mipi_observation import sample,scene,STAMP
from ui.hand_slots import hand_slots
from ui.feedback import feedback


def frames(latch,name,start,seq,count=12,**kw):
    out=[]
    for i in range(count):
        t=start+i*100_000_000
        out+=latch.observe(observation(t,seq+i,name),t,**kw)
    return out


def test_fist_is_required_and_one_static_action_consumes_it():
    latch=FistLatch(load()['gestures']);t=10**10
    assert not frames(latch,'Victory',t,1)
    assert not frames(latch,'Closed_Fist',t+1_200_000_000,13,count=5)
    assert latch.progress[1]['phase']=='ARMED'
    assert frames(latch,'Victory',t+1_700_000_000,18)==[(1,'next','Victory')]
    assert not frames(latch,'Thumb_Up',t+2_900_000_000,30)


def test_point_after_fist_does_not_click_or_emit_static_wake():
    latch=FistLatch(load()['gestures']);t=10**10
    frames(latch,'Closed_Fist',t,1,count=5)
    assert not frames(latch,'Pointing_Up',t+500_000_000,6)
    assert latch.progress[1]['phase']=='TRAJECTORY'
    assert not frames(latch,'Closed_Fist',t+1_700_000_000,18,layer='WRITE',confirming=True)


def test_modal_fist_confirmation_happens_once_and_stale_disarms():
    latch=FistLatch(load()['gestures']);t=10**10
    assert frames(latch,'Closed_Fist',t,1,confirming=True)==[(1,'confirm','Closed_Fist')]
    assert not latch.observe(observation(t,1,'Victory'),t+2_000_000_000)
    assert not frames(latch,'Victory',t+2_100_000_000,14)


def test_open_menu_navigation_and_calibration_cancel_need_no_new_arming_fist():
    latch=FistLatch(load()['gestures']);t=10**10
    assert frames(latch,'Victory',t,1,confirming=True)==[(1,'next','Victory')]
    assert frames(latch,'Closed_Fist',t+1_200_000_000,13,confirming=True)==[(1,'confirm','Closed_Fist')]
    assert frames(latch,'Open_Palm',t+2_400_000_000,25,calibrating=True)==[(1,'sleep','Open_Palm')]


def test_uncalibrated_fist_static_is_executable_without_any_face():
    e=Engine(load());t=10**10;healthy(e,t);accepted=False
    for i,name in enumerate(['Closed_Fist']*5+['Victory']*8):
        now=t+i*100_000_000;healthy(e,now)
        e.feed('vision.hands',observation(now,i+1,name),now)
        if e.out and not accepted:accepted=ActionGate().accept(e.out[0],e.snapshot(now),now)[0]
    assert not e.calibrated
    assert len(e.out)==1 and e.out[0]['name']=='demo.next'
    assert accepted


def test_automatic_stroke_entry_and_result_before_eye_calibration():
    e=Engine(load());t=10**10;healthy(e,t)
    hands=observation(t,1,'Pointing_Up');hands['recorder']={'1':{'state':'COUNTDOWN','remaining_s':1}}
    e.feed('vision.hands',hands,t)
    assert e.state=='WRITING' and not e.calibrated
    hands=observation(t+1,2,'Closed_Fist');hands['recorder']={'1':{'state':'RESULT'}}
    hands['hands'][0].update(side='Right',side_score=.99)
    e.feed('vision.hands',hands,t+1)
    e.feed('vision.stroke',message(t+2,track_id=1,label='L',confidence=.9,accepted=True),t+2)
    assert e.stroke['label']=='L' and not e.out and e.stroke_confirm.pending
    e.event('cancel','button',t+2,t+2)
    e.feed('vision.hands',observation(t+3,3,'None'),t+3)
    assert e.layer=='POINT' and e.state=='ONBOARD'


def test_left_right_slots_survive_reordering_and_single_right_hand():
    left={'track_id':1,'side':'Left'};right={'track_id':2,'side':'Right'}
    assert hand_slots([right,left])==[(0,left),(1,right)]
    assert hand_slots([right])==[(1,right)]
    assert not hand_slots([left,dict(left,track_id=3)])
    state,face,hands=sample();hands['hands'][0]['side']='Right'
    assert scene(state,face,hands)['scene'].valid==6


def test_old_mipi_protocol_shows_uncalibrated_trace_and_real_result():
    state,face,hands=sample(layer='WRITE',state='WRITING',writing={'state':'RESULT'},
        stroke={'label':'L','accepted':True,'confidence':.85},gesture={'name':'Closed_Fist'})
    hands['recorder']={'1':{'state':'RESULT','points':[[100,100],[200,200],[300,100]]}}
    decoded=scene(state,face,hands);meta=decoded['metadata']
    assert decoded['scene'].valid&16 and meta.trajectory_points==3
    assert meta.ui_status&15==3 and (meta.ui_status>>4)&15==1
    assert (meta.ui_status>>8)&15==1 and meta.ui_status&(1<<12)
    assert not meta.ui_status&(7<<13)
    assert '伸食指' in feedback({'state':'ONBOARD','gesture':{'phase':'ARMED','progress':1}})['hint']


def test_pointer_command_needs_gaze_but_never_steals_pointing_from_trajectory():
    from tests.test_interaction import gaze
    e=Engine(load());t=10**10;healthy(e,t);e.system('pointer',t)
    assert e.state!='POINTING' and not e.out
    e.calibrated=True;e._state('IDLE',t);gaze(e,t)
    e.system('pointer',t)
    assert e.state=='POINTING' and not e.cursor['valid']
    for i in range(4):
        now=t+1+i*30_000_000;catalog(e,now);gaze(e,now,i+2);e.tick(now)
    assert e.cursor['valid']


def test_gesture_menu_can_navigate_and_confirm_after_fist_prefix():
    e=Engine(load());t=10**10;healthy(e,t)
    names=['Closed_Fist']*5+['ILoveYou']*12+['Victory']*7+['Closed_Fist']*8
    for i,name in enumerate(names):
        now=t+i*100_000_000;healthy(e,now)
        e.feed('vision.hands',observation(now,i+1,name),now)
    assert e.context=='GAME' and e.application_request['context']=='GAME'
    assert not e.out  # Opening an app does not execute an application action.
