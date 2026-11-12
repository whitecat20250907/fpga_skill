"""One existing feature relay: registered pages, real strokes and app geometry.

No capture/model/extra publisher. Existing owner retains all Popen handles.
Its live process binding and existing ModeGate are required before input use.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import socket
import sys
import time

from app_scene import ApplicationScene,fresh
from owned_producers import OwnedProducers,read_json,bounded_bytes,json_object,identity as process_identity
from twb_sender_app import NativeSender,TWBError


def pinned(row):
    p=Path(row['path'])
    if not p.is_absolute() or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('source pin changed: '+str(p))
    return p


def support_modules(config):
    rows=config['support_modules']
    required=('interaction_ui','actor_controller','controlled_trajectory','face_set_contract','menu_page_input')
    if not set(required)<=set(rows) or set(rows)-set(required)-{'filtered_ui_export'}:raise ValueError('explicit UI support module set')
    for name in (*required,*(('filtered_ui_export',) if 'filtered_ui_export' in rows else ())):
        p=pinned(rows[name]);spec=importlib.util.spec_from_file_location(name,p)
        m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
    return {name:sys.modules[name] for name in rows}


def game_factory(config,modules):
    """Prepare pins now; resolve live producer context only after actual launch."""
    row=config.get('game_bridge_config')
    if row is None:return None
    template=read_json(pinned(row))
    if template.get('enabled') is not True:return None
    if template.get('owner_generation') is not None or template.get('capture_session') is not None:
        raise ValueError('game template must await actual owned producer context')
    path=pinned(template['adapter']);name='_app_same_actor_game_bridge'
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module)
    def create(binding):
        resolved=dict(template,owner_generation=binding['owner_generation'],capture_session=binding['capture_session'])
        return module.build_same_actor_game_bridge(resolved,mode_ack_matches=modules['controlled_trajectory'].mode_ack_matches)
    create.battle_acceptance=copy.deepcopy(template['battle_acceptance'])
    return create


class AppRelay:
    def __init__(self,state,sender,producers,mode_gate,modules,*,control_directory=None,game_bridge=None,game_builder=None,runtime_binding=None):
        self.state,self.sender,self.producers,self.gate=state,sender,producers,mode_gate
        self.modules=modules;self.controller=modules['actor_controller'].ActorController()
        self.scene=ApplicationScene(self.controller);self.game=game_bridge
        self.game_builder=game_builder;self.game_factory_attempted=game_bridge is not None;self.game_error=None
        self.runtime_binding=copy.deepcopy(runtime_binding or {})
        self.control_directory=Path(control_directory) if control_directory else None
        self.control_sequence=0;self.last_key=None;self.mode_view=None;self.effective_mode=0
        self.face_geometry={};self.people=None;self.hand=None;self.gaze=None
        self.last_error=None;self.last_observation=None
        self.counts=dict(received=0,source_updates=0,rejected=0,fixture_rejected=0,no_credit=0,enqueued=0,unchanged=0,geometry_rejected=0)

    def accept(self,body,peer,now_ns):
        self.counts['received']+=1
        try:
            if len(body)>32000:raise ValueError('oversize feature')
            p=json.loads(body)
            if not isinstance(p,dict):raise ValueError('feature object')
            if p.get('fixture'):
                self.counts['fixture_rejected']+=1;raise ValueError('production refuses fixture')
            self.producers.accept_peer(p,peer,now_ns,commit=False)
            if not self.state.accept(body,now_ns):raise ValueError('existing FeatureState rejected source')
            self.producers.commit_peer(p)
        except (OSError,ValueError,TypeError,KeyError,IndexError,OverflowError,RecursionError) as exc:
            self.last_error=str(exc);self.counts['rejected']+=1;return False
        self.counts['source_updates']+=1;return True

    def update_sources(self,now_ns):
        """Only the owned private people file can establish runtime source UUID."""
        binding=self.producers.refresh(now_ns)
        if self.game_builder is not None and not self.game_factory_attempted:
            self.game_factory_attempted=True
            try:
                self.game=self.game_builder(binding)
                if self.game is None:raise ValueError('enabled game factory did not create the original link')
            except Exception as exc:
                self.game_error=(type(exc).__name__+': '+str(exc))[:512]
        try:self.producers.people(now_ns)
        except (OSError,ValueError,KeyError,TypeError):pass
        face=self.state.fresh('face',now_ns)
        # A known expired hand suspends actions without falsely retiring the
        # current still-visible face. Never replace it with a fabricated ID.
        hand=self.state.samples.get('hand')
        geometry=[]
        if face and self.producers.model_session:
            try:
                geometry=self.modules['face_set_contract'].expand_face_set(face,now_ns=now_ns,
                    expected_model_session=self.producers.model_session)
                self.people=self.producers.attach_context(dict(timestamp_ns=face['timestamp_ns'],capture_sequence=face['capture_sequence'],
                    source_instance=self.producers.model_session,people=[dict(track_id=g['track_id'],valid=g['valid']) for g in geometry]))
            except (ValueError,TypeError,KeyError) as exc:
                self.last_error=str(exc);self.people=None
        else:self.people=None
        self.face_geometry={g['track_id']:g for g in geometry}
        self.hand=self.producers.attach_context(hand) if hand else None
        try:self.gaze=self.producers.filtered(now_ns)
        except (OSError,ValueError,KeyError,TypeError):self.gaze=None
        if self.people is not None and self.hand is not None:
            self.last_observation=self.controller.observe(self.people,self.hand,now_ns)
        else:self.controller.assignments(now_ns)
        self.mode_view=self.gate.read(now_ns)
        self.controller.sync_mode(self.mode_view)
        ack=self.hand.get('interaction_mode_ack') if self.hand else None
        matches=self.modules['controlled_trajectory'].mode_ack_matches(ack,self.mode_view,now_ns)
        if matches:
            matches=bool(self.hand.get('valid') is True and ack.get('source_instance')==self.hand.get('source_instance') and
                ack.get('timestamp_ns')==self.hand.get('timestamp_ns') and ack.get('capture_sequence')==self.hand.get('capture_sequence'))
        self.effective_mode=self.mode_view.code if matches else 0
        if self.game is not None:
            self.game.update(controller=self.controller,filtered=self.gaze,hand_packet=self.hand,
                mode_view=self.mode_view,mode_ack=ack,now_ns=now_ns)

    def control(self,request,now_ns):
        """Owner's existing RPC forwards an explicit action, never implicit page claim."""
        action=request.get('command');c=self.controller
        fields={k for k in request if k not in ('schema','sequence','controller','boot_id','timestamp_ns')}
        expected={'command'}
        if action=='people_mode':expected.add('mode')
        if action in ('register','unregister','page','trajectory_hand','claim'):expected.add('slot')
        if action in ('trajectory_hand','claim'):expected.add('hand_track_id')
        if fields!=expected:raise ValueError('exact command arguments required')
        if 'slot' in expected and (type(request['slot']) is not int or request['slot'] not in (1,2)):raise ValueError('actor slot')
        if 'hand_track_id' in expected and (type(request['hand_track_id']) is not int or not 0<request['hand_track_id']<0xffffffff):
            raise ValueError('positive transient hand track')
        if action=='status':return self.health(now_ns)
        if action=='people_mode':return c.set_people_mode(request['mode'])
        if action=='register':return c.register_visible_actor(request['slot'],now_ns=now_ns)
        if action=='unregister':c.unregister_actor(request['slot']);return dict(accepted=True)
        if action=='page':return dict(accepted=True,actor_slot=c.select_page(request['slot']))
        if action=='trajectory_hand':return self.scene.select_trajectory_hand(request['slot'],request['hand_track_id'])
        if action=='claim':
            if self.effective_mode!=2:return dict(accepted=False,reason='game_mode_not_acknowledged')
            return c.claim_game(request['slot'],request['hand_track_id'],now_ns=now_ns)
        if action=='release':c.release_game();return dict(accepted=True)
        raise ValueError('supported commands: status/register/unregister/page/trajectory_hand/claim/release')

    def poll_control(self,now_ns):
        if self.control_directory is None:return
        seq=self.control_sequence+1;path=self.control_directory/f'request_{seq:06d}.json'
        if not path.exists():return
        self.control_sequence=seq
        response=dict(sequence=seq,accepted=False,request_sha256=None,controller=self.producers.controller)
        try:
            raw=bounded_bytes(path,8192)
            response['request_sha256']=hashlib.sha256(raw).hexdigest()
            body=json_object(raw)
            b=self.producers.refresh(now_ns)
            if (body.get('schema')!='APP_UI_CONTROL_V1' or body.get('sequence')!=seq or
                    body.get('controller')!=b['controller'] or body.get('boot_id')!=b['boot_id'] or
                    type(body.get('timestamp_ns')) is not int or not 0<=now_ns-body['timestamp_ns']<=5_000_000_000):
                raise ValueError('fresh exact owner control required')
            response.update(accepted=True,result=self.control(body,now_ns))
        except (OSError,ValueError,TypeError,KeyError,IndexError) as exc:response['error']=str(exc)
        final=self.control_directory/f'response_{seq:06d}.json';temp=final.with_suffix('.tmp')
        temp.write_text(json.dumps(response,allow_nan=False,separators=(',',':'))+'\n',encoding='utf8');temp.replace(final)

    def tick(self,now_ns):
        try:self.update_sources(now_ns)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            self.last_error=str(exc);self.people=self.hand=self.gaze=None;self.face_geometry={}
            for slot in list(self.controller.registrations):self.controller._invalidate(slot,'source_temporarily_unavailable')
            self.effective_mode=0
            if self.game is not None:
                self.game.update(controller=self.controller,filtered=None,hand_packet=None,
                    mode_view=self.gate.read(now_ns),mode_ack=None,now_ns=now_ns)
        self.poll_control(now_ns)
        c=self.controller
        key=(tuple((k,p['source_instance'],p['timestamp_ns'],p['packet_sequence']) for k,p in sorted(self.state.samples.items()) if fresh(p,now_ns)),
            c.display_slot,c.display_generation,c.command_generation,self.effective_mode,
            self.gaze.get('timestamp_ns') if self.gaze else None,bool(self.face_geometry))
        if key==self.last_key:self.counts['unchanged']+=1;return False
        try:
            # All geometry and metadata are constructed at the native fenced
            # serialization clock, preserving source ages without re-stamping.
            sent=self.sender.send(lambda at:self.scene.build(at,face_geometry=copy.deepcopy(self.face_geometry),
                hand_packet=copy.deepcopy(self.hand),gaze=copy.deepcopy(self.gaze),acknowledged_mode=self.effective_mode))
        except (ValueError,TypeError,KeyError,IndexError,OverflowError) as exc:
            self.last_error=str(exc);self.counts['geometry_rejected']+=1;return False
        if sent:self.last_key=key;self.counts['enqueued']+=1
        else:self.counts['no_credit']+=1
        return sent

    def health(self,now_ns):
        c=self.controller
        gh=self.game.health() if self.game is not None else None
        binding=self.producers.binding or {}
        return dict(profile='HFT2_APPLICATION_V1',actor_slot=c.display_slot,display_generation=c.display_generation,
            schema='APP_UI_HEALTH_V1',timestamp_ns=now_ns,boot_id=self.producers.boot_id,controller=self.producers.controller,
            relay_identity=self.runtime_binding.get('relay_identity'),config_sha256=self.runtime_binding.get('config_sha256'),
            owner_generation=binding.get('owner_generation'),capture_session=binding.get('capture_session'),
            registrations=c.assignments(now_ns),candidate=c.candidate,observation=self.last_observation,
            people_mode=c.people_mode,registration_required=c.people_mode=='dual',
            interaction_ui=copy.deepcopy(self.hand.get('interaction_ui')) if self.hand and fresh(self.hand,now_ns) else None,
            filtered_gaze=copy.deepcopy(self.gaze) if self.gaze and fresh(self.gaze,now_ns) else None,
            effective_mode=self.effective_mode,requested_mode=self.mode_view.mode if self.mode_view else None,
            game_actor_slot=c.game_slot,game_hand_track=c.game_hand,geometry=dict(self.scene.last_diagnostic),
            game_factory_attempted=self.game_factory_attempted,game_error=self.game_error,
            game_factory_ready=bool(gh and gh.get('closed') is False and gh.get('fatal_error') is None and self.game_error is None),
            battle_acceptance=getattr(self.game_builder,'battle_acceptance',None),game_bridge=gh,
            last_error=self.last_error,counts=dict(self.counts),camera_created=False,inference_created=False)


