from copy import deepcopy
import pytest
from core.config import load
from core.interaction.engine import Engine
from adapters.policy import ActionGate
from tests.test_interaction import healthy,message

def command():
    t=10**10;e=Engine(load());healthy(e,t)
    e.feed('cmd.system',message(t,command='demo_rotate',producer='console'),t)
    return t,e,e.out[-1],e.snapshot(t)

def test_authenticated_demo_request_without_person_has_one_real_ack_path():
    t,e,action,state=command()
    assert not e.calibrated and e.state=='STANDBY'
    gate=ActionGate();assert gate.accept(action,state,t)[0]
    assert not gate.accept(action,state,t)[0]
    e.feed('hmi.ack',message(t+1,id=action['id'],ok=True),t+1)
    assert e.toast=='已执行：旋转三维'

@pytest.mark.parametrize('change', ['gesture','desktop','game','epoch','stale_action','stale_state','estop','health','calibrating','writing','menu','confirm'])
def test_manual_permission_cannot_escape_teaching_canvas(change):
    t,e,a,s=command();a=deepcopy(a);s=deepcopy(s)
    if change=='gesture':a['gesture']='Thumb_Up'
    if change in ('desktop','game'):a['name']=change+'.next';a['context']=s['context']=change.upper()
    if change=='epoch':a['epoch']+=1
    if change=='stale_action':a['src_ns']-=351_000_000
    if change=='stale_state':s['src_ns']-=351_000_000
    if change=='estop':s['estop']=True
    if change=='health':s['health']={'broken':['gaze']}
    if change in ('calibrating','writing','menu'):s['state']=change.upper()
    if change=='confirm':a['name']='demo.confirm'
    assert not ActionGate().accept(a,s,t)[0]

def test_engine_rejects_during_menu_with_feedback_and_does_not_enqueue():
    t,e,a,s=command();e.out.clear();e._state('MENU',t)
    e.system('demo_next',t+1)
    assert not e.out and '操作未执行' in e.toast
    e.system('estop',t+2);e.system('demo_next',t+3)
    assert not e.out and '紧急待机' in e.toast
