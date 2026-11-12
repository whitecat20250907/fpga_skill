"""Pure monotonic-time engine; no hardware, network, or OS input dependencies."""
from collections import deque
from copy import deepcopy
import uuid
from core.targets import select_target,center,same_target
from core.clock import fresh
from core.schema import finite_xy
from .fist_latch import FistLatch as Latch
from .stroke_confirm import StrokeConfirm
from .repeat_cycle import RepeatCycle
from .palm_command import PalmCommand
from .palm_shortcuts import PalmShortcuts
from .dual_zoom import DualZoom
from .model_demand import demand
from .target_vote import TargetVote
from core.action_requirements import independent_action,locked_action
from .people import People
from .calibration_entry import readiness as calibration_readiness
from core.bindings import defaults,validate as validate_bindings,label
from core.manual_demo import permitted as manual_demo
from core.manual_game import permitted as manual_game,validate as validate_game_input

STATES=('BOOT','STANDBY','PRESENT','ONBOARD','CALIBRATING','IDLE','POINTING','MENU','WRITING','DEGRADED')
MENU=('桌面眼控','游戏','医学演示','轨迹书写','标定当前使用者','单人 / 双人','第一人登记 / 标定','第二人登记 / 标定','待机')
BUDGET={'STANDBY':(0,15,10),'PRESENT':(0,15,10),'ONBOARD':(30,10,30),
        'CALIBRATING':(30,10,30),'IDLE':(30,30,30),'POINTING':(32,30,32),
        'WRITING':(10,40,10),'MENU':(10,30,10),'DEGRADED':(0,0,0),'BOOT':(0,0,0)}

