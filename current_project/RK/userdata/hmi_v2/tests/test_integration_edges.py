from core.config import load
from core.interaction.engine import Engine
from tests.test_interaction import healthy,message,gaze
from ui.mipi_composer import compose
from hft2_wire import decode

def test_operator_duplicate_does_not_toggle_twice():
 e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e._state('IDLE',t)
 m=message(t,command='menu');e.feed('cmd.system',m,t);assert e.state=='MENU'
 e.feed('cmd.system',m,t);assert e.state=='MENU'

def test_estop_aborts_calibration_and_hides_its_window():
 e=Engine(load());t=10**10;healthy(e,t);e._state('CALIBRATING',t)
 e.system('estop',t+1)
 assert e.state=='STANDBY' and e.estop and not e.out
 assert [m['command'] for m in e.commands]==['preview','hide_window']

def test_engine_restart_cannot_reuse_action_ids_with_same_hardware_epoch():
 t=10**10;engines=[Engine(load()),Engine(load())]
 for e in engines:
  healthy(e,t);e.calibrated=True;e._state('IDLE',t);e._action('demo.next','Victory',t,t)
 assert engines[0].out[0]['id']!=engines[1].out[0]['id']

def test_menu_closes_before_calibration_and_never_dispatches_app_actions():
 t=10**10;e=Engine(load());healthy(e,t);e._state('ONBOARD',t)
 e.system('menu',t);assert e.state=='MENU'
 e.system('menu',t+1);assert e.state=='ONBOARD'
 e.calibrated=True;e._state('CALIBRATING',t+2);e.system('demo_next',t+2)
 assert not e.out

def test_fast_gaze_restart_invalidates_calibration():
 e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e._state('POINTING',t)
 e.feed('sys.metrics',message(t+1,producer='gaze',instance='first',ok=True),t+1)
 e.feed('sys.metrics',message(t+2,producer='gaze',instance='second',ok=True),t+2)
 assert not e.calibrated and e.state=='ONBOARD' and not e.out

def test_dual_other_face_cannot_use_calibration():
 e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e.calibration_track=7;e.people.mode='dual';e._state('POINTING',t)
 e.feed('vision.gaze',message(t+1,track_id=8,valid=True,filtered_xy=[10,10],screen_size=[1920,1080],calib={'done':True}),t+1)
 assert not e.calibrated and e.state=='ONBOARD' and not e.out

def test_real_geometry_wire_budget_and_epoch_gate():
 t=10**10;e=Engine(load());e.epoch=7;e.calibrated=True;e.state='WRITING';e.layer='WRITE';state=e.snapshot(t)
 points=[[i%6,(i//6),i%3] for i in range(468)]
 face=message(t,faces=[dict(track_id=7,primary=True,valid=True,landmarks=points)])
 hand=[dict(track_id=i+1,side=('Left','Right')[i],world21=[[j%4,j//4,j%3] for j in range(21)]) for i in range(2)]
 hands=message(t,hands=hand,recorder={'1':{'state':'REC','points':[[i*10,180] for i in range(48)]}})
 state['active_hand_ids']=[1,2]
 packet,csr=compose(state,face,hands,t,22);data=decode(packet)
 assert len(packet)<=1908 and data['scene'].valid==23
 assert len(data['scene'].vertices)<=128 and data['metadata'].trajectory_points==48
 assert data['scene'].face_timestamp_ns==t and data['scene'].hand_timestamp_ns==t
 packet,_=compose(state,dict(face,epoch=8),hands,t,23)
 assert decode(packet)['scene'].valid==19  # Fresh hands/trace survive an unrelated face epoch.
 assert decode(packet)['scene'].face_timestamp_ns==0
 packet,_=compose(state,dict(face,epoch=8),dict(hands,epoch=8),t,24)
 assert decode(packet)['scene'].valid==0
