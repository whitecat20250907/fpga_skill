"""Read an existing app28 memfd from a SEPARATE process; never open V4L2.

The one read-only fd here is owned solely by this external reader. Closing it
cannot release the original process's POSIX record locks. All locks are
nonblocking. The original capture's commit-word/record-lock ABI is preserved.
"""
import errno
import fcntl
import mmap
import os
from pathlib import Path
import struct
import time
import numpy as np

HEADER=struct.Struct('<8s6I4Q')
WIDTH,HEIGHT,STRIDE=1920,1080,5760
PAYLOAD=STRIDE*HEIGHT

def identity(pid):
    base=Path('/proc')/str(pid)
    start=int((base/'stat').read_text().rsplit(')',1)[1].split()[19])
    return dict(pid=pid,start_ticks=start,cwd=str((base/'cwd').resolve()))

def expected_main_command(cmd,app):
    args=cmd.rstrip(b'\0').split(b'\0')
    if len(args)<2:return False
    if args[1] in (b'run_gaze.py',str(app/'run_gaze.py').encode()):return True
    wrapper=Path(__file__).resolve().parent/'tools/run_main_with_freeciv.py'
    if args[1] not in (str(wrapper).encode(),b'tools/run_main_with_freeciv.py'):return False
    if args.count(b'--app-dir')!=1:return False
    index=args.index(b'--app-dir')+1
    return index<len(args) and args[index]==str(app).encode()

class ExistingPreview:
    def __init__(self,app_dir,model_pid=None):
        self.fd=None;self.map=None;self.last_serial=0;self.last_stamp=0
        self.stats=dict(busy=0,stale=0,duplicate=0,invalid=0,accepted=0)
        app=Path(app_dir).resolve(strict=True)
        models=[];captures=[]
        for p in Path('/proc').iterdir():
            if not p.name.isdigit():continue
            try:
                cmd=(p/'cmdline').read_bytes()
                if (p/'cwd').resolve()!=app:continue
                if expected_main_command(cmd,app):models.append(identity(int(p.name)))
                if cmd.startswith(str(app/'capture_native').encode()+b'\0'):
                    captures.append(identity(int(p.name)))
            except (OSError,ValueError):continue
        if len(models)!=1 or len(captures)!=1:raise RuntimeError('Exactly one existing app28 model and capture required')
        self.model=models[0];self.capture=captures[0]
        if model_pid is not None and model_pid!=self.model['pid']:raise RuntimeError('Model PID changed')
        if self.model['pid']==os.getpid():raise RuntimeError('Preview reader must be a separate process')
        parent=int((Path('/proc')/str(self.capture['pid'])/'stat').read_text().rsplit(')',1)[1].split()[1])
        if parent!=self.model['pid']:raise RuntimeError('Capture is not owned by the selected model')
        choices=[]
        for p in (Path('/proc')/str(self.model['pid'])/'fd').iterdir():
            try:
                if os.readlink(p)=='/memfd:gaze-preview-rgb1080 (deleted)':
                    s=p.stat();choices.append((p,s.st_dev,s.st_ino))
            except OSError:continue
        if not choices or len({x[1:] for x in choices})!=1:raise RuntimeError('No unique existing RGB preview inode')
        inode=choices[0][1:]
        cap_inodes=[]
        for p in (Path('/proc')/str(self.capture['pid'])/'fd').iterdir():
            try:
                s=p.stat();cap_inodes.append((s.st_dev,s.st_ino))
            except OSError:pass
        if inode not in cap_inodes:raise RuntimeError('Selected capture does not share the preview inode')
        try:
            self.fd=os.open(choices[0][0],os.O_RDONLY|os.O_CLOEXEC)
            s=os.fstat(self.fd)
            if (s.st_dev,s.st_ino)!=inode or s.st_size!=HEADER.size+PAYLOAD:raise RuntimeError('Preview inode/size changed')
            seals=fcntl.fcntl(self.fd,fcntl.F_GET_SEALS)
            if seals & (fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK)!=(fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK):
                raise RuntimeError('Preview size seals absent')
            self.map=mmap.mmap(self.fd,0,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ)
            self.check_owners()
        except BaseException:
            self.close();raise

    def check_owners(self):
        if identity(self.model['pid'])!=self.model or identity(self.capture['pid'])!=self.capture:
            raise RuntimeError('Original model/capture instance changed; do not auto-reattach')

    def read(self):
        self.check_owners()
        try:fcntl.lockf(self.fd,fcntl.LOCK_SH|fcntl.LOCK_NB,1,0,os.SEEK_SET)
        except OSError as error:
            if error.errno in (errno.EACCES,errno.EAGAIN,errno.EINTR):
                self.stats['busy']+=1;return None
            raise
        try:
            f=HEADER.unpack(self.map[:HEADER.size])
            magic,version,w,h,stride,valid,sequence,stamp,dequeue,serial,published=f
            if (magic,version,w,h,stride)!=(b'GZPRV001',1,WIDTH,HEIGHT,STRIDE):
                raise RuntimeError('Preview ABI changed')
            now=time.monotonic_ns()
            if valid!=PAYLOAD or not (0<stamp<=dequeue<=published<=now and serial>0):
                self.stats['invalid']+=1;return None
            if now-stamp>250_000_000 or now-published>250_000_000:
                self.stats['stale']+=1;return None
            if serial==self.last_serial:
                self.stats['duplicate']+=1;return None
            if serial<self.last_serial or stamp<=self.last_stamp:raise RuntimeError('Preview serial/time regressed')
            # Copy just 640x360 RGB under the lock; no mmap view escapes it.
            view=np.ndarray((HEIGHT,WIDTH,3),np.uint8,buffer=self.map,offset=HEADER.size)
            rgb=view[1::3,1::3,:].copy();del view
            self.last_serial,self.last_stamp=serial,stamp
            self.stats['accepted']+=1
            return rgb,dict(sequence=sequence,serial=serial,timestamp_ns=stamp,published_ns=published)
        finally:fcntl.lockf(self.fd,fcntl.LOCK_UN,1,0,os.SEEK_SET)

    def close(self):
        if self.map is not None:self.map.close();self.map=None
        if self.fd is not None:os.close(self.fd);self.fd=None
