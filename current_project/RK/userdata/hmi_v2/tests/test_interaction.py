import random
import pytest
from core.config import load
from core.interaction.engine import Engine
from core.interaction.latch import Latch

def message(t,seq=1,**kw):return dict(epoch=7,seq=seq,src_ns=t,pub_ns=t,v=1,**kw)
def healthy(e,t):
    for p in ['fpga-io',*sorted(e.required-{'fpga-io'})]:e.feed('sys.metrics',message(t,producer=p,ok=True),t)
    e.tick(t)
def gaze(e,t,seq=1,valid=True):e.feed('vision.gaze',message(t,seq,track_id=e.people.slots[e.people.active],valid=valid,filtered_xy=[100,100],screen_size=[1920,1080],calib={'done':True}),t)
def catalog(e,t,targets=None):
    e.feed('app.targets',message(t,context=e.context,screen_size=[1920,1080],targets=targets or [dict(id='test:button',label='测试按钮',rect=[80,80,40,40],confidence=1.,action=e.context.lower()+'.click')]),t)

def face(e,t,seq):e.feed('vision.face',message(t,seq,faces=[dict(track_id=11,primary=True,valid=True,face_rect=[240,130,160,100],can_gaze=True)]),t)

def test_ack_feedback_names_the_original_action_not_an_arbitrary_ack_field():
    e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e._state('IDLE',t)
    e._action('demo.next','Victory',t,t)
    action=e.out[-1]
    e.feed('hmi.ack',message(t+1,id=action['id'],ok=True,name='game.end'),t+1)
    assert e.toast=='已执行：下一页'
    e.feed('hmi.ack',message(t+2,id=action['id'],ok=False,detail='old duplicate'),t+2)
    assert e.toast=='已执行：下一页'

def test_onboarding_calibration_point_confirm():
    e=Engine(load());t=10**10;healthy(e,t)
    assert e.state=='STANDBY'
    e.system('calibrate',t)
    face(e,t,1);e.tick(t)
    for i in range(1,15):
        now=t+i*100_000_000;healthy(e,now);face(e,now,i+1);e.tick(now)
    assert e.state=='CALIBRATING'
    for i in range(15,22):
        now=t+i*100_000_000;healthy(e,now);face(e,now,i+1);e.tick(now)
    e.event('end','Thumb_Up',now,now);assert e.state=='CALIBRATING'
    e.feed('vision.gaze',message(now+1,track_id=11,phase='READY',calib={'done':True},calibration_request=e.calibration_request),now+1)
    e.event('end','Thumb_Up',now+1,now+1);assert e.state=='IDLE'
    e.event('wake','Pointing_Up',now+2,now+2);assert e.state=='POINTING'
    for i in range(4):
        stamp=now+3+i*30_000_000;catalog(e,stamp);gaze(e,stamp,i+2);e.tick(stamp)
    now=stamp;e.event('confirm','Closed_Fist',now+1,now+1)
    assert e.state=='IDLE' and [m['name'] for m in e.out]==['demo.wake']
    assert e.target_session['phase']=='LOCKED' and e.snapshot(now+4)['budget']['gaze_hz']==0

@pytest.mark.parametrize('age',[250_000_001,350_000_001,2_100_000_000])
def test_stale_gaze_no_confirmation(age):
    e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e._state('IDLE',t);gaze(e,t)
    e.event('wake','Pointing_Up',t,t);e.out.clear();healthy(e,t+age)
    e.event('confirm','Closed_Fist',t+age,t+age);assert not e.out

def test_any_service_loss_and_epoch_stop_actions():
    e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e._state('IDLE',t)
    e.feed('sys.metrics',message(t+1,producer='hand',ok=False),t+1)
    e.event('next','Victory',t+1,t+1);assert e.state=='DEGRADED' and not e.out
    healthy(e,t+2);assert e.state=='STANDBY' and e.calibrated
    e.feed('sys.metrics',dict(message(t+3,producer='fpga-io',ok=True),epoch=8),t+3)
    assert not e.calibrated and not e.latest

def observation(t,seq,gesture='None',score=.9,second=None):
    hands=[dict(track_id=1,gesture=gesture,score=score)]
    if second:hands.append(dict(track_id=2,gesture=second,score=score))
    return message(t,seq,hands=hands)
def test_latch_neutral_hold_once_release():
    l=Latch(load()['gestures']);t=10**10
    for i in range(5):assert not l.observe(observation(t+i*100_000_000,i),t+i*100_000_000)
    got=[]
    for i in range(5,20):got+=l.observe(observation(t+i*100_000_000,i,'Pointing_Up'),t+i*100_000_000)
    assert [x[1] for x in got]==['wake']
    assert not l.observe(observation(t+2_000_000_000,21,'Closed_Fist'),t+2_000_000_000)

def test_conflict_resolved_before_commit():
    l=Latch(load()['gestures']);t=10**10
    for i in range(5):l.observe(observation(t+i*100_000_000,i,second='None'),t+i*100_000_000)
    got=[];conflict=False
    for i in range(5,15):
        got+=l.observe(observation(t+i*100_000_000,i,'Pointing_Up',second='Thumb_Down'),t+i*100_000_000);conflict|=l.conflict
    assert conflict and not got

def test_duplicate_disarms_and_write_owns_fist():
    l=Latch(load()['gestures']);t=10**10
    for i in range(5):l.observe(observation(t+i*100_000_000,i),t+i*100_000_000)
    m=observation(t+500_000_000,5,'Closed_Fist');l.observe(m,m['src_ns']);l.observe(m,m['src_ns']);assert not l.hands
    for i in range(6,30):assert not l.observe(observation(t+i*100_000_000,i,'Closed_Fist'),t+i*100_000_000,'WRITE')

def test_random_events_100000_safe():
    e=Engine(load());rng=random.Random(712);t=10**10
    for i in range(100000):
        t+=1_000_000
        if i%500==0:healthy(e,t)
        if rng.random()<.002:e.feed('sys.metrics',message(t,producer='hand',ok=False),t)
        e.event(rng.choice(['wake','confirm','cancel','next','end','sleep','menu']),'test',t,t)
        e.tick(t)
        assert e.state!='POINTING' or e.calibrated
        if not e.calibrated or e.state=='DEGRADED':assert not e.out
        e.out.clear();e.commands.clear()

def test_estop_stays_stopped_until_resume():
    e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e._state('IDLE',t);e.system('estop',t)
    for i in range(1,30):
        now=t+i*100_000_000;healthy(e,now);face(e,now,i);e.tick(now)
        assert e.state=='STANDBY' and not e.out
