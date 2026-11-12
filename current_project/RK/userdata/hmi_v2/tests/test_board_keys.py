from core.board_keys import ButtonLogic


def test_menu_short_and_long_do_not_double_fire():
    b=ButtonLogic();assert b.event(139,1,10,10)==[]
    assert b.event(139,0,10.1,10.1)==['app_basic']
    b.event(139,1,11,11)
    assert b.tick(13.1)==['estop']
    assert b.tick(13.2)==[] and b.event(139,0,13.3,13.3)==[]


def test_key_repeat_and_stale_events_do_not_execute():
    b=ButtonLogic();b.event(114,1,10,10)
    assert b.event(114,2,10.1,10.1)==[]
    assert b.event(114,0,10.2,10.2)==['app_game']
    b.event(114,1,11,11)
    assert b.event(114,0,11.2,12)==[]
    assert b.event(114,0,12.1,12.1)==[]


def test_long_shortcuts_do_not_emit_short_action_on_release():
    for code,command in ((158,'dual'),):
        b=ButtonLogic();assert not b.event(code,1,10,10)
        assert not b.tick(11.1)
        assert b.tick(11.3)==[command]
        assert not b.tick(11.4)
        assert not b.event(code,0,11.5,11.5)
        assert not b.event(code,1,12,12)
        assert b.event(code,0,13.3,13.3)==[command]
