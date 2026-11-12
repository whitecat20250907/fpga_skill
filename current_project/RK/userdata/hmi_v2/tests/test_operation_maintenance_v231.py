from copy import deepcopy
import pytest
from tests.test_gesture_contract_v92 import Driver
from tests.test_interaction import message, healthy


def proposed():
    x=Driver();x.frames('Closed_Fist');x.frames('Victory')
    assert x.e.shortcut and x.e.state=='MENU'
    return x


@pytest.mark.parametrize('command',['dual','single','person1','person2','calibrate_person1','calibrate_person2'])
def test_explicit_person_command_drops_old_static_proposal(command):
    x=proposed()
    if command!='dual':x.e.people.mode='dual'
    x.e.system(command,x.t)
    assert x.e.shortcut is None
    x.e.event('confirm','button',x.t+1,x.t+1)
    assert not any(a['name']=='demo.next' for a in x.e.out)


def save(x,bindings):
    x.t+=1
    x.e.feed('cmd.system',message(x.t,command='bindings',bindings=bindings,request_id='save'),x.t)


def test_changed_mapping_exits_old_confirmation_and_new_gesture_works():
    x=proposed();bindings=deepcopy(x.e.bindings);bindings['static']['DEMO']['Victory']='demo.rotate'
    save(x,bindings)
    assert x.e.shortcut is None and x.e.state=='ONBOARD'
    x.frames(None,6);x.frames('Closed_Fist');x.frames('Victory');x.frames('Closed_Fist')
    assert [a['name'] for a in x.e.out]==['demo.rotate']


def test_unchanged_mapping_save_keeps_current_confirmation():
    x=proposed();pending=deepcopy(x.e.shortcut)
    save(x,deepcopy(x.e.bindings))
    assert x.e.shortcut==pending and x.e.state=='MENU'
    x.frames('Closed_Fist');assert x.e.out[-1]['name']=='demo.next'


@pytest.mark.parametrize('command',['bindings','app_demo'])
def test_mapping_or_explicit_reentry_cancels_old_recording(command):
    x=Driver();x.frames('Pointing_Up',2,recorder={'1':{'state':'REC'}})
    generation=x.e.gesture_generation
    if command=='bindings':
        bindings=deepcopy(x.e.bindings);bindings['stroke']['DEMO']['L']='demo.rotate';save(x,bindings)
    else:x.e.system(command,x.t)
    assert x.e.stroke_owner is None and x.e.state!='WRITING'
    x.e.feed('vision.stroke',message(x.t+1,999,track_id=1,source_side='Right',ending_gesture='Closed_Fist',gesture_generation=generation,label='L',confidence=.9,accepted=True),x.t+1)
    assert not x.e.out


@pytest.mark.parametrize('entry',['static','stroke'])
def test_rotation_full_engine_gate_adapter_then_palm_and_absence_stop(entry):
    x=Driver();x.e.bindings[entry]['DEMO']['Victory' if entry=='static' else 'L']='demo.rotate'
    if entry=='static':
        x.frames('Closed_Fist');x.frames('Victory');x.frames('Closed_Fist')
    else:
        x.frames('Pointing_Up',2,recorder={'1':{'state':'REC'}})
        x.t+=1
        x.e.feed('vision.stroke',message(x.t,999,track_id=1,source_side='Right',ending_gesture='Closed_Fist',gesture_generation=0,label='L',confidence=.9,accepted=True),x.t)
    action=x.ack();assert action['args']['control_hand']=={'track_id':1,'side':'Right'}
    start=x.d.rotation_tick;x.t=start;x.seq+=1000
    for _ in range(4):
        x.frames('Closed_Fist',1);x.d.tick(x.t,x.e.snapshot(x.t))
    assert x.d.state['rotating'] and x.d.state['orbit'][1]>0
    for _ in range(4):
        x.frames('Open_Palm',1);x.d.tick(x.t,x.e.snapshot(x.t))
    assert not x.d.state['rotating']
    x.frames('Closed_Fist');x.ack();assert x.d.state['rotating']
    for _ in range(10):
        x.frames(None,1);x.d.tick(x.t,x.e.snapshot(x.t))
    assert not x.d.state['rotating']
