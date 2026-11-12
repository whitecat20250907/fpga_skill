import time
from copy import deepcopy
from collections import deque
from core.targets import medical_spec



class DemoAdapter:
    def __init__(self):
        self.state={'page':0,'snap':True,'awake':False,'anchor':[.5,.5],'revision':0}
        if medical_spec().get('workflow')=='renal_review':self.state['case_id']=medical_spec()['default_case']
        self.undo_history=deque(maxlen=64);self.continuous_zoom=None
        self.reset_view();self.rotation_hand=None;self.rotation_seen=0;self.rotation_tick=0;self.palm_since=0;self.palm_stamp=0

    def stop_rotation(self,reason='已停止旋转'):
        self.state['rotating']=False;self.state['rotation_notice']=reason;self.rotation_hand=None

    def tick(self,now,state):
        zoom=state.get('zoom_control',{})
        if self.continuous_zoom and zoom.get('action_id')==self.continuous_zoom['id'] and state.get('context')=='DEMO' and not state.get('estop') and not state.get('health',{}).get('broken') and 0<=now-state.get('src_ns',0)<500_000_000 and 0<=now-zoom.get('src_ns',0)<500_000_000:
            ratio=zoom.get('ratio',1.)
            if isinstance(ratio,(int,float)) and 0<ratio<1000:
                value=self.continuous_zoom['base']*ratio
                if value!=self.state['zoom']:self.state['zoom']=value;self.state['revision']+=1

        elapsed=max(0,min(.1,(now-self.rotation_tick)/1e9)) if self.rotation_tick else 0
        self.rotation_tick=now
        if not self.state['rotating']:return
        if state.get('context')!='DEMO' or state.get('estop') or state.get('health',{}).get('broken') or now-state.get('src_ns',0)>500_000_000:
            self.stop_rotation('已暂停旋转');return
        if state.get('state') in ('POINTING','CALIBRATING'):
            # Selecting a target needs a stationary scene. A frozen LOCKED
            # pointer is independent and must never disable volume rotation.
            self.stop_rotation('已停止旋转，正在选目标' if state['state']=='POINTING' else '已停止旋转，正在标定');return
        if self.rotation_hand:
            stamp=state.get('hand_src_ns',0)
            rows=state.get('hand_observations',[]) if 0<=now-stamp<500_000_000 else []
            side=self.rotation_hand.get('side')
            candidates=[h for h in rows if side not in ('Left','Right') or h.get('side')==side]
            hand=next((h for h in candidates if h.get('track_id')==self.rotation_hand.get('track_id')),None)
            if hand is None and side in ('Left','Right'):
                if len(candidates)==1:hand=candidates[0];self.rotation_hand['track_id']=hand['track_id']
            if hand:
                self.rotation_seen=max(self.rotation_seen,stamp)
                if stamp>self.palm_stamp:
                    self.palm_stamp=stamp
                    if hand.get('gesture')=='Open_Palm' and hand.get('score',0)>=.45:
                        self.palm_since=self.palm_since or stamp
                        if stamp-self.palm_since>=120_000_000:
                            self.stop_rotation('操作手张掌，旋转停止');return
                    else:self.palm_since=0
            elif now-self.rotation_seen>=600_000_000:
                self.stop_rotation('操作手已离开，旋转停止');return
        if self.state.get('case_id') and self.state['page']==1:
            from core.targets import medical_case
            axis={'axial':2,'coronal':1,'sagittal':0}[self.state['plane']]
            end=medical_case(self.state)['shape'][axis]-1
            self.scan_position=min(end,getattr(self,'scan_position',self.state['crosshair'][axis])+10*elapsed)
            self.state['crosshair'][axis]=round(self.scan_position)
            if self.scan_position>=end:self.stop_rotation('已到末层')
        else:self.state['orbit'][1]+=18*elapsed

    def reset_view(self):
        if self.state.get('case_id'):
            from .medical_workflow import reset
            reset(self);return
        case=medical_spec()['pages'][self.state['page']].get('case',{})
        self.state.update(zoom=1.,focus=False,part=None,rotation=0,orbit=[0,0,0],axis=1,
                          inspection=None,rotating=False,rotation_notice='',crosshair=[round(x) for x in case.get('tumor_voxel',[0,0,0])],window=0,overlay=True)

    def on_action(self,action):
        if action['name']=='demo.undo':
            self.continuous_zoom=None
            identity=action.get('args',{}).get('undo_id')
            if not self.undo_history or self.undo_history[-1][0]!=identity:
                raise ValueError('本轮操作已变化或已撤回')
            _,previous=self.undo_history.pop()
            revision=self.state['revision']+1
            self.state=deepcopy(previous);self.state['revision']=revision
            self.stop_rotation('已撤回本轮操作')
            return {'ok':True,'detail':deepcopy(self.state)}
        previous=deepcopy(self.state)
        if action['name']=='demo.zoom':
            import math
            ratio=action.get('args',{}).get('ratio')
            if not isinstance(ratio,(int,float)) or not math.isfinite(ratio) or not 0<ratio<1000:raise ValueError('无效双指倍率')
            self.stop_rotation('');self.state['zoom']=previous['zoom']*ratio;self.state['revision']+=1
            self.continuous_zoom=None if action.get('repeated_from') else {'id':action['id'],'base':previous['zoom']}
            result={'ok':True,'detail':deepcopy(self.state)}
        else:
            self.continuous_zoom=None
            result=self._apply_action(action)
        if action.get('id') and not action['name'].endswith(('.wake','.sleep')):self.undo_history.append((action['id'],previous))
        return result

    def _apply_action(self,action):
        if self.state.get('case_id'):
            from .medical_workflow import apply
            return apply(self,action)
        name=action['name'].split('.')[-1]
        args=action.get('args',{});lock=args.get('target_lock') or {};target=lock.get('target',{})
        if name=='activate':
            target=args.get('medical_target') or {}
            if target.get('page')!=self.state['page']:raise ValueError('页面已切换，请选择当前目标')
            name=target.get('action','').split('.')[-1]
        elif name in ('click','confirm'):
            if target.get('page')!=self.state['page']:raise ValueError('页面已切换，请重新选择目标')
            name=target.get('action','').split('.')[-1]
        if name not in {'wake','sleep','next','cancel','focus','inspect','reset','rotate','snap'}:
            raise ValueError('Unsupported demo action')
        page=medical_spec()['pages'][self.state['page']];case=page.get('case')
        if not self.state['rotating']:self.state['rotation_notice']=''
        if lock.get('phase')=='LOCKED':
            cur=lock['cursor'];self.state['anchor']=[cur['xy'][0]/cur['screen_size'][0],cur['xy'][1]/cur['screen_size'][1]]
        if name=='wake':self.state['awake']=True
        elif name=='sleep':self.state['awake']=False
        elif name=='inspect':
            content=target.get('content')
            valid={r.get('content') for r in page.get('controls',[])}
            if content not in valid or not content:raise ValueError('当前页没有该医学内容')
            self.state['inspection']=None if self.state['inspection']==content else content
        elif name=='focus':
            self.state['inspection']=None
            part=target.get('part');valid={p['key'] for p in page['parts']}
            if part not in valid:part=self.state.get('part')
            if case and part is None:part='tumor'
            self.state['focus']=not self.state['focus'] if part==self.state.get('part') else True
            self.state['part']=part
            if case and part:self.state['crosshair']=[round(x) for x in case.get('part_voxels',{}).get(part,case['tumor_voxel'])]
        elif name in ('next','cancel'):
            self.state['page']=(self.state['page']+(1 if name=='next' else -1))%len(medical_spec()['pages'])
            self.reset_view()
        elif name=='rotate':
            if self.state['rotating']:self.stop_rotation()
            else:
                self.state['rotating']=True;self.state['rotation']+=1
                self.rotation_hand=dict(args['control_hand']) if args.get('control_hand') else None
                self.rotation_seen=time.monotonic_ns();self.rotation_tick=self.rotation_seen
                self.palm_since=0;self.palm_stamp=self.rotation_seen
                self.state['rotation_notice']='旋转中 · 操作手张掌或离开即停' if self.rotation_hand else '旋转中 · 再次点击停止'
        elif name=='snap':raise ValueError('请使用统一的眼控接管入口')
        elif name=='reset':self.reset_view()
        self.state['revision']+=1
        return {'ok':True,'detail':{k:list(v) if isinstance(v,list) else v for k,v in self.state.items()}}
