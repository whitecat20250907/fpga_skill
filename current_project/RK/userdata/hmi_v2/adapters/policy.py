from collections import deque
from core.targets import same_target,same_medical_target
from core.clock import fresh
from core.schema import finite_xy
from core.manual_demo import permitted as manual_demo
from core.manual_game import permitted as manual_game
from core.action_requirements import independent_action,locked_action

class ActionGate:
    def __init__(self,gaze_ms=250,hand_ms=350):
        self.seen=set();self.order=deque(maxlen=1024);self.gaze_ms=gaze_ms;self.hand_ms=hand_ms
    def accept(self,action,state,now):
        identity=action.get('id')
        if not isinstance(identity,str) or identity in self.seen:return False,'duplicate/invalid action id'
        if len(self.order)==self.order.maxlen:self.seen.discard(self.order[0])
        self.order.append(identity);self.seen.add(identity)
        if action.get('epoch')!=state.get('epoch') or action.get('context')!=state.get('context'):return False,'context/epoch mismatch'
        manual=manual_demo(action.get('name'),action.get('gesture'),state.get('context'),state.get('state')) or manual_game(action.get('name'),action.get('gesture'),state.get('context'),state.get('state'))
        if manual and action.get('confirmation')!='operator':return False,'missing operator confirmation'
        if not fresh(state.get('src_ns'),350,now) or state.get('health',{}).get('broken'):return False,'unhealthy/stale state'
        confirmation='dual_index_sequence' if action.get('gesture')=='dual_index' else 'trajectory_fist' if action.get('gesture')=='stroke' else 'fist_sequence'
        independent=independent_action(action.get('name'),action.get('gesture')) and action.get('confirmation')==confirmation
        if action.get('gesture')=='stroke' and action.get('confirmation')!='trajectory_fist':return False,'stroke requires drawing-hand ending fist'
        locked=locked_action(action.get('name','')) and action.get('confirmation')==confirmation and state.get('target_session',{}).get('phase')=='LOCKED'
        if not manual and not state.get('calibrated') and not independent and not locked:return False,'uncalibrated spatial action or missing fist sequence'
        if (not manual and state.get('state') not in ('IDLE','POINTING','WRITING','ONBOARD','STANDBY','PRESENT')) or state.get('estop'):return False,'outputs disabled'
        if not fresh(action.get('src_ns'),self.hand_ms,now):return False,'stale action'
        if locked_action(action.get('name','')):
            lock=action.get('args',{}).get('target_lock') or {};current=state.get('target_session',{})
            catalog=state.get('target_catalog',{})
            if lock.get('phase')!='LOCKED' or not lock.get('lock_id') or lock.get('lock_id')!=current.get('lock_id'):return False,'请先眼控接管并锁定目标'
            target=lock.get('target',{})
            if action.get('name')!='demo.focus' and (not fresh(catalog.get('src_ns'),1500,now) or not any(same_target(target,r) or action.get('name')=='demo.click' and same_medical_target(target,r) for r in catalog.get('targets',[]))):return False,'目标已变化，请重新眼控接管'
        return True,''
