import copy
from core.bindings import defaults,validate,SHOWCASE,options
from core.config import load
from core.interaction.engine import Engine
from core.board_keys import ButtonLogic
from tests.test_interaction import healthy
from console.basic_preview import overlays,CounterRate


def test_old_saved_mappings_preserved_and_basic_added():
    old=defaults(load())
    for rows in old.values():rows.pop('BASIC')
    old['stroke']['DEMO']['L']='demo.zoom_out'
    before=copy.deepcopy(old);new=validate(old)
    assert old==before
    for kind in old:
        for c in old[kind]:assert new[kind][c]==old[kind][c]
    assert new['stroke']['BASIC']==SHOWCASE
    for context in new['stroke']:
        for target in SHOWCASE.values():assert target in options(context)


def test_basic_entry_is_actual_application_request_and_leaves_again():
    e=Engine(load());t=10**10;healthy(e,t)
    e.system('app_basic',t)
    assert e.context=='BASIC' and e.application_request['context']=='BASIC'
    assert not e.out and not e.pending
    e.event('next','Victory',t+1,t+1) # No fallback app action or missing dictionary.
    e.system('app_demo',t+2)
    assert e.context=='DEMO'


def test_five_key_entries_no_double_trigger_or_power_key():
    for code,command in ((139,'app_basic'),(115,'app_demo'),(114,'app_game'),(158,'single')):
        b=ButtonLogic();b.event(code,1,10,10)
        assert b.event(code,0,10.1,10.1)==[command]
    b=ButtonLogic();b.event(158,1,10,10)
    assert b.tick(11.3)==['dual']
    assert b.event(158,0,11.4,11.4)==[]
    for code in (116,408):
        b=ButtonLogic();b.event(code,1,10,10);assert not b.event(code,0,10.1,10.1)


def test_live_overlay_has_correct_coordinate_contract_and_source_age():
    now=10**10;msg={'epoch':7,'src_ns':now-20_000_000,'seq':12,'faces':[{'valid':True,'face_rect':[64,36,128,72],'source_size':[640,360],'track_id':1}]}
    rows=overlays({'vision.face':msg},7,now-5_000_000,now)
    assert rows[0]['rect']==[.1,.1,.2,.2] and rows[0]['offset_ms']==15
    assert not overlays({'vision.face':msg},8,now,now)
    assert not overlays({'vision.face':msg},7,now,now+1_000_000_000)
    msg['faces'][0]['face_rect'][0]=float('nan')
    assert not overlays({'vision.face':msg},7,now,now)


def test_frame_rate_is_source_delta_not_browser_refresh_and_resets_on_epoch():
    r=CounterRate();assert r.update('epoch1',100,10**10) is None
    assert r.update('epoch1',120,11*10**9)==20
    assert r.update('epoch1',120,11*10**9)==20
    assert r.update('epoch2',200,12*10**9) is None
    assert r.update('epoch2',1,13*10**9) is None


def test_menu_shortcut_can_resume_from_emergency_pause():
    e=Engine(load());t=10**10;healthy(e,t)
    e.system('estop',t);assert e.estop
    e.system('app_basic',t+1)
    assert not e.estop and e.context=='BASIC' and not e.pending and not e.out


def test_large_frame_work_stays_on_one_persistent_worker(tmp_path):
    import threading,time
    from concurrent.futures import ThreadPoolExecutor
    from console.basic_preview import BasicPreview
    preview=BasicPreview(tmp_path);seen=[]
    def encode(*_):
        seen.append(threading.get_ident());time.sleep(.01);return seen[-1]
    preview._capture=encode
    try:
        with ThreadPoolExecutor(max_workers=6) as requests:
            results=list(requests.map(lambda _:preview.capture({},{}),range(12)))
        assert len(set(results))==1 and results[0]!=threading.get_ident()
    finally:preview.close()
