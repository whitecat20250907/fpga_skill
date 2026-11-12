from tests.test_interaction import catalog
from core.config import load
from core.interaction.engine import Engine
from core.interaction.fist_latch import FistLatch
from core.interaction.stroke_confirm import StrokeConfirm
from adapters.policy import ActionGate
from vision.hand_visibility import usable_palm
from tests.test_interaction import healthy,observation,message,gaze


def test_optional_screen_console_and_gaze_failure_do_not_kill_hand_commands():
    for producer in ('ui','hud','console','gaze'):
        e=Engine(load());t=10**10;healthy(e,t)
        e.feed('sys.metrics',message(t+1,producer=producer,ok=False),t+1)
        e.event('next','Victory',t+2,t+2)
        assert not e.broken and producer in e.warnings
        assert e.out[-1]['name']=='demo.next'


def test_adapter_loss_keeps_recognition_but_reports_unexecuted_action():
    e=Engine(load());t=10**10;healthy(e,t)
    e.feed('sys.metrics',message(t+1,producer='adapters',ok=False),t+1)
    e.event('next','Victory',t+2,t+2)
    assert not e.broken and not e.out and '执行端' in e.toast
    assert e.snapshot(t+2)['budget']['hand_unlimited']


def test_hud_restart_does_not_reset_an_armed_hand():
    e=Engine(load());t=10**10;healthy(e,t)
    e.feed('sys.metrics',message(t,producer='hud',ok=True,instance='first'),t)
    for i in range(5):e.feed('vision.hands',observation(t+i*100_000_000,i+1,'Closed_Fist'),t+i*100_000_000)
    armed=e.latch.hands[1].armed_until
    e.feed('sys.metrics',message(t+500_000_000,producer='hud',ok=True,instance='new'),t+500_000_000)
    assert e.latch.hands[1].armed_until==armed


def test_one_missing_pose_preserves_hold_but_adds_no_missing_time():
    latch=FistLatch(load()['gestures']);t=10**10;commits=[]
    for i in range(7):
        m=observation(t+i*50_000_000,i+1,'Closed_Fist')
        if i==2:m['hands']=[]
        got=latch.observe(m,m['src_ns'],confirming=True)
        if i<=4:assert not got
        commits+=got
    assert commits==[(1,'confirm','Closed_Fist')]


def test_uncertain_pose_is_not_a_release_or_second_confirmation():
    latch=FistLatch(load()['gestures']);t=10**10;commits=[]
    for i in range(18):
        name='None' if i in (8,9) else 'Closed_Fist'
        m=observation(t+i*50_000_000,i+1,name)
        commits+=latch.observe(m,m['src_ns'],confirming=True)
    assert commits==[(1,'confirm','Closed_Fist')]


def test_duplicate_packet_does_not_clear_preparation_or_supply_a_frame():
    latch=FistLatch(load()['gestures']);t=10**10
    m=observation(t,1,'Closed_Fist');latch.observe(m,t)
    count=latch.hands[1].count
    assert not latch.observe(m,t+1) and latch.hands[1].count==count


def test_shortcut_is_confirmed_by_operating_hand_without_other_palm_conflict():
    e=Engine(load());t=10**10;healthy(e,t)
    e.bindings['static']['DEMO']['Victory']='demo.zoom_in'
    e.input_hand=1;e.event('next','Victory',t,t);e.input_hand=None
    for i in range(8):
        now=t+(i+1)*100_000_000;healthy(e,now)
        e.feed('vision.hands',observation(now,i+1,'Closed_Fist',second='Open_Palm'),now)
    assert len(e.out)==1 and e.out[0]['name']=='demo.zoom_in'


def test_open_resting_hand_does_not_cancel_or_block_a_menu_fist():
    latch=FistLatch(load()['gestures']);t=10**10;commits=[]
    for i in range(8):
        m=observation(t+i*100_000_000,i+1,'Closed_Fist',second='Open_Palm')
        commits+=latch.observe(m,m['src_ns'],confirming=True)
    assert commits==[(1,'confirm','Closed_Fist')]


def test_prepared_opposite_hand_survives_a_side_label_flicker():
    gate=StrokeConfirm(load()['gestures']);t=10**10
    assert gate.begin(message(t,label='L'),'demo.zoom_in',dict(track_id=1,side='Right',side_score=.6),(),t)
    commits=[]
    for i in range(8):
        m=observation(t+(i+1)*100_000_000,i+1,'Open_Palm' if i==0 else 'Closed_Fist')
        m['hands'][0].update(track_id=2,side='Left' if i==0 else 'Right',side_score=.6 if i==0 else .4)
        commits.append(gate.observe(m,m['hands'],m['src_ns']))
    assert sum(commits)==1


def test_small_fingertip_boundary_noise_does_not_hide_a_visible_palm():
    points=[[.5,.5,0] for _ in range(21)];points[8]=[1.02,.5,0]
    assert usable_palm(points)
    points[0]=[1.3,.5,0];assert not usable_palm(points)
    points[0]=[float('nan'),.5,0];assert not usable_palm(points)


def test_target_selection_does_not_expire_while_fresh_gaze_is_arriving():
    e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e.system('pointer',t)
    for i in range(1,401):
        now=t+i*30_000_000;healthy(e,now);catalog(e,now);gaze(e,now,i);e.tick(now)
    assert e.state=='POINTING' and e.cursor['valid']


def test_delayed_state_does_not_reject_a_fresh_deliberate_action():
    e=Engine(load());t=10**10;healthy(e,t)
    e.event('next','Victory',t,t);state=e.snapshot(t);state['src_ns']=t-250_000_000
    assert ActionGate().accept(e.out[-1],state,t)[0]
    state['src_ns']=t-400_000_000
    assert not ActionGate().accept(e.out[-1],state,t)[0]
