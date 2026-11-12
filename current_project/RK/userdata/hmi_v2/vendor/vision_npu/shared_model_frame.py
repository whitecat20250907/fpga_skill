"""CPU-only latest RGB640 export AFTER the unchanged native MCF1 receiver.

One producer in the existing model process. Independent readers copy a bounded
snapshot while holding a nonblocking POSIX record lock; no camera/DMA fd leaks.
Never duplicate/close this inode from another thread in the producer process.
"""
import errno,fcntl,mmap,os,struct,time

HEADER=struct.Struct('<8s6I6QI12x')
MAGIC=b'GZMDL002';WIDTH=640;HEIGHT=360;STRIDE=1920;PAYLOAD=850944
NAME='gaze-model-tensors-v2'

class SharedModelFrame:
    def __init__(self):
        self.fd=os.memfd_create(NAME,os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING);self.map=None
        self.serial=0;self.closed=False;self.published=0;self.busy=0;self.last_stamp=0
        try:
            os.ftruncate(self.fd,HEADER.size+PAYLOAD)
            self.map=mmap.mmap(self.fd,HEADER.size+PAYLOAD,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ|mmap.PROT_WRITE)
            self.map[:HEADER.size]=HEADER.pack(MAGIC,2,WIDTH,HEIGHT,STRIDE,0,0,0,0,0,0,0,0,125000000)
            fcntl.fcntl(self.fd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL)
        except BaseException:self.close();raise
    def publish(self,data,meta):
        if self.closed:raise RuntimeError('Model frame exporter closed')
        stamp=meta['timestamp_ns'];dequeue=meta['dequeue_ns'];now=time.monotonic_ns();sequence=meta['sequence']
        if len(data)!=PAYLOAD or not 0<stamp<=dequeue<=now or stamp<=self.last_stamp or not 0<=sequence<2**32:
            raise ValueError('Invalid source model frame')
        if meta.get('detector_contract')!='square640_warp_linear5_zero' or meta.get('fpga_crc_verified') is not True or not meta.get('fpga_epoch'):
            raise ValueError('Missing verified FPGA detector tensors')
        try:fcntl.lockf(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB,1,0,os.SEEK_SET)
        except OSError as e:
            if e.errno in (errno.EAGAIN,errno.EACCES,errno.EINTR):self.busy+=1;return False
            raise
        try:
            # Invalidate before mutating pixels, including if the process exits mid-copy.
            struct.pack_into('<I',self.map,24,0)
            self.map[HEADER.size:]=data
            self.serial+=1
            self.map[:HEADER.size]=HEADER.pack(MAGIC,2,WIDTH,HEIGHT,STRIDE,PAYLOAD,sequence,stamp,dequeue,self.serial,time.monotonic_ns(),meta['fpga_epoch'],meta['fpga_source_tick'],125000000)
            self.published+=1;self.last_stamp=stamp
            return True
        finally:fcntl.lockf(self.fd,fcntl.LOCK_UN,1,0,os.SEEK_SET)
    def close(self):
        if self.closed:return
        self.closed=True
        if self.map is not None:self.map.close();self.map=None
        if self.fd is not None:os.close(self.fd);self.fd=None
