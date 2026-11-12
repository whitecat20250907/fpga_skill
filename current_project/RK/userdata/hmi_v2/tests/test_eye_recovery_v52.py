from core.config import load
from core.interaction.engine import Engine
from tests.test_interaction import healthy,message,observation,gaze,catalog,face
from tests.test_eye_takeover_v49 import selecting
from vision.profile_selection import select_profile


def feed_pose(e,t,seq,name,key=1,side='Right',score=.9,others=(),valid=True):
    healthy(e,t);catalog(e,t);gaze(e,t,seq+20,valid=valid)
    m=observation(t,seq,name,score);m['hands'][0].update(track_id=key,side=side,side_score=.99)
    m['hands']+=list(others);e.feed('vision.hands',m,t)


def test_fist_ends_even_if_gaze_is_invalid_at_commit_no_click():
    e,t=selecting()
    feed_pose(e,t+1,1,'Open_Palm')
    for i in range(2,8):feed_pose(e,t+i*80_000_000,i,'Closed_Fist',score=.60,valid=False)
    assert e.state!='POINTING' and not e.target_session and not e.out
    assert e.snapshot(t+600_000_000)['budget']['gaze_hz']==0
    assert '眼控已结束' in e.toast


def test_console_fist_hand_wins_not_first_open_hand():
    e,t=selecting();e.system('eye_takeover',t+1);e.out.clear()
    left=dict(track_id=2,side='Left',side_score=.99,gesture='Open_Palm',score=.9)
    feed_pose(e,t+80_000_000,1,'Open_Palm',others=[left])
    assert e.target_session['hand'] is None
    # List order is deliberately left first, but right hand performs the fist.
    for i in range(2,8):
        now=t+i*80_000_000;healthy(e,now);catalog(e,now);gaze(e,now,i+20)
        m=observation(now,i,'Closed_Fist',.60);m['hands'][0].update(side='Right',side_score=.99)
        m['hands'].insert(0,left);e.feed('vision.hands',m,now)
        if e.target_session.get('phase')=='LOCKED':break
    assert e.target_session['phase']=='LOCKED' and e.target_session['hand']==1 and not e.out


def test_original_side_recovers_changed_track_without_other_hand_confirming():
    e,t=selecting();feed_pose(e,t+1,1,'Open_Palm')
    for i in range(2,8):
        feed_pose(e,t+i*80_000_000,i,'Closed_Fist',key=9,side='Right',score=.6)
        if e.target_session.get('phase')=='LOCKED':break
    assert e.target_session['phase']=='LOCKED' and e.target_session['hand']==9


def test_other_side_cannot_take_original_hand_lock():
    e,t=selecting();feed_pose(e,t+1,1,'Open_Palm')
    for i in range(2,8):feed_pose(e,t+i*80_000_000,i,'Closed_Fist',key=9,side='Left')
    assert e.state=='POINTING' and not e.out and e.target_session['hand']==1


def test_takeover_clears_unfinished_shortcut_and_stroke_confirmation():
    e,t=selecting();e.shortcut={'target':'demo.next','hand':2};e.stroke_confirm.pending={'target':'demo.next'}
    e.system('eye_takeover',t+1)
    assert e.state=='POINTING' and e.shortcut is None and e.stroke_confirm.pending is None


def test_single_loss_retains_session_and_explicit_recalibration_uses_current_face():
    e=Engine(load());t=10**10;healthy(e,t);face(e,t,1)
    e.people.slots[1]=11;e.people.calibrated[1]=True;e.calibrated=True;e.calibration_track=11;e._state('IDLE',t)
    now=t+5_100_000_000;healthy(e,now)
    e.feed('vision.face',message(now,2,faces=[]),now)
    assert e.calibrated and not any(m['command']=='invalidate_calibration' for m in e.commands)
    for i in range(1,8):
        stamp=now+i*100_000_000;healthy(e,stamp)
        e.feed('vision.face',message(stamp,i+2,faces=[dict(track_id=22,primary=True,valid=True,face_rect=[240,130,160,100],can_gaze=True)]),stamp);e.tick(stamp)
    e.system('calibrate',stamp)
    assert e.state=='CALIBRATING' and e.people.slots[1]==22
    assert [m['command'] for m in e.commands[-2:]]==['select_track','calibrate']
    assert all(m['track_id'] is None for m in e.commands[-2:])
    e.tick(stamp+1);assert e.state=='CALIBRATING'


def test_invalidated_profile_is_not_saved_or_reused_for_replacement():
    old=object();other=object();profiles={11:old,22:other}
    assert select_profile(profiles,11,old,None,True) is None
    assert profiles=={22:other}
    assert select_profile(profiles,None,None,22) is other


def test_eye_selection_disables_trajectory_recorder_only():
    from vision.gesture_flow import enabled
    assert not enabled({'state':'POINTING'})
    assert enabled({'state':'IDLE'}) and enabled({'state':'WRITING'})


def test_finished_calibration_or_validation_can_restart_directly():
    from tests.test_calibration_entry import ready
    for phase in ('READY','RESULT','FAILED'):
        e,t=ready();e._state('CALIBRATING',t);e.calib={'phase':phase,'done':phase!='FAILED'}
        e.system('calibrate',t)
        assert e.state=='CALIBRATING' and e.calibration_request>0 and e.calib=={}
        assert e.commands[-1]['command']=='calibrate'
