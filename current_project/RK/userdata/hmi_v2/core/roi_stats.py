"""Passive face ROI messages; no device access and no exposure control."""
import math
import struct


def command(face, epoch, now):
    face=face or {};stamp=int(face.get('src_ns',0));seq=int(face.get('seq',0))&0xffffffff
    active=face.get('epoch')==epoch and 0<stamp<=now and now-stamp<=250_000_000
    rows=[f for f in face.get('faces',[]) if f.get('valid')]
    primary=[f for f in rows if f.get('primary')]
    selected=primary[0] if len(primary)==1 else rows[0] if len(rows)==1 else None
    rect=[0]*4;size=[0,0]
    if active and selected:
        try:
            x,y,w,h=map(float,selected['face_rect']);sw,sh=map(int,selected['source_size'])
            active=all(math.isfinite(v) for v in (x,y,w,h)) and w>0 and h>0 and 0<sw<=8191 and 0<sh<=8191
            if active:
                rect=[max(0,math.floor(x)),max(0,math.floor(y)),min(sw,math.ceil(x+w)),min(sh,math.ceil(y+h))]
                size=[sw,sh];active=rect[0]<rect[2] and rect[1]<rect[3]
        except (KeyError,ValueError,TypeError,OverflowError):active=False
    else:active=False
    if not active:rect=[0]*4;size=[0,0]
    try:track=int(selected.get('track_id',0)) if selected else 0
    except (TypeError,ValueError,OverflowError):active=False;track=0
    if not 0<=track<=0xffffffff:active=False;track=0
    return b'ROI2'+struct.pack('<QQ9I',epoch,max(0,stamp),seq,int(active),*rect,*size,track)


def decode(reply):
    identity={}
    if len(reply)==120:
        result,epoch,stamp,track=struct.unpack_from('<iQQI',reply)
        v=struct.unpack_from('<24I',reply,24)
        identity=dict(epoch=epoch,source_ns=stamp,actor_track_id=track,source_verified=True)
    elif len(reply)==100:
        result,*v=struct.unpack('<i24I',reply)
        identity=dict(source_verified=False)
    else:return {'available':False,'error':'malformed_reply'}
    if result:return {'available':False,'error':result}
    seq,valid,frame,cmd,source,count,low,high,*hist=v
    total=low+(high<<32)
    coherent=bool(valid and count and sum(hist)==count and total<=1023*count)
    return dict(available=True,valid=coherent,stats_seq=seq,frame_id=frame,command_id=cmd,
                source_frame=source,pixels=count,mean_linear_rgb10=total/count if coherent else None,
                histogram=hist,**identity,scope='passive CCM RGB10 ROI; no exposure changes')
