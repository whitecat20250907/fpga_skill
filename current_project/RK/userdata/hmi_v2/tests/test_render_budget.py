from ui.render_budget import RenderBudget

def test_preview_cadence_does_not_defer_new_calibration_target():
    b=RenderBudget()
    assert b.due(1,('PREVIEW',0))
    assert not b.due(1.01,('PREVIEW',0))
    assert b.due(1.011,('CALIBRATE',0))
    assert not b.due(1.02,('CALIBRATE',0))
    assert b.due(1.021,('CALIBRATE',1))
    assert b.due(1.055,('CALIBRATE',1))

def test_hidden_windows_do_no_render_and_restore_immediately():
    b=RenderBudget();assert b.due(2,('TRACK',0))
    assert not b.due(2.001,('TRACK',0),visible=False)
    assert not b.due(3,('TRACK',0),visible=False)
    assert b.due(3.001,('TRACK',0))
    assert b.due(3.002,('RESULT',0))
