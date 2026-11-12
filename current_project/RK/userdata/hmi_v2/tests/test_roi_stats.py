import struct
from core.roi_stats import command,decode


def face():
    return dict(epoch=7,src_ns=900_000_000,seq=9,faces=[dict(valid=True,primary=True,face_rect=[10.2,20.6,100.3,80.2],source_size=[640,360])])


def test_actual_plane_and_covering_rectangle():
    assert struct.unpack('<QQ8I',command(face(),7,10**9)[4:])==(7,900_000_000,9,1,10,20,111,101,640,360)


def test_missing_stale_or_ambiguous_face_disables_roi():
    for mutate in (lambda f:f.update(epoch=8),lambda f:f.update(src_ns=1),
                   lambda f:f['faces'][0].pop('source_size'),lambda f:f['faces'][0].update(valid=False),
                   lambda f:f['faces'][0].update(face_rect=[float('nan'),0,5,5])):
        f=face();mutate(f);assert struct.unpack_from('<I',command(f,7,10**9),24)[0]==0
    f=face();f['faces']*=2
    assert struct.unpack_from('<I',command(f,7,10**9),24)[0]==0


def test_snapshot_does_not_present_invalid_statistics_as_zero_measurement():
    assert not decode(b'bad')['available']
    hist=[5]+[0]*15
    reply=struct.pack('<i24I',0,1,1,9,2,8,5,100,0,*hist)
    assert decode(reply)['mean_linear_rgb10']==20
    broken=struct.pack('<i24I',0,1,1,9,2,8,6,100,0,*hist)
    assert decode(broken)['mean_linear_rgb10'] is None
