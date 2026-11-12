"""On-demand copies of the sole owner's real image planes, never another capture."""
import base64
import io
import math
import json
import struct
import threading
import time
import os
from concurrent.futures import ThreadPoolExecutor


class CounterRate:
    """Publication counter rate over a real one-second window, not one interval."""
    def __init__(self):
        from ui.live_preview import Rate
        self.rate=Rate();self.value=None;self.previous=None
    def update(self, identity, sequence, stamp):
        if self.previous and (identity!=self.previous[0] or stamp-self.previous[2]>3_000_000_000):
            from ui.live_preview import Rate
            self.rate=Rate()
        self.previous=(identity,sequence,stamp)
        self.value=self.rate.update(identity,sequence,stamp)
        return self.value


def overlays(values, epoch, stamp, now):
    """Latest inference boxes, explicitly age-labelled; not claimed frame exact."""
    result=[]
    names={'Closed_Fist':'握拳','Open_Palm':'张掌','Pointing_Up':'食指','Victory':'比 V','Thumb_Up':'竖拇指','Thumb_Down':'拇指向下'}
    for topic in ('vision.face','vision.hands'):
        m=values.get(topic,{})
        if str(m.get('epoch'))!=str(epoch) or not 0<=now-m.get('src_ns',0)<=500_000_000:continue
        for row in m.get('faces' if topic=='vision.face' else 'hands',[]):
            if topic=='vision.face':
                if not row.get('valid'):continue
                w,h=row.get('source_size',[640,360]);r=row.get('face_rect',[])
                if len(r)!=4 or min(w,h)<=0:continue
                x,y,rw,rh=r;rect=[x/w,y/h,rw/w,rh/h];label='人脸 '+str(row.get('track_id',''));kind='face'
            else:
                pts=row.get('image21',[])
                if len(pts)!=21:continue
                xs=[p[0] for p in pts];ys=[p[1] for p in pts]
                x,y=min(xs),min(ys);rect=[x-.02,y-.03,max(xs)-x+.04,max(ys)-y+.06]
                label=('左手' if row.get('side')=='Left' else '右手')+' · '+names.get(row.get('gesture'),row.get('gesture',''))
                kind='hand'
            if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in rect):continue
            result.append(dict(rect=rect,label=label,kind=kind,source_sequence=m.get('seq'),offset_ms=(stamp-m['src_ns'])/1e6))
    from ui.live_preview import face_boxes
    face_message=values.get('vision.face',{})
    for box in face_boxes(face_message,epoch,now):
        if box['kind']=='face':continue
        result.append(dict(rect=box['rect'],label='眼 '+str(round(box['pixels'][0]))+'×'+str(round(box['pixels'][1]))+' px',
                           kind=box['kind'],source_sequence=face_message.get('seq'),offset_ms=(stamp-face_message['src_ns'])/1e6))
    return result


def face_landmarks(values, epoch, stamp, now):
    """Measured pixel coordinates; never synthesize missing iris landmarks."""
    m=values.get('vision.face',{})
    if str(m.get('epoch'))!=str(epoch) or not 0<=now-m.get('src_ns',0)<=500_000_000:return []
    result=[]
    for row in m.get('faces',[]):
        if not row.get('valid'):continue
        points=row.get('landmarks',[]);size=row.get('source_size',[640,360])
        if len(points) not in (468,478) or len(size)!=2:continue
        if not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in size):continue
        if not all(isinstance(p,(list,tuple)) and len(p)>=3 and all(isinstance(v,(int,float)) and math.isfinite(v) and abs(v)<32768 for v in p[:3]) for p in points):continue
        result.append(dict(track_id=row.get('track_id'),source_size=size,
            points=[[round(float(v),2) for v in p[:3]] for p in points],
            source_sequence=m.get('seq'),source_ns=m['src_ns'],offset_ms=(stamp-m['src_ns'])/1e6))
        if len(result)==2:break
    return result