def bind_local(port):
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,131072);sock.bind(('127.0.0.1',port));sock.setblocking(False)
    except BaseException:sock.close();raise
    return sock


def acquire(sender,bind):
    probe=sender.probe()
    if not probe['supported']:raise TWBError(probe['code'],'unsupported firmware; UDP not bound')
    sock=bind()
    try:sender.start_epoch()
    except BaseException:sock.close();raise
    return sock,probe


def run(args):
    if not 1<=args.hz<=10 or not 0<=args.seconds<=86400 or not 1<=args.port<=65535:raise ValueError('bounded relay parameters')
    cp=pinned(dict(path=str(args.ui_config),sha256=args.ui_config_sha256));config=read_json(cp)
    if config.get('schema')!='APP_UI_RELAY_V1':raise ValueError('application relay config')
    modules=support_modules(config)
    feature=pinned(dict(path=str(args.feature_module),sha256=args.feature_sha256))
    spec=importlib.util.spec_from_file_location('_app_existing_features',feature);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    producers=OwnedProducers(config['producer_binding'],boot_id=config['boot_id'],controller=config['controller'])
    mode_config=pinned(config['mode_config']);gate=modules['controlled_trajectory'].load_mode_gate(mode_config,config['mode_config']['sha256'])
    prepared_game_builder=game_factory(config,modules)  # Validate before binding/flush.
    running=True
    def stop(*_):
        nonlocal running
        running=False
    previous={s:signal.signal(s,stop) for s in (signal.SIGINT,signal.SIGTERM)}
    started=time.monotonic();last_health=started;last_snapshot=None;menu=None;menu_error=None
    try:
        try:menu=modules['menu_page_input'].MenuPageInput()
        except (OSError,RuntimeError,ValueError) as exc:menu_error=str(exc)
        with NativeSender(args.library,args.device) as sender:
            sock,probe=acquire(sender,lambda:bind_local(args.port))
            relay=AppRelay(m.FeatureState(),sender,producers,gate,modules,control_directory=config['control_directory'],game_builder=prepared_game_builder,
                runtime_binding=dict(relay_identity=process_identity(os.getpid()),config_sha256=args.ui_config_sha256))
            print(json.dumps(dict(status='RUNNING_EXISTING_FEATURE_RELAY',profile='HFT2_APPLICATION_V1',probe=probe,
                feature_sha256=args.feature_sha256,port=args.port,hz=args.hz,capture_created=False,inference_created=False)),flush=True)
            try:
                deadline=time.monotonic()
                while running and (not args.seconds or time.monotonic()-started<args.seconds):
                    now=time.monotonic();select.select([sock],[],[],min(.05,max(0.,deadline-now)))
                    end=time.monotonic()+.004
                    for _ in range(32):
                        if time.monotonic()>=end:break
                        try:body,_,flags,peer=sock.recvmsg(32001)
                        except BlockingIOError:break
                        if flags&socket.MSG_TRUNC:relay.counts['rejected']+=1;continue
                        relay.accept(body,peer,time.monotonic_ns())
                    if menu is not None:
                        try:
                            menu.state.page=relay.controller.display_slot-1
                            for page in menu.poll():relay.controller.select_page(page+1)
                        except (OSError,RuntimeError) as exc:menu_error=str(exc);menu.close();menu=None
                    now=time.monotonic()
                    if now>=deadline:
                        relay.tick(time.monotonic_ns());deadline=now+1/args.hz
                        # Shared live telemetry: no extra camera, model or unbound producer reads.
                        live=Path(config['health_path']).with_name('interaction_live.json')
                        temp=live.with_suffix('.tmp')
                        temp.write_text(json.dumps(relay.health(time.monotonic_ns()),allow_nan=False,separators=(',',':'))+'\n',encoding='utf8');temp.replace(live)
                    if now-last_health>=1:
                        read_started_ns=time.monotonic_ns()
                        last_snapshot=sender.snapshot()
                        read_ended_ns=time.monotonic_ns();last_health=now
                        health=relay.health(time.monotonic_ns());health.update(menu_error=menu_error,physical_button_open=menu is not None)
                        health['hardware_UI']=dict(schema='APP_UI_HARDWARE_SNAPSHOT_V1',
                            available=last_snapshot is not None,clock='CLOCK_MONOTONIC',
                            read_started_ns=read_started_ns,read_ended_ns=read_ended_ns,
                            snapshot=copy.deepcopy(last_snapshot),
                            context={key:copy.deepcopy(health.get(key)) for key in
                                ('boot_id','controller','relay_identity','config_sha256','owner_generation','capture_session')})
                        print(json.dumps(dict(status='EXISTING_FEATURE_RELAY_HEALTH',counts=dict(relay.counts),latest_UI_snapshot=last_snapshot,application=health)),flush=True)
                        target=Path(config['health_path']);temp=target.with_suffix('.tmp')
                        temp.write_text(json.dumps(health,allow_nan=False,separators=(',',':'))+'\n',encoding='utf8');temp.replace(target)
            finally:
                if relay.game is not None:relay.game.close()
                sock.close()
            return dict(status='STOPPED_EXISTING_FEATURE_RELAY',counts=relay.counts,latest_UI_snapshot=last_snapshot,
                game_closed=relay.game.health() if relay.game is not None else None,game_factory_error=relay.game_error,
                retained_source_kinds=len(relay.state.samples),capture_created=False,inference_created=False)
    finally:
        if menu is not None:menu.close()
        for s,handler in previous.items():signal.signal(s,handler)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True,action='store_true')
    p.add_argument('--library',required=True,type=Path);p.add_argument('--feature-module',required=True,type=Path)
    p.add_argument('--feature-sha256',required=True);p.add_argument('--ui-config',required=True,type=Path);p.add_argument('--ui-config-sha256',required=True)
    p.add_argument('--device',default='/dev/ANLOGIC-PCI0_user');p.add_argument('--port',type=int,default=29802)
    p.add_argument('--hz',type=float,default=10);p.add_argument('--seconds',type=float,default=0)
    try:result=run(p.parse_args())
    except (TWBError,OSError,ValueError,TimeoutError) as exc:
        print(json.dumps(dict(status='REFUSED_OR_STOPPED',error=str(exc))),flush=True);return 3
    print(json.dumps(result),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
