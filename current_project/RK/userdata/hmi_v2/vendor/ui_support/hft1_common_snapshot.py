"""HFT1: measured XYZ scenes for FPGA, independent of PCIe/UART transport.

The FPGA performs the oblique 3D projection. Host scaling only fits a panel.
Frame age is measured at serialization; FPGA adds receive/render residence.
"""
import math,struct,zlib
from dataclasses import dataclass,field

MAGIC=b'HFT1';HEADER_BYTES=96;MAX_VERTICES=128;MAX_EDGES=128;MAX_TRIANGLES=64
BOXES=((28,90,146,203),(162,90,280,203),(326,90,484,199),(36,244,220,271),(292,244,476,271))
HAND_EDGES=((0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),(5,9),(9,10),(10,11),(11,12),
            (9,13),(13,14),(14,15),(15,16),(13,17),(0,17),(17,18),(18,19),(19,20))
FACE_OVAL=(10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,
           148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109)
LEFT_EYE=(33,160,158,133,153,144)
RIGHT_EYE=(362,385,387,263,373,380)

def project_q4(point):
    """Exact signed fixed-point reference for hardware: yaw then pitch."""
    x,y,z=point
    xx=(230*x-111*z)>>8;zz=(111*x+230*z)>>8
    yy=(253*y-38*zz)>>8
    return xx>>4,yy>>4,zz

@dataclass
class Scene:
    vertices:list=field(default_factory=list)  # group, signed X/Y/Z in pixel Q4
    edges:list=field(default_factory=list)     # a,b,shade
    triangles:list=field(default_factory=list)# a,b,c,shade
    valid:int=0
    ages:list=field(default_factory=lambda:[65535]*5)
    offsets:list=field(default_factory=lambda:[(0,0)]*5)
    hand_timestamp_ns:int=0
    face_timestamp_ns:int=0
    capture_sequence:int=0xffffffff
    eye_metrics:tuple=(0,0)
    fixture:bool=False

