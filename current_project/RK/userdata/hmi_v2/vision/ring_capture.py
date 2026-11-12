import threading,time
from core.frame_ring import FrameRing
from core.config import load

class RingCapture:
    def __init__(self,settings):
        self.ring=FrameRing(settings.get('ring_path','/run/hmi/frames.memfd'))
        self.last_metadata={};self.end_metadata={};self.device='HMIRING1';self.serial=0;self.stop=threading.Event()
        self.hz=settings.get('capture_hz',30);self.deadline=0
        self.admission=settings.get('hmi_admission');self.bootstrap=True
        self.preview=None
        if load()['hardware'].get('preview',False):
            from .preview_reader import OwnerPreview
            try:self.preview=OwnerPreview(self.ring.path.parent/'preview.memfd',self.ring.path)
            except BaseException:self.ring.close();raise
    def read_rgb(self):
        end=time.monotonic()+1
        while not self.stop.is_set() and time.monotonic()<end:
            now=time.monotonic()
            hz=self.admission.rate('face') if self.admission and not self.bootstrap else self.hz
            if hz<=0:
                # Intentional suspension is not a failed camera read. Keep the
                # worker alive and interruptible without copying any frame.
                self.ring.check_owner()
                end=now+1;self.deadline=0;self.stop.wait(.02);continue
            if now<self.deadline:self.stop.wait(min(.01,self.deadline-now));continue
            f=self.ring.latest(self.serial)
            if f:
                self.serial=f.serial;self.last_metadata=f.meta
                self.bootstrap=False;self.deadline=now+1/hz
                return True,f.rgb
            self.stop.wait(.002)
        return False,None
    read=read_rgb
    def read_hdmi_preview(self,*args,**kwargs):
        self.ring.check_owner()
        if self.admission and not self.admission.rate('face'):return None
        return self.preview.read_latest(*args,**kwargs) if self.preview else None
    def getBackendName(self):return 'HMI_NATIVE_RING'
    def request_stop(self):self.stop.set()
    def release(self):
        self.request_stop()
        if self.preview:self.preview.close()
        self.ring.close()
