"""Edge-triggered action selection from the existing, bound hand telemetry."""
import math

TRAJECTORIES=('0','L','L_rev','L_up','L_rev_up','M','W','Z')
STATIC=('Open_Palm','Victory','Thumb_Up','Thumb_Down')
ACTIONS=('none','gaze_calibrate','gaze_recalibrate','gaze_validate','gaze_pointer','gaze_dwell','gaze_restore',
         'page1','page2','register1','register2','single','dual','wake','confirm','cancel','next','end',
         'demo_open','demo_next','demo_previous','demo_zoom_in','demo_zoom_out','demo_focus','demo_snap','demo_reset')
DEFAULTS={**{'trajectory:'+k:'none' for k in TRAJECTORIES},**{'static:'+k:'none' for k in STATIC},
          'static:Open_Palm':'demo_open','static:Victory':'gaze_calibrate','static:Thumb_Up':'demo_next','static:Thumb_Down':'demo_previous',
          'trajectory:L':'demo_zoom_in','trajectory:L_rev':'demo_zoom_out','trajectory:M':'demo_focus',
          'trajectory:W':'demo_snap','trajectory:0':'demo_reset'}

def validate_bindings(value):
    if not isinstance(value,dict) or set(value)!=set(DEFAULTS) or any(v not in ACTIONS for v in value.values()):
        raise ValueError('Exactly the supported gestures and actions are required')
    return dict(value)

def action_context(health):
    r=next((r for r in health.get('registrations',[]) if r.get('slot')==health.get('actor_slot') and r.get('tracking_state')=='active'),{})
    return tuple(health.get(k) for k in ('boot_id','owner_generation','capture_session','actor_slot'))+(r.get('registration_generation'),r.get('face_source_instance'),r.get('face_track_id'))

class GestureActions:
    def __init__(self):
        self.context=None;self.last_sequence=None;self.holds={};self.seen=set();self.last_action=-10**18
    def update(self,health,now_ns,bindings):
        ui=health.get('interaction_ui') or {};stamp=ui.get('timestamp_ns')
        ctx=action_context(health)
        if ctx!=self.context:
            self.context=ctx;self.last_sequence=None;self.holds.clear();self.seen.clear();self.context_started=now_ns
        if (not ui.get('valid') or type(stamp) is not int or not 0<=now_ns-stamp<=350_000_000):
            self.holds.clear();return None
        seq=ui.get('capture_sequence')
        if seq==self.last_sequence:return None
        self.last_sequence=seq
        reg=next((r for r in health.get('registrations',[]) if r['slot']==health.get('actor_slot') and r.get('tracking_state')=='active'),None)
        if not reg or reg.get('hand_source_instance')!=ui.get('source_instance'):
            self.holds.clear();return None
        allowed={h['track_id'] for h in reg['hands']}
        hands=[h for h in ui['hands'] if h['track_id'] in allowed]
        self.holds={k:v for k,v in self.holds.items() if k in {h['track_id'] for h in hands}}
        events=[]
        for h in hands:
            key=h['track_id'];result=h.get('classification')
            if h['state']=='RESULT' and result and result.get('accepted'):
                event=(ui['source_instance'],key,result['event_sequence'])
                if event not in self.seen and h.get('result_started_ns',now_ns)>=self.context_started:
                    self.seen.add(event)
                    events.append(('trajectory:'+result['label'],key))
            if h['state']!='IDLE':
                self.holds.pop(key,None);continue
            label=h.get('static_gesture');score=h.get('static_confidence',0)
            if label not in STATIC or not isinstance(score,(int,float)) or not math.isfinite(score) or score<.75:
                self.holds.pop(key,None);continue
            hold=self.holds.get(key)
            if hold is None or hold[0]!=label:self.holds[key]=[label,stamp,False]
            elif not hold[2] and stamp-hold[1]>=700_000_000:
                hold[2]=True;events.append(('static:'+label,key))
        # A gesture is consumed once, even when rejected by cooldown/conflict.
        if len(self.seen)>128:self.seen=set(sorted(self.seen,key=lambda x:x[2])[-64:])
        chosen=[(g,k,bindings[g]) for g,k in events if bindings.get(g,'none')!='none']
        if len(chosen)!=1 or now_ns-self.last_action<2_000_000_000:return None
        self.last_action=now_ns
        gesture,hand,action=chosen[0]
        return dict(action=action,gesture=gesture,hand_track_id=hand,timestamp_ns=stamp,context=ctx)
