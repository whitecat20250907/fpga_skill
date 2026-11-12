from copy import deepcopy
import pytest
from core.config import load
from core.interaction.engine import Engine
from adapters.demo import DemoAdapter
from adapters.policy import ActionGate
from tests.test_interaction import healthy,message

class Driver:
 def __init__(self):
  self.e=Engine(load());self.t=10**10;self.seq=0;healthy(self.e,self.t);self.e._state('ONBOARD',self.t);self.d=DemoAdapter()
  self.e.bindings['static']['DEMO']['Victory']='demo.next'
  self.e.bindings['stroke']['DEMO']['L']='demo.next'
 def frames(self,pose,count=4,side='Right',key=1,recorder=None,extra=None):
  for _ in range(count):
   self.t+=100000000;self.seq+=1;healthy(self.e,self.t)
   rows=[] if pose is None else [dict(track_id=key,side=side,side_score=.9,gesture=pose,score=.9,in_bounds=True)]
   if extra:rows+=extra
   self.e.feed('vision.hands',message(self.t,self.seq,hands=rows,recorder=recorder or {}),self.t)
  return self.t
 def ack(self):
  a=self.e.out[-1];assert ActionGate().accept(a,self.e.snapshot(self.t),self.t)[0]
  self.d.on_action(a);self.e.feed('hmi.ack',message(self.t+1,id=a['id'],ok=True),self.t+1);return a
 def action(self):
  self.e._action('demo.next','console',self.t,self.t);return self.ack()
 def shortcut(self,side='Left',pose='Closed_Fist',key=2):
  self.frames('Open_Palm',1,side,key);self.frames(pose,4,side,key)

@pytest.mark.parametrize('side',['Left','Right'])
def test_successful_action_survives_long_absence_repeat_and_undo(side):
 x=Driver();a=x.action();x.frames(None,40);x.t+=3600*10**9;healthy(x.e,x.t)
 x.shortcut(side,key=22);assert x.e.out[-1]['name']=='demo.next';b=x.ack();assert b['id']!=a['id'] and b['repeated_from']==a['id']
 x.frames(None,12);x.shortcut(side,'Thumb_Down',key=33);u=x.ack();assert u['args']['undo_id']==b['id'];assert x.d.state['page']==1
 x.shortcut(side,key=44);x.ack();assert x.d.state['page']==2

@pytest.mark.parametrize('cancel',[False,True])
def test_victory_pending_rebinds_right_track_and_confirms_or_cancels(cancel):
 x=Driver();x.frames('Closed_Fist');x.frames('Victory');assert x.e.shortcut
 x.frames('Open_Palm',1,key=17);x.frames('Thumb_Down' if cancel else 'Closed_Fist',4,key=17)
 assert x.e.shortcut is None
 assert len(x.e.out)==(0 if cancel else 1)
 if not cancel:x.ack();assert x.d.state['page']==1
 x.frames('Closed_Fist',10,key=17);assert len(x.e.out)==(0 if cancel else 1)

@pytest.mark.parametrize('pose',['Closed_Fist','Victory','Thumb_Up','ILoveYou','Pointing_Up','Thumb_Down'])
def test_left_unprepared_poses_cannot_confirm_or_select(pose):
 x=Driver();x.frames('Closed_Fist');x.frames('Victory');pending=deepcopy(x.e.shortcut)
 x.frames(pose,8,'Left',2)
 assert x.e.shortcut==pending and not x.e.out

@pytest.mark.parametrize('order',['stroke_first','hands_first'])
@pytest.mark.parametrize('accepted',[True,False])
def test_right_ending_fist_executes_trajectory_once_no_other_hand(order,accepted):
 x=Driver();x.frames('Pointing_Up',2,recorder={'1':{'state':'REC'}});assert x.e.state=='WRITING'
 x.t+=100000000;x.seq+=1;healthy(x.e,x.t)
 stroke=message(x.t,x.seq,track_id=1,source_side='Right',ending_gesture='Closed_Fist',gesture_generation=0,label='L',confidence=.9 if accepted else .2,accepted=accepted)
 hands=message(x.t,x.seq,hands=[dict(track_id=1,side='Right',side_score=.9,gesture='Closed_Fist',score=.9)],recorder={'1':{'state':'RESULT'}})
 for topic,msg in ([('vision.stroke',stroke),('vision.hands',hands)] if order=='stroke_first' else [('vision.hands',hands),('vision.stroke',stroke)]):x.e.feed(topic,msg,x.t)
 assert len(x.e.out)==int(accepted) and x.e.stroke_confirm.pending is None
 if accepted:
  assert x.e.out[-1]['confirmation']=='trajectory_fist';x.ack()
 x.e.feed('vision.stroke',stroke,x.t);x.frames('Closed_Fist',8,recorder={'1':{'state':'RESULT'}})
 assert len(x.e.out)==int(accepted) and x.e.state!='WRITING'

