import json,sys,time
from pathlib import Path
from core.clock import fresh
from core.config import load,ROOT
from core.hmibus import Publisher,Subscriber
from core.service import Service
from .policy import ActionGate
from .demo import DemoAdapter
from .launcher import Launcher
from .game import submit as submit_game,submit_locked
from .target_catalog import TargetCatalog
from core.targets import same_target,resolve_medical_click
from core.snapshot_file import SnapshotWriter

def main():
    c=load();run=c['paths']['run'];svc=Service('adapters',c);gate=ActionGate(c['freshness_ms']['gaze_action'],c['freshness_ms']['hand']);demo=DemoAdapter()
    from core.maintenance_resume import take,restore_demo
    restore_demo(demo,take(run,'demo'))
    for path in ['gaze_app','freeciv_bridge']:sys.path.insert(0,str(ROOT/'vendor'/path))
    from desktop_input import X11Input,display_geometry
    from screen_bridge import FreecivScreenInput
    from input_bridge import FreecivInput
    from gesture_control import send_game_action
    from Xlib import display,X,XK
    from Xlib.ext import xtest
    pointer=X11Input(display_geometry(c['display']['hdmi']));xd=display.Display();game=FreecivScreenInput()
    launcher=Launcher(c,xd);catalog=TargetCatalog(xd,display_geometry(c['display']['hdmi']));targets=Publisher('app.targets',run=run);target_seq=0;target_at=0;gs=None
    sub=Subscriber(['hmi.action','hmi.state'],run=run);ack=Publisher('hmi.ack',run=run);pending={};last_gaze=0;last_lock=None;started_ns=time.monotonic_ns()
    desktop_last=None
    snapshot=SnapshotWriter(Path(run)/'demo.json')
    try:
        while svc.running:
            sub.poll(10);state=sub.latest('hmi.state') or {};now=time.monotonic_ns();epoch=state.get('epoch',0)
            if fresh(state.get('src_ns'),350,now) and not state.get('health',{}).get('broken'):launcher.select(state)
            cursor=state.get('cursor',{});active=state.get('state')=='POINTING' and fresh(state.get('src_ns'),350,now) and not state.get('health',{}).get('broken') and cursor.get('valid') and fresh(cursor.get('src_ns'),c['freshness_ms']['gaze_action'],now)
            if active and cursor['src_ns']>last_gaze:
                xy=cursor['xy'];origin=cursor.get('screen_origin',[0,0])
                demo.state['anchor']=[xy[0]/cursor['screen_size'][0],xy[1]/cursor['screen_size'][1]]
                pointer.move(*xy)  # Only a fresh SELECTING sample may move the system pointer.
                last_gaze=cursor['src_ns']
            lock=state.get('target_session',{})
            if lock.get('phase')=='LOCKED' and lock.get('lock_id')!=last_lock:
                last_lock=lock.get('lock_id')
                if lock.get('locked_ns',0)>=started_ns and fresh(state.get('src_ns'),350,now):
                    pointer.move(*lock['cursor']['xy'])  # Commit the final selected point exactly once.
                    demo.state['anchor']=[lock['cursor']['xy'][i]/lock['cursor']['screen_size'][i] for i in (0,1)]
            for action in sub.events('hmi.action'):
                ok,detail=gate.accept(action,state,now)
                if ok:
                    try:
                        context=action['context'];name=action['name'].split('.')[-1]
                        locked=action.get('args',{}).get('target_lock') or {}
                        if locked and name in ('click','confirm'):
                            current=catalog.snapshot(context,demo.state,gs,True)
                            if context=='DEMO':locked['target']=resolve_medical_click(locked.get('target') or {},current['targets'])
                            elif not any(same_target(locked.get('target'),r) for r in current['targets']):raise ValueError('目标已变化，请重新眼控接管')
                        if name=='activate' and context=='DEMO':
                            current=catalog.snapshot(context,demo.state,gs,True)
                            requested=action.get('args',{}).get('medical_target') or {}
                            action['args']['medical_target']=resolve_medical_click(requested,current['targets'])
                        if context=='GAME' and name in ('click','confirm'):
                            ok,detail=submit_locked(game,locked)
                            if ok:pending[action['id']]=(action,game.sequence,now);continue
                        elif action['name'] in ('game.web_click','game.web_key'):
                            from .game_window import apply
                            game.invalidate_gaze();detail=apply(xd,c['paths']['game'],action['args'])
                        elif context=='DEMO' or action['name'].startswith('demo.'):result=demo.on_action(action);detail=result['detail']
                        elif context=='DESKTOP':
                            focus=xd.get_input_focus().focus
                            focus_id=getattr(focus,'id',focus)
                            if name=='undo':
                                if not desktop_last or desktop_last!=(action['args'].get('undo_id'),focus_id):
                                    raise ValueError('当前窗口或本轮操作已变化，未发送撤回')
                                ctrl=xd.keysym_to_keycode(XK.string_to_keysym('Control_L'));z=xd.keysym_to_keycode(XK.string_to_keysym('z'))
                                xtest.fake_input(xd,X.KeyPress,ctrl);xtest.fake_input(xd,X.KeyPress,z)
                                xtest.fake_input(xd,X.KeyRelease,z);xtest.fake_input(xd,X.KeyRelease,ctrl);xd.sync()
                                desktop_last=None;detail='已发送 Ctrl+Z，撤回结果由当前应用决定'
                            elif name=='click':
                                point=xd.screen().root.query_pointer();xy=locked['cursor']['xy'];origin=locked['cursor'].get('screen_origin',[0,0])
                                if abs(point.root_x-xy[0]-origin[0])>3 or abs(point.root_y-xy[1]-origin[1])>3:raise ValueError('鼠标已被外部移动，请重新眼控接管')
                                pointer.click()
                            elif name in ('cancel','next'):
                                code=xd.keysym_to_keycode(XK.string_to_keysym('Escape' if name=='cancel' else 'Tab'))
                                xtest.fake_input(xd,X.KeyPress,code);xtest.fake_input(xd,X.KeyRelease,code);xd.sync()
                            elif name not in ('wake','sleep'):raise ValueError('Unsupported desktop action')
                            if name!='undo':desktop_last=(action['id'],focus_id)
                        elif context=='GAME':
                            if name=='undo':raise ValueError('本轮游戏指令已提交，原生规则不支持撤回；未改变棋局')
                            ok=submit_game(game,action,send_game_action)
                            if ok and name=='wake':FreecivInput.action(game,'mouse')
                            if ok and name!='sleep':pending[action['id']]=(action,game.sequence,now);continue
                            detail='Game sleep' if ok else 'Game rejected/unavailable'
                        else:raise ValueError('Unknown context')
                    except Exception as exc:ok=False;detail=str(exc)
                ack.publish(dict(src_ns=now,seq=action['seq'],epoch=epoch or 1,id=action['id'],ok=ok,detail=detail))
            # Confirmation transitions engine to IDLE in the same tick. Keep
            # its fresh gaze until the one-shot event has been sent, then sleep.
            if state.get('context')!='GAME':game.invalidate_gaze()
            gs=game.update()
            for identity,(action,sent,started) in list(pending.items()):
                ok=bool(gs and int(gs.get('last_event',-1))==sent)
                if ok or now-started>=900_000_000:
                    ack.publish(dict(src_ns=now,seq=action['seq'],epoch=epoch,id=identity,ok=ok,detail='game last_event' if ok else 'game acknowledgement timeout'));del pending[identity]
            if now-target_at>=200_000_000 and epoch:
                target_at=now;target_seq+=1
                view=catalog.snapshot(state.get('context'),demo.state,gs,state.get('target_session',{}).get('phase') in ('SELECTING','LOCKED'))
                targets.publish(dict(src_ns=now,seq=target_seq,epoch=epoch,**view))
            demo.tick(now,state)
            signature=(demo.state['revision'],demo.state.get('rotating'),launcher.status.get('request_id'),launcher.status.get('status'),state.get('context'),state.get('estop'))
            if snapshot.due(now,signature):
                snapshot.publish(now,signature,{'demo':demo.state,'hmi':state,'application':launcher.status,'game':{'available':gs is not None,'state':gs or {}}})
            svc.heartbeat(epoch,application_error=launcher.error)
    finally:catalog.close();targets.close();launcher.close();game.invalidate_gaze();game.socket.close();pointer.close();xd.close();sub.close();ack.close();svc.close()

if __name__=='__main__':main()
