"""Read-only feature export for the existing hand/face pipelines.

No capture, model, game action or rendering is started here. Publishers never
block or raise an I/O error into the inference owner. All times are the source
frame's Linux CLOCK_MONOTONIC nanoseconds, not a fabricated display timestamp.
"""
import json,math,socket,time,uuid
from pathlib import Path

HAND_EDGES=((0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),(5,9),(9,10),(10,11),(11,12),
            (9,13),(13,14),(14,15),(15,16),(13,17),(0,17),(17,18),(18,19),(19,20))
FACE_OVAL=(10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,
           148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109)
LEFT_EYE=(33,160,158,133,153,144,33)
RIGHT_EYE=(362,385,387,263,373,380,362)

def _points(rows,expected=None):
    out=[[round(float(v),6) for v in row] for row in rows]
    if expected is not None and len(out)!=expected:raise ValueError('Point count')
    if not out or any(len(row)!=3 or any(not math.isfinite(v) or abs(v)>100 for v in row) for row in out):
        raise ValueError('Invalid XYZ points')
    return out

def hand_features(prediction,timestamp_ns,sequence=0,*,capture_sequence=None):
    hands=[]
    for i,points in enumerate(prediction.hand_world_landmarks):
        category=prediction.handedness[i][0]
        gesture=prediction.gestures[i][0] if i<len(prediction.gestures) and prediction.gestures[i] else None
        hands.append(dict(side=category.category_name,confidence=float(category.score),handedness_confidence=float(category.score),world=_points([(p.x,p.y,p.z) for p in points],21),
            image=_points([(p.x,p.y,p.z) for p in prediction.hand_landmarks[i]],21),
            gesture=gesture.category_name if gesture else None,gesture_confidence=float(gesture.score) if gesture else 0.))
    return dict(version=1,kind='hand',timestamp_ns=int(timestamp_ns),sequence=int(sequence),
        capture_sequence=capture_sequence,source='existing_mediapipe_gesture_result',coordinates='model_world_xyz',hands=hands)

def face_features(face,timestamp_ns,sequence=0):
    packet=dict(version=1,kind='face',timestamp_ns=int(timestamp_ns),sequence=int(sequence),
        source='existing_face_alignment_result',coordinates='image_xy_normalized_z_width',valid=False,
        capture_sequence=getattr(face,'capture_sequence',None),
        groups=dict(head=False,left_eye=False,right_eye=False,left_iris=False,right_iris=False))
    if not face.status:return packet
    w,h=int(face.img_w),int(face.img_h)
    if w<=0 or h<=0:raise ValueError('Face source geometry')
    raw=face.face_landmarks
    # status=True alone only means a face was detected, not that dense geometry
    # was assigned. Old app28 early ROI failures leave an all-zero array.
    if not getattr(face,'landmarks_valid',getattr(face,'can_gaze_estimation',False)):
        return packet
    points=_points([[float(x)/w,float(y)/h,float(z)/w] for x,y,z in raw])
    if len(points) not in (468,478) or any(max(p[a] for p in points)-min(p[a] for p in points)<=1e-6 for a in (0,1)):
        return packet
    left=bool(getattr(face,'left_eye_valid',getattr(face,'can_gaze_estimation',False)))
    right=bool(getattr(face,'right_eye_valid',getattr(face,'can_gaze_estimation',False)))
    packet.update(valid=True,size=[w,h],landmarks=points,
        groups=dict(head=True,left_eye=left,right_eye=right,
                    left_iris=left and len(points)==478 and bool(getattr(face,'left_iris_valid',True)),
                    right_iris=right and len(points)==478 and bool(getattr(face,'right_iris_valid',True))),
        eye_left=float(face.left_eye_openness),eye_right=float(face.right_eye_openness),
        eye_left_ear=getattr(face,'left_eye_ear',None),eye_right_ear=getattr(face,'right_eye_ear',None))
    return packet

def face_points_isotropic(packet):
    """v1 image-x/y-normalized and width-relative z -> common width units.

    The old misleading coordinate label used the same numbers; retain wire
    compatibility, and fix conversion at each 3D consumer exactly once.
    """
    if packet.get('coordinates') not in (None,'image_width_normalized_relative_xyz','image_xy_normalized_z_width'):
        raise ValueError('Unknown face coordinate convention')
    w,h=packet['size']
    if not all(type(v) is int and v>0 for v in (w,h)):raise ValueError('Face size')
    return [[x,y*h/w,z] for x,y,z in packet['landmarks']]

