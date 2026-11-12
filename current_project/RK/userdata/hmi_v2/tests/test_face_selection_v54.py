from vision.selection_sync import release_unselected,FACE_DETECTION_THRESHOLD
from core.interaction.people import People
from tests.test_interaction import message


def state(t,track=None):
    return dict(src_ns=t,epoch=7,state='ONBOARD',calibrated=False,participants={'active':1,'slots':{'1':{'track_id':track}}})


def test_engine_restart_releases_surviving_old_gaze_track():
    t=10**10
    assert release_unselected(state(t),12,7,t)
    assert not release_unselected(state(t),None,7,t)


def test_current_calibration_selection_and_out_of_order_state_are_not_revoked():
    t=10**10
    assert not release_unselected(state(t,12),12,7,t)
    assert not release_unselected(dict(state(t),state='CALIBRATING'),12,7,t)
    assert not release_unselected(dict(state(t),calibrated=True),12,7,t)
    assert not release_unselected(state(t),12,7,t,t+1)
    assert not release_unselected(state(t),12,8,t)
    assert not release_unselected(state(t),12,7,t+400_000_000)


def test_single_face_loss_keeps_session_without_faking_observations():
    p=People();t=10**10;p.slots[1]=12;p.calibrated[1]=True
    p.observe(message(t,faces=[dict(track_id=12,valid=True)]),t)
    assert not p.observe(message(t+4_000_000_000,faces=[]),t+4_000_000_000)
    assert p.calibrated[1] and not p.faces
    assert not p.observe(message(t+30_000_000_000,faces=[]),t+30_000_000_000)
    assert p.calibrated[1] and not p.faces


def test_return_inside_loss_window_preserves_calibration_and_dual_guard_remains():
    p=People();t=10**10;p.slots[1]=12;p.calibrated[1]=True;p.last_seen[12]=t
    assert not p.observe(message(t+4_000_000_000,faces=[dict(track_id=12,valid=True)]),t+4_000_000_000)
    assert p.calibrated[1]
    p.mode='dual';assert p.observe(message(t+5_100_000_000,faces=[]),t+5_100_000_000)==[1]
    assert FACE_DETECTION_THRESHOLD==.35
