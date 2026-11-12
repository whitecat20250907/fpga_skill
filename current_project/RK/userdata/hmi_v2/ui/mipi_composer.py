"""Bounded, source-timed HFT2 scenes and transaction-matched UI registers."""
import sys,time,math,json
from pathlib import Path
_GLYPHS=json.loads(Path(__file__).with_name("mipi_glyph_codes.json").read_text("utf8"))
from core.config import ROOT,load
from core.clock import fresh
from core.hmibus import Publisher,Subscriber
from core.service import Service
from ui.face_geometry import relative_pixels
from ui.head_topology import face_surface
from ui.trace_display import TraceDisplay
from ui.input_viewer import control_word

sys.path.insert(0,str(ROOT/'vendor/ui_support'))
from hft2_wire import Scene,AppMetadata,encode,BOXES
from app_scene import add_xyz,add_flat

STATES={'BOOT':0,'STANDBY':0,'PRESENT':1,'ONBOARD':2,'CALIBRATING':3,'IDLE':4,'POINTING':5,'MENU':6,'WRITING':7,'DEGRADED':8}
GESTURES=['None','Pointing_Up','Closed_Fist','Thumb_Down','Victory','Thumb_Up','Open_Palm','ILoveYou']
EDGES=[(a,b,3) for a,b in [(0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),(5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),(13,17),(17,18),(18,19),(19,20),(0,17)]]

def byte(value):return max(0,min(255,int(value)))
def bcd(value,percent=False):
    if not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:return None
    value=min(9999,round(value*(100 if percent else 1)))
    return sum(int(c)<<(4*i) for i,c in enumerate(reversed(str(value))))
