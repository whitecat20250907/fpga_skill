from detector_frame import make_frame, CONTRACT
"""Optional hands consume the existing model small frame, not display preview."""
import errno,fcntl,mmap,os,struct,time
from pathlib import Path
import numpy as np
from shared_model_frame import HEADER,MAGIC,WIDTH,HEIGHT,STRIDE,PAYLOAD,NAME
from pcie_preview_reader import identity,expected_main_command

class ExistingModelFrame:
    source='existing_FPGA_RGB640_face128_palm192'
    def __init__(self,app_dir,model_pid=None):
        self.fd=None;self.map=None;self.last_serial=0;self.last_stamp=0
        self.stats=dict(busy=0,stale=0,duplicate=0,invalid=0,accepted=0)
        app=Path(app_dir).resolve(strict=True);models=[];captures=[]
        for p in Path('/proc').iterdir():
            if not p.name.isdigit():continue
            try:
                if (p/'cwd').resolve()!=app:continue
                cmd=(p/'cmdline').read_bytes()
                if expected_main_command(cmd,app):models.append(identity(int(p.name)))
                if cmd.startswith(str(app/'capture_native').encode()+b'\0'):captures.append(identity(int(p.name)))
            except (OSError,ValueError):continue
        if len(models)!=1 or len(captures)!=1:raise RuntimeError('Exactly one existing model and capture required')
        self.model=models[0];self.capture=captures[0]
        if model_pid is not None and model_pid!=self.model['pid']:raise RuntimeError('Model PID changed')
        if self.model['pid']==os.getpid():raise RuntimeError('Use the original array inside the model process')
        parent=int((Path('/proc')/str(self.capture['pid'])/'stat').read_text().rsplit(')',1)[1].split()[1])
        if parent!=self.model['pid']:raise RuntimeError('Capture parent mismatch')
        choices=[]
        for p in (Path('/proc')/str(self.model['pid'])/'fd').iterdir():
            try:
                if os.readlink(p)==f'/memfd:{NAME} (deleted)':
                    s=p.stat();choices.append((p,s.st_dev,s.st_ino))
            except OSError:continue
        if not choices or len({x[1:] for x in choices})!=1:raise RuntimeError('No unique existing model RGB640 inode')
        try:
            self.fd=os.open(choices[0][0],os.O_RDONLY|os.O_CLOEXEC);s=os.fstat(self.fd)
            if (s.st_dev,s.st_ino)!=choices[0][1:] or s.st_size!=HEADER.size+PAYLOAD:raise RuntimeError('Model frame inode/size mismatch')
            seals=fcntl.fcntl(self.fd,fcntl.F_GET_SEALS)
            if seals&(fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK)!=(fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK):raise RuntimeError('Missing size seals')
            self.map=mmap.mmap(self.fd,0,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ)
            self.check_owners()
        except BaseException:self.close();raise
    def check_owners(self):
        if identity(self.model['pid'])!=self.model or identity(self.capture['pid'])!=self.capture:
            raise RuntimeError('Original owners changed; no automatic reattachment')
    def read(self):
        self.check_owners()
        try:fcntl.lockf(self.fd,fcntl.LOCK_SH|fcntl.LOCK_NB,1,0,os.SEEK_SET)
        except OSError as e:
            if e.errno in (errno.EAGAIN,errno.EACCES,errno.EINTR):self.stats['busy']+=1;return None
            raise
        try:
            magic,version,w,h,stride,valid,sequence,stamp,dequeue,serial,published,epoch,tick,hz=HEADER.unpack(self.map[:HEADER.size])
            if (magic,version,w,h,stride)!=(MAGIC,2,WIDTH,HEIGHT,STRIDE):raise RuntimeError('Model RGB640 ABI mismatch')
            now=time.monotonic_ns()
            if hz!=125000000 or epoch==0 or valid!=PAYLOAD or not 0<stamp<=dequeue<=published<=now or serial<=0:self.stats['invalid']+=1;return None
            if now-stamp>250_000_000 or now-published>250_000_000:self.stats['stale']+=1;return None
            if serial==self.last_serial:self.stats['duplicate']+=1;return None
            if serial<self.last_serial or stamp<=self.last_stamp:raise RuntimeError('Source regressed')
            # Private immutable bytes: neither inference nor overlay can mutate this snapshot.
            pixels=self.map[HEADER.size:]
            self.last_serial=serial;self.last_stamp=stamp;self.stats['accepted']+=1
        finally:fcntl.lockf(self.fd,fcntl.LOCK_UN,1,0,os.SEEK_SET)
        meta=dict(sequence=sequence,serial=serial,timestamp_ns=stamp,dequeue_ns=dequeue,published_ns=published,transform='area3_exact',fpga_epoch=epoch,fpga_source_tick=tick,fpga_crc_verified=True,detector_contract=CONTRACT)
        return make_frame(pixels,meta),meta
    def close(self):
        if self.map is not None:self.map.close();self.map=None
        if self.fd is not None:os.close(self.fd);self.fd=None
