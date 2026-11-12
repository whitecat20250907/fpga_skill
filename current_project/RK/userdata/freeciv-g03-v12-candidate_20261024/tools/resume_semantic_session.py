"""Resume only the interrupted screenshot/final assertion; preserve failed evidence."""
import json,os,sys,time
from pathlib import Path
sys.path.insert(0,'/home/linaro/pcie_fix_20261003')
import semantic_board_session as owned
from test_live_input import Link,need
root=owned.ROOT;out=owned.OUT;link=Link()
env,_=owned.environment(126531);os.environ.update(env)
registration=json.loads((out/'owner.json').read_text());report=json.loads((out/'result.json').read_text())
need(report['status']=='FAILED_PRESERVED' and "No module named 'PIL'" in report['error'],'Unexpected previous failure')
need(owned.identity(registration['launcher']['pid'])==registration['launcher'],'Owned launcher changed')
need(not (out/'resume_result.json').exists(),'Preserve resume evidence')
report['resumed_after']='Screenshot helper used system Python without Pillow; existing app_venv used, no installation.'
try:
    state=link.state();need(state.get('phase')!='menu' and state['moves']==6,'Scenario changed since interrupted test')
    link.sequence=int(state['last_event']);link.event('cancel');state=link.event('wake')
    target=max((t for t in state['targets'] if t['kind']==0),key=lambda t:t['x'])
    until=time.monotonic()+.4
    while time.monotonic()<until:
        link.raw(f"gaze2 {time.monotonic_ns()//1000} {target['x']/state['map'][2]:.8f} {target['y']/state['map'][3]:.8f}");time.sleep(.03)
    owned.screenshot(out/'stable_target.png')
    # Capturing the desktop can itself exceed the 250ms source-age budget.
    until=time.monotonic()+.3
    while time.monotonic()<until:
        link.raw(f"gaze2 {time.monotonic_ns()//1000} {target['x']/state['map'][2]:.8f} {target['y']/state['map'][3]:.8f}");time.sleep(.03)
    after=link.event('confirm');need(not after['awake'] and after['moves']<state['moves'],'Stable semantic movement did not execute')
    link.raw(f'event {link.sequence} confirm');time.sleep(.1);need(link.state()['moves']==after['moves'],'Repeated order')
    report['cases'].append(dict(name='stable_semantic_target_moves_once_then_sleeps',passed=True))
    report.update(status='PASS_REAL_NATIVE_SEMANTIC_SELECTION',final=after)
    report.pop('error',None);report.pop('traceback',None)
    owned.save('resume_result.json',report)
    # Leave the tested native game for now; its original real owner still waits.
    owned.save('ready.json',dict(status='TESTED_NATIVE_GAME_RUNNING',launcher=registration['launcher'],supervisor=registration['supervisor'],model=registration['model'],capture=registration['capture']))
    print(json.dumps(dict(status=report['status'],cases=len(report['cases']),moves_before=state['moves'],moves_after=after['moves'])))
finally:link.socket.close()
