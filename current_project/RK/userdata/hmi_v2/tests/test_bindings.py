import pytest
from core.config import load
from core.bindings import defaults,validate
from core.interaction.engine import Engine
from tests.test_interaction import healthy,message

def test_context_bound_allowlist_rejects_shell_and_wrong_application():
    b=defaults(load());assert validate(b)==b
    for target in ('shell.reboot','demo.zoom_in','system.execute'):
        b['static']['GAME']['Victory']=target
        with pytest.raises(ValueError):validate(b)

def test_static_shortcut_needs_second_confirmation_and_can_cancel():
    e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e._state('IDLE',t)
    e.bindings['static']['DEMO']['Victory']='system.dual'
    e.event('next','Victory',t,t)
    assert e.shortcut and e.people.mode=='single'
    e.event('cancel','Thumb_Down',t+1,t+1)
    assert not e.shortcut and e.people.mode=='single'
    e.event('next','Victory',t+2,t+2);e.event('confirm','Closed_Fist',t+3,t+3)
    assert e.people.mode=='dual' and not e.shortcut

def test_shortcut_expires_and_fault_cannot_replay_confirmation():
    e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e._state('IDLE',t)
    e.bindings['static']['DEMO']['Victory']='demo.zoom_in';e.event('next','Victory',t,t)
    for i in range(1,17):healthy(e,t+i*1_000_000_000)
    assert not e.shortcut and not e.out
    e.calibrated=True;e._state('IDLE',t);e.event('next','Victory',t,t)
    e.feed('sys.metrics',message(t+1,producer='hand',ok=False),t+1);e.tick(t+1)
    assert not e.shortcut and not e.out

def test_menu_navigation_never_uses_application_shortcut():
    e=Engine(load());t=10**10;healthy(e,t);e._state('MENU',t)
    e.bindings['static']['DEMO']['Victory']='system.dual';e.event('next','Victory',t,t)
    assert e.menu_index==1 and e.people.mode=='single' and not e.shortcut
