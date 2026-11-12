import time
import pytest
from core.config import load
from core.interaction.engine import Engine
from adapters.launcher import Launcher
from tests.test_interaction import healthy


def selected(index=2):
    e=Engine(load());t=time.monotonic_ns();healthy(e,t);e.system('menu',t)
    e.menu_index=index;e.event('confirm','button',t,t)
    return e,e.snapshot(t)


@pytest.mark.parametrize('index,context',[(0,'DESKTOP'),(1,'GAME'),(2,'DEMO')])
def test_explicit_menu_opens_once_without_calibration_or_application_action(index,context):
    e,s=selected(index);seen=[];l=Launcher(load(),None);l._focus=lambda c:seen.append(c) or True
    assert not s['calibrated'] and not e.out and not e.pending
    l.select(s);l.select(s)
    assert seen==[context]
    t=time.monotonic_ns()
    e.system('menu',t);e.menu_index=index;e.event('confirm','button',t,t)
    l.select(e.snapshot(t))
    assert seen==[context,context] and not e.out


@pytest.mark.parametrize('case',['startup','expired','future','estop','broken','calibrating','mismatch'])
def test_no_automatic_launch_or_replay_when_not_allowed(case):
    e,s=selected();seen=[];l=Launcher(load(),None);l._focus=lambda c:seen.append(c) or True
    if case=='startup':s['application_request']=None
    elif case=='expired':s['application_request']['src_ns']=time.monotonic_ns()-8_100_000_000
    elif case=='future':s['application_request']['src_ns']=time.monotonic_ns()+1_000_000_000
    elif case=='estop':s['estop']=True
    elif case=='broken':s['health']['broken']=['gaze']
    elif case=='calibrating':s['state']='CALIBRATING'
    elif case=='mismatch':s['application_request']['context']='GAME'
    l.select(s);assert not seen and not e.out


def test_estop_then_fast_resume_cannot_replay_pending_open():
    e,s=selected();t=s['src_ns'];e.system('estop',t+1);e.system('resume',t+2)
    assert e.snapshot(t+2)['application_request'] is None
    seen=[];l=Launcher(load(),None);l._focus=lambda c:seen.append(c) or True
    l.select(e.snapshot(t+2));assert not seen


def test_game_menu_requires_its_actual_process_working_directory(tmp_path):
    import os,sys
    from pathlib import Path
    from types import SimpleNamespace
    from adapters.launcher import owned_game_menu
    if sys.platform!='linux':pytest.skip('Actual /proc process identity check runs on target Linux')
    class Window:
        def get_wm_class(self):return ('launch.py','Launch.py')
        def get_full_property(self,*_):return SimpleNamespace(value=[os.getpid()])
    assert owned_game_menu(Window(),Path.cwd(),lambda v:v)
    assert not owned_game_menu(Window(),tmp_path,lambda v:v)


@pytest.mark.parametrize('context',['GAME','DEMO','BASIC'])
@pytest.mark.parametrize('uid',[0,1000])
def test_app_children_reserve_dma_cores_and_game_uses_original_launch_py(tmp_path,monkeypatch,context,uid):
    import adapters.launcher as module
    from types import SimpleNamespace
    c=load();c['paths']['logs']=str(tmp_path);c['paths']['game']=str(tmp_path/'game')
    game=tmp_path/'game';(game/'build-arm64').mkdir(parents=True);(game/'build-arm64/freeciv-gtk3.22').touch()
    monkeypatch.setattr(module.os,'geteuid',lambda:uid,raising=False);monkeypatch.setattr(module.shutil,'which',lambda _: '/usr/bin/chromium')
    calls=[]
    monkeypatch.setattr(module.subprocess,'Popen',lambda cmd,**kw:calls.append((cmd,kw)) or SimpleNamespace(poll=lambda:None))
    l=Launcher(c,None);l._focus=lambda _:False
    t=time.monotonic_ns();l.select(dict(state='ONBOARD',context=context,calibrated=False,application_request=dict(id='test',context=context,src_ns=t)))
    assert 23<l.deadline-time.monotonic()<=25
    assert calls[0][0][:3]==['taskset','-c','0,1']
    assert ('runuser' in calls[0][0]) == (uid==0)
    if uid==0:assert calls[0][0][3:7]==['runuser','-u','linaro','--']
    if context=='GAME':
        assert calls[0][1]['cwd']==game and str(game/'launch.py') in calls[0][0]
        assert not any('start-rk3576.sh' in arg for arg in calls[0][0])
    l.close()


def test_shared_chromium_process_uses_url_window_identity():
    from adapters.launcher import presentation_kind
    assert presentation_kind('127.0.0.1__basic hmimedical')=='BASIC'
    assert presentation_kind('127.0.0.1__demo hmibasic')=='DEMO'
    assert presentation_kind('chromium chromium') is None


def test_closed_browser_window_can_reopen_while_shared_process_lives(tmp_path,monkeypatch):
    import adapters.launcher as module
    from types import SimpleNamespace
    c=load();c['paths']['logs']=str(tmp_path)
    monkeypatch.setattr(module.os,'geteuid',lambda:1000,raising=False)
    monkeypatch.setattr(module.shutil,'which',lambda _: '/usr/bin/chromium')
    calls=[];monkeypatch.setattr(module.subprocess,'Popen',lambda cmd,**kw:calls.append(cmd) or SimpleNamespace(poll=lambda:None))
    l=Launcher(c,None);l._focus=lambda _:False
    def state(key):return dict(state='ONBOARD',context='BASIC',application_request=dict(id=key,context='BASIC',src_ns=time.monotonic_ns()))
    l.select(state('first'));l.select(state('first'));assert len(calls)==1
    l.select(state('second'));assert len(calls)==2
    l.close()
