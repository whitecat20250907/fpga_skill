from pathlib import Path
import ctypes,struct,threading
import pytest
from core.config import ROOT
from core.frame_ring import SIZE,SLOT,PAYLOAD,SLOT_HEADER

def test_native_writer_two_readers_no_torn_frames():
    import sys
    p=ROOT/'native/fpga_io'/('ring_test.dll' if sys.platform=='win32' else 'libring.so')
    if not p.exists():pytest.skip('Build native ring library first')
    lib=ctypes.CDLL(str(p));lib.hmi_ring_init.argtypes=[ctypes.c_void_p,ctypes.c_uint64]
    lib.hmi_ring_publish.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint64]
    lib.hmi_ring_snapshot.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint64]
    ring=ctypes.create_string_buffer(SIZE);lib.hmi_ring_init(ring,7);stop=threading.Event();accepted=[0,0];errors=[]
    def reader(index):
        out=ctypes.create_string_buffer(SLOT);serial=0
        while not stop.is_set():
            result=lib.hmi_ring_snapshot(ring,out,SLOT,serial)
            if result==1:
                data=out.raw;head=SLOT_HEADER.unpack_from(data);serial=head[1]
                if data[64:]!=bytes([head[2]%256])*PAYLOAD:errors.append('torn frame')
                accepted[index]+=1
    ts=[threading.Thread(target=reader,args=(i,)) for i in range(2)]
    for t in ts:t.start()
    for i in range(1,65):
        payload=ctypes.create_string_buffer(bytes([i])*PAYLOAD)
        assert lib.hmi_ring_publish(ring,payload,i,i*100,i*100+1,i)==0
    stop.set()
    for t in ts:t.join(timeout=5);assert not t.is_alive()
    assert not errors and all(n>0 for n in accepted)
