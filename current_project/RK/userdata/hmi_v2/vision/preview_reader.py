"""Attach the sole C owner's independent full-resolution preview slot."""
import os,mmap,threading,re
from pathlib import Path
from shared_preview import SharedPreview,TOTAL


class OwnerPreview(SharedPreview):
    @staticmethod
    def owner_of(path):
        # resolve() follows proc's magic link to '/memfd:... (deleted)', which
        # deliberately has no pathname. Inspect the published first hop only.
        target=os.readlink(path)
        if not re.fullmatch(r'/proc/[1-9][0-9]*/fd/[0-9]+',target):
            raise ValueError('Expected native proc-fd publication')
        return Path(target).parent

    def __init__(self,path,model_path):
        self.path=Path(path);self.model_path=Path(model_path)
        # Both symlinks must belong to exactly the same live native process.
        self.owner=self.owner_of(self.path)
        if self.owner!=self.owner_of(self.model_path):
            raise ValueError('Preview/model owners differ')
        stat=self.model_path.stat();self.model_identity=(stat.st_dev,stat.st_ino)
        self.lock=threading.Lock();self.closed=False;self.last_serial=0
        self.last_stamp=0;self.last_error=None;self.map=None
        # SharedPreview takes nonblocking POSIX write locks; the mapping itself
        # is read-only. Keep exactly one fd for this inode in the reader process.
        self.fd=os.open(self.path,os.O_RDWR|os.O_CLOEXEC)
        try:
            stat=os.fstat(self.fd);self.identity=(stat.st_dev,stat.st_ino)
            if stat.st_size!=TOTAL:raise ValueError('Preview allocation size')
            self.map=mmap.mmap(self.fd,TOTAL,access=mmap.ACCESS_READ)
        except BaseException:
            os.close(self.fd);raise

    def current(self):
        try:
            stat=self.path.stat()
            model=self.model_path.stat()
            return ((stat.st_dev,stat.st_ino)==self.identity and
                    (model.st_dev,model.st_ino)==self.model_identity and
                    self.owner_of(self.path)==self.owner and
                    self.owner_of(self.model_path)==self.owner)
        except (OSError,ValueError):return False

    def read_latest(self,now_ns=None):
        if self.closed or not self.current():return None
        result=super().read_latest(now_ns)
        return result if self.current() else None
