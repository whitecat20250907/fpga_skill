from ui.presentation_regions import regions

def test_both_cursor_positions_and_preview_are_repainted():
    r=regions('TRACK',(1920,1080),(360,640),(200,300),(400,500),38)
    assert (176,276,49,49) in r and (376,476,49,49) in r
    assert (1590,10,320,180) in r
    r=regions('TRACK',(1920,1080),None,(200,300),None,38)
    assert (176,276,49,49) in r

def test_preview_uses_original_scaling_and_calibration_does_not_repeat_flip():
    assert (480,270,960,540) in regions('PREVIEW',(1920,1080),(360,640),None,None,38)
    assert regions('CALIBRATE',(1920,1080),None,None,None,38)==[]
