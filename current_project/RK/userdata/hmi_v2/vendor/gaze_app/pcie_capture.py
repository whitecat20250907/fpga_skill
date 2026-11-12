from detector_frame import make_frame, TOTAL_BYTES, CONTRACT
"""Explicit FPGA PCIe RGB capture; bounded latest-frame delivery to inference."""
import fcntl
import json
import os
import signal
import struct
import subprocess
import threading
import time
from pathlib import Path
import numpy as np
import cv2
from shared_preview import SharedPreview
from shared_model_frame import SharedModelFrame


def exact(stream,n):
    chunks=[]
    while n:
        b=stream.read(n)
        if not b:raise EOFError('Incomplete native capture record')
        chunks.append(b);n-=len(b)
    return b''.join(chunks)


def resolve_device():
    candidates=[p.parent.name for p in Path('/sys/class/video4linux').glob('video*/name')
                if p.read_text().strip()=='Milianke PCIe Capture']
    if len(candidates)!=1:raise RuntimeError('Expected exactly one Milianke PCIe capture node')
    node=Path('/sys/class/video4linux')/candidates[0]
    if (node/'device/driver').resolve().name!='Anlogic-pcie':
        raise RuntimeError('Camera is not attached to Anlogic PCIe')
    return '/dev/'+candidates[0]


