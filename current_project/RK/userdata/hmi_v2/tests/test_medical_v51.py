import json,struct,math
from itertools import combinations
from pathlib import Path
import pytest
from core.targets import demo_targets,medical_spec,center,valid_target
from adapters.demo import DemoAdapter
from core.config import load
from core.interaction.engine import Engine
from tests.test_interaction import healthy,message

def test_shared_geometry_spaced_and_in_bounds():
    for page in range(3):
        rows=demo_targets({'page':page},[1920,1080])
        assert len(rows)==[8,8,8][page] and all(valid_target(r,[1920,1080]) for r in rows)
        for a,b in combinations(rows,2):
            assert math.dist(center(a),center(b))>=200
            x,y,w,h=a['rect'];xx,yy,ww,hh=b['rect']
            assert x+w<=xx or xx+ww<=x or y+h<=yy or yy+hh<=y

def test_every_anatomical_target_matches_real_glb_mesh():
    for p in medical_spec()['pages']:
        data=(Path(__file__).resolve().parents[1]/'console/assets/medical'/p['model']).read_bytes()
        n=struct.unpack_from('<I',data,12)[0];g=json.loads(data[20:20+n])
        names=[o['name'].lower() for o in g['nodes'] if 'mesh' in o]
        for part in p['parts']:
            pattern=part['match']
            match=(lambda n:n.endswith('_l')) if pattern=='__left__' else (lambda n:n.endswith('_r')) if pattern=='__right__' else (lambda n:any(s in n for s in ('pons','medulla','midbrain'))) if pattern=='__stem__' else (lambda n:pattern in n)
            assert any(match(n) for n in names),(p['key'],part)

def test_focus_targets_real_part_and_page_change_clears_it():
    d=DemoAdapter();r=next(r for r in demo_targets(d.state,[1920,1080]) if r['part']=='left_ventricle')
    action={'name':'demo.activate','args':{'medical_target':r}}
    d.on_action(action);assert d.state['focus'] and d.state['part']=='left_ventricle'
    d.on_action(action);assert not d.state['focus']
    d.on_action({'name':'demo.rotate'});assert d.state['rotation']==1
    d.on_action({'name':'demo.next'});assert d.state['page']==1 and not d.state['focus'] and d.state['part'] is None
    with pytest.raises(ValueError):d.on_action(action)

def test_manual_target_passes_engine_and_unknown_id_cannot_execute():
    e=Engine(load());t=10**10;healthy(e,t);e.context='DEMO';e._state('IDLE',t)
    rows=demo_targets({},[1920,1080]);e.feed('app.targets',message(t,context='DEMO',targets=rows,screen_size=[1920,1080]),t)
    e.feed('cmd.system',message(t+1,command='medical_target',target_id=rows[0]['id']),t+1)
    assert e.out[-1]['name']=='demo.activate' and e.out[-1]['args']['medical_target']==rows[0]
    count=len(e.out);e.feed('cmd.system',message(t+2,command='medical_target',target_id='demo:evil'),t+2)
    assert len(e.out)==count
