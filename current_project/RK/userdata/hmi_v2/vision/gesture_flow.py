"""Entry adapter for the preserved trajectory raster/classifier and state machine."""
from types import SimpleNamespace


def enabled(state):
    return (not state.get('estop') and not state.get('health',{}).get('broken')
            and not state.get('calibration_intent') and not state.get('shortcut')
            and not state.get('zoom_control',{}).get('active')
            and state.get('state','STANDBY') in ('STANDBY','PRESENT','ONBOARD','IDLE','WRITING'))


class GestureTrajectory:
    def __init__(self,gesture_config=None):
        # Import after the vendor resolver has pinned the frozen modules.
        from demo_trajectory import TrajectoryRecorder, observations
        config=gesture_config or {}
        class DemonstrationRecorder(TrajectoryRecorder):
            countdown_s=float(config.get('trajectory_countdown_s',.3))
            cooldown_s=float(config.get('trajectory_cooldown_s',.3))
            def tick(self, now):
                if self.state=='RESULT' and now-self.since>=self.cooldown_s:self.cancel('cooldown_complete',now)
                else:super().tick(now)
            def update(self, hands, sequence, source_time, now, width=640, height=360):
                new_sample=(self.last_stamp is None or source_time>self.last_stamp) and sequence!=self.last_sequence
                if (self.state=='ARMED' and new_sample and 0<=now-source_time<=.35
                        and len(hands)==1 and hands[0].get('label')=='Closed_Fist'
                        and hands[0].get('score',0)>=.5):
                    self.since=now
                image=super().update(hands,sequence,source_time,now,width,height)
                if self.state=='COUNTDOWN' and new_sample:
                    self.reason='hold_point_for_countdown'
                    if now-self.since>=self.countdown_s:
                        self.state,self.since,self.count='REC',now,0
                        self.reason='recording_close_fist_to_finish'
                return image
        self.factory=DemonstrationRecorder;self.observations=observations
        self.recorders={};self.session=None;self.palm_block={};self.gesture_config=gesture_config or {}
        self.used_confirmation=None

    def tick(self,now):
        for recorder in self.recorders.values():recorder.tick(now)

    def update(self,result,sequence,source_time,now,width,height,state):
        session=(state.get('epoch'),state.get('people'),state.get('participants',{}).get('active',1),state.get('gesture_generation',0))
        if session!=self.session or not enabled(state):self.recorders={};self.palm_block={};self.session=session
        if not enabled(state):return []
        ids=result.track_ids
        if len(ids)>4 or len(ids)!=len(set(ids)) or len(ids)!=len(result.hand_landmarks):raise ValueError('Invalid hand tracks')
        allowed=state.get('active_hand_ids',ids)
        reserved_ids=set(state.get('reserved_hand_ids',[]))
        pointing=[result.handedness[i][0].category_name for i,key in enumerate(ids) if key in allowed and result.handedness[i] and result.gestures[i] and result.gestures[i][0].category_name=='Pointing_Up' and result.gestures[i][0].score>=.5]
        if state.get('context')=='DEMO' and (sorted(pointing)==['Left','Right'] or state.get('zoom_control',{}).get('preparing')):
            # Pause ambiguous bilateral samples. The engine changes generation
            # after three frames; only that confirmed takeover discards a stroke.
            return []
        ids_present={key for i,key in enumerate(ids) if key in allowed and result.handedness[i] and result.handedness[i][0].category_name=='Right'}
        self.palm_block={k:v for k,v in self.palm_block.items() if k in ids_present}
        self.recorders={k:v for k,v in self.recorders.items() if k in ids_present};finished=[]
        for i,key in enumerate(ids):
            if key not in ids_present:continue
            sample=SimpleNamespace(hand_landmarks=[result.hand_landmarks[i]],gestures=[result.gestures[i]],handedness=[result.handedness[i]])
            obs=self.observations(sample)
            if key not in self.recorders:
                recorder=self.factory();recorder.released=True
                self.recorders[key]=recorder
            recorder=self.recorders[key]
            if not obs:recorder.cancel('hand_outside_frame',now);continue
            pose=obs[0]['label'];score=obs[0]['score']
            arm=state.get('confirmed_fist') or {};identity=(arm.get('epoch'),arm.get('src_ns'))
            if (pose=='Pointing_Up' and score>=.5 and recorder.state in ('IDLE','RESULT')
                    and identity!=self.used_confirmation and arm.get('track_id')==key
                    and arm.get('epoch')==state.get('epoch') and arm.get('context')==state.get('context')
                    and arm.get('generation')==state.get('gesture_generation',0)
                    and 0<=source_time-arm.get('src_ns',0)/1e9<=4.):
                recorder.cancel('confirmed_fist_continue',now)
                recorder.state='ARMED';recorder.released=True;recorder.last_seen=source_time
                self.used_confirmation=identity;self.palm_block.pop(key,None)
            # Local arbitration prevents a repeat fist from arming a trajectory
            # before the next engine-state publication arrives.
            if score>=.45 and pose=='Open_Palm' and recorder.state not in ('COUNTDOWN','REC'):
                self.palm_block[key]=True;recorder.cancel('palm_shortcut',now)
            elif (score>=.5 and pose=='Closed_Fist' and self.palm_block.get(key)!='cancel'
                  and state.get('target_session',{}).get('phase')=='LOCKED'):
                # Arming is not an action. This fist may click/repeat now, then
                # prepare a later pointing pose without another release cycle.
                self.palm_block.pop(key,None);recorder.released=True
            elif pose not in ('Closed_Fist','Thumb_Down','Open_Palm',None,'None') and score>=.5:
                self.palm_block.pop(key,None)
            if score>=.5 and pose=='Thumb_Down' and recorder.state in ('ARMED','COUNTDOWN','REC'):
                recorder.cancel('thumb_down_cancel',now);self.palm_block[key]='cancel';continue
            if self.palm_block.get(key) and recorder.state not in ('COUNTDOWN','REC'):continue
            if key in reserved_ids and pose!='Closed_Fist' and recorder.state not in ('COUNTDOWN','REC','RESULT'):continue
            # A deliberate non-point gesture chooses the static branch and
            # cannot later turn into a stroke without another fist.
            threshold=self.gesture_config.get('confidence_by_gesture',{}).get(obs[0]['label'],self.gesture_config.get('confidence',.7))
            if recorder.state=='ARMED' and obs[0]['score']>=threshold and obs[0]['label'] not in (None,'None','Closed_Fist','Pointing_Up'):
                recorder.cancel('static_gesture_branch',now);continue
            image=recorder.update(obs,sequence,source_time,now,width,height)
            if image is not None:finished.append((key,image))
        return finished
