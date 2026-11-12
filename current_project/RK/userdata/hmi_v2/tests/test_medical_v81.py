from itertools import combinations
from copy import deepcopy
from adapters.demo import DemoAdapter
from core.targets import demo_targets, medical_spec, center, select_target


def test_every_new_target_can_be_snapped_locked_executed_and_undone():
    size=[1920,1080]
    for page in range(4):
        d=DemoAdapter()
        for _ in range(page):d.on_action({'name':'demo.next'})
        for target in demo_targets(d.state,size):
            before=deepcopy(d.state)
            assert select_target(center(target),demo_targets(d.state,size),size)['id']==target['id']
            lock={'phase':'LOCKED','target':target,'cursor':{'xy':center(target),'screen_size':size}}
            d.on_action({'id':target['id'],'name':'demo.click','args':{'target_lock':lock}})
            if target.get('part'):assert d.state['part']==target['part'] and d.state['focus']
            else:assert d.state['inspection']==target['content']
            d.on_action({'name':'demo.undo','args':{'undo_id':target['id']}})
            for field in ('page','focus','part','inspection','crosshair','overlay','zoom'):
                assert d.state[field]==before[field]


def test_expansion_preserves_other_targets_and_no_invisible_duplicate_hits():
    base=demo_targets({'page':3},[1920,1080])
    for item in medical_spec()['pages'][3]['controls']:
        rows=demo_targets({'page':3,'inspection':item['content']},[1920,1080])
        assert len(rows)==10 and len({r['id'] for r in rows})==10
        for a,b in combinations(rows,2):
            x,y,w,h=a['rect'];xx,yy,ww,hh=b['rect']
            assert x+w<=xx or xx+ww<=x or y+h<=yy or yy+hh<=y
        for previous,current in zip(base,rows):
            if previous.get('content')!=item['content']:assert current['rect']==previous['rect']


def test_raw_and_annotation_views_use_same_case_plane_without_modifying_segmentation():
    controls=medical_spec()['pages'][3]['controls']
    raw=next(x for x in controls if x['content']=='raw_ct')
    label=next(x for x in controls if x['content']=='label_ct')
    assert raw['plane']==label['plane']=='axial'
    assert raw['overlay_override'] is False and label['overlay_override'] is True
    assert all(x['action']=='demo.inspect' for x in controls)