@pytest.mark.parametrize('phase',['MENU','WRITING','CALIBRATING','POINTING','IDLE','ONBOARD'])
@pytest.mark.parametrize('side',['Left','Right'])
def test_palm_down_undo_preempts_every_interactive_phase(phase,side):
 x=Driver();a=x.action();x.e._state(phase,x.t)
 x.shortcut(side,'Thumb_Down');assert x.e.out[-1]['name']=='demo.undo';u=x.ack();assert u['args']['undo_id']==a['id'];assert x.d.state['zoom']==1


def test_concurrent_both_repeat_is_one_action_and_held_fist_does_not_repeat():
 x=Driver();x.action()
 for pose,count in [('Open_Palm',1),('Closed_Fist',10)]:
  x.frames(pose,count,extra=[dict(track_id=2,side='Left',side_score=.9,gesture=pose,score=.9)])
 assert len(x.e.out)==2


def test_failed_ack_does_not_replace_previous_successful_action():
 x=Driver();a=x.action();x.e._action('demo.next','console',x.t,x.t)
 b=x.e.out[-1];x.e.feed('hmi.ack',message(x.t+1,id=b['id'],ok=False,detail='failed'),x.t+1)
 assert x.e.last_action['id']==a['id']
 x.shortcut();assert x.e.out[-1]['name']=='demo.next'


def test_pending_right_confirmation_is_not_repeat_even_after_palm():
 x=Driver();x.action();x.e.bindings['static']['DEMO']['Victory']='demo.next'
 x.frames('Closed_Fist');x.frames('Victory');assert x.e.shortcut
 x.frames('Open_Palm',1);x.frames('Closed_Fist');assert x.e.out[-1]['name']=='demo.next'


def test_context_memory_is_separate_and_returns_without_hand_identity():
 x=Driver();a=x.action();x.e.system('app_game',x.t);x.frames(None,2);assert x.e.last_action is None
 x.e.system('app_demo',x.t);x.frames(None,2);assert x.e.last_action['id']==a['id']


def test_right_palm_fist_after_eye_lock_clicks_but_left_repeats_previous():
 x=Driver();x.action();x.e.target_session={'phase':'LOCKED','lock_id':'locked','target':{'label':'test'},'cursor':{}}
 x.shortcut('Right');assert x.e.out[-1]['name']=='demo.click'
 x.e.feed('hmi.ack',message(x.t+1,id=x.e.out[-1]['id'],ok=False),x.t+1)
 x.shortcut('Left');assert x.e.out[-1]['name']=='demo.next'


def test_late_stroke_after_undo_generation_cannot_execute():
 x=Driver();x.action();x.frames('Pointing_Up',2,recorder={'1':{'state':'REC'}})
 x.shortcut('Left','Thumb_Down');n=len(x.e.out)
 x.e.feed('vision.stroke',message(x.t+1,999,track_id=1,source_side='Right',ending_gesture='Closed_Fist',gesture_generation=0,label='L',confidence=.9,accepted=True),x.t+1)
 assert len(x.e.out)==n


@pytest.mark.parametrize('valid',[True,False])
def test_eye_ending_fist_never_becomes_a_repeat_or_click_on_later_frames(valid):
 from tests.test_eye_takeover_v49 import selecting
 from tests.test_eye_recovery_v52 import feed_pose
 e,t=selecting();e.pending.clear()
 feed_pose(e,t+1,1,'Open_Palm')
 for i in range(2,14):feed_pose(e,t+i*80000000,i,'Closed_Fist',valid=valid)
 assert not e.out and e.state!='POINTING'
 if valid:assert e.target_session['phase']=='LOCKED'
 else:assert not e.target_session and '眼控已结束' in e.toast


def test_pending_can_cancel_directly_without_palm_or_another_fist():
 x=Driver();x.frames('Closed_Fist');x.frames('Victory');assert x.e.shortcut
 x.frames('Thumb_Down');assert not x.e.shortcut and not x.e.out


def test_no_fist_prefix_left_or_repeat_fist_can_arm_a_trajectory():
 pytest.importorskip('cv2')
 from vision.bootstrap import install_vendor_resolver
 from vision.gesture_flow import GestureTrajectory
 from tests.test_gesture_trajectory import result
 install_vendor_resolver();flow=GestureTrajectory(load()['gestures']);state=dict(state='ONBOARD',epoch=7,active_hand_ids=[9])
 for i,name in enumerate(['Open_Palm']+['Closed_Fist']*5+['Pointing_Up']*8):
  now=10+i*.1;assert not flow.update(result(name),i+1,now,now,640,360,state)
 assert flow.recorders[9].state=='IDLE'
 for i in range(5):
  data=result('Closed_Fist');data.handedness[0][0].category_name='Left'
  now=15+i*.1;flow.update(data,20+i,now,now,640,360,state)
 assert not flow.recorders



