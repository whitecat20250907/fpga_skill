from ui.calibration_feedback import summary,scorecard,pill_position
from ui.feedback import feedback


def test_evaluation_is_distinct_from_calibration_fit():
    assert scorecard({'phase':'CALIBRATE'}) is None
    assert scorecard({'phase':'VALIDATE','done':True}) is None
    assert '准确度' in scorecard({'phase':'READY'})['rows'][1]
    f=feedback({'state':'CALIBRATING','calibrated':True,'calib':{'phase':'VALIDATE','point_i':14,'total':20}})
    assert f['title']=='正在独立评测' and '15/20' in f['hint']


def test_scorecard_uses_held_out_numbers_and_never_invents_missing_values():
    r=summary({'filtered':{'mean_frame_error_px':30.5,'grid_8x8_hit_rate':.6,'p90_frame_error_px':float('nan')},'valid_rate':.9,'completed_points':19,'expected_points':20,'records':['private raw data']})
    assert 'records' not in r and 'p90_frame_error_px' not in r['filtered']
    rows=scorecard({'phase':'RESULT','evaluation':r})['rows']
    assert any('60%' in x for x in rows) and any('19/20' in x for x in rows)
    assert not any('停留' in x for x in rows)
    assert '没有有效' in scorecard({'phase':'RESULT'})['rows'][0]


def test_overlay_avoids_calibration_target_for_all_screen_regions():
    for x in (0,.1,.5,.9,1):
        for y in (0,.1,.5,.9,1):
            left,top=pill_position(1920,1080,(x,y))
            assert not(left-20<=x*1920<=left+460 and top-20<=y*1080<=top+152)
