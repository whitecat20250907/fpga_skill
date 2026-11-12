"""Registered same-source observations to bounded HFT2 application geometry.

No inference, camera, registration heuristic, transport, or OS input. The
single relay supplies snapshots already bound to its current owned producers.
"""
import math

from hft2_wire import AppFrame, AppMetadata, BOXES, Scene, _common, project_q4, validate

POSE_TTL_NS=350_000_000
RESULT_TTL_NS=1_200_000_000
HEAD_OVAL=_common.FACE_OVAL[::3]


def fresh(packet, now_ns, ttl=POSE_TTL_NS):
    stamp=packet.get('timestamp_ns') if packet else None
    return type(stamp) is int and 0<=now_ns-stamp<=ttl


def age(stamp,now_ns):
    if type(stamp) is not int or not 0<=now_ns-stamp:
        raise ValueError('source clock')
    return min(65535,(now_ns-stamp+999999)//1000000)


def _points(rows,count=None):
    if count is not None and len(rows)!=count:raise ValueError('point count')
    if not rows or any(len(p)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>100 for x in p) for p in rows):
        raise ValueError('finite XYZ')
    return rows


def add_xyz(scene,group,points,edges,triangles,source_age):
    """Fit actual relative XYZ to the new panel, preserving hardware projection."""
    _points(points)
    left,top,right,bottom=BOXES[group]
    projected=[(.8984375*x-.43359375*z,.98828125*y-.1484375*(.43359375*x+.8984375*z)) for x,y,z in points]
    dx=max(p[0] for p in projected)-min(p[0] for p in projected)
    dy=max(p[1] for p in projected)-min(p[1] for p in projected)
    if max(dx,dy)<1e-8:raise ValueError('degenerate XYZ')
    # Four logical pixels are reserved for the actual shaded hand capsule.
    pad=6 if group<2 else 3
    scale=min((right-left-2*pad)/max(dx,1e-8),(bottom-top-2*pad)/max(dy,1e-8))
    quantized=[tuple(round(float(v)*scale*16) for v in p) for p in points]
    if any(not -32768<=v<=32767 for p in quantized for v in p):raise ValueError('Q4 overflow')
    qp=[project_q4(p,group) for p in quantized]
    offset=((left+right-min(p[0] for p in qp)-max(p[0] for p in qp))//2,
            (top+bottom-min(p[1] for p in qp)-max(p[1] for p in qp))//2)
    if any(not left+pad-1<=p[0]+offset[0]<=right-pad+1 or not top+pad-1<=p[1]+offset[1]<=bottom-pad+1 for p in qp):
        raise ValueError('projected panel fit')
    start=len(scene.vertices)
    scene.vertices.extend((group,*p) for p in quantized)
    scene.edges.extend((start+a,start+b,shade) for a,b,shade in edges)
    scene.triangles.extend((start+a,start+b,start+c,shade) for a,b,c,shade in triangles)
    scene.valid|=1<<group;scene.ages[group]=source_age;scene.offsets[group]=offset


def add_flat(scene,group,xy,edges,source_age):
    """Absolute logical screen/trace XY: never yaw/pitch or re-fit each frame."""
    left,top,right,bottom=BOXES[group]
    if not xy or any(len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) or
            not left<=p[0]<=right or not top<=p[1]<=bottom for p in xy):raise ValueError('flat viewport')
    start=len(scene.vertices)
    scene.vertices.extend((group,round(x*16),round(y*16),0) for x,y in xy)
    scene.edges.extend((start+a,start+b,shade) for a,b,shade in edges)
    scene.valid|=1<<group;scene.ages[group]=source_age


def projection_sample(gaze,registration,context,now_ns):
    """Return only the personally calibrated primary's actual filtered pixel."""
    if not registration or not fresh(gaze,now_ns):return None
    if (gaze.get('source_instance')!=registration['face_source_instance'] or
            gaze.get('track_id')!=registration['face_track_id'] or
            tuple(gaze.get(k) for k in ('owner_generation','capture_session'))!=context or
            gaze.get('mode')!='TRACK' or gaze.get('valid') is not True or
            gaze.get('calibration_valid_for_track') is not True or gaze.get('projection_valid') is not True):return None
    xy,size=gaze.get('filtered'),gaze.get('screen_size')
    if (not isinstance(size,(list,tuple)) or len(size)!=2 or any(type(v) is not int or v<=0 for v in size)
            or not isinstance(xy,(list,tuple)) or len(xy)!=2 or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in xy) or
            not 0<=xy[0]<size[0] or not 0<=xy[1]<size[1]):return None
    return xy,size


