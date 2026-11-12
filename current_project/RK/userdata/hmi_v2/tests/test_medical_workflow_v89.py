from copy import deepcopy
from itertools import combinations
import math
import pytest
from adapters.demo import DemoAdapter
from core.targets import demo_targets,medical_spec,medical_case,medical_view,center,select_target,resolve_medical_click

def activate(d,content,identity='test'):
    target=next(t for t in demo_targets(d.state,[1920,1080]) if t.get('content')==content)
    d.on_action({'name':'demo.activate','id':identity,'args':{'medical_target':target}})
    return target

@pytest.mark.parametrize('case',[c['id'] for c in medical_spec()['cases']])
def test_complete_same_case_review_and_undo(case):
    d=DemoAdapter();activate(d,'case:'+case);assert d.state['page']==1 and d.state['case_id']==case
    meta=medical_case(d.state);assert d.state['crosshair']==meta['initial_voxel'] and not d.state['overlay']
    activate(d,'locate:kidney_b');activate(d,'plane:coronal');position=list(d.state['crosshair'])
    activate(d,'mark');activate(d,'stage:2');assert d.state['crosshair']==position==d.state['suspect_voxel']
    tumor=next(t for t in demo_targets(d.state,[1920,1080]) if t.get('part')=='tumor')
    d.on_action({'name':'demo.activate','args':{'medical_target':tumor}})
    assert d.state['focus'] and d.state['crosshair']==[round(v) for v in meta['tumor_voxel']]
    before=deepcopy(d.state);activate(d,'record','record-1')
    assert d.state['page']==3 and d.state['confirmed']
    assert d.state['record']['case_id']==case and d.state['record']['source']=='user_confirmed_location'
    assert d.state['record']['voxel']==before['crosshair']
    assert d.state['record']['reviewed']=={'ct':True,'volume':True}
    d.on_action({'name':'demo.undo','args':{'undo_id':'record-1'}})
    assert d.state['page']==2 and d.state['record'] is None and not d.state['confirmed']

def test_old_case_lock_cannot_act_on_new_case_and_case_switch_is_undoable():
    d=DemoAdapter();activate(d,'case:case_00000');old=next(t for t in demo_targets(d.state,[1920,1080]) if t.get('content')=='annotation')
    activate(d,'stage:2');activate(d,'stage:3');activate(d,'stage:0');activate(d,'case:case_00001','case-switch')
    before=deepcopy(d.state)
    with pytest.raises(ValueError):d.on_action({'name':'demo.click','args':{'target_lock':{'target':old}}})
    assert d.state==before
    with pytest.raises(ValueError):resolve_medical_click(old,demo_targets(d.state,[1920,1080]))
    d.on_action({'name':'demo.undo','args':{'undo_id':'case-switch'}})
    assert d.state['case_id']=='case_00000' and d.state['page']==0

@pytest.mark.parametrize('page',range(4))
@pytest.mark.parametrize('plane',['axial','coronal','sagittal'])
def test_browser_rectangles_are_identical_to_gaze_targets_and_separated(page,plane):
    state={'page':page,'plane':plane,'case_id':'case_00000'};view=medical_view(state);targets=demo_targets(state,[1920,1080])
    for row,t in zip(view['rows'],targets):
        assert row['id']==t['id'] and [v*d for v,d in zip(row['rect'],[1920,1080,1920,1080])]==t['rect']
        assert select_target(center(t),targets,[1920,1080])['id']==t['id']
    for a,b in combinations(targets,2):
        assert math.dist(center(a),center(b))>=150
        x,y,w,h=a['rect'];xx,yy,ww,hh=b['rect']
        assert x+w<=xx or xx+ww<=x or y+h<=yy or yy+hh<=y

def test_rotation_opens_volume_preserves_ct_and_palm_stops():
    d=DemoAdapter();activate(d,'case:case_00000')
    d.on_action({'name':'demo.rotate','args':{'control_hand':{'track_id':2,'side':'Right'}}})
    started=d.rotation_tick;original=d.state['crosshair'][2]
    state={'context':'DEMO','health':{},'src_ns':started,'hand_src_ns':started,
           'hand_observations':[{'track_id':2,'side':'Right','gesture':'Closed_Fist','score':.9}]}
    for i in range(1,6):
        now=started+i*100_000_000;state['src_ns']=state['hand_src_ns']=now;d.tick(now,state)
    assert d.state['page']==2 and d.state['crosshair'][2]==original
    assert d.state['orbit'][1]>0
    state['hand_observations'][0]['gesture']='Open_Palm'
    for i in range(6,9):
        now=started+i*100_000_000;state['src_ns']=state['hand_src_ns']=now;d.tick(now,state)
    assert not d.state['rotating']

def test_viewing_never_automatically_claims_a_record_or_diagnosis():
    d=DemoAdapter();activate(d,'case:case_00002');activate(d,'stage:2');activate(d,'stage:3')
    assert not d.state['confirmed'] and d.state['record'] is None


@pytest.mark.parametrize('case',[c['id'] for c in medical_spec()['cases']])
@pytest.mark.parametrize('page',range(4))
def test_each_current_semantic_target_executes_and_exactly_undoes(case,page):
    d=DemoAdapter();activate(d,'case:'+case)
    from adapters.medical_workflow import stage
    stage(d,page)
    for target in demo_targets(d.state,[1920,1080]):
        before=deepcopy(d.state)
        d.on_action({'id':target['id'],'name':'demo.click','args':{'target_lock':{'phase':'LOCKED','target':target}}})
        d.on_action({'name':'demo.undo','args':{'undo_id':target['id']}})
        for key in before:
            if key not in ('revision','rotation_notice'):assert d.state[key]==before[key],(case,page,target['id'],key)

@pytest.mark.parametrize('meta',medical_spec()['cases'],ids=lambda c:c['id'])
def test_real_glb_uses_same_normalization_as_ct_marker(meta):
    import struct,json
    from pathlib import Path
    blob=(Path(__file__).resolve().parents[1]/'console/assets/medical'/meta['model']).read_bytes()
    length=struct.unpack_from('<I',blob,12)[0];gltf=json.loads(blob[20:20+length])
    positions=[gltf['accessors'][primitive['attributes']['POSITION']] for mesh in gltf['meshes'] for primitive in mesh['primitives']]
    lo=[min(a['min'][i] for a in positions) for i in range(3)]
    hi=[max(a['max'][i] for a in positions) for i in range(3)]
    norm=lambda p:[(p[i]-meta['mesh_center'][i])*meta['mesh_scale'] for i in range(3)]
    assert all(abs(x)<=1.326 for p in (lo,hi) for x in norm(p))
    assert max((hi[i]-lo[i])*meta['mesh_scale'] for i in range(3))==pytest.approx(2.65,abs=.002)
    v=meta['tumor_voxel'];ras=[meta['origin_ras_mm'][i]+v[i]*meta['spacing_mm'][i] for i in range(3)]
    p=[ras[0],ras[2],-ras[1]]
    assert all(lo[i]<=p[i]<=hi[i] for i in range(3))
