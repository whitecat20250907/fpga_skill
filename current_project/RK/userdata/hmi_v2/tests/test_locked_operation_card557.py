from copy import deepcopy

from tests.test_locked_rotation295 import locked, ack
from ui.operation_card import card


def test_locked_rotation_proposal_prompts_confirmation_not_target_click():
    x = locked()
    x.e.bindings['static']['DEMO']['Victory'] = 'demo.rotate'
    x.frames('Closed_Fist')
    x.frames('Victory')
    view = card(x.e.snapshot(x.t))
    assert '待确认' in view['title']
    assert '右手握拳执行' in view['hint']
    assert '点击' not in view['hint']
    x.frames('Closed_Fist')
    assert ack(x)['name'] == 'demo.rotate'
    assert x.d.state['rotating']


def test_locked_pointer_keeps_trajectory_instructions():
    x = locked()
    x.frames('Pointing_Up', 2, recorder={'1': {'state': 'REC'}})
    view = card(x.e.snapshot(x.t))
    assert view['title'] == '正在记录轨迹'
    assert '右手握拳结束' in view['hint']
    assert '点击' not in view['hint']


def test_changed_page_does_not_offer_click_on_expired_target():
    x = locked()
    pointer = deepcopy(x.e.cursor)
    assert x.e._action('demo.next', 'console', x.t, x.t)
    ack(x)
    view = card(x.e.snapshot(x.t))
    assert view['title'] == '位置已保持'
    assert '眼控选择新目标' in view['hint']
    assert '旋转、缩放可继续' in view['hint']
    assert '点击' not in view['hint']
    assert x.e.cursor == pointer


def test_locked_idle_undo_hint_does_not_require_both_hands():
    x = locked()
    view = card(x.e.snapshot(x.t))
    assert '右手张掌→握拳点击' in view['hint']
    assert '任一手' in view['hint']


def test_locked_arm_hint_explains_next_gesture():
    x = locked()
    x.frames('Closed_Fist')
    view = card(x.e.snapshot(x.t))
    assert view['title'] == '手势识别已开启'
    assert '伸食指切换轨迹' in view['hint']