class ApplicationScene:
    """One scene builder for the relay's one explicit ActorController.

    With one registered hand it is the drawing hand. With two, choose one
    explicitly via select_trajectory_hand; no list-order or nearest-face guess.
    """
    def __init__(self,controller):
        self.controller=controller
        self.trajectory_hands={}
        self.last_diagnostic={}

    def select_trajectory_hand(self,slot,track_id):
        r=self.controller.registrations.get(slot)
        if not r or type(track_id) is not int or track_id not in [h['track_id'] for h in r['hands']]:
            raise ValueError('explicit registered trajectory hand required')
        self.trajectory_hands[slot]=(r['registration_generation'],track_id)
        return dict(accepted=True,actor_slot=slot,hand_track_id=track_id)

    def build(self,now_ns,*,face_geometry,hand_packet,gaze,acknowledged_mode):
        c=self.controller
        assignments=c.assignments(now_ns)
        r=next((r for r in assignments if r['slot']==c.display_slot and r.get('tracking_state','active')=='active'),None)
        scene=Scene()
        hand_packet=hand_packet or {}
        hand_ok=bool(r and fresh(hand_packet,now_ns) and hand_packet.get('valid') is True and
            hand_packet.get('source_instance')==r['hand_source_instance'] and
            tuple(hand_packet.get(k) for k in ('owner_generation','capture_session'))==c.context)
        current={h['track_id']:h for h in hand_packet.get('hands',[])} if hand_ok else {}
        bound=[b for b in r['hands'] if b['track_id'] in current] if r else []
        if hand_ok:
            scene.hand_timestamp_ns=hand_packet['timestamp_ns']
            scene.capture_sequence=hand_packet.get('capture_sequence',0xffffffff)
            scene.fixture|=bool(hand_packet.get('fixture'))
            for b in bound:
                h=current[b['track_id']]
                if h.get('confidence',0)<.6:continue
                points=_points(h['world'],21);origin=points[0]
                local=[tuple(p[i]-origin[i] for i in range(3)) for p in points]
                group={'Left':0,'Right':1}[b['side']]
                add_xyz(scene,group,local,[(a,z,1) for a,z in _common.HAND_EDGES],
                    [(0,5,9,0),(0,9,13,0),(0,13,17,0)],age(hand_packet['timestamp_ns'],now_ns))
        face=face_geometry.get(r['face_track_id']) if r else None
        if (face and fresh(face,now_ns) and face.get('valid') is True and
                face.get('model_source_instance')==r['face_source_instance']):
            raw=_points(face['landmarks']);w,h=face['size'];origin=raw[1]
            isotropic=[(p[0]-origin[0],(p[1]-origin[1])*h/w,p[2]-origin[2]) for p in raw]
            groups=face.get('groups',{})
            eye_pairs=[pair for side,pair in (('left',(33,133)),('right',(362,263))) if groups.get(side+'_eye',True)]
            irises=[key for side,key in (('left',468),('right',473)) if len(raw)==478 and groups.get(side+'_eye',True) and groups.get(side+'_iris',True)]
            indices=list(HEAD_OVAL)+[1,61,291]+[i for pair in eye_pairs for i in pair]+irises
            lookup={key:i for i,key in enumerate(indices)}
            head=[isotropic[i] for i in indices]
            edges=[(lookup[a],lookup[b],1) for a,b in zip(HEAD_OVAL,HEAD_OVAL[1:]+HEAD_OVAL[:1])]
            edges += [(lookup[a],lookup[b],2) for a,b in eye_pairs+[(61,291),(1,10)]]
            edges += [(lookup[i],lookup[i],3) for i in irises]
            tris=[(lookup[1],lookup[a],lookup[b],0) for a,b in zip(HEAD_OVAL,HEAD_OVAL[1:]+HEAD_OVAL[:1])]
            arrow=_common.head_direction_arrow(isotropic)
            if arrow is not None:
                start=len(head);head.extend(arrow)
                edges.extend(((lookup[1],start,2),(start,start+1,2),(start,start+2,2)))
            add_xyz(scene,2,head,edges,tris,age(face['timestamp_ns'],now_ns))
            scene.face_timestamp_ns=face['timestamp_ns'];scene.fixture|=bool(face.get('fixture'))
            if face['timestamp_ns']>=scene.hand_timestamp_ns:scene.capture_sequence=face['capture_sequence']
            scene.eye_metrics=tuple(min(65535,max(0,round(face[k]))) for k in ('eye_left','eye_right'))
        interaction=hand_packet.get('interaction_ui',{}) if hand_ok else {}
        selected=None
        if (r and interaction.get('valid') is True and interaction.get('source_instance')==r['hand_source_instance'] and
                interaction.get('timestamp_ns')==hand_packet.get('timestamp_ns') and
                interaction.get('capture_sequence')==hand_packet.get('capture_sequence')):
            choice=self.trajectory_hands.get(c.display_slot)
            key=choice[1] if choice and choice[0]==r['registration_generation'] else None
            candidates=[h for h in interaction.get('hands',[]) if h.get('track_id') in current and h.get('track_id') in {b['track_id'] for b in r['hands']}]
            if key is None and candidates:
                # Select the active stroke; deterministic idle preference only within this bound person's hands.
                priority={'REC':5,'COUNTDOWN':4,'ARMED':3,'RESULT':2,'IDLE':0}
                right={b['track_id'] for b in r['hands'] if b['side']=='Right'}
                key=max(candidates,key=lambda h:(priority.get(h['state'],0),h['track_id'] in right,-h['track_id']))['track_id']
            selected=next((h for h in interaction.get('hands',[]) if h.get('track_id')==key and key in current),None)
        # HFT2 group 4 is a trajectory view. Switch the displayed view during
        # the actual stroke, without changing the owner's action policy mode.
        display_mode=1 if selected and selected['state'] in ('ARMED','COUNTDOWN','REC','RESULT') else acknowledged_mode
        semantic=c.metadata(now_ns=now_ns,acknowledged_mode=display_mode,selected_hand=selected,
            hand_fresh=selected is not None,gaze=gaze)
        if not gaze or tuple(gaze.get(k) for k in ('owner_generation','capture_session'))!=c.context:
            semantic['status']&=~((1<<13)|(1<<14)|(1<<15))
        # Native/RTL require a qualified TRACK bit. Original application phase
        # alone is insufficient when a different track invalidates calibration.
        if not semantic['status']&(1<<13):semantic['status']&=~((1<<14)|(1<<15))
        projected=projection_sample(gaze,r,c.context,now_ns)
        if projected is not None and scene.valid&4:
            (x,y),(w,h)=projected
            px=420+64*x/max(1,w-1);py=82+52*y/max(1,h-1)
            add_flat(scene,3,[(390,106),(px,py),(max(420,px-2),py),(min(484,px+2),py)],
                [(0,1,2),(2,3,3),(1,1,3)],age(gaze['timestamp_ns'],now_ns))
            # Face and filtered samples may arrive on different frames. The
            # shared group source must never claim a newer time than either.
            scene.face_timestamp_ns=min(scene.face_timestamp_ns,gaze['timestamp_ns'])
            scene.ages[2]=max(scene.ages[2],age(scene.face_timestamp_ns,now_ns))
            scene.ages[3]=max(scene.ages[3],age(scene.face_timestamp_ns,now_ns))
        else:semantic['status']&=~(1<<15)
        trace_reason='no_registered_selected_hand'
        if selected is not None and selected.get('points'):
            stamp=hand_packet['timestamp_ns'];ttl=POSE_TTL_NS
            if selected['state']=='RESULT':
                stamp=selected.get('result_started_ns')
                ttl=RESULT_TTL_NS
            if type(stamp) is int and 0<=now_ns-stamp<=ttl:
                width,height=interaction['source_size'];points=selected['points']
                if (type(width) is not int or type(height) is not int or min(width,height)<=0 or len(points)>48 or
                        any(len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) or
                            not 0<=p[0]<=width or not 0<=p[1]<=height for p in points)):
                    raise ValueError('real trajectory canvas')
                xy=[(318+168*p[0]/width,166+54*p[1]/height) for p in points]
                add_flat(scene,4,xy,[(i,i+1,2) for i in range(len(xy)-1)],
                    max(age(stamp,now_ns),age(hand_packet['timestamp_ns'],now_ns)))
                trace_reason='actual_bounded_points'
            else:trace_reason='result_end_time_missing_or_expired'
        semantic['actual_saved_points']=sum(v[0]==4 for v in scene.vertices)
        meta=AppMetadata(semantic['actor_slot'],semantic['face_track_id'],semantic['status'],
            semantic['display_generation'],semantic['confidence'],semantic['actual_saved_points'],semantic['association_flags'])
        validate(scene,meta)
        if len(scene.vertices)>128 or len(scene.edges)>128 or len(scene.triangles)>64:raise ValueError('full scene capacity')
        self.last_diagnostic=dict(actor_slot=c.display_slot,registered=bool(r),hand_count=len(bound),
            valid_mask=scene.valid,vertices=len(scene.vertices),edges=len(scene.edges),triangles=len(scene.triangles),
            projected=bool(scene.valid&8),trace_reason=trace_reason,mode=acknowledged_mode)
        return AppFrame(scene,meta)