class PcieCapture:
    def __init__(self,settings):
        if settings['camera']!='fpga-pcie':raise ValueError('Explicit FPGA PCIe source required')
        self.output_size=(int(settings['camera_width']),int(settings['camera_height']))
        if not (0<self.output_size[0]<=1920 and 0<self.output_size[1]<=1080):
            raise ValueError('Delivery dimensions must fit the native 1920x1080 frame')
        self.device=resolve_device()
        usb=Path('/sys/firmware/devicetree/base/usb@23400000/status').read_bytes().rstrip(b'\0')
        if usb!=b'disabled':raise RuntimeError('Expected USB/PCIe mux state is not present')
        cap=bytearray(104);fd=os.open(self.device,os.O_RDWR|os.O_NONBLOCK)
        try:fcntl.ioctl(fd,0x80685600,cap,True)
        finally:os.close(fd)
        driver=bytes(cap[:16]).split(b'\0')[0].decode()
        if driver!='milianke-v4l2':raise RuntimeError('Selected node is not the FPGA PCIe driver')
        self.condition=threading.Condition();self.pending=None;self.error=None;self.done=False
        self.dropped=0;self.last_metadata=None;self.start_metadata=None;self.end_metadata=None
        self.closed=False;self.last_sequence=None;self.last_stamp=None
        self.stop_lock=threading.Lock();self.stop_requested=False
        native=Path(__file__).with_name('capture_native')
        if not native.is_file():raise RuntimeError('Build capture_native before starting the app')
        self.reduced_output=self.output_size==(640,360)
        self.packet_width,self.packet_height,self.packet_stride=1920,1080,5760
        args=[str(native),self.device,'1920','1080','RGB3','0']
        model_fd_text=os.environ.get('FPGA_MODEL_FDS','')
        model_fds=tuple(int(v) for v in model_fd_text.split(',')) if model_fd_text else ()
        if model_fds and (len(model_fds)!=2 or min(model_fds)<3 or len(set(model_fds))!=2 or not self.reduced_output):
            raise ValueError('Invalid FPGA model DMA/BAR descriptors')
        self.fpga_model=bool(model_fds)
        if self.reduced_output:args.append('--fpga-model-fds='+model_fd_text if model_fds else '--rgb-area3')
        self.model_only=self.fpga_model
        if self.model_only:args.append('--fpga-model-only')
        self.preview_store=SharedPreview(int(settings.get('shared_preview_fps',0))) if self.reduced_output and not self.model_only else None
        if self.preview_store is not None:
            args.extend(['--preview-fd='+str(self.preview_store.fd), '--preview-fps='+str(self.preview_store.fps)])
        self.model_store=None
        try:
            if self.reduced_output:self.model_store=SharedModelFrame()
            if self.model_only:args.append("--model-store-fd="+str(self.model_store.fd))
            self.process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,pipesize=1048576 if self.model_only else -1,
                                          pass_fds=model_fds+(() if self.preview_store is None else (self.preview_store.fd,))+((self.model_store.fd,) if self.model_only else ()))
        except BaseException:
            if self.model_store is not None:self.model_store.close()
            if self.preview_store is not None:self.preview_store.close()
            raise
        self.thread=threading.Thread(target=self._reader,name='FPGA-frame-reader',daemon=True);self.thread.start()

    def _reader(self):
        try:
            while True:
                magic,jlen,n=struct.unpack('<4sII',exact(self.process.stdout,12))
                if magic!=b'MCF1' or not 0<jlen<=65536 or n>67108864:raise ValueError('Invalid native frame envelope')
                meta=json.loads(exact(self.process.stdout,jlen));data=exact(self.process.stdout,n)
                if meta['kind']=='start':
                    if self.start_metadata is not None or n:raise ValueError('Repeated native start')
                    if (meta['driver'],meta['width'],meta['height'],meta['fourcc'])!=('milianke-v4l2',1920,1080,'RGB3'):raise ValueError('Native camera contract changed')
                    if len(meta['planes'])!=1 or meta['planes'][0]['stride']<5760:raise ValueError('Unsupported native RGB plane')
                    if self.reduced_output:
                        if (meta.get('output_transform'),meta.get('output_width'),meta.get('output_height'),meta.get('output_stride'))!=('rgb_area3_1920x1080_to_640x360',640,360,1920):raise ValueError('Exact native model resize contract missing')
                        self.packet_width,self.packet_height,self.packet_stride=640,360,1920
                    else:
                        if 'output_transform' in meta:raise ValueError('Unexpected native pixel transform')
                        self.packet_stride=meta['planes'][0]['stride']
                    if self.fpga_model and (meta.get('transform_executor')!='fpga' or meta.get('model_channel')!=1 or meta.get('fpga_tensor_bundle')!='BND1'):raise ValueError('FPGA small-frame path was not activated')
                    if self.model_only and (meta.get('preview_dma_policy')!='drain_initial_buffers_no_requeue' or meta.get('full_resolution_preview') is not False):raise ValueError('Model-only capture schedule was not activated')
                    self.start_metadata=meta;continue
                if meta['kind']=='end':
                    self.end_metadata=meta
                    if n or meta['errno'] or meta['cleanup_errno']:raise RuntimeError(('Native capture failed',meta))
                    break
                if meta['kind']!='frame' or self.start_metadata is None:raise ValueError('Frame before start')
                if meta['flags']&0x40:continue
                if meta['flags']&0xe000!=0x2000:raise ValueError('Capture timestamp is not monotonic')
                seq=meta['sequence'];stamp=meta['timestamp_ns']
                if self.last_sequence is not None and (seq==self.last_sequence or stamp<=self.last_stamp):raise ValueError('Duplicate or nonmonotonic physical frame')
                self.last_sequence=seq;self.last_stamp=stamp
                stride=self.packet_stride
                if self.fpga_model:
                    if n!=TOTAL_BYTES or [p['payload'] for p in meta['planes']]!=[691200,49152,110592] or meta.get('detector_contract')!=CONTRACT:
                        raise ValueError('Incomplete same-frame FPGA tensor bundle')
                elif len(meta['planes'])!=1 or meta['planes'][0]['payload']!=n or n!=stride*self.packet_height:raise ValueError('Incomplete RGB image')
                if self.model_store is not None and not self.model_only:self.model_store.publish(data,meta)
                # Native RGB3 is RGB. The original MediaPipe entry takes BGR.
                rgb=make_frame(data,meta) if self.fpga_model else np.frombuffer(data,np.uint8).reshape(self.packet_height,stride)[:,:self.packet_width*3].reshape(self.packet_height,self.packet_width,3)
                with self.condition:
                    if self.pending is not None:self.dropped+=1
                    # Keep the RGB view backed by this immutable frame payload.
                    # Convert only frames consumed by inference, not overwritten ones.
                    self.pending=(rgb,meta);self.condition.notify_all()
        except Exception as e:
            with self.condition:self.error=e
        finally:
            with self.condition:self.done=True;self.condition.notify_all()

    def read_rgb(self):
        deadline=time.monotonic()+6
        with self.condition:
            while self.pending is None and not self.done:
                wait=deadline-time.monotonic()
                if wait<=0:raise TimeoutError('FPGA capture stopped delivering frames')
                self.condition.wait(wait)
            if self.error:raise self.error
            if self.pending is None:return False,None
            rgb,self.last_metadata=self.pending;self.pending=None
        # Release the producer lock before the full-frame channel conversion.
        # Bilinear resize is channel-independent. Avoid a 6 MB full-resolution
        # channel copy for a 640x360 model input; raw MCF1 validation is unchanged.
        small=(rgb if (rgb.shape[1],rgb.shape[0]) == self.output_size else
               cv2.resize(rgb,self.output_size,interpolation=cv2.INTER_LINEAR))
        # Native bytes remain immutable; drawing makes its own copy downstream.
        return True,small

    def read(self):
        """Compatibility BGR API; the live pipeline uses read_rgb()."""
        ok,rgb=self.read_rgb()
        return (ok,cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)) if ok else (False,None)

    def read_hdmi_preview(self,now_ns=None):
        # UI calls independently of the camera/face/NPU owner threads.
        return None if self.preview_store is None else self.preview_store.read_latest(now_ns)

    def getBackendName(self):return 'FPGA_PCIE_NATIVE_RGB3'

    def request_stop(self):
        """Wake the owner's blocking read without releasing its resources."""
        # Caller and owner cleanup may request the same stop concurrently.
        # Signal at most once, while the reader still validates/drains MCF1 end.
        with self.stop_lock:
            if self.stop_requested:
                return
            self.stop_requested=True
            if self.process.poll() is None:
                try:
                    self.process.send_signal(signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def release(self):
        if self.closed:return
        self.closed=True
        self.request_stop()
        self.thread.join(8)
        forced=False
        try:
            rc=self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            # Terminate only the exact child owned by this adapter. A forced
            # stop is always a failed cleanup, never a clean capture result.
            forced=True;self.process.kill();rc=self.process.wait(timeout=3)
        self.thread.join(3)
        stderr=self.process.stderr.read().decode(errors='replace')
        self.process.stdout.close();self.process.stderr.close()
        # The Python publisher must finish before its buffer can be unmapped.
        if self.model_store is not None and not self.thread.is_alive():self.model_store.close()
        # Child capture/writer has ended before closing the parent snapshot.
        if self.preview_store is not None:self.preview_store.close()
        if forced or rc or self.error or self.end_metadata is None or self.thread.is_alive():
            raise RuntimeError('Capture did not close cleanly: '+repr(self.error)+' '+stderr)
