from tests.test_interaction import catalog
import pytest
from core.config import load
from core.interaction.engine import Engine
from core.manual_game import validate
from adapters.policy import ActionGate
from tests.test_interaction import healthy,message,gaze


def args(t):return dict(kind='click',window=12,rect=[0,0,1024,600],frame_ns=t,x=.4,y=.5,button=1)


def test_game_browser_input_uses_engine_and_gate_once_without_gaze():
    e=Engine(load());t=10**10;healthy(e,t);e.system('app_game',t)
    assert e.context=='GAME' and e.application_request['context']=='GAME'
    e.feed('cmd.system',message(t+1,command='game_input',args=args(t)),t+1)
    assert len(e.out)==1 and e.out[0]['confirmation']=='operator'
    gate=ActionGate();state=e.snapshot(t+1)
    assert gate.accept(e.out[0],state,t+1)[0]
    assert not gate.accept(e.out[0],state,t+1)[0]


def test_game_input_rejected_in_wrong_context_estop_or_pending_confirmation():
    for mode in ('DEMO','estop','writing'):
        e=Engine(load());t=10**10;healthy(e,t)
        if mode!='DEMO':e.system('app_game',t)
        if mode=='estop':e.system('estop',t)
        if mode=='writing':e._state('WRITING',t)
        e.feed('cmd.system',message(t+1,command='game_input',args=args(t)),t+1)
        assert not e.out


def test_game_input_accepts_only_bounded_coordinates_and_five_keys():
    t=10**10
    for change in ({'x':float('nan')},{'x':1.01},{'button':2},{'window':0},{'kind':'key','key':'Delete'}):
        with pytest.raises(ValueError):validate(dict(args(t),**change))
    assert validate(dict(args(t),kind='key',key='Escape'))


def test_pointer_command_wakes_real_game_before_gaze_confirmation():
    e=Engine(load());t=10**10;healthy(e,t);e.context='GAME';e.calibrated=True;e._state('IDLE',t);gaze(e,t)
    e.system('pointer',t)
    assert e.state=='POINTING' and e.out[-1]['name']=='game.wake'
    for i in range(4):
        now=t+1+i*30_000_000;catalog(e,now);gaze(e,now,i+2);e.tick(now)
    t=now;e.event('confirm','Closed_Fist',t+2,t+2)
    assert e.out[-1]['name']=='game.wake'
    assert e.target_session['phase']=='LOCKED'
    assert e._action('game.click','Victory',t+3,t+3)
    assert e.out[-1]['name']=='game.click'


def test_switch_application_cancels_pending_stroke_without_executing():
    from tests.test_gesture_actions_v34 import stroke_engine
    e,t=stroke_engine();e.feed('vision.stroke',message(t+1,track_id=1,label='L',confidence=.99,accepted=True),t+1)
    assert e.stroke_confirm.pending
    e.system('app_game',t+2)
    assert not e.stroke_confirm.pending and not e.out and e.context=='GAME'