def registers(state,generation,profile='legacy'):
    regs={str(x):0 for x in range(0xc80,0xcfc,4)};context={'DESKTOP':0,'GAME':1,'DEMO':2,'BASIC':0}.get(state.get('context'),2)
    regs[str(0xc80)]=STATES.get(state.get('state'),8)|(context<<4)|(int(state.get('layer')=='WRITE')<<6)|(int(bool(state.get('calibrated')))<<8)
    g=state.get('gesture',{});name=g.get('name','None')
    regs[str(0xc84)]=(GESTURES.index(name) if name in GESTURES else 0)|(byte(g.get('progress',0)*255)<<4)
    cursor=state.get('cursor',{});xy=cursor.get('xy');size=cursor.get('screen_size')
    if xy and size and all(v>0 for v in size):
        x=max(0,min(447,round(xy[0]/size[0]*447)));y=max(0,min(251,round(xy[1]/size[1]*251)))
        regs[str(0xc88)]=x|(y<<11)|(int(cursor.get('frozen',True))<<22)|(int(cursor.get('valid',False))<<23)
        phase=state.get('target_session',{}).get('phase')
        if phase=='LOCKED' and cursor.get('valid') and cursor.get('locked'):
            # New legacy-layout renderer: a retained application target, not
            # a live gaze sample. Physical panel coordinates, no RTL division.
            px=840+round(max(0.,min(1.,xy[0]/size[0]))*128)
            py=164+round(max(0.,min(1.,xy[1]/size[1]))*104)
            regs[str(0xc8c)]=px|(py<<10)|(1<<21)
    menu=state.get('menu',{})
    items=menu.get('items',[]);index=max(0,min(8,int(menu.get('index',0))))
    regs[str(0xcb0)]=int(menu.get('open',False))|(index<<1)|(min(9,len(items))<<5)
    title=str(items[index]) if index<len(items) else ''
    title=title.replace(' ','').replace('/','').replace('／','')[:8]
    codes=[_GLYPHS.get(ch,63) for ch in title]+[32]*8
    regs[str(0xcb4)]=sum(codes[i]<<(i*8) for i in range(4))
    regs[str(0xcb8)]=sum(codes[i+4]<<(i*8) for i in range(4))
    writing=state.get('writing',{});stroke=state.get('stroke',{})
    phase={'IDLE':0,'ARMED':1,'COUNTDOWN':2,'REC':3,'RESULT':4}.get(writing.get('state'),0)
    label=stroke.get('label');classes=['0','L','L_rev','L_up','L_rev_up','M','W','Z']
    regs[str(0xcc8)]=(classes.index(label) if label in classes else 0)|(int(stroke.get('accepted',False))<<4)|(phase<<8)
    calib=state.get('calib',{});regs[str(0xcbc)]=(min(31,calib.get('point_i',0)))|(min(31,calib.get('total',13))<<5)|(byte(calib.get('samples',0))<<10)
    total=max(1,int(calib.get('total',13)));progress=max(0.,min(1.,calib.get('point_i',0)/total))
    regs[str(0xcbc)]|=byte(progress*255)<<18
    # BCD is prepared once per UI update, rather than decimal division per pixel.
    report=calib.get('evaluation') or {};metrics=report.get('filtered') or {}
    values=[bcd(metrics.get('mean_frame_error_px')),bcd(metrics.get('p90_frame_error_px')),
            bcd(metrics.get('grid_8x8_hit_rate'),True),bcd(metrics.get('grid_8x8_hit_rate_dwell'),True),
            bcd(report.get('valid_rate'),True),bcd(report.get('completed_points'))]
    phase={'CALIBRATE':1,'VALIDATE':2,'READY':3,'RESULT':4}.get(calib.get('phase'),0) if state.get('state')=='CALIBRATING' else 0
    regs[str(0xce0)]=phase|sum((v is not None)<<(8+i) for i,v in enumerate(values))
    regs[str(0xce4)]=(values[0] or 0)|((values[1] or 0)<<16)
    regs[str(0xce8)]=(values[2] or 0)|((values[3] or 0)<<16)
    regs[str(0xcec)]=(values[4] or 0)|(((values[5] or 0)&255)<<16)|(((bcd(report.get('expected_points')) or 0)&255)<<24)
    check=state.get('onboard',{});regs[str(0xcd0)]=sum(int(bool(check.get(k)))<<i for i,k in enumerate(('distance','centered','eyes')))
    regs[str(0xcd4)]=state.get('participants',{}).get('active',1)|(int(state.get('people')=='dual')<<4)
    regs[str(0xcf8)]=generation & 0xffffffff
    probabilities=state.get('stroke',{}).get('probabilities',[])
    for offset in range(2):
        regs[str(0xcc0+offset*4)]=sum(byte(probabilities[i]*255)<<(8*(i%4)) for i in range(offset*4,min(offset*4+4,len(probabilities))))
    stage_services=['gaze']*6+['hand']*5+['adapters']
    broken=state.get('health',{}).get('broken',[])
    for i,producer in enumerate(stage_services):
        # Healthy indicates service heartbeat, not inferred per-layer timings.
        value=(1<<11) if producer in broken else (1<<10)
        address=str(0xc94+(i//2)*4);regs[address]|=value<<((i%2)*12)
    return regs

def compose(state,face,hands,now,generation,profile="legacy",slotter=None,trace_display=None,heatmap=None,gaze=None):
    if profile=="theater":
        from ui.theater_geometry import add_xyz,add_flat,BOXES
    else:
        from app_scene import add_xyz,add_flat,BOXES
    scene=Scene();meta=AppMetadata(display_generation=generation);active_hands=[]
    meta.actor_slot=state.get('participants',{}).get('active',1)
    # Algorithm geometry is useful before calibration. Calibration qualifies
    # gaze projection/control, not observation of a fresh, selected person.
    # In dual mode the selected track must still be explicitly registered.
    primary=next((f for f in (face or {}).get('faces',[]) if f.get('primary') and f.get('valid')),None)
    visible=bool(primary and face.get('epoch')==state.get('epoch') and fresh(face.get('src_ns'),350,now))
    if visible and state.get('people')=='dual':
        slot=state.get('participants',{}).get('slots',{}).get(str(meta.actor_slot),{})
        visible=slot.get('track_id')==primary['track_id']
    qualified=bool(visible and state.get('calibrated'))
    if visible:
        meta.actor_track_id=int(primary['track_id']);meta.association_flags=1
        meta.ui_status=15<<8
        if qualified:meta.ui_status|=1<<13
        if qualified and state.get('state') in ('IDLE','POINTING'):meta.ui_status|=1<<14
        scene.face_timestamp_ns=face['src_ns'];scene.capture_sequence=face['seq']
        points=primary.get('landmarks',[])
        if len(points)>=3:
            if len(points)>=468:
                points,edges,triangles=face_surface(points)
            else:
                points=points[:32];edges=[(i,i+1,2) for i in range(len(points)-1)];triangles=[]
            try:add_xyz(scene,2,relative_pixels(points),edges,triangles,(now-face['src_ns'])//1_000_000)
            except ValueError:pass
    if (state.get('people','single')=='single' or visible) and hands and fresh(hands.get('src_ns'),350,now) and hands.get('epoch')==state.get('epoch'):
        if not visible:
            meta.actor_track_id=0xfffffffe  # Reserved single-user display owner.
            meta.association_flags=1
            scene.capture_sequence=hands.get('seq',0)
        from core.interaction.people import People
        people=People();people.mode=state.get('people','single');people.active=state.get('participants',{}).get('active',1)
        people.slots={int(k):v['track_id'] for k,v in state.get('participants',{}).get('slots',{'1':{'track_id':meta.actor_track_id},'2':{'track_id':None}}).items()}
        people.faces=[f for f in (face or {}).get('faces',[]) if f.get('valid')] if visible else []
        allowed=state.get('active_hand_ids')
        active_hands=([h for h in hands.get('hands',[]) if h.get('track_id') in allowed] if allowed is not None else people.hands_for_active(hands.get('hands',[])))
        from ui.hand_slots import hand_slots
        slots=(slotter.select(active_hands,now,(state.get('epoch'),state.get('people'),meta.actor_slot,meta.actor_track_id if state.get('people')=='dual' else None))
               if slotter is not None else hand_slots(active_hands))
        for group,hand in slots:
            points=hand.get('world21',[])
            if len(points)!=21:continue
            try:add_xyz(scene,group,points,EDGES,[(0,5,9,1),(0,9,13,1),(0,13,17,1),(0,1,5,1)],min(65535,(now-hands['src_ns'])//1_000_000))
            except ValueError:continue
            meta.association_flags|=2<<group
        scene.hand_timestamp_ns=hands['src_ns']
    trace=(trace_display or TraceDisplay()).select(state,hands,active_hands,now)
    trace_ns=0
    if trace and meta.association_flags&6:
        points=trace['points'];l,t,rr,b=BOXES[4];scale=min((rr-l)/640,(b-t)/360)
        xy=[[(l+rr)/2+(p[0]-320)*scale,(t+b)/2+(p[1]-180)*scale] for p in points]
        trace_ns=trace['src_ns']
        add_flat(scene,4,xy,[(i,i+1,min(3,i*4//max(1,len(xy)-1))) for i in range(len(xy)-1)],(now-trace_ns+999_999)//1_000_000)
        meta.trajectory_points=len(xy)
    cursor=state.get('cursor',{})
    if qualified and cursor.get('valid') and not cursor.get('locked') and fresh(cursor.get('src_ns'),250,now) and cursor.get('xy'):
        x,y=cursor['xy'];w,h=cursor['screen_size']
        # Match the renderer's actual screen inset, rather than mapping the
        # point across the eye icon and the entire group viewport.
        if profile=='theater':
            l,t,r,b=324,50,459,140;origin=(324,95)
        else:l,t,r,b=420,82,484,134;origin=(390,106)
        px=l+max(0.,min(1.,x/w))*(r-l);py=t+max(0.,min(1.,y/h))*(b-t)
        xy=[origin,(px,py),(max(l,px-2),py),(min(r,px+2),py)]
        add_flat(scene,3,xy,[(0,1,2),(2,3,3),(1,1,3)],(now-cursor['src_ns'])//1_000_000)
        # Face and gaze can be from different frames; retain the older source
        # time for this shared face/projection source group.
        scene.face_timestamp_ns=min(scene.face_timestamp_ns,cursor['src_ns'])
        scene.ages[2]=max(scene.ages[2],(now-scene.face_timestamp_ns)//1_000_000)
        scene.ages[3]=max(scene.ages[3],(now-scene.face_timestamp_ns)//1_000_000)
        meta.ui_status|=(1<<13)|(1<<14)|(1<<15)
    # Yesterday's renderer consumes HFT2 metadata, not the new UI11 CSR.
    # Populate the same real draw/static/result fields as the original relay.
    from interaction_ui import STATIC_CODES,STATE_CODES,CLASSES
    writing=state.get('writing',{});stroke=trace['result'] if trace else {}
    phase=writing.get('state','IDLE');draw=STATE_CODES.get(phase,0)
    if trace:phase=trace['phase'];draw=STATE_CODES.get(phase,0)
    elif phase=='RESULT':phase='IDLE';draw=0
    # Observation and action qualification are separate. A held gesture must
    # stay visible after its one-shot action has been consumed by the engine.
    candidates=[h for h in active_hands if h.get('score',0)>=.5 and h.get('gesture') in STATIC_CODES]
    selected=max(candidates,key=lambda h:(h['track_id']==state.get('gesture',{}).get('hand'),h.get('side')=='Right',h.get('score',0)),default={})
    gesture=selected.get('gesture',state.get('gesture',{}).get('name'))
    static=STATIC_CODES.get(gesture,0)
    meta.ui_status=(meta.ui_status & (7<<13)) | (15<<8) | (static<<4) | draw
    if phase in ('COUNTDOWN','REC','RESULT') or scene.valid&16:meta.ui_status|=1<<16
    if phase=='RESULT' and stroke.get('accepted') and stroke.get('label') in CLASSES:
        meta.ui_status=(meta.ui_status & ~(15<<8)) | (CLASSES.index(stroke['label'])<<8) | (1<<12)
        meta.classification_confidence=byte(stroke['confidence']*255)
    if len(scene.vertices)>128 or len(scene.edges)>128:raise ValueError('HFT2 geometry budget exceeded')
    # CSR and geometry are one display transaction. The engine intentionally
    # retains its last action, but that is not a fresh trajectory result.
    display_state=dict(state,stroke=stroke,writing=dict(writing,state=phase))
    csr=registers(display_state,generation,profile)
    if heatmap is not None and profile=='legacy':
        csr[str(0xccc)],csr[str(0xcdc)]=heatmap.select(state,face,gaze,now)
    return encode(scene,meta,state['epoch'],generation,trace_timestamp_ns=trace_ns),csr

def main():
    c=load();run=c['paths']['run'];svc=Service('ui',c);sub=Subscriber(['hmi.state','vision.face','vision.hands','vision.stroke','vision.gaze'],run=run);pub=Publisher('ui.scene',run=run);generation=0
    from ui.heatmap_samples import HeatmapSamples
    heatmap=HeatmapSamples()
    from ui.hand_slots import DisplayHandSlots
    slotter=DisplayHandSlots();trace_display=TraceDisplay()
    try:
        while svc.running:
            started=time.monotonic()
            sub.poll(10);now=time.monotonic_ns();state=sub.latest('hmi.state')
            if not state:continue
            if not fresh(state['src_ns'],350,now):state=dict(state,state='DEGRADED',calibrated=False,cursor={},gesture={})
            generation=(generation+1)&0xffffffff
            sub.events('vision.stroke')  # Only engine-approved, active-person strokes are displayed.
            packet,csr=compose(state,sub.latest('vision.face'),sub.latest('vision.hands'),now,generation,c['mipi'].get('profile','legacy'),slotter,trace_display,heatmap,sub.latest('vision.gaze'))
            csr[str(0xcd8)]=control_word(state,c['mipi'].get('input_viewer','off'),now) if c['mipi'].get('profile','legacy')=='legacy' else 0
            svc.measurements.observe(time.monotonic_ns(),compose=(time.monotonic_ns()-now)/1e6)
            pub.publish(dict(src_ns=now,seq=generation,epoch=state['epoch'],hft2=packet,csr=csr))
            svc.heartbeat(state['epoch']);time.sleep(max(0,1/c['mipi']['scene_hz']-(time.monotonic()-started)))
    finally:pub.close();sub.close();svc.close()

if __name__=='__main__':main()

