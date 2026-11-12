import json,math,struct,time
from pathlib import Path
from itertools import combinations
import pytest
from adapters.demo import DemoAdapter
from core.bindings import options,validate,defaults,LABELS
from core.targets import medical_spec,demo_targets,center

def rotating():
 d=DemoAdapter();d.on_action({'name':'demo.rotate','args':{'control_hand':{'track_id':7,'side':'Right'}}});return d

def observe(d,elapsed,rows):
 now=d.rotation_seen+int(elapsed*1e9)
 d.tick(now,{'context':'DEMO','src_ns':now,'hand_src_ns':now,'hand_observations':rows})

def test_rotation_continuous_pause_palm_and_no_other_hand_stop():
 d=rotating();right={'track_id':7,'side':'Right','gesture':'Closed_Fist','score':.9};left={'track_id':9,'side':'Left','gesture':'Open_Palm','score':.99}
 observe(d,.1,[right,left]);assert d.state['rotating'] and d.state['orbit'][1]>0
 right.update(gesture='Open_Palm',score=.48);observe(d,.08,[right]);assert d.state['rotating']
 observe(d,.13,[right]);assert not d.state['rotating']
 angle=d.state['orbit'][1];observe(d,.2,[right]);assert d.state['orbit'][1]==angle

def test_rotation_loss_tolerance_track_recovery_and_departure():
 d=rotating();observe(d,.3,[]);assert d.state['rotating']
 observe(d,.1,[{'track_id':8,'side':'Right','gesture':'Closed_Fist','score':.8}]);assert d.rotation_hand['track_id']==8
 observe(d,.65,[{'track_id':9,'side':'Left','gesture':'Closed_Fist','score':1}]);assert not d.state['rotating']

def test_rotation_duplicate_hand_sample_does_not_accumulate_palm():
 d=rotating();start=d.rotation_seen;row={'track_id':7,'side':'Right','gesture':'Open_Palm','score':.9}
 for i in range(1,10):d.tick(start+i*50_000_000,{'context':'DEMO','src_ns':start+i*50_000_000,'hand_src_ns':start+10_000_000,'hand_observations':[row]})
 assert d.state['rotating']

def test_rotation_web_toggle_pause_and_page_reset():
 d=DemoAdapter();d.on_action({'name':'demo.rotate'});observe(d,.1,[]);assert d.state['rotating']
 d.on_action({'name':'demo.rotate'});assert not d.state['rotating']
 d.on_action({'name':'demo.rotate'});d.on_action({'name':'demo.next'});assert not d.state['rotating'] and d.state['orbit']==[0,0,0]
 d.on_action({'name':'demo.rotate'});now=time.monotonic_ns();d.tick(now,{'context':'GAME','src_ns':now});assert not d.state['rotating']

def test_only_simple_actions_exposed_old_focus_binding_migrates():
 opts=options('DEMO');assert 'demo.click' not in opts and 'demo.rotate' in opts
 assert not any(x in opts for x in ['demo.focus','demo.axis','demo.plane','demo.window','demo.slice_next','demo.rotate_reverse'])
 assert len(opts)==len(set(opts)) and len({LABELS[x] for x in opts if x})==len(opts)-1
 bindings=defaults({});bindings['stroke']['DEMO']['L']='demo.focus';assert validate(bindings)['stroke']['DEMO']['L']=='system.eye_takeover'

def test_all_targets_nonoverlapping_and_spaced():
 for i,p in enumerate(medical_spec()['pages']):
  rows=demo_targets({'page':i},[1920,1080]);assert len(rows)==len(p['parts'])+len(p.get('controls',[]))
  for a,b in combinations(rows,2):
   assert math.dist(center(a),center(b))>=200,(i,a['id'],b['id'])
   x,y,w,h=a['rect'];xx,yy,ww,hh=b['rect'];assert x+w<=xx or xx+ww<=x or y+h<=yy or yy+hh<=y

def test_real_case_grid_centroid_and_mesh_registration():
 root=Path(__file__).resolve().parents[1]/'console/assets/medical/kits19';m=json.loads((root/'case.json').read_text());assert medical_spec()['pages'][-1]['case']==m
 n=math.prod(m['shape']);assert (root/'ct.i16').stat().st_size==n*2 and (root/'labels.u8').stat().st_size==n
 v=m['tumor_voxel'];ras=[m['origin_ras_mm'][i]+v[i]*m['spacing_mm'][i] for i in range(3)];assert max(abs(a-b) for a,b in zip(ras,m['tumor_ras_mm']))<1e-6
 labels=(root/'labels.u8').read_bytes();x,y,z=map(round,v);assert labels[(x*m['shape'][1]+y)*m['shape'][2]+z]==2
 data=(root/'case_00000.glb').read_bytes();length=struct.unpack_from('<I',data,12)[0];g=json.loads(data[20:20+length]);names={node['name'] for node in g['nodes'] if 'mesh' in node};assert names=={'kidney_a','kidney_b','tumor'}
 assert 'CC BY-NC-SA 4.0' in (root/'ATTRIBUTION.md').read_text()

def test_locked_click_focuses_actual_case_annotation():
 d=DemoAdapter()
 for _ in range(3):d.on_action({'name':'demo.next'})
 r=next(r for r in demo_targets(d.state,[1920,1080]) if r['part']=='tumor')
 lock={'phase':'LOCKED','target':r,'cursor':{'xy':center(r),'screen_size':[1920,1080]}}
 d.on_action({'name':'demo.click','args':{'target_lock':lock}})
 assert d.state['part']=='tumor' and d.state['focus']
 assert d.state['crosshair']==[round(x) for x in medical_spec()['pages'][3]['case']['tumor_voxel']]
 d.on_action({'name':'demo.next'})
 with pytest.raises(ValueError):d.on_action({'name':'demo.click','args':{'target_lock':lock}})


def test_hdmi_targets_are_only_medical_content_and_inspection_matches_catalog():
 d=DemoAdapter()
 for i in range(4):
  rows=demo_targets(d.state,[1920,1080])
  assert all(r['action'] in ('demo.focus','demo.inspect') for r in rows)
  assert not any(r['action'] in ('demo.next','demo.cancel','demo.rotate','demo.reset','demo.zoom_in','demo.zoom_out') for r in rows)
  d.on_action({'name':'demo.next'})
 for _ in range(3):d.on_action({'name':'demo.next'})
 for content in ('axial','coronal','sagittal','report'):
  row=next(r for r in demo_targets(d.state,[1920,1080]) if r.get('content')==content)
  d.on_action({'name':'demo.activate','args':{'medical_target':row}})
  rows=demo_targets(d.state,[1920,1080]);assert len(rows)==10
  expanded=next(r for r in rows if r.get('content')==content);assert expanded['rect'][2]>row['rect'][2]
  d.on_action({'name':'demo.activate','args':{'medical_target':expanded}});assert d.state['inspection'] is None

def test_select_kidney_updates_ct_to_that_kidney_without_extra_controls():
 d=DemoAdapter()
 for _ in range(3):d.on_action({'name':'demo.next'})
 m=medical_spec()['pages'][3]['case']
 for part in ('kidney_a','kidney_b','tumor'):
  row=next(r for r in demo_targets(d.state,[1920,1080]) if r['part']==part)
  d.on_action({'name':'demo.activate','args':{'medical_target':row}})
  assert d.state['part']==part and d.state['crosshair']==[round(x) for x in m['part_voxels'][part]]
