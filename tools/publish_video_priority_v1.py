"""Apply the user's twenty-hour video milestone without removing full scope."""
import copy
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];Y=R/'projects/twb_feature_integration_20261023'
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def ref(p):
    p=Path(p);return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
    before=(R/'GOAL_PROGRESS.json').read_bytes();progress=load(R/'GOAL_PROGRESS.json');previous=progress['full_task_ledger']
    assert ref(previous['path'])==previous
    old=load(previous['path']);ledger=copy.deepcopy(old);revision=old['revision']+1
    out=Path(previous['path']).parent.parent/f'goal_task_ledger_v{revision}';assert not out.exists()
    milestone=dict(priority='HIGHEST_USER_DEADLINE',requested_local='2026-10-23T18:06:43+08:00',
        deadline_local='2026-10-24T14:06:43+08:00',deadline_utc='2026-10-24T06:06:43Z',
        primary_tasks=['U05','U02','U03','U04','G01','G02','G03','G04','M11'],
        report=ref(Y/'VIDEO_V1_DEADLINE.md'),first_video_board_run_accepted=False,
        full_goal_scope_retained=True,source='Explicit current user instruction: twenty hours, U05 and game first')
    ledger['first_video_milestone']=milestone
    for task in ledger['tasks']:
        if task['id'] in milestone['primary_tasks']:task['execution_priority']='VIDEO_V1_HIGHEST'
    assert [(x['id'],x['status']) for x in old['tasks']]==[(x['id'],x['status']) for x in ledger['tasks']]
    schedule=load(R/'TASK_SCHEDULING.json');estimates=load(R/'PENDING_TASK_ESTIMATES.json')
    eta='首版板上整合4–8小时（已有3D内核；完整身份关联由R01/R11继续验收）'
    schedule['entries']['U05'].update(estimate=eta,basis='已有真实XYZ编码和RTL投影，当前缺口是主程序/发送端/实屏整合；用户指定最高优先、20小时首版视频。完整目标保留。')
    estimates['main']['U05'][1]=eta
    schedule['first_video_milestone']=milestone
    save(R/'TASK_SCHEDULING.json',schedule);save(R/'PENDING_TASK_ESTIMATES.json',estimates)
    generator=R/'tools/refresh_pending_tasks.py';text=generator.read_text(encoding='utf8')
    a="PRIORITY=['U01','U02','U05','U03','U04'";b="PRIORITY=['U05','U02','U03','U01','U04'"
    assert text.count(a)==1;text=text.replace(a,b);generator.write_text(text,encoding='utf8')
    ledger.update(revision=revision,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        previous_ledger=previous,publisher=ref(Path(__file__)),task_scheduling=ref(R/'TASK_SCHEDULING.json'),full_goal_complete=False)
    ledger['evidence'][f'v{revision}_user_twenty_hour_video_priority']=milestone
    out.mkdir();save(out/'ledger.json',ledger)
    progress.update(observed_utc=ledger['updated_utc'],full_task_ledger=ref(out/'ledger.json'),first_video_milestone=milestone)
    progress['active_work'].update(task='U05 actual board digital twin and Freeciv video first',
        status='HIGHEST_PRIORITY_TWENTY_HOUR_BOARD_VIDEO_DELIVERY_ACTIVE',
        next_action='复用已实测正式v12位流，接真实脸/手结果到MIPI；游戏独立完整战斗并行推进；新张量CAD/可选扩展不阻塞首版。')
    progress['pending_task_view'].update(generator=ref(generator),estimate_catalog=ref(R/'PENDING_TASK_ESTIMATES.json'),scheduling_source=ref(R/'TASK_SCHEDULING.json'))
    assert (R/'GOAL_PROGRESS.json').read_bytes()==before
    temporary=R/'GOAL_PROGRESS.video_priority.tmp';save(temporary,progress);os.replace(temporary,R/'GOAL_PROGRESS.json')
    p=subprocess.run([sys.executable,'-X','utf8','-B',str(generator)],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(p.stdout);(out/'refresh.stderr').write_bytes(p.stderr);assert p.returncode==0
    for name in ('GOAL_PROGRESS.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json','TASK_SCHEDULING.json','PENDING_TASK_ESTIMATES.json'):
        path=R/name;(out/(path.stem+'_snapshot'+path.suffix)).write_bytes(path.read_bytes())
    save(out/'publication.json',dict(status='USER_VIDEO_DEADLINE_AND_PRIORITY_APPLIED',revision=revision,
        deadline=milestone['deadline_local'],no_acceptance_status_changed=True,full_scope_retained=True,full_goal_complete=False))
    print(json.dumps(dict(status='VIDEO_FIRST_PRIORITY_SET',revision=revision,deadline=milestone['deadline_local']),ensure_ascii=False))
if __name__=='__main__':main()
