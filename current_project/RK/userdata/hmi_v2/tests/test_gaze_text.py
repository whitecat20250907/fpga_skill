from ui.gaze_text import interaction_text

def test_engine_control_does_not_appear_as_disabled_legacy_mouse():
    old='有效人脸    处理 29.7 FPS    鼠标：关    停留点击：关'
    text=interaction_text(old,dict(state='POINTING'))
    assert '29.7 FPS' in text and '眼控已唤醒' in text and '鼠标：关' not in text

def test_precalibration_instructions_follow_current_stage():
    old='保持头部稳定、眼睛睁开，让脸居中；准备好后按空格开始 13 点标定。'
    assert '完整人脸' in interaction_text(old,dict(state='STANDBY'))
    assert '竖拇指或按确认' in interaction_text(old,dict(state='ONBOARD'))
    assert '比 V' in interaction_text(old,dict(state='MENU'))
    assert interaction_text('原始1080p预览',{})=='原始1080p预览'
