from types import SimpleNamespace
import pytest
from vision.calibration_transaction import CalibrationTransaction
from vision.profile_selection import select_profile
from tests.test_calibration_entry import ready
from tests.test_interaction import healthy,message


def test_same_single_selection_keeps_fitted_object():
    fitted=SimpleNamespace(has_calibrated=True)
    assert select_profile({},None,fitted,None) is fitted
    assert select_profile({},None,fitted,None,True) is None


def test_cancel_restores_exact_object_success_commits_new_object():
    old=SimpleNamespace(has_calibrated=True);new=SimpleNamespace(has_calibrated=True)
    transaction=CalibrationTransaction();transaction.begin(old)
    assert transaction.finish(None) is old
    transaction.begin(old)
    assert transaction.finish(new) is new
    transaction.begin(old);transaction.clear()
    assert transaction.finish(None) is None


@pytest.mark.parametrize('exit',['cancel','app_basic','app_demo','estop','failure','hand_gap','gaze_gap'])
def test_recalibration_abort_preserves_previous_fit(exit):
    e,t=ready();e.calibrated=True;e.calibration_track=11;e.people.calibrated[1]=True
    e.calib={'done':True,'report':'previous fit'};e.system('calibrate',t)
    assert e.state=='CALIBRATING' and not e.calibrated
    if exit=='failure':
        e.feed('vision.gaze',message(t+1,phase='FAILED',calib={'done':False},calibration_request=e.calibration_request),t+1)
    elif exit.endswith('_gap'):
        e.feed('sys.metrics',message(t+1,producer=exit.split('_')[0],ok=False),t+1);e.tick(t+1)
    else:e.system(exit,t+1)
    assert e.calibrated and e.people.calibrated[1]
    assert e.calib['report']=='previous fit'
    assert e.calibration_backup is None


@pytest.mark.parametrize('change',['owner','gaze','mode'])
def test_real_replacement_does_not_restore_abandoned_fit(change):
    e,t=ready();e.instances['gaze']='old';e.calibrated=True;e.system('calibrate',t)
    if change=='owner':e.feed('sys.metrics',dict(message(t+1,producer='fpga-io',ok=True),epoch=8),t+1)
    elif change=='gaze':e.feed('sys.metrics',message(t+1,producer='gaze',instance='new',ok=True),t+1)
    else:e.system('dual',t+1)
    e.system('cancel',t+2)
    assert not e.calibrated and e.calibration_backup is None


def test_new_completed_fit_wins_over_backup_on_cancel():
    e,t=ready();e.calibrated=True;e.system('calibrate',t)
    e.feed('vision.gaze',message(t+1,phase='READY',track_id=11,calib={'done':True,'report':'new fit'},calibration_request=e.calibration_request),t+1)
    e.system('cancel',t+2)
    assert e.calibrated and e.calib['report']=='new fit'


def test_hand_gap_suspends_actions_without_losing_fit():
    e,t=ready();e.calibrated=True;e._state('IDLE',t)
    e.feed('sys.metrics',message(t+1,producer='hand',ok=False),t+1);e.tick(t+1)
    assert e.state=='DEGRADED' and e.calibrated and not e.out
    healthy(e,t+2)
    assert e.calibrated
