from copy import deepcopy
from core.config import load
from core.bindings import options,validate
from core.interaction.engine import Engine
from core.targets import select_target,demo_targets,center
from adapters.policy import ActionGate
from adapters.demo import DemoAdapter
from tests.test_interaction import healthy,message,gaze,catalog,observation

def selecting():
    e=Engine(load());t=10**10;healthy(e,t);e.calibrated=True;e._state('IDLE',t)
    e.input_hand=1;e.system('eye_takeover',t);e.input_hand=None
    for i in range(4):
        now=t+(i+1)*30_000_000;catalog(e,now);gaze(e,now,i+1);e.tick(now)
    e.out.clear()
    return e,now

def lock(e,t):
    e.target_session['released']=True;e.input_hand=1;e.event('confirm','Closed_Fist',t,t);e.input_hand=None

def test_no_grid_or_targetless_pointer_fallback():
    e,t=selecting();e.target_catalog={};e._update_cursor(t)
    assert not e.cursor['valid']
    assert not select_target([100,100],[],[1920,1080])

def test_closest_real_button_confidence_and_hysteresis():
    a=dict(id='a',rect=[90,90,20,20],confidence=1.)
    b=dict(id='b',rect=[190,90,20,20],confidence=1.)
    assert select_target([110,100],[a,b],[1920,1080])['id']=='a'
    a['confidence']=.05
    assert select_target([150,100],[a,b],[1920,1080])['id']=='b'

def test_original_hand_lock_requires_new_fist_and_never_clicks():
    e,t=selecting();e.input_hand=1;e.event('confirm','Closed_Fist',t,t)
    assert e.state=='POINTING' and not e.out
    e.target_session['released']=True;e.input_hand=2;e.event('confirm','Closed_Fist',t,t)
    assert e.state=='POINTING' and not e.out
    lock(e,t+1)
    assert e.state=='IDLE' and e.target_session['phase']=='LOCKED' and not e.out
    assert e.cursor['xy']==[100,100] and e.cursor['frozen']
    assert e.snapshot(t+1)['budget']['gaze_hz']==0
    assert e.snapshot(t+1)['budget']['face_hz']==15

def test_real_hand_frames_release_then_fist_and_recorder_cannot_steal_eye_control():
    e,t=selecting()
    for i,name in enumerate(['Closed_Fist']*5+['Open_Palm']*2+['Closed_Fist']*6):
        now=t+(i+1)*100_000_000;healthy(e,now);catalog(e,now);gaze(e,now,i+2)
        m=observation(now,i+1,name);m['recorder']={'1':{'state':'REC'}}
        e.feed('vision.hands',m,now)
        if i<7:assert e.state=='POINTING'
    assert e.target_session['phase']=='LOCKED' and not e.out

def test_lock_is_persistent_not_retimestamped_and_action_requires_explicit_gesture():
    e,t=selecting();lock(e,t);original=deepcopy(e.cursor)
    for i in range(1,22):
        now=t+i*1_000_000_000;healthy(e,now);catalog(e,now)
        e.feed('vision.gaze',message(now,i+1,valid=True,filtered_xy=[1700,900],screen_size=[1920,1080]),now)
        e.tick(now)
    assert e.cursor==original and not e.out and e.snapshot(now)['budget']['gaze_hz']==0
    assert e._action('demo.click','Victory',now,now)
    assert ActionGate().accept(e.out[-1],e.snapshot(now),now)[0]
    assert e.out[-1]['args']['cursor']['src_ns']==original['src_ns']

def test_target_disappearance_blocks_click_without_moving_pointer():
    e,t=selecting();lock(e,t);assert e._action('demo.click','Victory',t+1,t+1)
    s=e.snapshot(t+1);s['target_catalog']['targets']=[]
    assert not ActionGate().accept(e.out[-1],s,t+1)[0]
    assert e.cursor['xy']==[100,100]