def test_static_system_menu_confirm_does_not_select_menu_on_the_same_held_fist():
 x=Driver();x.e.bindings['static']['DEMO']['Victory']='system.menu'
 x.frames('Closed_Fist');x.frames('Victory');x.frames('Closed_Fist',12)
 assert x.e.state=='MENU' and x.e.shortcut is None and x.e.application_request is None
 x.frames('Victory');x.frames('Closed_Fist');assert x.e.context=='GAME'


def test_two_hand_conflicting_shortcuts_prioritize_undo_without_repeat():
 x=Driver();original=x.action()
 x.frames('Open_Palm',1,extra=[dict(track_id=2,side='Left',side_score=.9,gesture='Open_Palm',score=.9)])
 x.frames('Closed_Fist',6,extra=[dict(track_id=2,side='Left',side_score=.9,gesture='Thumb_Down',score=.9)])
 assert len(x.e.out)==2 and x.e.out[-1]['name']=='demo.undo'
 assert x.e.out[-1]['args']['undo_id']==original['id']


def test_old_opposite_hand_protocol_is_rejected_but_new_finish_protocol_passes():
 x=Driver();x.e._action('demo.next','stroke',x.t,x.t);a=x.e.out[-1]
 a['confirmation']='opposite_hand';assert not ActionGate().accept(a,x.e.snapshot(x.t),x.t)[0]
 a['confirmation']='trajectory_fist';assert ActionGate().accept(a,x.e.snapshot(x.t),x.t)[0]


def test_palm_down_cancels_recording_locally_and_cannot_produce_old_stroke():
 pytest.importorskip('cv2')
 from vision.bootstrap import install_vendor_resolver
 from vision.gesture_flow import GestureTrajectory
 from tests.test_gesture_trajectory import result
 install_vendor_resolver();flow=GestureTrajectory(load()['gestures']);state=dict(state='ONBOARD',epoch=7,active_hand_ids=[9])
 for i,name in enumerate(['Closed_Fist']*3+['Pointing_Up']*10):
  now=10+i*.1;flow.update(result(name),i+1,now,now,640,360,state)
 assert flow.recorders[9].state=='REC'
 for i,name in enumerate(['Thumb_Down']*3+['Closed_Fist']*4):
  now=12+i*.1;assert not flow.update(result(name),30+i,now,now,640,360,state)
 assert flow.recorders[9].state=='IDLE'



def test_unmapped_right_static_has_no_hidden_direct_action():
 x=Driver();x.e.bindings['static']['DEMO'].clear()
 x.frames('Closed_Fist');x.frames('Victory');assert not x.e.out and not x.e.shortcut and '未绑定' in x.e.toast


def test_low_confidence_gesture_never_commits_and_short_gap_recovers():
 x=Driver();x.frames('Closed_Fist');x.frames('Victory');assert x.e.shortcut
 x.t+=100000000;x.seq+=1;healthy(x.e,x.t)
 x.e.feed('vision.hands',message(x.t,x.seq,hands=[dict(track_id=1,side='Right',side_score=.9,gesture='Closed_Fist',score=.1)]),x.t)
 assert not x.e.out
 x.frames('Closed_Fist');assert len(x.e.out)==1



def test_cancelled_recording_rejects_late_classifier_and_old_recorder_packets():
 x=Driver();x.frames('Pointing_Up',2,recorder={'1':{'state':'REC'}})
 x.frames('Thumb_Down',1,recorder={'1':{'state':'IDLE','reason':'thumb_down_cancel'}})
 assert x.e.state!='WRITING' and x.e.gesture_generation==1
 x.frames('Pointing_Up',1,recorder={'1':{'state':'REC'}});assert x.e.state!='WRITING'
 x.e.feed('vision.stroke',message(x.t+1,999,track_id=1,source_side='Right',ending_gesture='Closed_Fist',gesture_generation=0,label='L',confidence=.9,accepted=True),x.t+1)
 assert not x.e.out



def test_victory_calibration_wait_can_cancel_directly_without_fist_prefix():
 x=Driver();x.e.bindings['static']['DEMO']['Victory']='system.calibrate'
 x.frames('Closed_Fist');x.frames('Victory');x.frames('Closed_Fist')
 assert x.e.shortcut is None and x.e.calibration_intent
 x.frames('Thumb_Down');assert x.e.calibration_intent is None and not x.e.out


def test_registration_does_not_let_other_person_repeat_or_undo_active_history():
 x=Driver();x.e.people.mode='dual';x.e.people.slots={1:11,2:22}
 x.e.people.faces=[dict(track_id=11,face_rect=[60,100,100,100]),dict(track_id=22,face_rect=[460,100,100,100])]
 x.action();x.e.people.request(1);before=len(x.e.out)
 for pose,count in [('Open_Palm',1),('Thumb_Down',5)]:
  for _ in range(count):
   x.t+=100000000;x.seq+=1;healthy(x.e,x.t)
   x.e.feed('vision.hands',message(x.t,x.seq,hands=[dict(track_id=5,side='Left',score=.9,side_score=.9,gesture=pose,image21=[[.8,.5,0]]*21)]),x.t)
 assert len(x.e.out)==before
