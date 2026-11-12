import copy,json,struct
import pytest
from console.basic_preview import face_landmarks,pack_images

def message(count=478):
 return {'vision.face':dict(epoch=7,seq=23,src_ns=1000000000,faces=[dict(valid=True,track_id=1,source_size=[640,360],landmarks=[[100+i*.1,80+i*.05,0] for i in range(count)])])}

@pytest.mark.parametrize('count',[468,478])
def test_preserves_all_measured_points(count):
 rows=face_landmarks(message(count),7,1100000000,1200000000)
 assert len(rows)==1 and len(rows[0]['points'])==count
 assert rows[0]['offset_ms']==100 and rows[0]['source_sequence']==23
 assert rows[0]['points'][10]==[101,80.5,0]
 d=pack_images(dict(faces=rows,raw_image=None,model_image=b'jpeg',planes=[]))
 size=struct.unpack('<I',d[4:8])[0]
 assert len(json.loads(d[8:8+size])['faces'][0]['points'])==count

@pytest.mark.parametrize('epoch,now',[(8,1200000000),(7,1600000000),(7,900000000)])
def test_stale_epoch_and_future_rejected(epoch,now):
 assert face_landmarks(message(),epoch,1100000000,now)==[]

@pytest.mark.parametrize('bad',[float('nan'),float('inf'),40000])
def test_nonfinite_points_rejected(bad):
 m=message();m['vision.face']['faces'][0]['landmarks'][9][0]=bad
 assert face_landmarks(m,7,1100000000,1200000000)==[]

def test_two_people_bounded_and_no_padding():
 m=message();m['vision.face']['faces']*=3
 assert len(face_landmarks(m,7,1100000000,1200000000))==2
 assert face_landmarks(message(477),7,1100000000,1200000000)==[]