class Engine:
    def __init__(self, config):
        self.config=config;self.state='BOOT';self.context=config['startup']['context'];self.layer='POINT'
        self.epoch=0;self.latest={};self.last_seq={};self.heartbeats={};self.required=set(config['health']['required'])
        self.gaze_ttl=config['freshness_ms']['gaze_action'];self.hand_ttl=config['freshness_ms']['hand']
        self.latch=Latch(config['gestures'],self.hand_ttl);self.calibrated=False;self.calib={};self.menu_index=0
        self.target_session={};self.target_catalog={};self.target_vote=TargetVote()
        self.face_since=0;self.no_face_since=0;self.last_hand=0;self.entered=0;self.invalid_since=0
        self.onboard_since=0;self.onboard={};self.onboard_track=None;self.cursor={'xy':None,'valid':False,'frozen':True}
        self.out=[];self.commands=[];self.history=deque(maxlen=20);self.pending={};self.action_seq=0
        self.action_namespace=uuid.uuid4().hex
        self.application_request=None;self.application_request_seq=0;self.control_receipts=deque(maxlen=16)
        self.people=People();self.writing={};self.stroke={};self.calibration_request=0
        self.bindings=validate_bindings(config.get('bindings',defaults(config)));self.shortcut=None
        self.stroke_confirm=StrokeConfirm(config['gestures']);self.repeat=RepeatCycle(config['gestures'])
        self.undo_palm=PalmCommand(config['gestures'],'Left','Thumb_Down');self.eye_palm=PalmCommand(config['gestures'],'Right','Closed_Fist')
        self.undo_stack=deque(maxlen=64);self.undo_scope=None;self.gesture_generation=0
        self.memories={};self.action_scopes={};self.last_action=None;self.consumed_right=False;self.stroke_owner=None;self.right_seen_ns=0
        self.palms={side:PalmShortcuts(config["gestures"],side) for side in ("Left","Right")}
        self.zoom=DualZoom()
        self.confirmed_fist={}
        self.calibration_intent=None
        self.tuning=config.get('interaction',{})
        self.face_demand_since=0;self.last_face_demand=False;self.warnings=[];self.input_hand=None;self.input_side=None
        self.calibration_stable_ns=int(self.tuning.get('calibration_stable_s',.2)*1e9)
        self.toast='';self.broken=[];self.confirmed_calibration=False;self.estop=False;self.now=0;self.command_seq=0;self.command_seen={};self.calibration_track=None;self.instances={};self.calibration_backup=None
    def feed(self, topic, msg, now):
        self.now=now
        if topic=='sys.metrics':
            producer=msg.get('producer')
            if producer in self.required and fresh(msg.get('pub_ns'),2000,now) and type(msg.get('epoch')) is int:
                if producer=='fpga-io' and msg['epoch']!=self.epoch:
                    self.people=People();self.writing={};self.stroke={};self.calibration_request=0;self.repeat.clear();self.zoom.reset()
                    self.memories.clear();self.action_scopes.clear();self.undo_scope=None;self.last_action=None
                    for palm in self.palms.values():palm.clear()
                    self._clear_target();self.target_catalog={}
                    self.epoch=msg['epoch'];self.latest.clear();self.last_seq.clear();self.latch.reset()
                    self.calibration_backup=None
                    self.heartbeats.clear();self.calibrated=False;self.confirmed_calibration=False;self.pending.clear();self.application_request=None
                    self._state('STANDBY',now)
                if msg['epoch']==self.epoch:
                    if msg.get('application_error'):self.toast=str(msg['application_error'])
                    instance=msg.get('instance')
                    if instance and producer in self.instances and self.instances[producer]!=instance:
                        if producer=='hand':
                            self.zoom.stop();self.repeat.clear()
                            self.out.clear();self.latch.reset();self.stroke_confirm.clear();self.shortcut=None
                            self.writing={};self.stroke={}
                            if self.state=='WRITING':self._state('IDLE' if self.calibrated else 'ONBOARD',now)
                        if producer=='gaze':
                            self.calibration_backup=None
                            if not self._retained_lock():self._clear_target()
                            self.people.calibrated={1:False,2:False}
                            self.calibrated=False;self.calibration_track=None
                            if self.state in ('POINTING','CALIBRATING'):
                                self.out.clear();self.commands.clear();self._state('ONBOARD',now)
                    if instance:self.instances[producer]=instance
                    self.heartbeats[producer]=(msg['pub_ns'],msg.get('ok') is True)
            return
        if msg.get('epoch')!=self.epoch or not self.epoch:return
        if topic=='app.targets':
            if msg.get('context')==self.context and fresh(msg.get('src_ns'),1500,now):self.target_catalog=deepcopy(msg)
            return
        if topic=='hmi.ack':
            pending=self.pending.pop(msg.get('id'),None)
            if pending is not None:
                action=next((a for a in reversed(self.history) if a['id']==msg.get('id')), {})
                self.repeat.acknowledge(msg.get('id'),msg.get('ok'),action.get('name','').endswith('.undo'))
                scope=self.action_scopes.pop(msg.get('id'),self._repeat_context())
                if msg.get('ok') and action:
                    memory=self.memories.setdefault(scope,{'last':None,'undo':deque(maxlen=64)})
                    if action['name'].endswith('.undo'):
                        if memory['undo'] and memory['undo'][-1]['id']==action.get('args',{}).get('undo_id'):memory['undo'].pop()
                    elif not action['name'].endswith(('.wake','.sleep')):
                        memory['undo'].append(deepcopy(action));memory['last']=deepcopy(action)
                    self._sync_memory()
                    detail=msg.get('detail')
                    target=self.target_session.get('target') or {}
                    if action.get('context')=='DEMO' and isinstance(detail,dict) and target and (
                            detail.get('page',target.get('page'))!=target.get('page') or
                            detail.get('case_id',target.get('case_id'))!=target.get('case_id')):
                        # Pointer stays frozen; a different page's button does not.
                        self.target_session['target']={}
                        self.target_session['target_notice']='视图已切换，请眼控选择新目标'
                if not msg.get('ok') and action.get('name')=='demo.zoom':self.zoom.stop()
                self.toast=('已执行：'+(action.get('args',{}).get('medical_target',{}).get('label') or label(action.get('name')))) if msg.get('ok') else '应用未执行：'+str(msg.get('detail',''))
                if action.get('name','').endswith('.undo') and msg.get('ok'):self.toast='已撤回本轮操作' if action['context']=='DEMO' else str(msg.get('detail','已发送撤回'))
            return
        if topic in ('cmd.system','cmd.operator'):
            identity=(topic,msg.get('producer','default'))
            if fresh(msg.get('src_ns'),800,now) and msg['src_ns']>self.command_seen.get(identity,0):
                self.command_seen[identity]=msg['src_ns']
                receipt={'id':msg.get('request_id'),'command':msg.get('command'),'received_ns':now}
                if receipt['id']:self.control_receipts.append(receipt)
                if msg.get('command')=='bindings':
                    try:bindings=validate_bindings(msg.get('bindings'))
                    except ValueError:self.toast='映射无效，未应用';return
                    if bindings!=self.bindings:
                        self._reset_gesture_flow(now);self.bindings=bindings
                        self.toast='手势映射已更新'
                    else:self.toast='映射已保存，当前操作保持不变'
                elif msg.get('command')=='medical_target':
                    row=next((r for r in self.target_catalog.get('targets',[]) if r.get('id')==msg.get('target_id')),None)
                    if self.context!='DEMO' or not row or not fresh(self.target_catalog.get('src_ns'),1500,now):
                        self.toast='页面已变化，请重新选择当前目标'
                    elif not self._health(now) and self._action('demo.activate','console',msg['src_ns'],now):
                        self.out[-1]['args']['medical_target']=deepcopy(row)
                    else:self.toast='请先结束标定或当前确认，再选择目标'
                elif msg.get('command')=='game_input':
                    try:args=validate_game_input(msg.get('args'))
                    except ValueError:self.toast='游戏输入无效';return
                    if self._health(now):return
                    name='game.web_click' if args['kind']=='click' else 'game.web_key'
                    if self._action(name,'console',msg['src_ns'],now):self.out[-1]['args']=deepcopy(args)
                    else:self.toast='请先切换到游戏并结束当前确认或标定'
                else:self.system(msg.get('command'),now)
                receipt.update(detail=self.toast,context=self.context,application_request_id=(self.application_request or {}).get('id'))
            return
        if topic not in ('vision.face','vision.gaze','vision.hands','vision.stroke'):return
        ttl=self.gaze_ttl if topic=='vision.gaze' else self.hand_ttl if topic in ('vision.hands','vision.stroke') else 350
        previous=self.last_seq.get(topic,(-1,0));seq=msg.get('seq');stamp=msg.get('src_ns')
        if type(seq) is not int or not fresh(stamp,ttl,now) or seq<=previous[0] or stamp<=previous[1]:
            return  # Ignore a rejected packet; do not erase the latest good one.
        self.last_seq[topic]=(seq,stamp);self.latest[topic]=msg
        if topic=='vision.face':
            self._observe_people(msg,now)
        if topic=='vision.gaze':
            selected=self.people.slots[self.people.active]
            if self.people.mode=='dual' and selected is not None and msg.get('track_id')!=selected:
                self.latest.pop(topic,None);return
            self.calib=msg.get('calib',{})
            if self.people.mode=='dual' and self.calibrated and self.calibration_track is not None and msg.get('track_id') not in (None,self.calibration_track):
                self.calibrated=False;self.people.calibrated[self.people.active]=False
                if not self._retained_lock():self.out.clear();self.latch.reset();self._state('ONBOARD',now)
                self._command('invalidate_calibration',now);self.toast='眼控标定已失效；已锁定位置仍可手势操作' if self._retained_lock() else '使用者已变化，请重新标定'
            if self.state=='CALIBRATING' and msg.get('phase')=='FAILED' and msg.get('calibration_request')==self.calibration_request:self._state('ONBOARD',now)
            if self.state=='CALIBRATING' and msg.get('phase') in ('READY','RESULT') and self.calib.get('done') and msg.get('calibration_request')==self.calibration_request:
                self.calibration_backup=None
                self.calibrated=True;self.calibration_track=msg.get('track_id')
                self.people.slots[self.people.active]=self.calibration_track;self.people.calibrated[self.people.active]=True
                self.toast='标定完成：✌评测 / 👍使用'
        if topic=='vision.hands':
            if msg.get('hands'):self.last_hand=now
            rows=msg.get('hands',[])
            if not self.people.pending:rows=self.people.hands_for_active(rows)
            self._sync_memory()
            events=[]
            for side,palm in self.palms.items():
                event=palm.observe(msg,self.people.hands_for_active(rows) if self.people.pending and self.people.mode=='dual' else rows,now)
                if event:events.append((side,event,palm.hand))
            # Undo has one global meaning, even inside a pending/modal operation.
            undo=next((event for event in events if event[1]=='undo'),None)
            if undo and not self._health(now) and not self.estop:
                if undo[0]=='Right' and self.shortcut is not None:
                    # The operating hand is answering the current proposal.
                    # Cancelling it must not undo an unrelated completed action.
                    self._reset_gesture_flow(now)
                    self.consumed_right=True;self.toast='已取消快捷操作'
                    return
                self.input_hand=undo[2];self.input_side=undo[0]
                try:self._undo_last(stamp,now)
                finally:self.input_hand=None;self.input_side=None
                self.consumed_right=undo[0]=='Right';return
            modal=self.shortcut is not None or self.state in ('MENU','CALIBRATING','POINTING','WRITING') or self.people.pending is not None or self.calibration_intent is not None
            repeat=next((event for event in events if event[1]=='repeat' and (event[0]=='Left' or not modal)),None)
            if repeat and not self._health(now) and not self.estop:
                self.input_hand=repeat[2];self.input_side=repeat[0]
                try:
                    if repeat[0]=='Right' and self.target_session.get('phase')=='LOCKED':
                        if not self.pending:self._action(self.context.lower()+'.click','Closed_Fist',stamp,now)
                        else:self.toast='等待上一步回执'
                    else:self._repeat_last(stamp,now)
                finally:self.input_hand=None;self.input_side=None
                self.latch.reset()
                if repeat[0]=='Right':self._consume_right()
                return
            # A bilateral continuous control owns both index fingers before the stroke branch.
            zoom_allowed=self.context=='DEMO' and not self.estop and not self._health(now) and self.state not in ('CALIBRATING','POINTING') and not self.people.pending and not self.calibration_intent
            if zoom_allowed:
                zoom_event=self.zoom.observe(rows,stamp)
                if zoom_event in ('prepare','start','update'):
                    # Preparation reserves these samples, not the pending action.
                    # Only the third bilateral sample transfers gesture ownership.
                    if zoom_event=='start':
                        if self.pending:self.zoom.stop();return
                        self.gesture_generation+=1;self.stroke_owner=None;self.writing={};self.stroke={};self.layer='POINT';self.shortcut=None
                        self.latch.reset();self._state('IDLE' if self.calibrated else 'ONBOARD',now)
                        for palm in self.palms.values():palm.clear()
                    if zoom_event=='start':
                        if not self._action('demo.zoom','dual_index',stamp,now):self.zoom.stop();return
                        self.zoom.action_id=self.out[-1]['id'];self.out[-1]['args']={'ratio':1.}
                    if zoom_event=='update':self._remember_zoom_ratio()
                    self.toast='双指缩放 '+str(round(self.zoom.ratio,2))+'×' if self.zoom.active else '双指准备 '+str(self.zoom.count)+'/3'
                    return
                if zoom_event=='end':self._remember_zoom_ratio();self.toast='缩放已保持';self._consume_right();self.latch.reset();return
            else:self.zoom.stop()
            # Left hand has no static/trajectory/confirmation ownership.

            right=[h for h in rows if h.get('side')=='Right' and h.get('in_bounds',True)]
            if len(right)!=1:right=[]
            if right:self.right_seen_ns=stamp
            elif stamp-self.right_seen_ns>450_000_000:self.consumed_right=False
            if right and right[0].get('gesture') not in ('Closed_Fist',None,'None'):self.consumed_right=False
            accepted_msg=dict(msg,hands=right)
            if self.shortcut and right and self.shortcut.get('hand')!=right[0]['track_id']:
                self.shortcut['hand']=right[0]['track_id'];self.latch.reset()
            if not modal and self.palms['Right'].prepared and (not right or right[0].get('gesture')!='Closed_Fist'):accepted_msg['hands']=[]
            if self.target_session.get('phase')!='LOCKED' and ((not modal and self.palms['Right'].owns) or self.consumed_right):accepted_msg['hands']=[]
            if self.state=='POINTING':accepted_msg['hands']=self._eye_hands(right,stamp)
            commits=self.latch.observe(accepted_msg,now,self.layer,self.state=='CALIBRATING',confirming=self.state in ('MENU','POINTING') or self.people.pending is not None or self.calibration_intent is not None,locking=self.state=='POINTING')
            if self.state=='POINTING' and not self.target_session.get('released'):commits=[]
            records=[r for k,r in msg.get('recorder',{}).items() if int(k) in {v['track_id'] for v in right}] if msg.get('gesture_generation',0)==self.gesture_generation else []
            self.writing=next((r for r in records if r.get('state') not in ('IDLE','RESULT')),records[0] if records else {})
            recording=[r for r in records if r.get('state') in ('COUNTDOWN','REC')]
            if len(recording)==1 and not self.estop and self.state in ('STANDBY','PRESENT','ONBOARD','IDLE','WRITING'):
                self.stroke_owner={'track_id':right[0]['track_id'],'context':self._repeat_context(),'generation':self.gesture_generation,'seen_ns':stamp}
                self.layer='WRITE'
                if self.state!='WRITING':self._state('WRITING',now)
                commits=[]
            elif self.state=='WRITING' and not recording:
                ended=any(r.get('state')=='RESULT' for r in records)
                if not ended:self.stroke_owner=None;self.gesture_generation+=1
                self.layer='POINT';self._state('IDLE' if self.calibrated else 'ONBOARD',now)
                if not ended:self.toast='已取消轨迹，右手重新握拳可开始'
            if self.latch.conflict:self.toast='请用一只手操作'
            self._health(now)
            for key,event,name in commits:
                self.input_hand=key;self.input_side='Right'
                try:self.event(event,name,stamp,now)
                finally:self.input_hand=None;self.input_side=None
        if topic=='vision.stroke' and self.state in ('WRITING','IDLE','ONBOARD','STANDBY','PRESENT') and not self._health(now) and not self.estop:
            active=self.people.hands_for_active(self.latest.get('vision.hands',{}).get('hands',[]))
            source=next((h for h in active if h['track_id']==msg.get('track_id') and h.get('side')=='Right'),None)
            owner=self.stroke_owner or {}
            if owner.get('track_id')!=msg.get('track_id') or owner.get('context')!=self._repeat_context() or now-owner.get('seen_ns',0)>1_000_000_000:return
            if source is None or msg.get('source_side')!='Right' or msg.get('ending_gesture')!='Closed_Fist' or msg.get('gesture_generation')!=self.gesture_generation:return
            self.stroke_owner=None;self.stroke=deepcopy(msg);self.layer='POINT';self._state('IDLE' if self.calibrated else 'ONBOARD',now)
            self.latch.reset();self.consumed_right=True
            self.toast='轨迹未识别，请重新画'
            if msg.get('accepted') is True and msg.get('confidence',0)>=self.config['gestures'].get('stroke_confidence',.5):
                action=self.bindings['stroke'].get(self.context,{}).get(msg.get('label'))
                if action:
                    self.input_hand=source['track_id'];self.input_side='Right';previous=self.action_seq
                    try:self._bound(action,'stroke',stamp,now)
                    finally:self.input_hand=None;self.input_side=None
                    if self.action_seq>previous and self.out:
                        self.out[-1]['stroke_source']={k:msg.get(k) for k in ('src_ns','seq','track_id','label')}
                        self.out[-1]['confirmation']='trajectory_fist'
                else:self.toast='已识别 '+str(msg.get('label'))+'，当前应用未绑定'
    def _remember_zoom_ratio(self):
        identity=self.zoom.action_id
        if not identity:return
        for action in self.history:
            if action['id']==identity:action['args']['ratio']=self.zoom.ratio
        for memory in self.memories.values():
            for action in list(memory['undo'])+([memory['last']] if memory['last'] else []):
                if action['id']==identity:action['args']['ratio']=self.zoom.ratio
    def _eye_hands(self,rows,stamp):
        session=self.target_session;key=session.get('hand')
        rows=[h for h in rows if h.get('in_bounds',True)]
        prepared=session.setdefault('prepared',{})
        prepared={k:t for k,t in prepared.items() if stamp-t<=1_000_000_000}
        for h in rows:
            if h.get('gesture') not in (None,'None','Closed_Fist') and h.get('score',0)>=.5:
                prepared[str(h['track_id'])]=stamp
        session['prepared']=prepared
        if key is None:
            # Console entry has no source hand. Let the prepared hand that
            # actually makes the fist take ownership, not the first open hand.
            candidates=[h for h in rows if str(h['track_id']) in prepared and h.get('gesture')=='Closed_Fist']
            if len(candidates)!=1:session['hand_status']='choose_hand';return []
            key=candidates[0]['track_id'];session.update(hand=key,released=True)
        current=next((h for h in rows if h['track_id']==key),None)
        if current is None and session.get('hand_side') in ('Left','Right'):
            candidates=[h for h in rows if h.get('side')==session['hand_side'] and h.get('side_score',0)>=.55]
            if len(candidates)==1:
                current=candidates[0];key=current['track_id']
                session.update(hand=key,released=bool(session.get('released') and stamp-session.get('hand_seen_ns',0)<=600_000_000))
                self.latch.reset()
        if current is None:session['hand_status']='missing';return []
        if current.get('side') in ('Left','Right') and current.get('side_score',0)>=.55:session['hand_side']=current['side']
        session['hand_seen_ns']=stamp
        if str(key) in prepared:session['released']=True
        session['hand_status']='ready' if session.get('released') else 'release'
        return [current]

    def _stroke_context(self):
        return (self.epoch,self.context,self.people.mode,self.people.active,
                self.people.slots[self.people.active],tuple(sorted(f['track_id'] for f in self.people.faces)))
    def _stroke_invalid_reason(self,now):
        p=self.stroke_confirm.pending
        if not p:return None
        if now>p['expires_ns']:return '另一只手确认超时，请重新画'
        current=self._stroke_context();previous=p['context']
        if current[:4]!=previous[:4] or (p.get('face_guard',True) and current[4]!=previous[4]):return '应用或使用者已切换，请重新画'
        # In unregistered single-user mode a non-spatial command needs hands,
        # not face tracking or personal gaze calibration. A changing face
        # detector ID must not cancel an otherwise valid opposite-hand action.
        if not p.get('face_guard',True):return None
        old=set(previous[5]);new=set(current[5])
        if new-old:return '检测到新的使用者，请重新画'
        # Tracking may miss one face frame while both hands remain valid.
        # No new identity is admitted; use the existing one-second loss gate.
        if any(now-self.people.last_seen.get(key,0)>1_000_000_000 for key in old-new):
            return '使用者已离开，请重新画'
        return None
    def _cancel_stroke(self,now,reason):
        self.stroke_confirm.clear();self.latch.reset();self.layer='POINT'
        self._state('IDLE' if self.calibrated else 'ONBOARD',now);self.toast=reason
    def _observe_people(self,message,now):
        lost=self.people.observe(message,now)
        if self.people.mode=='single':
            current=next((f for f in self.people.faces if f.get('primary')),None)
            if current and (self.calibrated or self.state=='CALIBRATING'):
                self.people.slots[1]=current['track_id'];self.calibration_track=current['track_id']
        if self.people.pending:
            p=self.people.pending
            selected=p['choices'][p['index']] if p['choices'] else None
            choices=[f['track_id'] for f in sorted(self.people.faces,key=lambda f:f.get('face_rect',[0])[0])
                     if f['track_id']!=self.people.slots[3-p['slot']]]
            p['choices']=choices;p['index']=choices.index(selected) if selected in choices else 0
        if self.people.active in lost and (self.calibrated or self.state=='CALIBRATING'):
            retained=self._retained_lock()
            if not retained:self._clear_target()
            self.calibration_backup=None
            self.calibrated=False;self.confirmed_calibration=False;self.calibration_track=None
            if not retained:self.out.clear();self.latch.reset();self._state('ONBOARD',now)
            if self.people.mode=='single':self.people.slots[self.people.active]=None
            self._command('invalidate_calibration',now);self.toast='已锁定位置保留；再次眼控接管前需重新标定' if retained else '使用者离开，请重新确认并标定'
    def _model_demand(self):
        return demand(self.state,estop=self.estop,registration=self.people.pending is not None,
                      calibration=self.calibration_intent is not None,
                      calibration_phase=self.calib.get('phase'),dual=self.people.mode=='dual',
                      target_phase=getattr(self,'target_session',{}).get('phase'),
                      head_display_hz=self.tuning.get('head_display_hz',15))
    def _health(self,now):
        missing={p for p in self.required if p not in self.heartbeats or not self.heartbeats[p][1] or not fresh(self.heartbeats[p][0],2000,now)}
        self.broken=sorted(missing & {'fpga-io','hand'})
        self.warnings=sorted(missing-{'fpga-io','hand'})
        if 'gaze' in missing and not self.broken:
            self.latest.pop('vision.gaze',None);self.people.faces=[]
            if self.state in ('POINTING','CALIBRATING') or self.calibration_intent or self.people.pending:
                self.calibration_intent=None;self.people.pending=None
                self._state('IDLE' if self.calibrated else 'ONBOARD',now)
                self.toast='眼控服务暂不可用，手势操作可以继续'
        if self.broken and self.state!='DEGRADED':self._state('DEGRADED',now);self.out.clear();self.commands.clear();self.latch.reset()
        return bool(self.broken)
    def _calibration_scope(self):
        return (self.epoch,self.instances.get('gaze'),self.people.mode,self.people.active,
                self.people.slots[self.people.active] if self.people.mode=='dual' else None)
    def _save_calibration(self):
        self.calibration_backup=(dict(scope=self._calibration_scope(),calib=deepcopy(self.calib),
            track=self.calibration_track,confirmed=self.confirmed_calibration) if self.calibrated else None)
    def _restore_calibration(self):
        saved=self.calibration_backup;self.calibration_backup=None
        if saved and saved['scope']==self._calibration_scope():
            self.calibrated=True;self.calib=saved['calib'];self.calibration_track=saved['track']
            self.confirmed_calibration=saved['confirmed'];self.people.calibrated[self.people.active]=True
    def _state(self,state,now):
        if self.state=='CALIBRATING' and state!='CALIBRATING':self._restore_calibration()
        self.state=state;self.entered=now;self.invalid_since=0
        if state in ('STANDBY','DEGRADED','CALIBRATING'):self.calibration_intent=None
        if state!='WRITING':self.stroke_confirm.clear()
        if state!='MENU':self.shortcut=None
        if state=='CALIBRATING' or self.estop or (state=='DEGRADED' and not (self._retained_lock() and self.broken==['hand'])):self._clear_target()
        elif state!='POINTING' and self.target_session.get('phase')=='SELECTING':self._clear_target()
        elif state!='POINTING' and self.target_session.get('phase')!='LOCKED':self.cursor={'xy':None,'valid':False,'frozen':True}
        if state in ('DEGRADED','CALIBRATING','POINTING') or self.estop:self.repeat.clear()
        if state=='DEGRADED':
            # A missed heartbeat suspends actions, not a fitted calibration.
            # Actual hardware epochs / gaze process changes invalidate in feed().
            self.pending.clear();self.application_request=None
            self.people.pending=None;self.writing={};self.stroke={}
        if state=='STANDBY':self.face_since=self.no_face_since=self.onboard_since=0;self.layer='POINT'
    def _command(self,name,stamp):
        if name=='preview':self._restore_calibration()
        elif name=='invalidate_calibration':self.calibration_backup=None
        self.command_seq+=1
        if name=='calibrate':self.calibration_request=self.command_seq
        self.commands.append(dict(command=name,src_ns=stamp,seq=self.command_seq,epoch=self.epoch,track_id=self.people.slots[self.people.active] if self.people.mode=='dual' else None,person=self.people.active))
    def _action(self,name,gesture,stamp,now):
        if 'adapters' in self.warnings:self.toast='应用执行端暂不可用，手势识别保持运行';return False
        if locked_action(name):
            if self.target_session.get('phase')!='LOCKED':self.toast='请先眼控接管并握拳锁定目标';return False
            if not self.target_session.get('target'):self.toast='视图已切换，请眼控选择新目标';return False
        manual=manual_demo(name,gesture,self.context,self.state) or manual_game(name,gesture,self.context,self.state)
        if self.broken or self.estop or (not manual and (self.state not in ('IDLE','POINTING','WRITING','ONBOARD','STANDBY','PRESENT') or (not self.calibrated and not independent_action(name,gesture) and not (locked_action(name) and self.target_session.get('phase')=='LOCKED')))):return False
        self._sync_memory()
        self.action_seq+=1
        m=dict(id=f'{self.epoch:x}:{self.action_namespace}:{self.action_seq}',name=name,context=self.context,gesture=gesture,
               args={'cursor':deepcopy(self.cursor),'target_lock':deepcopy(self.target_session) if self.target_session.get('phase')=='LOCKED' else None},src_ns=stamp,seq=self.action_seq,epoch=self.epoch,
               confirmation='dual_index_sequence' if gesture=='dual_index' else 'operator' if manual else 'fist_sequence' if independent_action(name,gesture) or locked_action(name) else 'gaze')
        if self.context=='DEMO' and self.input_hand is not None:
            hand=next((h for h in self.latest.get('vision.hands',{}).get('hands',[]) if h.get('track_id')==self.input_hand),{})
            m['args']['control_hand']={'track_id':self.input_hand,'side':hand.get('side',self.input_side)}
        self.toast='已确认，正在执行：'+label(name)
        if self.context in ('DEMO','GAME') and self.application_request is None:
            self.application_request_seq+=1
            self.application_request=dict(id=f'{self.action_namespace}:{self.application_request_seq}',context=self.context,src_ns=now)
        self.out.append(m);self.pending[m['id']]=now;self.history.append(m)
        self.action_scopes[m['id']]=self._repeat_context()
        return True
    def _repeat_context(self):
        return (self.epoch,self.context,self.people.mode,self.people.active,self.people.slots[self.people.active] if self.people.mode=='dual' else None)
    def _undo_last(self,stamp,now):
        self.zoom.stop()
        self.confirmed_fist={}
        self.gesture_generation+=1
        had_proposal=bool(self.stroke_confirm.pending or self.shortcut or self.state in ('MENU','WRITING','CALIBRATING','POINTING'))
        if self.state=='CALIBRATING':self._command('preview',stamp);self._command('hide_window',stamp)
        self.calibration_intent=None;self.people.pending=None;self.shortcut=None;self.stroke_confirm.clear()
        self.repeat.clear();self.eye_palm.clear();self.writing={};self.stroke={};self.layer='POINT';self.latch.reset()
        self._state('IDLE' if self.calibrated else 'ONBOARD',now)
        if self.pending:
            self.toast='正在等待上一步执行回执，请稍后撤回';return
        if not self.undo_stack:
            self.toast='已取消当前操作；没有可撤回的已执行动作' if had_proposal else '没有可撤回的已执行动作';return
        previous=self.undo_stack[-1]
        if self._action(self.context.lower()+'.undo','Thumb_Down',stamp,now):
            self.out[-1]['args']={'undo_id':previous['id']}
            self.toast='正在撤回上一步：'+label(previous['name'])

    def _consume_right(self):
        self.consumed_right=True
        palm=self.palms['Right'];palm.prepared=False;palm.consumed=True;palm.latch.reset()
        rows=self.people.hands_for_active(self.latest.get('vision.hands',{}).get('hands',[]))
        right=[h for h in rows if h.get('side')=='Right' and h.get('gesture')=='Closed_Fist']
        if len(right)==1 and self.target_session.get('phase')=='LOCKED':
            stamp=self.latest['vision.hands']['src_ns'];key=right[0]['track_id']
            self.latch.arm_confirmed(key,stamp)
            self.confirmed_fist=dict(track_id=key,src_ns=stamp,epoch=self.epoch,
                                     generation=self.gesture_generation,context=self.context)

    def _reset_gesture_flow(self,now):
        """End the old proposal when its mapping, application or person changes."""
        proposed=self.shortcut is not None or self.state=='WRITING'
        self.confirmed_fist={}
        self.gesture_generation+=1;self.stroke_owner=None
        self.shortcut=None;self.stroke_confirm.clear();self.writing={};self.stroke={};self.layer='POINT'
        self.zoom.stop();self.repeat.clear();self.latch.reset()
        for palm in self.palms.values():palm.clear()
        if proposed:self._state('IDLE' if self.calibrated else 'ONBOARD',now)

    def _sync_memory(self):
        scope=self._repeat_context()
        memory=self.memories.setdefault(scope,{'last':None,'undo':deque(maxlen=64)})
        if scope!=self.undo_scope:
            self.zoom.reset()
            for palm in self.palms.values():palm.clear()
        self.undo_scope=scope;self.undo_stack=memory['undo'];self.last_action=memory['last']

    def _repeat_last(self,stamp,now):
        self._sync_memory()
        if self.pending:self.toast='等待上一步回执';return
        original=deepcopy(self.last_action)
        if not original:self.toast='暂无已执行动作可重复';return
        if self.state=='CALIBRATING':self._command('preview',stamp);self._command('hide_window',stamp)
        if self.state in ('MENU','CALIBRATING','POINTING','WRITING'):
            self.gesture_generation+=1;self.shortcut=None;self.stroke_confirm.clear();self.calibration_intent=None;self.people.pending=None
            self.writing={};self.layer='POINT';self._state('IDLE' if self.calibrated else 'ONBOARD',now)
        if not self._action(original['name'],original['gesture'],stamp,now):return
        action=self.out[-1];control=action['args'].get('control_hand')
        if not locked_action(original['name']):action['args']=deepcopy(original['args'])
        if control:action['args']['control_hand']=control
        action['confirmation']=original['confirmation'];action['repeated_from']=original['id']
        if 'stroke_source' in original:action['stroke_source']=deepcopy(original['stroke_source'])
        self.toast='正在重复：'+label(original['name'])
    def _bound(self,target,gesture,stamp,now):
        if self.input_side=='Right':self._consume_right()
        if target.startswith('system.'):
            self.layer='POINT';self.system(target[7:],now)
        else:self._action(target,gesture,stamp,now)
    def system(self,command,now):
        if command=='demo_snap':command='eye_takeover'  # Legacy console alias, never a second snap mode.
        if command=='app_basic' and self.estop:self.system('resume',now)
        if self.estop and command not in ('estop','takeover','resume','menu'):
            self.toast='紧急待机中，请先恢复交互';return
        if command=='menu':self.calibration_intent=None
        if command in ('estop','takeover'):
            self.shortcut=None;self.out.clear();self.commands.clear();self.pending.clear();self.latch.reset();self.estop=True;self._state('STANDBY',now)
            self.people.pending=None;self.writing={};self.stroke={};self.application_request=None;self.toast='已暂停交互，短按 MENU 或网页恢复'
            self._command('preview',now);self._command('hide_window',now)
        elif command=='resume':self.estop=False;self.toast='已恢复，请入座'
        elif command=='mode_next':
            self.system({'DESKTOP':'app_game','GAME':'app_demo','DEMO':'app_basic','BASIC':'app_desktop'}[self.context],now)
        elif command=='people_toggle':
            self.system('single' if self.people.mode=='dual' else 'dual',now)
        elif command in ('app_desktop','app_game','app_demo','app_basic') and not self._health(now):
            self._reset_gesture_flow(now)
            if self.state=='CALIBRATING':
                self._command('preview',now);self._command('hide_window',now)
                if not self.calibrated:self.people.calibrated[self.people.active]=False
            self._clear_target();self.target_catalog={}
            self.context={'app_desktop':'DESKTOP','app_game':'GAME','app_demo':'DEMO','app_basic':'BASIC'}[command]
            self.layer='POINT';self.latch.reset();self.stroke_confirm.clear();self.writing={};self.stroke={};self.calibration_intent=None
            self.out.clear();self._state('IDLE' if self.calibrated else 'ONBOARD',now)
            self.application_request_seq+=1
            self.application_request=dict(id=f'{self.action_namespace}:{self.application_request_seq}',context=self.context,src_ns=now)
            self.toast='已切换'+{'DESKTOP':'桌面','GAME':'游戏','DEMO':'医学演示','BASIC':'基础功能展示'}[self.context]+'，使用本应用的手势映射'
        elif command in ('pointer','eye_takeover') and not self._health(now):
            if not self.calibrated:self.toast='眼控接管需要先标定；手势和轨迹可直接使用';return
            self.shortcut=None;self.stroke_confirm.clear();self.writing={};self.stroke={};self.calibration_intent=None
            self.latest.pop('vision.gaze',None)
            self._clear_target();self.latch.reset()
            self.target_session={'phase':'SELECTING','hand':self.input_hand,'released':False,'context':self.context,'epoch':self.epoch,'started_ns':now}
            source=next((h for h in self.latest.get('vision.hands',{}).get('hands',[]) if h['track_id']==self.input_hand),{})
            self.target_session.update(hand_side=source.get('side',self.input_side),hand_seen_ns=now)
            self.layer='POINT';self._state('POINTING',now);self._update_cursor(now);self._command('track',now)
            action=self.config['actions'][self.context].get('wake')
            if action:self._action(action,'pointer',now,now)
            self.toast='眼控接管：注视目标，原操作手松开再握拳锁定；不自动点击'
        elif command in ('confirm','next','cancel'):
            self.event(command,'button',now,now)
        elif command in ('single','dual') and not self._health(now):
            if self.people.mode==command:
                self.toast='当前已经是'+('单人模式' if command=='single' else '双人模式');return
            self._reset_gesture_flow(now)
            self.calibration_intent=None
            self._clear_target();self.target_catalog={}
            self.people.mode=command;self.people.pending=None;self.people.hand_owners.clear();self.latch.reset();self.out.clear();self.stroke={};self.writing={}
            if command=='single':self.people.active=1;self.people.slots[2]=None;self.people.calibrated[2]=False
            self.calibrated=False;self.people.calibrated[self.people.active]=False;self._command('invalidate_calibration',now)
            self._state('MENU',now);self.toast='已切换'+('双人模式：请分别登记、标定' if command=='dual' else '单人模式：请重新标定')
        elif command in ('person1','person2') and not self._health(now):
            self.calibration_intent=None
            slot=int(command[-1])
            if slot==1 and self.people.mode=='single':self.system('calibrate',now);return
            if slot==2 and self.people.mode!='dual':self.toast='请先开启双人模式';return
            self._reset_gesture_flow(now)
            self._clear_target();self.people.request(slot);self.latch.reset();self._state('MENU',now)
            self.toast=f'登记第 {slot} 人：比 V 选择画面中的候选人，握拳确认'
        elif command in ('calibrate_person1','calibrate_person2') and not self._health(now):
            self._clear_target()
            slot=int(command[-1])
            if self.state=='CALIBRATING' and self.calib.get('phase') not in ('READY','RESULT','FAILED'):self.toast='请先完成或取消当前标定';return
            if slot==2 and self.people.mode!='dual':self.toast='第二人标定需要先切换双人模式';return
            self._reset_gesture_flow(now)
            if self.people.mode=='dual':
                track=self.people.slots[slot]
                if track is None or track not in {f['track_id'] for f in self.people.faces}:
                    self.system('person'+str(slot),now)
                else:
                    self.people.active=slot;self.calibrated=False;self._command('select_track',now)
                    self._state('ONBOARD',now);self.onboard_since=0
            else:self._state('ONBOARD',now)
            self.calibration_intent={'slot':slot,'epoch':self.epoch,'mode':self.people.mode,'expires_ns':now+20_000_000_000}
            self.toast=f'第 {slot} 人：'+('先选择候选并握拳确认，然后自动标定' if self.people.pending else '请居中睁眼，稳定后自动开始标定')
        elif command=='calibrate' and not self.estop and not self._health(now):
            if self.state=='CALIBRATING' and self.calib.get('phase') not in ('READY','RESULT','FAILED'):self.toast='正在标定，请先取消再重新开始';return
            self.shortcut=None;self.stroke_confirm.clear();self.writing={};self.stroke={};self.latch.reset();self.layer='POINT'
            ready,key,reason=calibration_readiness(self.latest.get('vision.face',{}),self.people,now,self.tuning.get('calibration_entry'))
            if reason or key!=self.onboard_track or not self.onboard_since or now-self.onboard_since<self.calibration_stable_ns:
                self._state('MENU' if self.people.mode=='dual' and (self.people.slots[self.people.active] is None or self.people.pending) else 'ONBOARD',now)
                self.calibration_intent={'slot':self.people.active,'epoch':self.epoch,'mode':self.people.mode,'expires_ns':now+20_000_000_000}
                self.toast='尚未开始标定：'+(reason or '请保持片刻')+'，就绪后自动开始';return
            self.calibration_intent=None;self._clear_target()
            self._save_calibration()
            self.people.slots[self.people.active]=key[2];self.calibration_track=key[2]
            self._command('select_track',now)
            self.calib={};self.calibrated=False;self.people.calibrated[self.people.active]=False;self._state('CALIBRATING',now);self._command('calibrate',now)
        elif command=='validate' and self.calibrated and not self.estop and not self._health(now):
            self.calib=dict(self.calib,phase='VALIDATE');self._state('CALIBRATING',now);self._command('validate',now)
        elif command=='use_calibration':self.event('end','keyboard',now,now)
        elif command in ('demo_next','demo_previous','demo_focus','demo_snap','demo_reset','demo_rotate'):
            if self.estop:self.toast='操作未执行：请先解除紧急待机'
            elif self._health(now):self.toast='操作未执行：等待服务恢复'
            elif self.context!='DEMO':self.toast='操作未执行：请先选择医学演示'
            elif not manual_demo('demo.'+('cancel' if command=='demo_previous' else command[5:]),'console',self.context,self.state):
                self.toast='操作未执行：请先结束标定、菜单或轨迹书写'
            else:self._action('demo.'+('cancel' if command=='demo_previous' else command[5:]),'console',now,now)
        elif command=='menu' and self.estop:
            self.estop=False;self._state('MENU',now);self.toast='已恢复，选择操作'
        elif command=='menu' and not self._health(now) and self.state not in ('BOOT','DEGRADED','CALIBRATING'):
            self._state(('IDLE' if self.calibrated else 'ONBOARD') if self.state=='MENU' else 'MENU',now)
    def event(self,event,gesture,stamp,now):
        if self._health(now) or self.estop or not fresh(stamp,self.hand_ttl,now):return
        if self.calibration_intent and event in ('cancel','sleep'):
            self.calibration_intent=None;self.people.pending=None;self.toast='已取消预约标定';return
        if self.stroke_confirm.pending:
            if event in ('cancel','sleep','menu'):self._cancel_stroke(now,'已取消轨迹操作')
            else:self.toast='另一只手张掌入镜即可准备，握拳确认轨迹'
            return
        if self.shortcut:
            target=self.shortcut['target']
            if event=='confirm':
                source_gesture=self.shortcut['gesture']
                self.shortcut=None;self._state('IDLE',now);self._bound(target,source_gesture,stamp,now)
            elif event in ('cancel','sleep','menu'):
                self.shortcut=None;self._state('IDLE',now);self.toast='已取消快捷操作'
            return
        target=self.bindings['static'].get(self.context,{}).get(gesture)
        if self.input_side=='Right' and self.state in ('IDLE','ONBOARD','STANDBY','PRESENT') and gesture not in ('button','keyboard','stroke'):
            if not target and event=='menu':target='system.menu'
            if not target:self.toast='当前手势未绑定功能';return
        if self.state in ('IDLE','ONBOARD','STANDBY','PRESENT') and target:
            self.confirmed_fist={}
            self.repeat.clear()
            self.shortcut={'target':target,'gesture':gesture,'label':label(target),'hand':self.input_hand,'expires_ns':now+int(self.tuning.get('shortcut_timeout_s',15.)*1e9)}
            self.latch.reset();self._state('MENU',now);self.toast='右手握拳执行 · 拇指向下取消：'+label(target)
            return
        if event=='menu':self.people.pending=None;self.system('menu',now);return
        if self.people.pending:
            if event=='next':self.people.next_candidate()
            elif event in ('cancel','sleep'):self.people.pending=None;self.calibration_intent=None;self.toast='已取消登记'
            elif event=='confirm':
                track=self.people.confirm()
                if track is None:self.toast='候选人已离开，请重新选择登记';return
                self.calibrated=self.people.calibrated[self.people.active];self.calibration_track=track
                self.stroke={};self.writing={}
                self.latest.pop('vision.gaze',None);self._command('select_track',stamp);self.latch.reset()
                self._state('IDLE' if self.calibrated else 'ONBOARD',now)
                self.toast=f'已选择第 {self.people.active} 人，'+('可以操作' if self.calibrated else '竖拇指或按确认开始标定')
            return
        if self.state=='ONBOARD':
            if event=='end' or event=='confirm' and gesture=='button':
                self.system('calibrate',now)
            elif event in ('next','cancel'):
                action=self.config['actions'][self.context].get(event)
                if action:self._action(action,gesture,stamp,now)
            return
        if self.state=='CALIBRATING':
            if event in ('sleep','cancel'):self._command('preview',stamp);self._state('ONBOARD',now);self.toast='已取消标定'
            elif self.calibrated and event=='next':self.calib=dict(self.calib,phase='VALIDATE');self._command('validate',stamp)
            elif self.calibrated and (event=='end' or event=='confirm' and gesture=='button'):
                self.confirmed_calibration=True;self._command('track',stamp);self._command('hide_window',stamp);self._state('IDLE',now)
            return
        if self.state=='MENU':
            if event=='next':self.menu_index=(self.menu_index+1)%len(MENU)
            elif event in ('cancel','sleep'):self._state('IDLE' if self.calibrated else 'ONBOARD',now)
            elif event=='confirm':
                i=self.menu_index
                if i<3:
                    self._clear_target();self.target_catalog={};self.context=('DESKTOP','GAME','DEMO')[i];self.layer='POINT'
                    self.application_request_seq+=1
                    self.application_request=dict(id=f'{self.action_namespace}:{self.application_request_seq}',context=self.context,src_ns=now)
                    self._state('IDLE' if self.calibrated else 'ONBOARD',now)
                    self.toast='已选择'+MENU[i]+('；眼控可用' if self.calibrated else '；手势可用，眼控请先标定')
                elif i==3:
                    self.layer='POINT';self._state('IDLE' if self.calibrated else 'ONBOARD',now);self.toast='握拳准备，伸食指保持0.3秒开始记录'
                elif i==4:self.system('calibrate',now)
                elif i==5:self.system('dual' if self.people.mode=='single' else 'single',now)
                elif i in (6,7):self.system('calibrate_person1' if i==6 else 'calibrate_person2',now)
                elif i==8:self.system('estop',now)
            return
        if self.state=='WRITING':
            if event=='sleep':self.layer='POINT';self._state('IDLE',now)
            return
        if event=='sleep':
            self.layer='POINT';self.latch.reset();self._state('STANDBY',now)
            self.toast='已退出当前手势；再次握拳开始'
            return
        if not self.calibrated:
            action=self.config['actions'][self.context].get(event)
            if action:self._action(action,gesture,stamp,now)
            return
        actions=self.config['actions'][self.context]
        if self.state=='IDLE':
            if event=='wake':
                self.system('pointer',now)
            elif event in ('cancel','next','end') and actions.get(event):self._action(actions[event],gesture,stamp,now)
        elif self.state=='POINTING':
            self._update_cursor(now)
            if event=='confirm':
                if self.input_hand is not None and (not self.target_session.get('released') or self.input_hand!=self.target_session.get('hand',self.input_hand)):return
                if not self.cursor.get('valid') or not self.target_session.get('target'):
                    # A fist always ends this eye-control segment. An invalid
                    # gaze sample must not swallow it and leave selection running.
                    self._clear_target();self._state('IDLE',now);self.latch.reset()
                    self._consume_right()
                    self.toast='眼控已结束；未锁定目标，请重新接管后选择';return
                self.target_session.update(phase='LOCKED',lock_id=uuid.uuid4().hex,locked_ns=now,cursor=deepcopy(self.cursor))
                self.cursor.update(frozen=True,locked=True)
                self._state('IDLE',now);self.latch.reset()
                self._consume_right()
                self.toast='已锁定 '+self.target_session['target']['label']+'；右手张掌→握拳点击，双手均可张掌→拇指向下撤回'
            elif event in ('cancel','sleep'):
                self._clear_target();self._state('IDLE',now);self.toast='已结束眼控接管，未点击'
    def _retained_lock(self):
        # A frozen pointer is no longer a live eye-control session. In single
        # user mode head-display tracking cannot revoke subsequent hand actions.
        return self.people.mode=='single' and self.target_session.get('phase')=='LOCKED'
    def _clear_target(self):
        self.target_vote.reset()
        if hasattr(self,'eye_palm'):self.eye_palm.clear()
        self.target_session={};self.cursor={'xy':None,'valid':False,'frozen':True}
    def _update_cursor(self,now):
        if self.state!='POINTING':return
        g=self.latest.get('vision.gaze',{});xy=g.get('filtered_xy');size=g.get('screen_size',[])
        valid=bool(g.get('valid') and self.calibrated and fresh(g.get('src_ns'),self.gaze_ttl,now) and finite_xy(xy) and finite_xy(size) and all(n>0 for n in size))
        catalog=self.target_catalog
        rows=catalog.get('targets',[]) if catalog.get('context')==self.context and fresh(catalog.get('src_ns'),1500,now) and catalog.get('screen_size')==size else []
        if valid and rows:
            # Normalize/clamp only the selection coordinate; calibration and
            # continuous filtered samples keep their original numerical values.
            xy=[max(0.,min(1.,xy[i]/size[i]))*size[i] for i in (0,1)]
            target=self.target_vote.update(xy,rows,size,g.get('src_ns'),g.get('seq'))
        else:
            self.target_vote.pause();target=None
        self.target_session['vote']=dict(self.target_vote.details)
        valid=bool(target)
        self.cursor.update(valid=valid,frozen=not valid,locked=False,src_ns=g.get('src_ns',0))
        if target:
            self.target_session['target']=target
            self.cursor.update(xy=center(target),screen_size=size,screen_origin=g.get('screen_origin',[0,0]))
            self.invalid_since=0
        else:
            self.invalid_since=self.invalid_since or now
            self.toast='等待有效视线' if not g.get('valid') else '正在稳定目标，稍候握拳锁定' if rows else catalog.get('detail','当前应用暂无可操作目标')
    def tick(self,now):
        self.now=now
        if self.zoom.active and (now-self.zoom.stamp>350_000_000 or self.context!='DEMO' or self.estop):self.zoom.stop()
        if self._health(now):self.zoom.stop();return self.snapshot(now)
        if self.state in ('BOOT','DEGRADED'):self._state('STANDBY',now)
        if self.repeat.session and (now-self.repeat.session['last_seen']>600_000_000 or self.repeat.session['context']!=self._repeat_context()):self.repeat.clear()
        if self.shortcut and now>self.shortcut['expires_ns']:
            self.shortcut=None;self._state('IDLE' if self.calibrated else 'ONBOARD',now);self.toast='快捷操作已超时取消'
        for key,stamp in list(self.pending.items()):
            if now-stamp>1_000_000_000:
                self.pending.pop(key);self.action_scopes.pop(key,None);self.repeat.acknowledge(key,False)
                self.toast='应用未响应，请重新操作（不自动重发）'
        f=self.latest.get('vision.face',{})
        faces=f.get('faces',[]) if fresh(f.get('src_ns'),350,now) else []
        face_active=self._model_demand()['face_hz']>0
        if face_active and not self.last_face_demand:self.face_demand_since=now
        self.last_face_demand=face_active
        # A paused detector provides no evidence of absence. On activation,
        # wait for actual observations before applying the usual loss policy.
        if face_active and (f.get('src_ns',0)>=self.face_demand_since or now-self.face_demand_since>2_000_000_000):
            self._observe_people(f,now)
        elif face_active and not faces:
            self.people.faces=[]
        elif not face_active:
            if not faces:self.people.faces=[]
            self.face_since=self.no_face_since=0
        stroke_reason=self._stroke_invalid_reason(now)
        if stroke_reason:self._cancel_stroke(now,stroke_reason)
        primary=next((f for f in faces if f.get('primary') and f.get('valid')),None)
        ready,key,reason=calibration_readiness(f,self.people,now,self.tuning.get('calibration_entry'))
        self.onboard=ready
        if reason or key!=self.onboard_track:self.onboard_since=0
        self.onboard_track=key
        if not reason:self.onboard_since=self.onboard_since or now
        intent=self.calibration_intent
        if intent:
            if (intent['mode']=='dual' and now>intent['expires_ns']) or intent['epoch']!=self.epoch or intent['mode']!=self.people.mode:
                self.calibration_intent=None;self.toast='预约标定已超时或模式变化，请重新选择'
            elif self.state=='ONBOARD' and not self.people.pending and self.people.active==intent['slot'] and not reason and self.onboard_since and now-self.onboard_since>=self.calibration_stable_ns:
                self.calibration_intent=None;self.system('calibrate',now)
        if primary:self.face_since=self.face_since or now;self.no_face_since=0
        elif face_active:self.face_since=0;self.no_face_since=self.no_face_since or now
        if self.state=='STANDBY' and not self.estop and self.face_since and now-self.face_since>=1e9:self._state('PRESENT',now)
        elif self.state=='PRESENT':self._state('IDLE' if self.calibrated else 'ONBOARD',now)
        if self.state=='POINTING':
            self._update_cursor(now)
            if self.invalid_since and now-self.invalid_since>15e9:
                self._state('IDLE',now);self.toast='视线暂不可用，已返回手势操作'
        if not fresh(self.latest.get('vision.hands',{}).get('src_ns'),self.hand_ttl,now):self.latch.reset()
        if self.state=='WRITING' and now-self.last_hand>10e9:self.layer='POINT';self._state('IDLE',now)
        if self.state in ('IDLE','PRESENT','ONBOARD') and not self.calibration_intent and self.no_face_since and now-self.no_face_since>=(5e9 if self.state=='IDLE' else 3e9):self._state('STANDBY',now)
        return self.snapshot(now)
    def snapshot(self,now):
        g,h,f=BUDGET[self.state]
        hand_unlimited=h>0 and not self.estop
        if hand_unlimited:h=60  # source ceiling; no sleep is added after inference
        hand_msg=self.latest.get('vision.hands',{})
        active_hands=self.people.hands_for_active(hand_msg.get('hands',[])) if fresh(hand_msg.get('src_ns'),self.hand_ttl,now) else []
        return dict(v=1,src_ns=now,pub_ns=now,seq=self.action_seq,epoch=self.epoch or 1,state=self.state,context=self.context,layer=self.layer,people=self.people.mode,participants=self.people.snapshot(),writing=deepcopy(self.writing),stroke=deepcopy(self.stroke),
                    target_session=deepcopy(self.target_session),target_catalog=deepcopy(self.target_catalog),
                    active_hand_ids=[h['track_id'] for h in active_hands],application_request=deepcopy(self.application_request),control_receipts=deepcopy(list(self.control_receipts)),
                    hand_src_ns=hand_msg.get('src_ns',0),hand_observations=[{k:h.get(k) for k in ('track_id','side','gesture','score')} for h in active_hands],
                    zoom_control=self.zoom.snapshot(),gesture_generation=self.gesture_generation,gesture_contract=96,confirmed_fist=deepcopy(self.confirmed_fist),reserved_hand_ids=[p.hand for p in self.palms.values() if p.prepared and p.hand is not None],
                    last_action=({'name':self.last_action['name'],'label':label(self.last_action['name']),'id':self.last_action['id']} if self.last_action else None),undo_available=bool(self.undo_stack),
                    repeat_cycle=self.repeat.snapshot(),bindings=deepcopy(self.bindings),shortcut=deepcopy(self.shortcut),stroke_pending=deepcopy(self.stroke_confirm.pending),
                    calibration_intent=deepcopy(self.calibration_intent),
                    calibrated=self.calibrated,calib=self.calib,cursor=deepcopy(self.cursor),gesture=max(self.latch.progress.values(),key=lambda p:p['progress'],default={}),
                    menu={'open':self.state=='MENU','items':MENU,'index':self.menu_index},onboard=self.onboard,toast=self.toast,
                    health={'broken':self.broken,'warnings':self.warnings},budget={'hand_hz':h,'hand_unlimited':hand_unlimited,**self._model_demand()},history=list(self.history),estop=self.estop)
