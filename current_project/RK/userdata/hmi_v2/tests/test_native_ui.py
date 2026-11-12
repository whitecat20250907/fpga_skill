"""Exercise the unchanged TWB2 protocol core through real compiled C glue."""
import ctypes as C,struct,sys,zlib
from core.config import ROOT
from ui.mipi_composer import compose

READ=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint32,C.POINTER(C.c_uint32))
WRITE=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint32,C.c_uint32)
CLOCK=C.CFUNCTYPE(C.c_uint64,C.c_void_p)
class IO(C.Structure):_fields_=[('context',C.c_void_p),('read32',READ),('write32',WRITE),('monotonic_ns',CLOCK)]
class Session(C.Structure):
    _fields_=[('io',IO)]+[(n,C.c_uint32) for n in ('depth','maximum','flush_generation','generation','accepted_before','rejected_before','reserve')]+[(n,C.c_uint64) for n in ('token','prepared_ns')]+[(n,C.c_uint) for n in ('bound','needs_flush','flush_pending','prepared')]

class Device:
    def __init__(self):
        self.writes=[];self.payload=bytearray();self.now=123_456_789
        self.regs={0xc00:0x32544648,0xc38:0x32425754,0xc3c:(2048<<16)|1908,0xc04:16,0xc08:2048,0xcf0:0x55493130}
        self.read_cb=READ(self.read);self.write_cb=WRITE(self.write);self.clock_cb=CLOCK(lambda _:self.now)
        self.io=IO(None,self.read_cb,self.write_cb,self.clock_cb);self.session=Session()
        path=ROOT/'native/fpga_io'/('ui_test.dll' if sys.platform=='win32' else 'libui_test.so')
        self.lib=C.CDLL(str(path));self.lib.twb_init.argtypes=[C.POINTER(Session),IO]
        self.lib.twb_probe.argtypes=[C.POINTER(Session),C.c_void_p]
        self.lib.twb_flush_begin.argtypes=[C.POINTER(Session)]
        self.lib.hmi_ui_submit.argtypes=[C.POINTER(Session),C.c_void_p,C.c_size_t,C.c_int,C.POINTER(C.c_uint32)]
        self.lib.twb_init(C.byref(self.session),self.io)
        assert self.lib.twb_probe(C.byref(self.session),None)==0
        assert self.lib.twb_flush_begin(C.byref(self.session))==0
        self.writes.clear()
    def read(self,_,off,out):out[0]=self.regs.get(off,0);return 0
    def write(self,_,off,value):
        self.writes.append((off,value))
        if off==0xc14:self.regs[0xc1c]=self.regs.get(0xc1c,0)+1;self.regs[0xc04]=16
        elif off==0xc28:self.regs[0xc04]|=32
        elif off==0xc10:self.payload+=struct.pack('<I',value);self.regs[0xc0c]=self.regs.get(0xc0c,0)+1
        elif off==0xcfc:self.regs[off]=1
        elif off==0xcf0:pass  # ABI is read-only in the real CSR block.
        else:self.regs[off]=value
        return 0
    def submit(self,packet,csr,enabled=True):
        values=(C.c_uint32*31)(*(csr[str(0xc80+4*i)] for i in range(31)))
        return self.lib.hmi_ui_submit(C.byref(self.session),C.create_string_buffer(packet),len(packet),int(enabled),values)

def fixture():
    stamp=100_000_000
    state=dict(epoch=7,state='IDLE',context='DEMO',calibrated=True,health={'broken':[]})
    face=dict(epoch=7,seq=1,src_ns=stamp,faces=[dict(track_id=1,primary=True,valid=True,landmarks=[[0,0,0],[1,0,0],[0,1,0]])])
    return compose(state,face,None,stamp+1_000_000,3)

def test_native_submit_uses_token_retimes_age_and_arms_csr_before_fifo():
    d=Device();packet,csr=fixture()
    assert d.submit(packet,csr)==0
    offsets=[off for off,_ in d.writes]
    assert offsets.index(0xcfc)<offsets.index(0xc10)
    assert bytes(d.payload[40:104])==packet[40:104]  # Original sources and metadata, except transport generation.
    assert bytes(d.payload[108:-4])==packet[108:-4]  # Original classification and geometry.
    assert struct.unpack_from('<Q',d.payload,32)[0]==1 and struct.unpack_from('<I',d.payload,104)[0]==1
    assert d.regs[0xcf8]==1
    assert struct.unpack_from('<H',d.payload,18)[0]==24
    assert zlib.crc32(d.payload[:-4])==struct.unpack_from('<I',d.payload,len(d.payload)-4)[0]
    assert d.session.prepared==0 and d.session.token==1

def test_native_submit_rejects_corruption_or_generation_before_writes():
    d=Device();packet,csr=fixture();corrupt=bytearray(packet);corrupt[-1]^=1
    assert d.submit(bytes(corrupt),csr)==-4 and not d.writes
    csr[str(0xcf8)]+=1
    assert d.submit(packet,csr)==-6 and not d.writes

def test_native_submit_rejects_future_source_and_structural_errors_before_csr():
    d=Device();packet,csr=fixture();d.now=90_000_000
    assert d.submit(packet,csr)==-4
    assert all(off not in (0xc10,0xcfc) and off<0xc80 for off,_ in d.writes)
    d=Device();bad=bytearray(packet);bad[111]=1;struct.pack_into('<I',bad,len(bad)-4,zlib.crc32(bad[:-4]))
    assert d.submit(bytes(bad),csr)==-4
    assert all(off not in (0xc10,0xcfc) and off<0xc80 for off,_ in d.writes)

def test_native_busy_drops_scene_without_writes_and_legacy_path_has_no_csr():
    d=Device();packet,csr=fixture();d.regs[0xcfc]=1
    assert d.submit(packet,csr)==1 and not d.writes
    assert d.submit(packet,csr,False)==0
    assert not any(off>=0xc80 for off,_ in d.writes)

def test_composer_restart_cannot_replay_fpga_transport_sequence():
    d=Device();packet,csr=fixture()
    assert d.submit(packet,csr)==0
    d.regs[0xcfc]=0;d.payload.clear();d.writes.clear()
    assert d.submit(packet,csr)==0  # Same input generation after a composer restart.
    assert struct.unpack_from('<Q',d.payload,32)[0]==2
    assert struct.unpack_from('<I',d.payload,104)[0]==2 and d.regs[0xcf8]==2

def test_layout_abi_cannot_mix_theater_and_legacy():
    packet,csr=fixture()
    for abi,mode in [(0x55493130,2),(0x55493131,1),(0x55493131,0),(0,2)]:
        d=Device();d.regs[0xcf0]=abi
        assert d.submit(packet,csr,mode)<0 and not d.writes
    d=Device();d.regs[0xcf0]=0x55493131
    assert d.submit(packet,csr,2)==0
