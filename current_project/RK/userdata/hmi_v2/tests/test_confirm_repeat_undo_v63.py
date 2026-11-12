from copy import deepcopy
from core.config import load
from core.interaction.repeat_cycle import RepeatCycle
from tests.test_stroke_confirm_v37 import gate,step
from tests.test_gesture_actions_v34 import stroke_engine
from tests.test_interaction import healthy,message,observation
from adapters.demo import DemoAdapter
import pytest


def test_prepared_opposite_thumb_down_cancels_stroke_without_action():
    e,t=stroke_engine()
    e.feed('vision.stroke',message(t+1,track_id=1,label='L',confidence=.99,accepted=True),t+1)
    assert e.stroke_confirm.pending
    for i,name in enumerate(['Open_Palm']+['Thumb_Down']*12):
        now=t+(i+1)*100_000_000;healthy(e,now)
        m=observation(now,i+10,name);m['hands'][0].update(track_id=2,side='Left',side_score=.99)
        e.feed('vision.hands',m,now)
        if not e.stroke_confirm.pending:break
    assert not e.stroke_confirm.pending and not e.out
    assert e.toast=='已取消当前操作；没有可撤回的已执行动作'


def test_same_drawing_hand_cannot_cancel_other_hand_confirmation():
    g,t=gate();step(g,t+1,'Open_Palm',key=1,side='Right')
    for i in range(1,12):step(g,t+i*100_000_000,'Thumb_Down',key=1,side='Right')
    assert not g.pending.get('cancelled')


def test_thumb_down_cancellation_has_visible_progress():
    g,t=gate();step(g,t+1,'Open_Palm',key=2,side='Left')
    step(g,t+100_000_000,'Thumb_Down',key=2,side='Left')
    step(g,t+200_000_000,'Thumb_Down',key=2,side='Left')
    assert g.pending['reason']=='holding_cancel'
    assert 0<g.pending['progress']<1


def cycle():
    r=RepeatCycle(load()['gestures']);t=10**10
    a=dict(id='test1',name='demo.zoom_in',gesture='stroke',args={},confirmation='opposite_hand')
    r.begin(a,2,'Left',(7,'DEMO'),t);r.acknowledge('test1',True)
    return r,t


def observe(r,t,seq,name,key=2):
    m=observation(t,seq,name);m['hands'][0].update(track_id=key,side='Left')
    return r.observe(m,m['hands'],t,(7,'DEMO'))


@pytest.mark.parametrize('pose,event',[('Closed_Fist','repeat'),('Thumb_Down','undo')])
def test_repeat_or_undo_requires_palm_and_is_one_shot(pose,event):
    r,t=cycle()
    for i in range(10):assert not observe(r,t+i*100_000_000,i,pose)
    observe(r,t+1_000_000_000,10,'Open_Palm')
    got=[observe(r,t+i*100_000_000,i,pose) for i in range(11,26)]
    assert got.count(event)==1


def test_hand_disappearance_context_change_and_failed_ack_end_cycle():
    r,t=cycle();observe(r,t+1,1,'Open_Palm')
    observe(r,t+700_000_000,2,'Closed_Fist',key=3)
    assert r.session is None
    r,t=cycle();m=observation(t+1,1,'Open_Palm')
    r.observe(m,m['hands'],t+1,(7,'GAME'));assert r.session is None
    r,t=cycle();r.session['pending_id']='again';r.acknowledge('again',False);assert r.session is None


def test_medical_undo_restores_exact_view_including_clamped_zoom_and_page():
    d=DemoAdapter();d.state.update(zoom=2.5,focus=True,part='test',orbit=[12,34,56])
    before=deepcopy(d.state)
    d.on_action(dict(id='a',name='demo.next',args={}))
    d.on_action(dict(id='b',name='demo.undo',args={'undo_id':'a'}))
    for k in ('page','zoom','focus','part','orbit','inspection','crosshair'):assert d.state[k]==before[k]
    assert d.state['revision']==before['revision']+2 and not d.state['rotating']
    with pytest.raises(ValueError):d.on_action(dict(id='c',name='demo.undo',args={'undo_id':'a'}))


def test_undo_cannot_restore_over_an_intervening_action():
    d=DemoAdapter()
    d.on_action(dict(id='a',name='demo.zoom_in',args={}))
    d.on_action(dict(id='b',name='demo.zoom_out',args={}))
    with pytest.raises(ValueError):d.on_action(dict(id='c',name='demo.undo',args={'undo_id':'a'}))


def test_stroke_confirm_repeat_and_undo_end_to_end():
    e,t=stroke_engine();e.feed('vision.stroke',message(t+1,track_id=1,label='L',confidence=.99,accepted=True),t+1)
    seq=20
    def poses(names):
        nonlocal t,seq
        for name in names:
            t+=100_000_000;seq+=1;healthy(e,t)
            m=observation(t,seq,name);m['hands'][0].update(track_id=2,side='Left',side_score=.99)
            e.feed('vision.hands',m,t)
    poses(['Open_Palm']+['Closed_Fist']*10)
    assert len(e.out)==1 and e.repeat.session['hand']==2
    original=e.out[-1];e.feed('hmi.ack',message(t+1,id=original['id'],ok=True),t+1)
    poses(['Open_Palm']+['Closed_Fist']*10)
    assert len(e.out)==2 and e.out[-1]['confirmation']=='opposite_hand'
    repeated=e.out[-1];assert repeated['id']!=original['id']
    e.feed('hmi.ack',message(t+1,id=repeated['id'],ok=True),t+1)
    poses(['Open_Palm']+['Thumb_Down']*12)
    assert len(e.out)==3 and e.out[-1]['name']=='demo.undo'
    assert e.out[-1]['args']['undo_id']==repeated['id']


def test_ack_timeout_releases_repeat_hand_without_replaying_action():
    e,t=stroke_engine();e._state('ONBOARD',t)
    e.input_hand=2;e.input_side='Left'
    assert e._action('demo.zoom_in','Victory',t,t)
    e.input_hand=None;e.input_side=None
    action=e.out[-1]
    assert e.repeat.session
    for i in range(1,13):
        now=t+i*100_000_000;healthy(e,now)
        m=observation(now,i+10,'Open_Palm');m['hands'][0].update(track_id=2,side='Left')
        e.feed('vision.hands',m,now);e.tick(now)
    assert not e.repeat.session and len(e.out)==1 and not e.pending
    e.feed('hmi.ack',message(now+1,id=action['id'],ok=True),now+1)
    assert not e.repeat.session and len(e.out)==1


@pytest.mark.parametrize('target',['system.eye_takeover','system.menu'])
def test_system_stroke_never_reuses_queued_action_as_repeat(target):
    e,t=stroke_engine();e.calibrated=True;e.confirmed_calibration=True
    e.bindings['stroke']['DEMO']['L']=target
    # A previously queued action must retain its metadata even when a system
    # command adds no application action to the queue.
    e._action('demo.zoom_in','console',t,t);old=deepcopy(e.out[-1])
    e.feed('vision.stroke',message(t+1,track_id=1,label='L',confidence=.99,accepted=True),t+1)
    assert e.stroke_confirm.pending
    for i,name in enumerate(['Open_Palm']+['Closed_Fist']*10):
        now=t+(i+1)*100_000_000;healthy(e,now)
        m=observation(now,i+10,name);m['hands'][0].update(track_id=2,side='Left',side_score=.99)
        e.feed('vision.hands',m,now)
    assert not e.repeat.session
    assert e.out[0]==old
    assert e.state==('POINTING' if target=='system.eye_takeover' else 'MENU')
