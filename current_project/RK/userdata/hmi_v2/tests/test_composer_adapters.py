import pytest
from core.config import load
from core.interaction.engine import Engine
from adapters.policy import ActionGate
from adapters.demo import DemoAdapter
from ui.mipi_composer import compose,registers
from hft2_wire import decode

@pytest.mark.parametrize('state',['BOOT','STANDBY','PRESENT','ONBOARD','CALIBRATING','IDLE','POINTING','MENU','WRITING','DEGRADED'])
def test_all_states_valid_hft2(state):
    e=Engine(load());e.epoch=7;e.state=state;s=e.snapshot(10**10)
    packet,csr=compose(s,None,None,10**10,42)
    frame=decode(packet)
    assert frame['metadata'].display_generation==42
    assert csr[str(0xcf8)]==42 and len(packet)<=1908

def test_adapter_no_duplicate_no_stale_no_fault_actions():
    gate=ActionGate();now=10**10;s=dict(epoch=7,context='DEMO',src_ns=now,state='IDLE',calibrated=True,health={'broken':[]})
    a=dict(id='7:1',epoch=7,context='DEMO',src_ns=now,name='demo.next')
    assert gate.accept(a,s,now)[0];assert not gate.accept(a,s,now)[0]
    assert not gate.accept(dict(a,id='7:2'),dict(s,state='DEGRADED'),now)[0]
    assert not gate.accept(dict(a,id='7:3',src_ns=now-400_000_000),s,now)[0]

def test_adapter_confirm_requires_action_gaze_time():
    gate=ActionGate();now=10**10;s=dict(epoch=7,context='DEMO',src_ns=now,state='IDLE',calibrated=True,health={'broken':[]})
    a=dict(id='7:1',epoch=7,context='DEMO',src_ns=now,name='demo.confirm',args={'cursor':dict(valid=True,frozen=False,xy=[100,100],src_ns=now-251_000_000)})
    assert not gate.accept(a,s,now)[0]

def test_demo_actions():
    d=DemoAdapter();d.on_action({'name':'demo.next'});assert d.state['page']==1
    d.on_action({'name':'demo.zoom_in'});assert d.state['zoom']==1.25
    d.on_action({'name':'demo.reset'});assert d.state['page']==1 and d.state['zoom']==1.

def test_ninth_menu_entry_does_not_overlap_count_in_ui11():
    csr=registers({'menu':{'open':True,'index':8,'items':list(range(9))}},1,'theater')
    value=csr[str(0xcb0)]
    assert value&1 and (value>>1)&15==8 and (value>>5)&15==9

def test_real_scorecard_bcd_and_missing_metric_flags():
    s={'calib':{'phase':'RESULT','evaluation':{'filtered':{'mean_frame_error_px':30.7,'p90_frame_error_px':90.1,'grid_8x8_hit_rate':.6},'valid_rate':.95,'completed_points':19,'expected_points':20}}}
    csr=registers(s,9,'theater')
    assert csr[str(0xce4)]==0x00900031
    assert csr[str(0xce8)]==0x00000060
    assert csr[str(0xcec)]==0x20190095
    assert csr[str(0xce0)]&7==4
    assert not csr[str(0xce0)]&(1<<11)  # No invented dwell accuracy.
    assert registers(s,9,'legacy')[str(0xce0)]==0