def add_group(scene,group,points,edges,triangles=(),iris=None,age_ms=0):
    if not 0<=group<5 or not points or len(points)>MAX_VERTICES:raise ValueError('Group geometry')
    if any(len(p)!=3 or any(not math.isfinite(float(x)) or abs(x)>100_000 for x in p) for p in points):raise ValueError('XYZ')
    projected=[(.8984375*x-.43359375*z,.98828125*y-.1484375*(.43359375*x+.8984375*z)) for x,y,z in points]
    left,top,right,bottom=BOXES[group]
    dx=max(p[0] for p in projected)-min(p[0] for p in projected)
    dy=max(p[1] for p in projected)-min(p[1] for p in projected)
    if max(dx,dy)<1e-8:raise ValueError('Degenerate geometry')
    scale=min((right-left-6)/max(dx,1e-8),(bottom-top-6)/max(dy,1e-8))
    quantized=[tuple(round(float(x)*scale*16) for x in p) for p in points]
    if any(not -32768<=x<=32767 for p in quantized for x in p):raise ValueError('Q4 overflow')
    qp=[project_q4(p) for p in quantized]
    offset=((left+right-min(p[0] for p in qp)-max(p[0] for p in qp))//2,
            (top+bottom-min(p[1] for p in qp)-max(p[1] for p in qp))//2)
    if any(not left+2<=p[0]+offset[0]<=right-2 or not top+2<=p[1]+offset[1]<=bottom-2 for p in qp):raise ValueError('Panel fit')
    first=len(scene.vertices)
    scene.vertices += [(group,*p) for p in quantized]
    scene.edges += [(first+a,first+b,1) for a,b in edges]
    scene.triangles += [(first+a,first+b,first+c,0) for a,b,c in triangles]
    if iris is not None:scene.edges.append((first+iris,first+iris,3))
    scene.valid|=1<<group;scene.offsets[group]=offset;scene.ages[group]=min(65535,int(age_ms))

def panel_hands(items):
    """Reject ambiguous reduction to a two-hand panel; this is not identity.

    Two distinct sides can be shown in a single-operator view. They still do
    not prove that the hands belong to the selected face. Three/four hands or
    repeated sides must clear the hand panels instead of picking winners.
    """
    sides=[item['side'] for item in items]
    if len(items)>2 or len(sides)!=len(set(sides)):return ()
    return items


def head_direction_arrow(points):
    """Geometric cue from existing dense XYZ, not calibrated/PnP head pose.

    Cheek width and forehead-to-chin define an oriented local plane. If that
    plane is unusable, omit only the arrow; do not invent a default direction
    or discard otherwise valid head/eye landmarks.
    """
    right=tuple(points[454][i]-points[234][i] for i in range(3))
    down=tuple(points[152][i]-points[10][i] for i in range(3))
    width=math.sqrt(sum(x*x for x in right));height=math.sqrt(sum(x*x for x in down))
    if not math.isfinite(width+height) or min(width,height)<1e-8:return None
    right=tuple(x/width for x in right);down=tuple(x/height for x in down)
    normal=(down[1]*right[2]-down[2]*right[1],down[2]*right[0]-down[0]*right[2],down[0]*right[1]-down[1]*right[0])
    norm=math.sqrt(sum(x*x for x in normal))
    if not math.isfinite(norm) or norm<1e-3:return None
    normal=tuple(x/norm for x in normal);length=.38*min(width,height)
    tip=tuple(points[1][i]+length*normal[i] for i in range(3))
    return (tip,*(tuple(tip[i]-length*.28*normal[i]+sign*length*.18*right[i] for i in range(3)) for sign in (-1,1)))


def scene_from_features(state,now_ns):
    scene=Scene();hand=state.fresh('hand',now_ns);face=state.fresh('face',now_ns)
    if hand:
        scene.fixture|=bool(hand.get('fixture',False));scene.hand_timestamp_ns=hand['timestamp_ns']
        capture=hand.get('capture_sequence')
        scene.capture_sequence=0xffffffff if capture is None else int(capture)&0xffffffff
        for item in panel_hands(hand['hands']):
            group={'Left':0,'Right':1}.get(item['side'])
            if group is None or item['confidence']<.6:continue
            origin=item['world'][0];points=[tuple(p[i]-origin[i] for i in range(3)) for p in item['world']]
            add_group(scene,group,points,HAND_EDGES,((0,5,9),(0,9,13),(0,13,17)),age_ms=math.ceil((now_ns-hand['timestamp_ns'])/1e6))
    if face and face['valid']:
        scene.fixture|=bool(face.get('fixture',False));scene.face_timestamp_ns=face['timestamp_ns']
        capture=face.get('capture_sequence')
        if capture is not None and (not hand or face['timestamp_ns']>=hand['timestamp_ns']):
            scene.capture_sequence=int(capture)&0xffffffff
        groups=face.get('groups',{})
        w,h=face['size'];raw=face['landmarks'];origin=raw[1]
        # Current face export has image x/w, y/h, and relative z/w.
        # Restore isotropic pixel axes before projecting the real XYZ.
        points=[(p[0]-origin[0],(p[1]-origin[1])*h/w,p[2]-origin[2]) for p in raw]
        chains=[FACE_OVAL,(1,4,6,168,10),(61,13,291,14)]
        closed_chains=[FACE_OVAL,chains[2]]
        if groups.get('left_eye',True):chains.append(LEFT_EYE);closed_chains.append(LEFT_EYE)
        if groups.get('right_eye',True):chains.append(RIGHT_EYE);closed_chains.append(RIGHT_EYE)
        extra={1}
        if len(points)==478:
            if groups.get('left_iris',True):extra.add(468)
            if groups.get('right_iris',True):extra.add(473)
        indices=sorted(set(i for chain in chains for i in chain)|extra)
        lookup={value:i for i,value in enumerate(indices)};edges=[]
        for chain in chains:
            edges.extend((lookup[a],lookup[b]) for a,b in zip(chain,chain[1:]))
        edges += [(lookup[chain[-1]],lookup[chain[0]]) for chain in closed_chains]
        triangles=[(lookup[1],lookup[a],lookup[b]) for a,b in zip(FACE_OVAL,FACE_OVAL[1:]+FACE_OVAL[:1])]
        age=math.ceil((now_ns-face['timestamp_ns'])/1e6)
        head_points=[points[i] for i in indices];arrow=head_direction_arrow(points)
        if arrow is not None:
            first=len(head_points);head_points.extend(arrow)
            edges.extend(((lookup[1],first),(first,first+1),(first,first+2)))
        add_group(scene,2,head_points,edges,triangles,age_ms=age)
        if arrow is not None:
            scene.edges[-3:]=[(a,b,2) for a,b,_ in scene.edges[-3:]]
        for group,chain,iris in ((3,LEFT_EYE,468),(4,RIGHT_EYE,473)):
            side='left' if group==3 else 'right'
            if not groups.get(side+'_eye',True):continue
            eye=list(chain)+([iris] if len(points)==478 and groups.get(side+'_iris',True) else []);origin_eye=points[chain[0]]
            local=[tuple(points[i][a]-origin_eye[a] for a in range(3)) for i in eye]
            add_group(scene,group,local,[(i,(i+1)%len(chain)) for i in range(len(chain))],
                      iris=6 if len(eye)==7 else None,age_ms=age)
        scene.eye_metrics=tuple(min(65535,max(0,round(face[k]))) for k in ('eye_left','eye_right'))
    return scene

def encode(scene,epoch,sequence,previous_epoch=0):
    vc,ec,tc=map(len,(scene.vertices,scene.edges,scene.triangles))
    if not 0<epoch<2**64 or not 0<=sequence<2**64 or not 0<=previous_epoch<2**64:raise ValueError('Epoch/sequence')
    if not 0<=vc<=128 or not 0<=ec<=128 or not 0<=tc<=64 or not 0<=scene.valid<32:raise ValueError('Scene capacity')
    header=bytearray(HEADER_BYTES);payload=bytearray()
    for group,x,y,z in scene.vertices:payload+=struct.pack('<BBhhh',group,0,x,y,z)
    for a,b,shade in scene.edges:payload+=struct.pack('<BBBB',a,b,shade,0)
    for a,b,c,shade in scene.triangles:payload+=struct.pack('<BBBB',a,b,c,shade)
    flags=int(scene.fixture)|(2 if previous_epoch else 0)
    struct.pack_into('<4s8BH',header,0,MAGIC,1,flags,96,vc,ec,tc,scene.valid,0,len(payload))
    struct.pack_into('<5HQQQQI',header,14,*scene.ages,epoch,sequence,scene.hand_timestamp_ns,scene.face_timestamp_ns,scene.capture_sequence)
    struct.pack_into('<10h2HQI',header,60,*(v for pair in scene.offsets for v in pair),*scene.eye_metrics,previous_epoch,0)
    frame=bytes(header+payload);return frame+struct.pack('<I',zlib.crc32(frame))

def decode(frame):
    if len(frame)<100 or frame[:4]!=MAGIC or frame[4]!=1 or frame[5]&~3 or frame[6]!=96 or frame[11] or any(frame[92:96]):raise ValueError('Header')
    vc,ec,tc,valid=frame[7:11];length=struct.unpack_from('<H',frame,12)[0]
    if vc>128 or ec>128 or tc>64 or valid&~31 or length!=vc*8+ec*4+tc*4 or len(frame)!=100+length:raise ValueError('Length/counts')
    if zlib.crc32(frame[:-4])!=struct.unpack_from('<I',frame,len(frame)-4)[0]:raise ValueError('CRC')
    epoch,sequence,hand_ns,face_ns,capture=struct.unpack_from('<QQQQI',frame,24)
    if not epoch:raise ValueError('Zero epoch')
    scene=Scene(valid=valid,ages=list(struct.unpack_from('<5H',frame,14)),fixture=bool(frame[5]&1),
        hand_timestamp_ns=hand_ns,face_timestamp_ns=face_ns,capture_sequence=capture,
        offsets=[struct.unpack_from('<hh',frame,60+i*4) for i in range(5)],eye_metrics=struct.unpack_from('<2H',frame,80))
    pos=96
    for _ in range(vc):
        group,res,x,y,z=struct.unpack_from('<BBhhh',frame,pos);pos+=8
        if group>4 or res:raise ValueError('Vertex')
        scene.vertices.append((group,x,y,z))
    for _ in range(ec):
        a,b,shade,res=struct.unpack_from('<4B',frame,pos);pos+=4
        if a>=vc or b>=vc or shade>3 or res or scene.vertices[a][0]!=scene.vertices[b][0]:raise ValueError('Edge')
        scene.edges.append((a,b,shade))
    for _ in range(tc):
        a,b,c,shade=struct.unpack_from('<4B',frame,pos);pos+=4
        if max(a,b,c)>=vc or shade>3 or len({scene.vertices[i][0] for i in (a,b,c)})!=1:raise ValueError('Triangle')
        scene.triangles.append((a,b,c,shade))
    return dict(scene=scene,epoch=epoch,sequence=sequence,previous_epoch=struct.unpack_from('<Q',frame,84)[0],rebind=bool(frame[5]&2))