class BasicPreview:
    def __init__(self,run,worker_cpus=None):
        if worker_cpus is not None and (not isinstance(worker_cpus,list) or not worker_cpus or
                any(type(v) is not int or not 0<=v<8 for v in worker_cpus) or len(set(worker_cpus))!=len(worker_cpus)):
            raise ValueError('Preview worker CPU affinity must contain unique RK CPU indices 0..7')
        self.run=run;self.lock=threading.Lock();self.ring=None;self.preview=None
        self.cached=None;self.cached_ns=0;self.raw=None;self.raw_meta=None
        self.worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix='basic-image',
            initializer=self._start_worker,initargs=(worker_cpus,))
        self.dispatch_lock=threading.Lock();self.pending=None
        self.raw_rate=CounterRate();self.resize=None;self.resize_backend='waiting'
        from ui.live_preview import Rate
        self.input_rate=Rate()

    @staticmethod
    def _start_worker(cpus):
        # Linux affinity is per thread: leave console/network work on small cores.
        if cpus is not None:os.sched_setaffinity(0,set(cpus))
        import cv2
        cv2.setNumThreads(1)

    def close(self):
        self.worker.shutdown(wait=True,cancel_futures=True)
        self._reset()

    def _reset(self):
        for name in ('ring','preview'):
            obj=getattr(self,name)
            if obj:obj.close();setattr(self,name,None)
        self.raw=None;self.raw_meta=None;self.cached=None
        if self.resize:self.resize.close();self.resize=None

    @staticmethod
    def jpeg(pixels,thumbnail=None):
        import cv2
        if thumbnail:
            # Keep the existing thumbnail dimensions and interpolation.
            from PIL import Image
            import numpy as np
            image=Image.fromarray(pixels,'RGB')
            image.thumbnail(thumbnail,Image.Resampling.BILINEAR)
            pixels=np.asarray(image)
        ok,jpeg=cv2.imencode('.jpg',cv2.cvtColor(pixels,cv2.COLOR_RGB2BGR),
                            [cv2.IMWRITE_JPEG_QUALITY,82])
        if not ok:raise ValueError('Display JPEG encoding failed')
        return jpeg.tobytes()

    def _dispatch(self,values,telemetry):
        # Large numpy/PIL/RGA allocations must stay on one persistent thread.
        # A new HTTP thread per frame otherwise retains many malloc arenas.
        with self.dispatch_lock:
            if self.pending is None or self.pending.done():
                self.pending=self.worker.submit(self._capture,values,telemetry)
            future=self.pending
        return future.result(timeout=3)

    def capture(self,values,telemetry):
        value=self._dispatch(values,telemetry)
        if not isinstance(value,dict):return value
        encode=lambda b:'data:image/jpeg;base64,'+base64.b64encode(b).decode() if b else None
        return dict(value,raw_image=encode(value['raw_image']),model_image=encode(value['model_image']),
                    planes=[dict(p,image=encode(p['image'])) for p in value['planes']])

    def capture_packet(self,values,telemetry):
        return pack_images(self._dispatch(values,telemetry))

    def _capture(self,values,telemetry):
        from core.frame_ring import FrameRing
        from vision.bootstrap import install_vendor_resolver
        install_vendor_resolver()
        from detector_frame import detector_input
        from vision.preview_reader import OwnerPreview
        with self.lock:
            started=now=time.monotonic_ns()
            if self.ring:
                try:self.ring.check_owner()
                except RuntimeError:self._reset()
            if self.cached and 0<=now-self.cached_ns<15_000_000:
                return dict(self.cached,age_ms=(now-self.cached['source_ns'])/1e6)
            if not self.ring:self.ring=FrameRing(str(self.run/'frames.memfd'))
            frame=self.ring.latest()
            # A new source frame can arrive while the snapshot is being copied.
            # Compare its timestamp with the clock AFTER acquisition, not before.
            now=time.monotonic_ns()
            if frame is None:
                if self.cached and 0<=now-self.cached['source_ns']<500_000_000:
                    return dict(self.cached,age_ms=(now-self.cached['source_ns'])/1e6)
                raise ValueError('等待新的 FPGA 模型图像')
            if not 0<=now-frame.meta['timestamp_ns']<500_000_000:
                raise ValueError('等待新的 FPGA 模型图像')
            read_done=now
            epoch=frame.meta['fpga_epoch'];stamp=frame.meta['timestamp_ns']
            if self.preview and not self.preview.current():self.preview.close();self.preview=None;self.raw=None;self.raw_meta=None
            raw_error=''
            try:
                if not self.preview:self.preview=OwnerPreview(self.run/'preview.memfd',self.run/'frames.memfd')
                item=self.preview.read_latest()
                if item:
                    rgb,self.raw_meta=item
                    # Display only: measured faster than the mapped RGA/PIL
                    # round trip on this board. Never touches model pixels.
                    import cv2
                    small=cv2.resize(rgb,(960,540),interpolation=cv2.INTER_AREA)
                    bgr=cv2.cvtColor(small,cv2.COLOR_RGB2BGR)
                    ok,jpeg=cv2.imencode('.jpg',bgr,[cv2.IMWRITE_JPEG_QUALITY,82])
                    if not ok:raise ValueError('Preview JPEG encoding failed')
                    self.raw=jpeg.tobytes();self.resize_backend='CPU · 显示专用'
                    self.raw_rate.update(epoch,self.raw_meta['publication_serial'],self.raw_meta['published_ns'])
            except (OSError,ValueError) as exc:raw_error=str(exc)
            raw_done=time.monotonic_ns()
            planes=[]
            # ROI cards crop this same display frame in the browser; no extra capture.
            planes_done=time.monotonic_ns()
            model_image=self.jpeg(frame.rgb)
            now=time.monotonic_ns()  # Snapshot acquisition may cross a preview publication.
            valid_raw=self.raw_meta and 0<=now-self.raw_meta['timestamp_ns']<500_000_000
            metrics={}
            for name in ('hand','gaze'):
                hb=values.get('sys.metrics.'+name,{})
                if str(hb.get('epoch'))==str(epoch) and 0<=now-hb.get('src_ns',0)<=2_000_000_000:
                    metrics[name]={'measurements':hb.get('measurements',{}),'inference':hb.get('inference',{}),'counter_ns':hb.get('src_ns'),'instance':hb.get('instance')}
            owner=values.get('sys.metrics.fpga-io',{})
            native=owner.get('native',{}) if str(owner.get('epoch'))==str(epoch) and 0<=now-owner.get('src_ns',0)<2_000_000_000 else {}
            self.cached=dict(source_ns=stamp,sequence=frame.meta['sequence'],publication_serial=frame.serial,publication_ns=frame.meta['pub_ns'],epoch=str(epoch),age_ms=(now-stamp)/1e6,
                input_hz=self.input_rate.update(epoch,frame.serial,frame.meta['pub_ns']),
                raw_image=self.raw if valid_raw else None,raw_hz=self.raw_rate.value if valid_raw else None,
                raw_source_ns=self.raw_meta['timestamp_ns'] if valid_raw else None,raw_published_ns=self.raw_meta['published_ns'] if valid_raw else None,
                raw_sequence=self.raw_meta['sequence'] if valid_raw else None,raw_publication=self.raw_meta['publication_serial'] if valid_raw else None,raw_error=raw_error,resize_backend=self.resize_backend,
                model_image=model_image,planes=planes,boxes=overlays(values,epoch,stamp,now),faces=face_landmarks(values,epoch,stamp,now),metrics=metrics,
                telemetry=telemetry,capture=native.get('capture',{}),display=native.get('display',{}),
                source_contract=frame.meta.get('detector_contract'),encode_ms=(time.monotonic_ns()-started)/1e6,
                processing_ms={'shared_read':(read_done-started)/1e6,'preview_resize_jpeg':(raw_done-read_done)/1e6,
                    'detector_jpeg':(planes_done-raw_done)/1e6,'model_jpeg':(now-planes_done)/1e6},
                compression={'available':False,'detail':'当前共享平面为 RGB；压缩比与压缩吞吐尚未接入实时计数'})
            # Rate-limit starts, not completion + another full interval. The
            # latter halved unique display FPS when encoding took ~40 ms.
            self.cached_ns=started
            return self.cached


def pack_images(snapshot):
    """HBP1: uint32 metadata length + JSON + JPEG blobs, without base64 copies."""
    metadata=dict(snapshot);blobs=[];images=[]
    def add(key,image):
        if image is None:return None
        if not isinstance(image,bytes):raise ValueError('Binary image required')
        images.append(dict(key=key,length=len(image),type='image/jpeg'));blobs.append(image)
        return key
    metadata['raw_image']=add('raw',snapshot.get('raw_image'))
    metadata['model_image']=add('model',snapshot['model_image'])
    metadata['planes']=[dict(p,image=add('plane'+str(p['size']),p['image'])) for p in snapshot['planes']]
    metadata['images']=images
    encoded=json.dumps(metadata,ensure_ascii=False,separators=(',',':')).encode()
    return b'HBP1'+struct.pack('<I',len(encoded))+encoded+b''.join(blobs)
