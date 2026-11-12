"""Application UI hooks inside the retained original Popen owner/session.

No owner, subprocess, camera, model, hardware access or background thread is
created here. The existing owner calls the proxy and forwards its own RPC.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import time
from types import SimpleNamespace

from owned_producers import exact_identity,identity,read_json


def pin(row):
    p=Path(row['path'])
    if not p.is_absolute() or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('application source pin changed')
    return p


def ref(path):
    path=Path(path);return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def write_new(path,value,uid=None,gid=None):
    with Path(path).open('x',encoding='utf8') as f:
        f.write(json.dumps(value,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n')
    if uid is not None and hasattr(os,'chown'):os.chown(path,uid,gid)


def simple(row):
    return exact_identity({k:row[k] for k in ('pid','start_ticks')})


def application_proxy(base,owner,spec_pin):
    """Wrap the actual session class; never start a second session coordinator.

    spec is a pinned APP_UI_SESSION_V1 containing support_modules, mode_config
    and optional game_bridge_config. All three producers retain original Popen
    handles and the original full-close and native-reap proofs.
    """
    spec=read_json(pin(spec_pin))
    if spec.get('schema')!='APP_UI_SESSION_V1':raise ValueError('application session spec')
    for row in spec['support_modules'].values():pin(row)
    mode=read_json(pin(spec['mode_config']))
    controller=simple(owner.m.identity(os.getpid()))
    if mode['interaction_controller']!=controller or mode['boot_id']!=owner.cfg['boot_id']:
        raise ValueError('mode controller must be this actual owner')
    state=Path(mode['interaction_state'])
    if state!=Path(owner.interaction_path):raise ValueError('same existing mode state required')
    support=pin(spec['support_modules']['interaction_ui']).parent
    helpers={str(support),str(pin(spec['support_modules']['face_set_contract']).parent)}

    class ApplicationSession(base.OwnedFeatureSession):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.ui_work=self.work/'application';self.ui_work.mkdir(mode=0o700)
            if hasattr(os,'chown'):os.chown(self.ui_work,self.uid,self.gid)
            self.ui_sequence=0;self.ui_pending=None;self.ui_started_ns=time.monotonic_ns()
            self.ui_binding=self.ui_work/'producers.json';self.ui_health=self.ui_work/'health.json'
            self.ui_control=self.ui_work/'control';self.ui_control.mkdir(mode=0o700)
            if hasattr(os,'chown'):os.chown(self.ui_control,self.uid,self.gid)
            config=dict(schema='APP_UI_RELAY_V1',boot_id=owner.cfg['boot_id'],controller=controller,
                support_modules=spec['support_modules'],mode_config=spec['mode_config'],
                producer_binding=str(self.ui_binding),control_directory=str(self.ui_control),health_path=str(self.ui_health),
                game_bridge_config=spec.get('game_bridge_config'))
            self.ui_config=self.ui_work/'config.json';write_new(self.ui_config,config,self.uid,self.gid)
            self.ui_config_pin=ref(self.ui_config)

        def _spawn(self,kind,args,env,user=False):
            args=list(args)
            if kind=='relay':args+=['--ui-config',str(self.ui_config),'--ui-config-sha256',self.ui_config_pin['sha256']]
            if kind=='hand':
                if '--trajectory-ui-dir' in args or '--interaction-mode-config' in args:raise ValueError('duplicate trajectory consumer options')
                args+=['--trajectory-ui-dir',str(support),'--interaction-mode-config',spec['mode_config']['path'],
                    '--interaction-mode-config-sha256',spec['mode_config']['sha256']]
            return super()._spawn(kind,args,env,user=user)

        def main_environment(self,environment):
            value=super().main_environment(environment)
            if value.get('TWB_UI_FILTERED_EXPORT') not in (None,'1'):raise ValueError('unknown filtered export overlay')
            value['TWB_UI_FILTERED_EXPORT']='1'
            paths=[str(support),*(p for p in sorted(helpers) if p!=str(support))]
            if value.get('PYTHONPATH'):paths.append(value['PYTHONPATH'])
            value['PYTHONPATH']=os.pathsep.join(paths)
            return value

        def start_hand(self,environment):
            result=super().start_hand(environment)
            if owner.row is None or not owner.row.get('owners'):raise ValueError('actual original runtime missing')
            captures=[r for r in owner.row['owners'] if Path(shlex.split(r['cmdline'])[0]).name=='capture_native']
            if len(captures)!=1:raise ValueError('exact original capture child required')
            capture=simple(captures[0]);main=simple(self.model);hand=simple(self.children['hand'].identity)
            for row in (controller,capture,main,hand):
                if identity(row['pid'])!=row:raise ValueError('actual producer changed before publication')
            b=dict(schema='APP_UI_PRODUCERS_V1',boot_id=owner.cfg['boot_id'],controller=controller,
                owner_generation=str(owner.root.name)+':'+self.work.name,capture_session=f"{owner.cfg['boot_id']}:{capture['pid']}:{capture['start_ticks']}",
                main=main,hand=hand,capture=capture,not_before_ns=self.ui_started_ns,generation_directory=str(self.work),
                people_path=f"/dev/shm/gaze_npu_people_{main['pid']}.json",filtered_path=f"/dev/shm/gaze_ui_filtered_{main['pid']}.json")
            write_new(self.ui_binding,b,self.uid,self.gid)
            return dict(result,application_binding=self.ui_config_pin)

        def application_command(self,body,timeout=3.):
            if not 0<timeout<=5:raise ValueError('bounded UI control wait')
            self.health()
            if self.ui_pending is not None:
                previous_request,previous_response,previous_seq=self.ui_pending
                if not previous_response.is_file():raise TimeoutError('previous application command still pending; no second request issued')
                previous=read_json(previous_response)
                if (previous.get('sequence')!=previous_seq or previous.get('controller')!=controller or
                        previous.get('request_sha256')!=ref(previous_request)['sha256']):raise ValueError('previous application response differs')
                self.ui_pending=None
            seq=self.ui_sequence+1;request=self.ui_control/f'request_{seq:06d}.json'
            response=self.ui_control/f'response_{seq:06d}.json'
            if request.exists() or response.exists():raise ValueError('pending application request retained; no duplicate retry')
            allowed={'command','slot','hand_track_id','mode'}
            if not set(body)<=allowed or body.get('command') not in ('status','register','unregister','page','trajectory_hand','claim','release','people_mode'):
                raise ValueError('explicit application command')
            value=dict(body,schema='APP_UI_CONTROL_V1',sequence=seq,controller=controller,
                boot_id=owner.cfg['boot_id'],timestamp_ns=time.monotonic_ns())
            # Atomic no-overwrite publication, readable only by this session.
            temporary=request.with_suffix('.tmp');write_new(temporary,value,self.uid,self.gid)
            try:os.link(temporary,request)
            finally:temporary.unlink()
            self.ui_sequence=seq;self.ui_pending=(request,response,seq);deadline=time.monotonic()+timeout
            while not response.is_file() and time.monotonic()<deadline:
                self.health();time.sleep(.02)
            if not response.is_file():raise TimeoutError('same application command pending; inspect retained response, do not resubmit')
            result=read_json(response)
            if (result.get('sequence')!=seq or result.get('controller')!=controller or
                    result.get('request_sha256')!=ref(request)['sha256']):raise ValueError('application response sequence/owner/hash')
            self.ui_pending=None
            return result

    return SimpleNamespace(OwnedFeatureSession=ApplicationSession,read_identity=base.read_identity)


def application_control(owner,body):
    """Call only from this original owner's serialized RPC dispatch."""
    if owner.phase not in ('FEATURE_RUNNING','FEATURE_KEEP_RUNNING') or owner.session is None:
        raise ValueError('application controls require live original feature generation')
    if not hasattr(owner.session,'application_command'):raise ValueError('current generation has no application profile')
    return owner.session.application_command(body)
