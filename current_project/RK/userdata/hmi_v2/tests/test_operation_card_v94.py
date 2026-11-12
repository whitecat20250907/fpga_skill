from ui.operation_card import card,placement

def test_pending_shows_actual_bound_action_and_same_hand_confirm():
    v=card({'state':'MENU','shortcut':{'label':'放大'},'menu':{'open':True}})
    assert v['title']=='待确认 · 放大' and '右手握拳' in v['hint'] and '取消' in v['hint']

def test_eye_lock_click_and_recording_are_distinct():
    v=card({'state':'IDLE','target_session':{'phase':'LOCKED','target':{'label':'肾脏 A'}}})
    assert '肾脏 A' in v['title'] and '点击' in v['hint']
    v=card({'state':'WRITING','writing':{'state':'REC'}})
    assert '记录轨迹' in v['title'] and '直接执行' in v['hint']

def test_bottom_right_card_moves_for_calibration_target():
    assert placement(1920,1080,440,126,{})==(1456,930)
    assert placement(1920,1080,440,126,{'state':'CALIBRATING','calib':{'target':[.9,.9]}})==(24,930)
    assert placement(1920,1080,440,126,{'state':'CALIBRATING','calib':{'target':[1800,1000]}})==(24,930)