class FeaturePublisher:
    def __init__(self,address=('127.0.0.1',29802),fps=5):
        if address[0]!='127.0.0.1' or not math.isfinite(fps) or fps<0:raise ValueError('Local nonnegative finite publication rate only')
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.socket.setblocking(False)
        self.address=address;self.period=1/fps if fps else 0.;self.deadline=0.;self.sequence=0;self.sent=0;self.dropped=0
        self.instance=uuid.uuid4().hex
        path=Path('/proc/sys/kernel/random/boot_id')
        self.boot_id=path.read_text().strip() if path.is_file() else None
    def due(self):return time.monotonic()>=self.deadline
    def send(self,packet):
        if not self.due():return False
        self.deadline=time.monotonic()+self.period;self.sequence+=1
        packet=dict(packet,packet_sequence=self.sequence,source_instance=self.instance,boot_id=self.boot_id)
        try:
            body=json.dumps(packet,separators=(',',':'),allow_nan=False).encode()
            if len(body)>32000:raise ValueError('Feature packet budget')
            self.socket.sendto(body,self.address);self.sent+=1;return True
        except (OSError,ValueError,TypeError):self.dropped+=1;return False
    def close(self):self.socket.close()

class FeatureState:
    def __init__(self):
        self.samples={};self.rejected=0;self.retired={}
        path=Path('/proc/sys/kernel/random/boot_id')
        self.boot_id=path.read_text().strip() if path.is_file() else None
    def accept(self,body,now_ns=None):
        now=time.monotonic_ns() if now_ns is None else now_ns
        try:
            if len(body)>32000:raise ValueError('size')
            packet=json.loads(body);kind=packet['kind'];stamp=packet['timestamp_ns']
            if packet['version']!=1 or kind not in ('hand','face') or type(stamp)!=int or not 0<=now-stamp<=750_000_000:raise ValueError('epoch/age')
            old=self.samples.get(kind)
            if old and stamp<=old['timestamp_ns']:raise ValueError('old sample')
            capture=packet.get('capture_sequence')
            if capture is not None and (type(capture) is not int or not 0<=capture<2**32):raise ValueError('capture sequence')
            instance=packet.get('source_instance')
            if instance is not None:
                if not isinstance(instance,str) or len(instance)!=32 or any(c not in '0123456789abcdef' for c in instance):raise ValueError('source instance')
                if self.boot_id and packet.get('boot_id')!=self.boot_id:raise ValueError('source boot')
                seq=packet.get('packet_sequence')
                if type(seq) is not int or seq<=0:raise ValueError('packet sequence')
                if instance in self.retired.get(kind,[]):raise ValueError('retired source')
                if old and old.get('source_instance')==instance:
                    if seq<=old['packet_sequence']:raise ValueError('replayed packet')
                    if capture is not None and capture==old.get('capture_sequence'):raise ValueError('repeated capture')
                elif old and old.get('source_instance'):
                    if now-old['timestamp_ns']<=350_000_000:raise ValueError('active source changed')
            elif old and old.get('source_instance'):
                raise ValueError('source identity downgrade')
            if kind=='hand':
                if len(packet['hands'])>4:raise ValueError('hand count')
                for hand in packet['hands']:
                    _points(hand['world'],21);_points(hand['image'],21)
                    if not math.isfinite(hand['confidence']) or not 0<=hand['confidence']<=1:raise ValueError('confidence')
            elif packet['valid']:
                _points(packet['landmarks'])
                if len(packet['landmarks']) not in (468,478):raise ValueError('face shape')
                face_points_isotropic(packet)
                if any(max(p[a] for p in packet['landmarks'])-min(p[a] for p in packet['landmarks'])<=1e-6 for a in (0,1)):raise ValueError('degenerate face')
                if any(not math.isfinite(packet[k]) for k in ('eye_left','eye_right')):raise ValueError('eye metric')
                if any(packet.get(k) is not None and (type(packet[k]) not in (int,float) or not math.isfinite(packet[k]) or packet[k]<0) for k in ('eye_left_ear','eye_right_ear')):raise ValueError('EAR metric')
                groups=packet.get('groups')
                if groups is not None:
                    if set(groups)!={'head','left_eye','right_eye','left_iris','right_iris'} or any(type(v) is not bool for v in groups.values()):raise ValueError('group flags')
                    if not groups['head']:raise ValueError('valid face needs head geometry')
                    for side in ('left','right'):
                        if groups[side+'_iris'] and (not groups[side+'_eye'] or len(packet['landmarks'])!=478):raise ValueError('iris availability')
            if old and old.get('source_instance') and instance!=old['source_instance']:
                self.retired[kind]=(self.retired.get(kind,[])+[old['source_instance']])[-32:]
            self.samples[kind]=packet;return True
        except (ValueError,TypeError,KeyError,IndexError):self.rejected+=1;return False
    def fresh(self,kind,now_ns=None):
        now=time.monotonic_ns() if now_ns is None else now_ns;p=self.samples.get(kind)
        return p if p and 0<=now-p['timestamp_ns']<=350_000_000 else None
