from itertools import combinations
import math
from adapters.demo import DemoAdapter
from core.targets import demo_targets,center,medical_spec
from core.targets import resolve_medical_click,same_target
import pytest

def test_case_links_remain_available_across_ct_and_knowledge_views():
    d=DemoAdapter()
    for _ in range(3):d.on_action({'name':'demo.next'})
    contents=[r['content'] for r in medical_spec()['pages'][3]['controls']]
    for content in contents:
        rows=demo_targets(d.state,[1920,1080])
        assert {r.get('content') for r in rows if r.get('content')}==set(contents)
        target=next(r for r in rows if r.get('content')==content)
        d.on_action({'name':'demo.activate','args':{'medical_target':target}})
        assert d.state['inspection']==content
        rows=demo_targets(d.state,[1920,1080]);assert len(rows)==10
        for a,b in combinations(rows,2):
            assert math.dist(center(a),center(b))>=200
            x,y,w,h=a['rect'];xx,yy,ww,hh=b['rect']
            assert x+w<=xx or xx+ww<=x or y+h<=yy or yy+hh<=y
    selected=next(r for r in rows if r.get('content')==contents[-1])
    d.on_action({'name':'demo.activate','args':{'medical_target':selected}})
    assert d.state['inspection'] is None

def test_targets_use_compact_labels_and_content_captions():
    for page in medical_spec()['pages']:
        for part in page['parts']:
            assert part['rect'][2]<=.155 and part['rect'][3]<=.065
            assert part['caption']
    case=medical_spec()['pages'][3]
    assert len(case['controls'])==7
    assert all(row['caption'] for row in case['controls'])
    assert [row['plane'] for row in case['controls'] if 'plane' in row]==['axial','coronal','sagittal','axial','axial']

def test_direct_ct_link_survives_reflow_but_gaze_lock_and_wrong_page_do_not():
    overview=demo_targets({'page':3},[1920,1080])
    detail=demo_targets({'page':3,'inspection':'axial'},[1920,1080])
    old=next(r for r in overview if r.get('content')=='axial')
    current=resolve_medical_click(old,detail)
    assert current['rect']!=old['rect'] and current['content']=='axial'
    assert not same_target(old,current)
    with pytest.raises(ValueError):resolve_medical_click(old,demo_targets({'page':2},[1920,1080]))
    with pytest.raises(ValueError):resolve_medical_click({**old,'action':'demo.next'},detail)
