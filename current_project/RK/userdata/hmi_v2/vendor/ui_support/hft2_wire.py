"""CRC-protected HFT2 app metadata; source identity/time fields stay intact."""
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import struct
import zlib

_source=Path(__file__).with_name('hft1_common_snapshot.py')
_spec=importlib.util.spec_from_file_location('_app_hft1_common_snapshot',_source)
_common=importlib.util.module_from_spec(_spec)
import sys
sys.modules[_spec.name]=_common
_spec.loader.exec_module(_common)
Scene=_common.Scene
HEADER_BYTES=112
BOXES=((24,70,141,224),(153,70,270,224),(314,74,366,139),(376,74,490,139),(314,162,490,224))

@dataclass
class AppMetadata:
    actor_slot:int=1
    actor_track_id:int=0xffffffff
    ui_status:int=0x00010f00
    display_generation:int=0
    classification_confidence:int=0
    trajectory_points:int=0
    association_flags:int=0

@dataclass
class AppFrame:
    geometry:Scene
    metadata:AppMetadata

def _integer(value,maximum,name):
    if type(value) is not int or not 0<=value<=maximum:
        raise ValueError(name)

def validate(scene,meta):
    if type(meta.actor_slot) is not int or meta.actor_slot not in (1,2):raise ValueError('actor_slot')
    for name in ('actor_track_id','ui_status','display_generation'):_integer(getattr(meta,name),0xffffffff,name)
    _integer(meta.classification_confidence,255,'confidence')
    _integer(meta.trajectory_points,48,'trajectory points')
    _integer(meta.association_flags,7,'association flags')
    status=meta.ui_status;draw=status&15;static=(status>>4)&15;label=(status>>8)&15;mode=(status>>16)&3
    if status>>18 or mode==3 or draw not in (0,1,2,3,4,5,15) or static not in (0,1,2,3,4,5,6,15) or label not in (*range(8),15):
        raise ValueError('status enums/reserved')
    assoc=meta.association_flags
    if (scene.valid&1 and not assoc&2) or (scene.valid&2 and not assoc&4):raise ValueError('unassigned hand')
    if (scene.valid&12 or assoc&6) and not assoc&1:raise ValueError('unassigned face')
    if assoc&1 and meta.actor_track_id==0xffffffff:raise ValueError('unknown registered track')
    if scene.valid&16 and (mode!=1 or not assoc&6 or meta.trajectory_points==0):raise ValueError('trajectory mode/source')
    calibrated=bool(status&(1<<13));track=bool(status&(1<<14));projection=bool(status&(1<<15))
    if track and (not calibrated or not assoc&1):raise ValueError('unqualified TRACK')
    if projection and not (track and calibrated and assoc&1):raise ValueError('unqualified projection')
    if status&(1<<12) and (draw!=3 or label>7 ):raise ValueError('unqualified classification')
    if scene.valid&16 and sum(v[0]==4 for v in scene.vertices)!=meta.trajectory_points:
        raise ValueError('actual rendered trajectory point count')

def encode(scene,metadata,epoch,sequence,previous_epoch=0,trace_timestamp_ns=0):
    validate(scene,metadata)
    old=_common.encode(scene,epoch,sequence,previous_epoch)
    header=bytearray(old[:96]);header[4]=2;header[6]=112;header[11]=metadata.actor_slot
    extension=struct.pack('<IIIBBBB',metadata.actor_track_id,metadata.ui_status,metadata.display_generation,
        metadata.classification_confidence,metadata.trajectory_points,metadata.association_flags,0)
    trace=b''
    if trace_timestamp_ns:
        _integer(trace_timestamp_ns,2**64-1,'trace source timestamp')
        if not scene.valid&16:raise ValueError('trace timestamp without trace')
        header[4]=3;header[6]=120;trace=struct.pack('<Q',trace_timestamp_ns)
    body=bytes(header)+extension+trace+old[96:-4]
    return body+struct.pack('<I',zlib.crc32(body))

def decode(frame):
    if len(frame)<116 or frame[:4]!=b'HFT1' or (frame[4],frame[6]) not in ((2,112),(3,120)) or len(frame)<frame[6]+4 or frame[111]:raise ValueError('HFT2 header')
    if zlib.crc32(frame[:-4])!=struct.unpack_from('<I',frame,len(frame)-4)[0]:raise ValueError('HFT2 CRC')
    trace_ns=struct.unpack_from('<Q',frame,112)[0] if frame[4]==3 else 0
    if frame[4]==3 and frame[10]&16 and not trace_ns:raise ValueError('missing trace timestamp')
    values=struct.unpack_from('<IIIBBBB',frame,96)
    meta=AppMetadata(frame[11],*values[:6])
    header=bytearray(frame[:96]);header[4]=1;header[6]=96;header[11]=0
    old=bytes(header)+frame[frame[6]:-4]
    common=_common.decode(old+struct.pack('<I',zlib.crc32(old)))
    validate(common['scene'],meta)
    return dict(**common,metadata=meta,trace_timestamp_ns=trace_ns)

def project_q4(point,group):
    return (point[0]>>4,point[1]>>4,point[2]) if group>=3 else _common.project_q4(point)
