import time
from core.config import load
from core.hmibus import Publisher,Subscriber
from core.service import Service
from .engine import Engine
from ui.feedback import feedback
from core.board_keys import BoardKeys,KEY_LABELS

def main():
    c=load();run=c['paths']['run'];e=Engine(c);svc=Service('engine',c)
    from core.maintenance_resume import take,restore_engine
    maintenance=take(run,'engine')
    from core.hotkeys import Hotkeys
    keys=Hotkeys();board_keys=BoardKeys()
    sub=Subscriber(['app.targets','vision.face','vision.gaze','vision.hands','vision.stroke','sys.metrics','hmi.ack','cmd.system','cmd.operator'],run=run)
    pubs={t:Publisher(t,run=run) for t in ['hmi.state','hmi.action','cmd.gaze']}
    transition=None
    try:
        while svc.running:
            start=time.monotonic_ns();changed=sub.poll(5)
            now=time.monotonic_ns()
            for command in keys.poll():e.system(command,time.monotonic_ns())
            for command in board_keys.poll():
                svc.log('board_key',command=command,device='adc-keys')
                e.system(command,time.monotonic_ns())
            for key,msg in changed.items():
                if key.startswith('sys.metrics.'):e.feed('sys.metrics',msg,now)
            if maintenance and e.epoch and not e._health(now):
                restore_engine(e,maintenance,now);maintenance=None
            for topic in ('app.targets','vision.face','vision.gaze','vision.hands'):
                if topic in changed:e.feed(topic,changed[topic],now)
            for topic in ('vision.stroke','hmi.ack','cmd.system','cmd.operator'):
                for msg in sub.events(topic):e.feed(topic,msg,now)
            state=e.tick(time.monotonic_ns());state['feedback']=feedback(state)
            session=state.get('target_session',{})
            observed=(state['state'],session.get('phase'),session.get('hand'),session.get('hand_status'),bool(state.get('calibration_intent')))
            if observed!=transition:
                svc.log('interaction_transition',state=state['state'],eye_phase=session.get('phase'),hand=session.get('hand'),hand_status=session.get('hand_status'),detail=state.get('toast',''),health=state.get('health'),calibrated=state.get('calibrated'),lock_id=session.get('lock_id'))
                transition=observed
            state['controls']={'adc_keys_ready':board_keys.fd is not None,'adc_keys_error':board_keys.error,
                               'keys':KEY_LABELS}
            pubs['hmi.state'].publish(state)
            for msg in e.out:pubs['hmi.action'].publish(msg);svc.log('action',action=msg)
            for msg in e.commands:pubs['cmd.gaze'].publish(msg)
            e.out.clear();e.commands.clear();svc.heartbeat(e.epoch,state=e.state)
            time.sleep(max(0,(10_000_000-(time.monotonic_ns()-start))/1e9))
    finally:
        board_keys.close();keys.close();sub.close();svc.close()
        for p in pubs.values():p.close()

if __name__=='__main__':main()
