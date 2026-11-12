import json,math
from pathlib import Path
import pytest
from ui.face_surface import surface
from ui.mipi_composer import compose
from hft2_wire import decode

def points():
    rows=json.loads((Path(__file__).parent/'fixtures/face_canonical_v88.json').read_text())
    # Synthetic iris centres/rings ONLY for offline capacity fixtures.
    for ids in ((33,159,133,145),(362,386,263,374)):
        c=[sum(rows[i][axis] for i in ids)/4 for axis in range(3)]
        rows.append(c)
        rows.extend([[c[0]+2*math.cos(i*math.pi/2),c[1]+2*math.sin(i*math.pi/2),c[2]] for i in range(4)])
    return rows

@pytest.mark.parametrize('count', [34,35,36,50,82])
def test_surface_capacity_and_measured_coordinates(count):
    raw=points();p,e,t=surface(raw,count,36,56)
    assert len(p)==count and len(e)<=36 and len(t)==44
    assert all(0<=i<count for row in e for i in row[:2])
    assert all(0<=i<count for row in t for i in row[:3])
    assert all(0<=row[3]<=3 for row in t)
    assert len({row[3] for row in t})>=2
    assert surface([[x+100,y-50,z+30] for x,y,z in raw],count,36,56)[1:]==(e,t)

@pytest.mark.parametrize('profile',['legacy','theater'])
@pytest.mark.parametrize('trace',[False,True])
def test_full_scene_preserves_two_hands_projection_and_48_trace(profile,trace):
    now=10**10
    state=dict(epoch=7,state='IDLE',people='single',calibrated=True,
        active_hand_ids=[1,2],layer='WRITE' if trace else 'CONTROL',
        writing={'state':'REC' if trace else 'IDLE'},
        cursor=dict(valid=True,src_ns=now,xy=[700,300],screen_size=[1920,1080]))
    face=dict(epoch=7,seq=11,src_ns=now,faces=[dict(track_id=1,primary=True,valid=True,landmarks=points())])
    hands=dict(epoch=7,seq=11,src_ns=now,hands=[dict(track_id=i,side=side,score=.9,gesture='Open_Palm',
        world21=[[.03*math.cos(j),.04*math.sin(j),.01*math.sin(j*.3)] for j in range(21)])
        for i,side in ((1,'Left'),(2,'Right'))],
        recorder={'2':dict(state='REC',points=[[50+10*i,180+30*math.sin(i)] for i in range(48)])} if trace else {})
    scene=decode(compose(state,face,hands,now,1,profile)[0])['scene']
    counts=[sum(v[0]==i for v in scene.vertices) for i in range(5)]
    assert counts==([21,21,29,4,48] if trace else [21,21,29,4,0])
    assert len(scene.vertices)==sum(counts) and len(scene.edges)<=128 and len(scene.triangles)==12
    assert scene.valid==(31 if trace else 15)

def test_missing_iris_does_not_make_up_points():
    assert len(surface(points()[:468])[0])<82

@pytest.mark.parametrize('bad',[float('nan'),float('inf'),50000])
def test_invalid_measured_point_rejects_surface(bad):
    raw=points();raw[450][1]=bad
    with pytest.raises(ValueError):surface(raw)
