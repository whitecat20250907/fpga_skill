"""Immutable three-plane frames. Native acquire fences are mandatory for live reads."""
from pathlib import Path
from dataclasses import dataclass
import ctypes, mmap, struct, zlib, os
from core.config import ROOT

PAYLOAD=850944;SLOT=64+PAYLOAD;SIZE=64+3*SLOT
HEADER=struct.Struct('<8sIIIIQQ24x')
SLOT_HEADER=struct.Struct('<QQIIQQQQII')

@dataclass
class Frame:
    serial:int
    rgb:object
    meta:dict

def decode_slot(raw, epoch, make_frame):
    lock,serial,seq,flags,stamp,dequeue,pub,tick,crc,valid=SLOT_HEADER.unpack_from(raw)
    pixels=raw[64:]
    if lock&1 or not valid or flags!=1 or len(pixels)!=PAYLOAD or zlib.crc32(pixels)!=crc:
        raise ValueError('Unstable or corrupt ring slot')
    if not epoch or not stamp or pub<stamp or dequeue<stamp:raise ValueError('Invalid ring identity')
    meta=dict(timestamp_ns=stamp,sequence=seq,dequeue_ns=dequeue,pub_ns=pub,fpga_source_tick=tick,
              fpga_epoch=epoch,fpga_crc_verified=True,detector_contract='square640_warp_linear5_zero',fpga_tick_hz=125000000)
    return Frame(serial,make_frame(pixels,meta),meta)

class FrameRing:
    def __init__(self,path='/run/hmi/frames.memfd',library=None):
        self.path=Path(path);self.file=open(path,'rb');self.map=mmap.mmap(self.file.fileno(),0,access=mmap.ACCESS_COPY)
        stat=os.fstat(self.file.fileno());self.identity=(stat.st_dev,stat.st_ino)
        if len(self.map)!=SIZE:self.close();raise ValueError('Ring size mismatch')
        magic,ver,slots,slot,payload,epoch,seq=HEADER.unpack_from(self.map)
        if (magic,ver,slots,slot,payload)!=(b'HMIRING1',1,3,SLOT,PAYLOAD):self.close();raise ValueError('Ring ABI mismatch')
        self.lib=ctypes.CDLL(str(library or ROOT/'native/fpga_io/libring.so'))
        self.lib.hmi_ring_snapshot.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint64]
        self.lib.hmi_ring_snapshot.restype=ctypes.c_int
        self.buffer=(ctypes.c_char*SIZE).from_buffer(self.map);self.out=ctypes.create_string_buffer(SLOT)
        self.epoch=epoch
    def latest(self,after_seq=None):
        self.check_owner()
        from detector_frame import make_frame
        result=self.lib.hmi_ring_snapshot(self.buffer,self.out,SLOT,after_seq or 0)
        if result<0:raise ValueError('Ring snapshot ABI invalid')
        if not result:return None
        epoch=HEADER.unpack_from(self.map)[5]
        if self.epoch and epoch!=self.epoch:raise RuntimeError('Hardware epoch changed: restart reader')
        self.epoch=epoch
        return decode_slot(self.out.raw,epoch,make_frame)
    def check_owner(self):
        # The old memfd mapping stays valid after its owner dies. Follow the
        # published path as well, so consumers restart on a replaced ring.
        try:stat=self.path.stat()
        except OSError as exc:raise RuntimeError('Frame owner unavailable; restart reader') from exc
        if (stat.st_dev,stat.st_ino)!=self.identity:
            raise RuntimeError('Frame owner replaced; restart reader')
    def close(self):
        if hasattr(self,'buffer'):del self.buffer
        if getattr(self,'map',None):self.map.close();self.map=None
        if getattr(self,'file',None):self.file.close();self.file=None
