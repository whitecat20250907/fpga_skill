import importlib.util,sys,struct,zlib
import numpy as np
import pytest
from core.config import ROOT
from core.frame_ring import decode_slot,PAYLOAD,SLOT_HEADER,FrameRing

spec=importlib.util.spec_from_file_location('hmi_test_detector',ROOT/'vendor/vision_npu/detector_frame.py')
detector=importlib.util.module_from_spec(spec);spec.loader.exec_module(detector)

def sample():
    b=np.arange(PAYLOAD,dtype=np.uint8).tobytes()
    return SLOT_HEADER.pack(2,1,5,1,100,100,120,900,zlib.crc32(b),1)+b

def test_three_planes_byte_exact_and_immutable():
    raw=sample();f=decode_slot(raw,7,detector.make_frame)
    assert f.rgb.shape==(360,640,3) and not f.rgb.flags.writeable
    assert f.rgb.tobytes()==raw[64:64+691200]
    assert detector.detector_input(f.rgb,128).tobytes()==raw[64+691200:64+740352]
    assert detector.detector_input(f.rgb,192).tobytes()==raw[64+740352:]
    assert detector.detector_input(f.rgb.copy(),128) is None

@pytest.mark.parametrize('offset',[0,20,60,64,1000,850000])
def test_invalid_or_torn_slot_rejected(offset):
    raw=bytearray(sample());raw[offset]^=1
    with pytest.raises(ValueError):decode_slot(bytes(raw),7,detector.make_frame)

def test_reader_detects_replaced_owner_even_if_old_mapping_survives(tmp_path):
    path=tmp_path/'frames.memfd';path.write_bytes(b'old')
    reader=FrameRing.__new__(FrameRing);reader.path=path
    stat=path.stat();reader.identity=(stat.st_dev,stat.st_ino)
    reader.check_owner()
    other=tmp_path/'replacement';other.write_bytes(b'new');other.replace(path)
    with pytest.raises(RuntimeError,match='replaced'):reader.check_owner()
    path.unlink()
    with pytest.raises(RuntimeError,match='unavailable'):reader.check_owner()
