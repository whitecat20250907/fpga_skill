"""One-shot maintenance continuity; never replay actions or old hand poses."""
import json,time
from pathlib import Path

def take(run,role):
    path=Path(run)/('maintenance_'+role+'.json')
    try:
        record=json.loads(path.read_text());path.unlink()
        if record['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():return None
        if not 0<=time.monotonic_ns()-record['created_ns']<=30_000_000_000:return None
        for pid,start in record['producers'].items():
            if Path('/proc/'+pid+'/stat').read_text().rsplit(')',1)[1].split()[19]!=start:return None
        return record
    except (OSError,ValueError,KeyError,IndexError):return None

def restore_engine(engine,record,now):
    if not record or engine.epoch!=record['state']['epoch'] or engine.broken:return False
    state=record['state']
    # Existing single-person gaze estimator remains running with its fitted
    # model. No pending action, arming pose, undo queue or click is replayed.
    if state.get('people')!='single' or state.get('estop'):return False
    engine.context=state['context'];engine.calibrated=bool(state.get('calibrated'))
    engine.calib=state.get('calib',{});engine.confirmed_calibration=engine.calibrated
    if state.get('target_session',{}).get('phase')=='LOCKED':
        engine.target_session=state['target_session'];engine.cursor=state['cursor']
        target=engine.target_session.get('target') or {};view=record.get('demo') or {}
        if view and (target.get('page')!=view.get('page') or target.get('case_id')!=view.get('case_id')):
            engine.target_session['target']={};engine.target_session['target_notice']='视图已切换，请眼控选择新目标'
    engine._state('IDLE' if engine.calibrated else 'ONBOARD',now)
    if engine.context in ('DEMO','GAME','BASIC'):
        engine.application_request_seq+=1
        engine.application_request=dict(id=f'{engine.action_namespace}:{engine.application_request_seq}',context=engine.context,src_ns=now)
    engine.toast='交互已恢复';return True

def restore_demo(demo,record):
    if not record:return False
    from core.targets import medical_spec
    state=record['demo']
    if state.get('case_id') not in {c['id'] for c in medical_spec().get('cases',[])}:return False
    if not 0<=state.get('page',-1)<len(medical_spec()['pages']):return False
    demo.state=state;demo.stop_rotation('');demo.continuous_zoom=None
    demo.state['revision']+=1
    return True
