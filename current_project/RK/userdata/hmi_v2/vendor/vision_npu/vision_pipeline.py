"""Image -> NPU face/hand detection, landmarks, embedding and static gesture.

Geometry follows MediaPipe v0.10.18 (Apache-2.0); pinned source references are
in upstream_reference. Tracking IDs are short-lived spatial tracks, not users.
All neural network calls use Model; ReferenceModel must be explicitly supplied
by a test. Supports up to two faces and four independent hands on one image.
"""
import math,os,time
from types import SimpleNamespace
import cv2,numpy as np
from npu_runtime import Model
from roi_workers import OwnerPool
from runtime_policy import POLICY
from detector_frame import detector_input

LABELS=['None','Closed_Fist','Open_Palm','Pointing_Up','Thumb_Down','Thumb_Up','Victory','ILoveYou']
def sigmoid(x):return 1/(1+np.exp(-np.clip(x,-80,80)))
def rotation(a):return (a+math.pi)%(2*math.pi)-math.pi
def rotmat(a):return np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]],np.float32)
def points(p):return [SimpleNamespace(x=float(x),y=float(y),z=float(z)) for x,y,z in p]
def anchors(size):
    return np.array([[(x+.5)/s,(y+.5)/s] for stride,n in [(8,2),(16,6)] for s in [size//stride] for y in range(s) for x in range(s) for _ in range(n)],np.float32)
def overlap(box,boxes):
    xy=np.maximum(box[:2],boxes[:,:2]);end=np.minimum(box[2:4],boxes[:,2:4]);inter=np.prod(np.maximum(0,end-xy),axis=1)
    area=np.prod(np.maximum(0,boxes[:,2:4]-boxes[:,:2]),axis=1);a=np.prod(np.maximum(0,box[2:4]-box[:2]))
    return inter/np.maximum(1e-9,a+area-inter)
def weighted_nms(coords,scores,limit,threshold=.3):
    order=np.argsort(-scores);out=[]
    while len(order) and len(out)<limit:
        group=overlap(coords[order[0]],coords[order])>threshold
        group[0]=True;ids=order[group];weights=scores[ids]
        out.append((np.sum(coords[ids]*weights[:,None],axis=0)/weights.sum(),float(scores[ids].mean())))
        order=order[~group]
    return out
def crop(rgb,rect,size,zero=False):
    cx,cy,w,h,a=map(float,rect)
    src=cv2.boxPoints(((cx,cy),(w,h),a*180/math.pi))
    dst=np.array([[0,size],[0,0],[size,0],[size,size]],np.float32)
    matrix=cv2.getPerspectiveTransform(src,dst)
    return cv2.warpPerspective(rgb,matrix,(size,size),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT if zero else cv2.BORDER_REPLICATE)
def project(raw,rect,size,width,height,hand=False):
    q=np.asarray(raw,np.float32).reshape(-1,3).copy();q/=size
    if hand:q[:,2]/=.4
    q[:,:2]=(q[:,:2]-.5)*np.array(rect[2:4]);q[:,:2]=q[:,:2]@rotmat(rect[4]).T+np.array(rect[:2]);q[:,2]*=rect[2]
    q/=np.array([width,height,width]);return q
def transform_rect(cx,cy,w,h,a,scale,shift_y=0.,square=False):
    cx-=h*shift_y*math.sin(a);cy+=h*shift_y*math.cos(a)
    if square:w=h=max(w,h)
    return np.array([cx,cy,max(1,w*scale),max(1,h*scale),a],np.float32)
def next_rect(p,width,height,hand):
    xy=p[:,:2]*np.array([width,height])
    if hand:
        q=xy[[0,1,2,3,5,6,9,10,13,14,17,18]]
        v=(q[4]+q[8]+2*q[6])/4-q[0];a=rotation(math.pi/2+math.atan2(v[1],v[0]))
        center=(q.min(0)+q.max(0))/2;local=(q-center)@rotmat(a)
        wh=local.max(0)-local.min(0);c=(local.max(0)+local.min(0))/2@rotmat(a).T+center
        return transform_rect(*c,*wh,a,2.,-.1,True)
    v=xy[263]-xy[33];a=rotation(math.atan2(v[1],v[0]));lo=xy.min(0);hi=xy.max(0)
    return transform_rect(*((lo+hi)/2),*(hi-lo),a,1.5,0,True)
def normalize_object(p,width=None,height=None):
    q=p.copy()
    if width is not None:q[:,:2]=(q[:,:2]-.5)*np.array([width,height])/max(width,height)+.5
    q-=q[0];q/=max(float(np.ptp(q[:,0])),float(np.ptp(q[:,1])))+1e-5
    return q[None].astype(np.float32)

class Detector:
    def __init__(self,hand=False,backend=Model,core=0,threshold=None):
        self.hand=hand;self.size=192 if hand else 128;self.anchors=anchors(self.size)
        self.model=backend('hand_detector' if hand else 'face_detector',core)
        self.threshold=threshold if threshold is not None else (.6 if hand else .5)
    def __call__(self,rgb,limit):
        h,w=rgb.shape[:2];side=max(h,w)
        prepared=detector_input(rgb,self.size)
        if prepared is None:
            if os.environ.get('NPU_REQUIRE_FPGA_DETECTOR')=='1':raise RuntimeError('Same-frame FPGA detector input missing or transformed')
            prepared=crop(rgb,[w/2,h/2,side,side,0],self.size,True)
            self.last_preprocess_executor='cpu'
        else:self.last_preprocess_executor='fpga'
        tensor=prepared.astype(np.float32);tensor/=255
        if not self.hand:tensor*=2;tensor-=1
        boxes,logits=self.model(tensor[None]);scores=sigmoid(logits.reshape(-1));keep=scores>=self.threshold
        b=boxes.reshape(len(self.anchors),-1)[keep];an=self.anchors[keep];sc=scores[keep]
        if not len(b):return []
        center=b[:,:2]/self.size+an;wh=b[:,2:4]/self.size
        key=b[:,4:].reshape(len(b),-1,2)/self.size+an[:,None,:]
        coords=np.concatenate([center-wh/2,center+wh/2,key.reshape(len(b),-1)],axis=1)
        out=[]
        for c,score in weighted_nms(coords,sc,limit):
            c=c.reshape(-1,2)*side+np.array([(w-side)/2,(h-side)/2]);lo,hi=c[:2];k=c[2:]
            v=k[2 if self.hand else 1]-k[0];a=rotation((math.pi/2 if self.hand else 0)+math.atan2(v[1],v[0]))
            rect=transform_rect(*((hi+lo)/2),*(hi-lo),a,2.6 if self.hand else 1.5,-.5 if self.hand else 0,self.hand)
            out.append(dict(rect=rect,score=score))
        return out
    def close(self):self.model.close()

class ROIProcessor:
    def __init__(self,hand,backend,core):
        self.hand=hand;self.landmark=self.embed=self.classify=None
        try:
            self.landmark=backend('hand_landmarks_detector' if hand else 'face_landmarks_detector',core)
            if hand:self.embed=backend('gesture_embedder',core);self.classify=backend('canned_gesture_classifier',core)
        except BaseException:self.close();raise
        self.embed_active=[x.get('active',True) for x in self.embed.io['inputs']] if hand and hasattr(self.embed,'io') else [True]*3
    def __call__(self,rgb,c,stamp,record):
        h,w=rgb.shape[:2];rect=c['rect'];size=224 if self.hand else 256;captured=[]
        tensor=crop(rgb,rect,size).astype(np.float32);tensor/=255
        raw=self.landmark(tensor[None]);presence=float(raw[1].reshape(-1)[0]);presence=presence if self.hand else float(sigmoid(presence))
        if presence<(.6 if self.hand else .5):return None,None,captured
        p=project(raw[0],rect,size,w,h,self.hand)
        if not np.isfinite(p).all():return None,None,captured
        item=dict(id=c['id'],landmarks=p,presence=presence,rect=rect.copy(),stamp=stamp)
        if self.hand:
            right=float(raw[2].reshape(-1)[0]);world=raw[3].reshape(21,3).copy();world[:,:2]=world[:,:2]@rotmat(rect[4]).T
            tensors=[normalize_object(p,w,h),
                     np.array([[right]],np.float32) if self.embed_active[1] or record else None,
                     normalize_object(world) if self.embed_active[2] or record else None]
            emb=self.embed(*tensors)[0];prob=self.classify(emb)[0].reshape(-1);label=int(np.argmax(prob))
            item.update(world=world,right=right,gesture=LABELS[label],score=float(prob[label]),probabilities=prob)
            if record:captured.extend([dict(name='gesture_embedder',inputs=tensors,outputs=[emb]),dict(name='canned_gesture_classifier',inputs=[emb],outputs=[prob])])
        if record:captured.append(dict(name=self.landmark.name,inputs=[tensor[None]],outputs=raw))
        return item,dict(id=c['id'],rect=next_rect(p,w,h,self.hand)),captured
    def close(self):
        for x in (self.landmark,self.embed,self.classify):
            if x is not None:x.close()

class LandmarkPipeline:
    def __init__(self,hand=False,limit=None,backend=Model,core=0,detect_interval=.2,tracking=True,roi_cores=None):
        self.hand=hand;self.limit=limit or (4 if hand else 2)
        if not 1<=self.limit<=(4 if hand else 2):raise ValueError('capacity')
        self.detector=Detector(hand,backend,core);self.pool=None;self.processor=None
        if roi_cores is None:
            default=','.join(map(str,POLICY['hand_roi_cores' if hand else 'face_roi_cores']))
            setting=os.environ.get('NPU_HAND_CORES' if hand else 'NPU_FACE_CORES',default) if backend is Model else ''
            roi_cores=[int(x) for x in setting.split(',') if x.strip()]
        self.roi_cores=list(roi_cores)
        try:
            if roi_cores:self.pool=OwnerPool(lambda c:ROIProcessor(hand,backend,c),roi_cores)
            else:self.processor=ROIProcessor(hand,backend,core)
        except BaseException:self.detector.close();raise
        self.tracks=[];self.next_id=1;self.last_detection=-float('inf');self.last_stamp=None
        self.detect_interval=detect_interval;self.tracking=tracking;self.last_ms={};self.captured=[]
    def reset(self):self.tracks=[];self.last_detection=-float('inf');self.last_stamp=None
    def process(self,rgb,stamp=None,record=False):
        start=time.perf_counter();stamp=time.monotonic() if stamp is None else stamp
        if self.last_stamp is not None and (stamp<=self.last_stamp or stamp-self.last_stamp>.5):self.reset()
        self.last_stamp=stamp;h,w=rgb.shape[:2];old=self.tracks
        redetect=not self.tracking or not old or stamp-self.last_detection>=self.detect_interval
        if redetect:
            candidates=self.detector(rgb,self.limit);self.last_detection=stamp
            # Match each new ROI at most once. Missing tracks are invalidated.
            available=list(old)
            for c in candidates:
                distances=[np.linalg.norm(c['rect'][:2]-t['rect'][:2])/max(c['rect'][2],t['rect'][2],1) for t in available]
                j=int(np.argmin(distances)) if distances else -1
                ordered=sorted(distances)
                ambiguous=len(ordered)>1 and ordered[1]-ordered[0]<.12
                if j>=0 and distances[j]<.6 and not ambiguous:c['id']=available.pop(j)['id']
                else:c['id']=self.next_id;self.next_id+=1
        else:candidates=[dict(rect=t['rect'],id=t['id']) for t in old]
        detected=time.perf_counter();results=[];tracks=[]
        jobs=[(rgb,c,stamp,record) for c in candidates[:self.limit]]
        outputs=self.pool.map(jobs) if self.pool else [self.processor(*j) for j in jobs]
        for item,track,captured in outputs:
            self.captured.extend(captured)
            if item is not None:tracks.append(track);results.append(item)
        # Overlapping ROIs must not count the same physical landmark set twice.
        unique=[];kept=[]
        for item,track in sorted(zip(results,tracks),key=lambda pair:-pair[0]['presence']):
            if any(np.mean(np.linalg.norm(item['landmarks'][:,:2]-u['landmarks'][:,:2],axis=1))<.035 for u in unique):continue
            unique.append(item);kept.append(track)
        results=unique;tracks=kept;self.tracks=tracks
        if len(tracks)<len(candidates):self.last_detection=-float('inf')
        self.last_ms=dict(detector=(detected-start)*1000,total=(time.perf_counter()-start)*1000,redetected=redetect)
        return results
    def close(self):
        try:
            if self.pool:self.pool.close()
            if self.processor:self.processor.close()
        finally:self.detector.close()

class HandRecognizer:
    """Small MediaPipe-result adapter used by existing gesture consumers."""
    def __init__(self,num_hands=4,core=0):self.pipeline=LandmarkPipeline(True,num_hands,core=core)
    def recognize_for_video(self,image,timestamp_ms):return self._run(image,timestamp_ms/1000)
    def recognize(self,image):
        self.pipeline.reset()
        return self._run(image,None)
    def _run(self,image,stamp):
        rgb=image.numpy_view() if hasattr(image,'numpy_view') else image
        hands=self.pipeline.process(rgb,stamp)
        cat=lambda label,score:SimpleNamespace(category_name=label,score=score,index=0,display_name=label)
        return SimpleNamespace(hand_landmarks=[points(h['landmarks']) for h in hands],hand_world_landmarks=[points(h['world']) for h in hands],
            handedness=[[cat('Right' if h['right']>=.5 else 'Left',max(h['right'],1-h['right']))] for h in hands],
            gestures=[[cat(h['gesture'],h['score'])] for h in hands],track_ids=[h['id'] for h in hands])
    def close(self):self.pipeline.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

class FaceLandmarker:
    def __init__(self,num_faces=2,core=0):self.pipeline=LandmarkPipeline(False,num_faces,core=core)
    def detect_for_video(self,image,timestamp_ms):return self._run(image,timestamp_ms/1000)
    def detect(self,image):
        self.pipeline.reset()
        return self._run(image,None)
    def _run(self,image,stamp):
        rgb=image.numpy_view() if hasattr(image,'numpy_view') else image
        faces=self.pipeline.process(rgb,stamp)
        return SimpleNamespace(face_landmarks=[points(f['landmarks']) for f in faces],track_ids=[f['id'] for f in faces])
    def close(self):self.pipeline.close()
