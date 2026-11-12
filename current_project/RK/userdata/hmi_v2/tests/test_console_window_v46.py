import time
from core.config import load
from core.interaction.engine import Engine
from adapters.launcher import Launcher
from tests.test_interaction import healthy,message


def test_explicit_switch_survives_hand_state_transition_and_startup_latency():
    e=Engine(load());t=time.monotonic_ns();healthy(e,t);e.system('app_game',t)
    s=e.snapshot(t);s['state']='WRITING';s['application_request']['src_ns']-=2_000_000_000
    seen=[];l=Launcher(load(),None);l._focus=lambda c:seen.append(c) or True
    l.select(s);assert seen==['GAME'] and l.pending
    l.select(s);assert l.status['status']=='active' and not l.pending
    assert seen==['GAME']


def test_web_commands_and_saved_bindings_get_correlated_receipts_without_duplicate_execution():
    e=Engine(load());t=time.monotonic_ns();healthy(e,t)
    cmd=message(t+1,command='app_game',request_id='switch-1')
    e.feed('cmd.system',cmd,t+2);s=e.snapshot(t+2)
    receipt=s['control_receipts'][-1]
    assert receipt['id']=='switch-1' and receipt['context']=='GAME'
    assert receipt['application_request_id']==s['application_request']['id']
    e.feed('cmd.system',cmd,t+3)
    assert len(e.control_receipts)==1
    e.feed('cmd.system',message(t+4,command='bindings',bindings=e.bindings,request_id='save-1'),t+5)
    assert e.snapshot(t+5)['control_receipts'][-1]['detail']=='映射已保存，当前操作保持不变'


def test_display_inference_does_not_enable_gaze_and_can_be_disabled():
    e=Engine(load());t=time.monotonic_ns();healthy(e,t)
    b=e.snapshot(t)['budget']
    assert b['face_hz']==15 and b['gaze_hz']==0 and b['reason']=='head_display'
    e.tuning['head_display_hz']=0
    assert e.snapshot(t)['budget']['face_hz']==0


def test_window_ack_requires_actual_fullscreen_not_just_focus(monkeypatch):
    import sys
    from types import SimpleNamespace
    monkeypatch.setitem(sys.modules,'Xlib',SimpleNamespace(X=SimpleNamespace(AnyPropertyType=0)))
    props={'_NET_ACTIVE_WINDOW':[123],'_NET_WM_STATE':[]}
    class Window:
        def get_full_property(self,name,_):return SimpleNamespace(value=props[name])
    w=Window()
    d=SimpleNamespace(screen=lambda:SimpleNamespace(root=w),intern_atom=lambda s:s,create_resource_object=lambda *a:w)
    l=Launcher(load(),d);l.context='DEMO';l.window_id=123
    assert not l._selected()
    props['_NET_WM_STATE']=['_NET_WM_STATE_FULLSCREEN']
    assert l._selected()
    props['_NET_ACTIVE_WINDOW']=[124]
    assert not l._selected()
