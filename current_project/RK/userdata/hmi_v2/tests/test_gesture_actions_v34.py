from core.config import load
from core.interaction.engine import Engine
from core.interaction.fist_latch import FistLatch
from tests.test_interaction import healthy,observation,message
from ui.feedback import feedback


def test_thumb_at_observed_confidence_needs_fist_and_full_hold():
    latch=FistLatch(load()['gestures']);t=10**10;seq=0
    def step(name,score,count):
        nonlocal t,seq
        commits=[]
        for _ in range(count):
            t+=100_000_000;seq+=1
            commits+=latch.observe(observation(t,seq,name,score),t)
        return commits
    assert not step('Thumb_Up',.64,12)
    assert not step('Closed_Fist',.9,5)
    assert not step('Thumb_Up',.64,3)
    assert step('Thumb_Up',.64,5)==[(1,'end','Thumb_Up')]
    assert not step('Thumb_Up',.64,15)
    assert not step('Closed_Fist',.9,5)
    assert not step('Thumb_Up',.49,12)
    assert not step('Victory',.59,12)


def test_onboard_thumb_rejection_explains_calibration_readiness():
    e=Engine(load());t=10**10;healthy(e,t);e._state('ONBOARD',t)
    e.event('end','Thumb_Up',t,t)
    assert '尚未开始标定' in e.toast and not e.out


def stroke_engine(context='DEMO'):
    e=Engine(load());t=10**10;healthy(e,t);e.context=context
    hands=observation(t,1,'Closed_Fist');hands['recorder']={'1':{'state':'RESULT'}}
    hands['hands'][0].update(side='Right',side_score=.99)
    e.feed('vision.hands',hands,t)
    assert e.state=='WRITING'
    return e,t


def test_unmapped_stroke_has_explicit_context_feedback_and_no_action():
    e,t=stroke_engine('DESKTOP')
    e.feed('vision.stroke',message(t+1,track_id=1,label='L',confidence=.99,accepted=True),t+1)
    assert e.stroke['label']=='L' and not e.out
    assert '桌面未绑定此轨迹' in e.toast
    assert '桌面' in feedback(e.snapshot(t+1))['person']


def test_bound_stroke_emits_once_and_reports_actual_ack():
    e,t=stroke_engine()
    msg=message(t+1,track_id=1,label='L',confidence=.99,accepted=True)
    e.feed('vision.stroke',msg,t+1);e.feed('vision.stroke',msg,t+2)
    assert not e.out and e.stroke_confirm.pending
    for i,name in enumerate(['Open_Palm']*2+['Closed_Fist']*8):
        now=t+100_000_000*(i+1);healthy(e,now)
        h=observation(now,i+2,name);h['hands'][0].update(track_id=2,side='Left',side_score=.99)
        e.feed('vision.hands',h,now)
    assert len(e.out)==1 and e.out[0]['name']=='demo.zoom_in'
    assert e.out[0]['src_ns']>msg['src_ns'] and e.out[0]['stroke_source']['source_ns']==msg['src_ns']
    e.feed('hmi.ack',message(now+1,id=e.out[0]['id'],ok=True),now+1)
    assert e.toast=='已执行：放大'


def test_same_hand_and_preheld_opposite_fist_cannot_confirm():
    from core.interaction.stroke_confirm import StrokeConfirm
    gate=StrokeConfirm(load()['gestures']);t=10**10
    source=dict(track_id=1,side='Right',side_score=.99)
    assert gate.begin(message(t,label='L'),'demo.zoom_in',source,(7,'DEMO'),t)
    for key,side in [(1,'Right'),(3,'Right'),(2,'Left')]:
        for i in range(10):
            t+=100_000_000;m=observation(t,t,'Closed_Fist');m['hands'][0].update(track_id=key,side=side,side_score=.99)
            assert not gate.observe(m,m['hands'],t)


def test_cancel_timeout_epoch_and_context_clear_proposal_without_actions():
    for mode in ('cancel','timeout','epoch','context'):
        e,t=stroke_engine();e.feed('vision.stroke',message(t+1,track_id=1,label='L',confidence=.99,accepted=True),t+1)
        assert e.stroke_confirm.pending
        if mode=='cancel':e.event('cancel','button',t+2,t+2)
        elif mode=='timeout':healthy(e,t+31_000_000_000);e.tick(t+31_000_000_000)
        elif mode=='epoch':e.feed('sys.metrics',dict(message(t+2,producer='fpga-io',ok=True),epoch=8),t+2)
        else:e.context='GAME';e.tick(t+2)
        assert not e.stroke_confirm.pending and not e.out


def test_low_confidence_stroke_is_not_called_confirmed():
    e,t=stroke_engine()
    e.feed('vision.stroke',message(t+1,track_id=1,label='L',confidence=.49,accepted=True),t+1)
    assert not e.out and '置信度不足' in e.toast