def test_context_epoch_and_calibration_clear_lock():
    for command in ('app_game','dual','estop'):
        e,t=selecting();lock(e,t);e.system(command,t+1)
        assert not e.target_session
    e,t=selecting();lock(e,t);e.feed('sys.metrics',dict(message(t+1,producer='fpga-io',ok=True),epoch=8),t+1)
    assert not e.target_session

def test_only_new_takeover_can_replace_locked_point():
    e,t=selecting();lock(e,t);e.system('eye_takeover',t+1)
    assert e.target_session['phase']=='SELECTING' and not e.cursor['valid']
    assert e.snapshot(t+1)['budget']['gaze_hz']==32

def test_focus_uses_locked_anchor_not_live_mouse_or_live_gaze():
    e,t=selecting();lock(e,t);assert e._action('demo.focus','Victory',t+1,t+1)
    d=DemoAdapter();d.on_action(e.out[-1]);assert d.state['anchor']==[100/1920,100/1080]
    assert d.state['focus']

def test_legacy_bindings_migrate_without_duplicate_public_eye_functions():
    c=load()['bindings'];c['stroke']['DEMO']['W']='demo.snap';c['static']['GAME']['Victory']='system.pointer'
    b=validate(c);assert b['stroke']['DEMO']['W']=='system.eye_takeover'
    assert b['static']['GAME']['Victory']=='system.eye_takeover'
    for context in ('DEMO','GAME','DESKTOP'):
        opt=options(context)
        assert opt.count('system.eye_takeover')==1 and 'system.pointer' not in opt and 'demo.snap' not in opt
        assert context.lower()+'.click' not in opt

def test_medical_targets_have_real_controls_and_regions_on_each_page():
    for page in range(3):
        rows=demo_targets({'page':page},[1920,1080])
        assert len(rows)==[8,8,8][page] and len({r['id'] for r in rows})==len(rows)
        assert sum(':roi:' in r['id'] for r in rows)==[8,8,8][page]


def test_game_locked_confirmation_uses_native_selection_without_synthesizing_gaze():
    from adapters.game import submit_locked
    class Game:
        def __init__(self):self.names=[];self.ready=True;self.pick=2
        def update(self):return {'phase':'menu','targets':[{'kind':11,'id':2,'arg':2}], 'pick':self.pick,'selection_ready':self.ready}
        def action(self,name):self.names.append(name);return True
    game=Game();lock={'target':{'native':{'kind':11,'id':2,'arg':2}}}
    assert submit_locked(game,lock)[0] and game.names==['confirm']
    game.pick=1;assert not submit_locked(game,lock)[0]
    game.pick=2;game.ready=False;assert not submit_locked(game,lock)[0]
    assert game.names==['confirm']


def test_old_console_snap_command_routes_to_takeover_instead_of_toggle():
    e,t=selecting();lock(e,t);e.system('demo_snap',t+1)
    assert e.target_session['phase']=='SELECTING' and e.state=='POINTING'
    assert all(a['name']!='demo.snap' for a in e.out)


def test_image_region_geometry_tracks_zoom_and_focus_keeps_the_locked_screen_point():
    size=[1920,1080];d=DemoAdapter();rows=demo_targets(d.state,size);roi=next(r for r in rows if r['id']=='demo:roi:0:left_ventricle')
    p=center(roi);assert 150<p[0]<500 and 200<p[1]<400
    d.state.update(anchor=[p[0]/1920,p[1]/1080],zoom=2.)
    moved=next(r for r in demo_targets(d.state,size) if r['id']==roi['id'])
    assert abs(center(moved)[0]-p[0])<1 and abs(center(moved)[1]-p[1])<1
    e,t=selecting();lock(e,t);assert e._action('demo.focus','Victory',t+1,t+1)
    s=e.snapshot(t+1);s['target_catalog']['targets']=[]
    assert ActionGate().accept(e.out[-1],s,t+1)[0]  # Focus is an operation on the locked coordinate.
