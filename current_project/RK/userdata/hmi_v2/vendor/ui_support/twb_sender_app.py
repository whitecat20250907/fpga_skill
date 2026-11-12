"""Existing FeatureState/Scene -> native aligned 32-bit BAR writer.

No camera, model or gesture detector is created. One producer owns a device
flock; callbacks run only after a whole packet fits and ANCH readback drains.
Supply a feature snapshot taken before the callback's serialization time.
"""
import argparse
import ctypes as C
import json
import secrets
import threading
import time
from pathlib import Path

import hft2_wire as twin_wire


class TWBError(RuntimeError):
    def __init__(self, code, text):
        super().__init__(f"TWB2 {text} ({code})")
        self.code=code


class Probe(C.Structure):
    _fields_=[(name,C.c_uint32) for name in ('cap','abi','limits','device_status')]


class Snapshot(C.Structure):
    _fields_=[(name,C.c_uint32) for name in ('generation','flags','scenes','accepted','crc_errors','format_errors','sequence_errors','clock_delta')]


class NativeSender:
    """Single sender; default CLI offers only a read-only capability probe."""
    def __init__(self,library,device='/dev/ANLOGIC-PCI0_user'):
        self.lib=C.CDLL(str(Path(library).resolve()))
        self.device=str(device).encode()
        self.handle=C.c_void_p()
        self.lock=threading.Lock()
        self.epoch=None;self.sequence=0;self.old_snapshot=None
        self.lib.twb_native_library_abi.argtypes=[]
        self.lib.twb_native_library_abi.restype=C.c_uint32
        if self.lib.twb_native_library_abi()!=0x32535754:
            raise TWBError(-1,'unsupported native library ABI')
        signatures={
            'twb_native_probe':[C.c_char_p,C.POINTER(Probe)],
            'twb_native_open':[C.c_char_p,C.POINTER(C.c_void_p)],
            'twb_native_close':[C.c_void_p],
            'twb_native_flush_begin':[C.c_void_p],
            'twb_native_flush_poll':[C.c_void_p],
            'twb_native_prepare':[C.c_void_p,C.c_uint32,C.POINTER(C.c_uint64),C.POINTER(C.c_uint64)],
            'twb_native_cancel':[C.c_void_p,C.c_uint64],
            'twb_native_commit':[C.c_void_p,C.c_uint64,C.POINTER(C.c_uint8),C.c_size_t],
            'twb_native_snapshot':[C.c_void_p,C.POINTER(Snapshot)],
        }
        for name,args in signatures.items():
            fn=getattr(self.lib,name);fn.argtypes=args;fn.restype=None if name=='twb_native_close' else C.c_int
        self.lib.twb_error.argtypes=[C.c_int];self.lib.twb_error.restype=C.c_char_p

    def checked(self,code):
        if code:
            raise TWBError(code,self.lib.twb_error(code).decode())

    def probe(self):
        result=Probe()
        code=self.lib.twb_native_probe(self.device,C.byref(result))
        return dict(code=code,supported=code==0,readonly=True,MMIO_writes=0,
                    **{name:getattr(result,name) for name,_ in result._fields_})

    def start_epoch(self,epoch=None,timeout=.25):
        """Explicitly flush once, then poll the same request within a deadline."""
        if timeout<=0 or timeout>2:raise ValueError('Flush timeout must be in (0,2] seconds')
        value=secrets.randbits(64) or 1 if epoch is None else epoch
        if not isinstance(value,int) or not 0<value<2**64:raise ValueError('Nonzero uint64 epoch required')
        with self.lock:
            if self.handle.value:raise TWBError(-3,'sender already open')
            self.checked(self.lib.twb_native_open(self.device,C.byref(self.handle)))
            try:
                deadline=time.monotonic()+timeout
                old=Snapshot()
                code=self.lib.twb_native_snapshot(self.handle,C.byref(old))
                while code==1 and time.monotonic()<deadline:
                    time.sleep(.001)
                    code=self.lib.twb_native_snapshot(self.handle,C.byref(old))
                if code==1:raise TimeoutError('No coherent UI baseline; no flush issued')
                self.checked(code)
                self.old_snapshot=old.generation
                code=self.lib.twb_native_flush_begin(self.handle)
                while code==2 and time.monotonic()<deadline:
                    time.sleep(.001)
                    code=self.lib.twb_native_flush_poll(self.handle)
                if code==2:raise TimeoutError('Same TWB2 flush still pending; no reset retry')
                self.checked(code)
                self.epoch=value;self.sequence=0
            except BaseException:
                self.lib.twb_native_close(self.handle);self.handle=C.c_void_p();raise
        return value

    def send(self,scene_factory):
        """Return True for enqueue, False for no credit; never wait for credit.

        The callback receives CLOCK_MONOTONIC ns after ANCH and returns AppFrame.
        It must use existing results and must not start inference or reenter us.
        UI acceptance is independent and is observed through snapshot().
        """
        with self.lock:
            if not self.handle.value or self.epoch is None:raise TWBError(-3,'start_epoch required')
            if self.sequence>=2**64:raise OverflowError('Restart the epoch before sequence wrap')
            now=C.c_uint64();token=C.c_uint64()
            code=self.lib.twb_native_prepare(self.handle,1908,C.byref(now),C.byref(token))
            if code==1:return False
            self.checked(code)
            try:
                scene=scene_factory(now.value)
                packet=twin_wire.encode(scene.geometry,scene.metadata,self.epoch,self.sequence)
                array=(C.c_uint8*len(packet)).from_buffer_copy(packet)
            except BaseException:
                self.lib.twb_native_cancel(self.handle,token.value);raise
            self.checked(self.lib.twb_native_commit(self.handle,token.value,array,len(packet)))
            self.sequence+=1
            return True

    def snapshot(self):
        with self.lock:
            if not self.handle.value:raise TWBError(-3,'sender is closed')
            row=Snapshot();code=self.lib.twb_native_snapshot(self.handle,C.byref(row))
            if code==1:return None
            self.checked(code)
            if self.old_snapshot is not None:
                if row.generation==self.old_snapshot:return None
                self.old_snapshot=None
            return {name:getattr(row,name) for name,_ in row._fields_}

    def close(self):
        """No implicit MMIO write; old visible groups expire in FPGA time."""
        with self.lock:
            if self.handle.value:self.lib.twb_native_close(self.handle)
            self.handle=C.c_void_p();self.epoch=None

    def __enter__(self):return self
    def __exit__(self,*_):self.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',required=True,type=Path)
    parser.add_argument('--device',default='/dev/ANLOGIC-PCI0_user')
    parser.add_argument('--probe',required=True,action='store_true')
    args=parser.parse_args()
    with NativeSender(args.library,args.device) as sender:
        result=sender.probe();print(json.dumps(result));return 0 if result['supported'] else 3


if __name__=='__main__':raise SystemExit(main())
