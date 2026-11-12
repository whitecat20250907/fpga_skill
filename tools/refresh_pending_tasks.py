"""Render pending-only tasks/ETAs from the authoritative full ledger.

Completion never comes from estimates or this renderer. Refresh after each
authoritative status change; accepted/waived/completed rows disappear without
deleting historical evidence. No hardware, processes or external service used.
"""
import datetime
import hashlib
import json
from pathlib import Path

R=Path(__file__).resolve().parents[1]
DONE={'DONE','WAIVED','ACCEPTED','USER_ACCEPTED','USER_ACCEPTED_HARDWARE','NOT_APPLICABLE_VERIFIED'}
CANCELLED={'REMOVED_FROM_SCOPE'}
DEFERRED={'DEFERRED_BY_USER'}
RK_DONE=DONE|{'USER_CONFIRMED_CSI0','USER_CORRECTED_CABLE','CSI0_I2C8_ID_CONFIRMED','READONLY_IDENTIFIED'}
PRIORITY=['U05','U02','U03','U01','U04','G01','G02','G03','G04','T04','T01','T02','T03','T05','T06','T07','T08','T10','F11','F10','F16','F17',
          'K09','K01','K04','K05','K06','K07','K08','S01','S02','S03','S04','S05',
          'L11','I02','I03','I04','I05','I06','I07','D01','C03','C04','C05','C06','D02','D03','D04']
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def ref(p):return dict(path=str(Path(p).resolve()),sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest())
def pending(row,kind):
    status=row['status']
    if status in CANCELLED|DEFERRED or row.get('scheduling_status')=='DEFERRED_BY_USER':return False
    return status not in (RK_DONE if kind=='RK' else DONE) and not (kind=='RK' and status.startswith('PASS_'))
def table(rows):
    return ['| ID | 未完成任务 | 预计剩余时间 |','|---|---|---|']+[
        '| '+x['id']+' | '+x['remaining_task'].replace('|','／')+' | '+x['estimate'].replace('|','／')+' |' for x in rows]
def test_table(rows):
    return ['| ID | 待实测项目 | 预计测试时间 | 前置条件 |','|---|---|---|---|']+[
        '| '+x['id']+' | '+x['remaining_task'].replace('|','／')+' | '+x['estimate'].replace('|','／')+' | '+x['prerequisites'].replace('|','／')+' |' for x in rows]
def replace(path,data):
    temp=path.with_name(path.name+'.tmp');temp.write_bytes(data);temp.replace(path)

def render_closeout(ledger,source):
    """Show the user's current closeout groups, without rewriting history."""
    policy_ref=ledger.get('closeout_execution')
    if not policy_ref:return False
    assert ref(policy_ref['path'])==policy_ref,'Closeout policy bytes changed'
    policy=load(policy_ref['path']);rows=policy['remaining']
    assert len({row['order'] for row in rows})==len(rows)
    rows=sorted(rows,key=lambda row:row['order'])
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')
    items=[dict(id='/'.join(row['ids']),order=row['order'],remaining_task=row['title'],
                current_state=row['state'],estimate=row['estimate'],source_ids=row['ids']) for row in rows]
    lines=['# 当前收尾任务','',f'更新时间：{now}。依据完整账本 v{ledger["revision"]} 及用户最新收尾安排。','',
           '只列本轮仍需处理的项目。历史任务状态保留在完整账本；移出当前展示不代表技术验收通过。','',
           '| 顺序 | 范围 | 待完成任务 | 当前进展 | 时间与依赖 |','|---|---|---|---|---|']
    for row in items:
        lines.append('| '+' | '.join(str(row[k]).replace('|','／') for k in ('order','id','remaining_task','current_state','estimate'))+' |')
    replacement=policy.get('replaced_task5')
    if replacement:
        lines+=['','原第5项真人重复验收已按用户要求替换为展示流程设计，设计已完成，不再作为待办。']
    lines+=['','不再追加最低FPGA占用率目标、任务8/9/10或重复的大范围回归。仅保留当前改动必要的构建、上板和数据链路检查。','']
    artifact=dict(updated_at=now,source_ledger=source,closeout_policy=policy_ref,current_main=items,
                  formal=[],system_roadmap=[],RK_subchecks=[],view='CURRENT_USER_CLOSEOUT',
                  historical_states_unchanged=True,replaced_task5=replacement)
    field=dict(updated_at=now,source_ledger=source,closeout_policy=policy_ref,current_main=[],formal=[],RK_subchecks=[],
               verification_included_in_closeout_ids=[row['id'] for row in items],classification_does_not_grant_acceptance=True)
    assert ref(source['path'])==source
    replace(R/'PENDING_TASKS.json',(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    replace(R/'PENDING_TASKS.md','\n'.join(lines).encode('utf8'))
    replace(R/'PENDING_FIELD_TESTS.json',(json.dumps(field,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    replace(R/'PENDING_FIELD_TESTS.md',('# 当前必要实测\n\n必要的上板、收图、曝光响应和显示检查已经包含在[当前收尾任务](PENDING_TASKS.md)中，不重复列项。\n\n按用户要求，不再安排手势与医学拍摄流程的真人重复验收；具体问题由用户反馈后维护。历史验收状态保留在完整账本。\n').encode('utf8'))
    print(json.dumps(dict(status='REFRESHED_CURRENT_USER_CLOSEOUT',revision=ledger['revision'],current_main=len(items),historical_states_unchanged=True),ensure_ascii=False))
    return True

def main():
    progress=load(R/'GOAL_PROGRESS.json');source=progress['full_task_ledger']
    assert ref(source['path'])==source,'Full ledger bytes changed'
    ledger=load(source['path'])
    if render_closeout(ledger,source):return
    formal_ref=ledger['additional_formal_goal'];assert ref(formal_ref['path'])==formal_ref
    formal=load(formal_ref['path'])['tasks'];estimates=load(R/'PENDING_TASK_ESTIMATES.json')
    schedule_path=R/'TASK_SCHEDULING.json'
    schedule=load(schedule_path) if schedule_path.is_file() else {'entries':{}}
    entries=schedule['entries']
    assert schedule.get('classification_does_not_grant_acceptance',True)
    sources={'main':ledger['tasks'],'formal':formal,'RK':ledger['RK_camera_subchecks']};out={}
    for kind,rows in sources.items():
        out[kind]=[]
        for row in rows:
            if not pending(row,kind):continue
            estimate=estimates[kind].get(row['id'])
            assert estimate is not None,'Add an honest ETA before publishing a new pending task: '+row['id']
            title=row.get('title',row.get('task',row.get('check','')))
            name,time=(title,estimate) if kind=='RK' else estimate
            phase=entries.get(row['id'],{})
            bucket=phase.get('bucket','development')
            assert bucket in ('development','field_test'),(row['id'],bucket)
            out[kind].append(dict(id=row['id'],remaining_task=phase.get('title',name),estimate=phase.get('estimate',time),
                scope=row.get('scope'),parent_id=row.get('parent_id'),bucket=bucket,
                prerequisites=phase.get('prerequisites',''),classification_basis=phase.get('basis','Implementation or integration still incomplete'),
                acceptance_status_unchanged=row['status']))
    field={kind:[x for x in rows if x['bucket']=='field_test'] for kind,rows in out.items()}
    out={kind:[x for x in rows if x['bucket']=='development'] for kind,rows in out.items()}
    ordinary=[x for x in out['main'] if x['scope'] not in ('system_roadmap','acceptance_view')]
    acceptance=[x for x in out['main'] if x['scope']=='acceptance_view']
    roadmap=[x for x in out['main'] if x['scope']=='system_roadmap']
    rank={name:i for i,name in enumerate(PRIORITY)};ordinary.sort(key=lambda x:(rank.get(x['id'],len(rank)),x['id']))
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')
    lines=['# 待完成任务与预计时间','',f'更新时间：{now}。依据任务账本 v{ledger["revision"]}。','',
        estimates['basis']+' 1工作日按约8小时估算；这是范围估计，不是固定完成日期。','',
        '本页只列仍需开发、修复、集成或交付的工作。软件已完成且只差验证的项目见 [待实测任务单](PENDING_FIELD_TESTS.md)。暂缓项目保留历史记录，不列入两份当前清单。分类不等于验收通过。','',
        '## 项目与比赛主任务','',*table(ordinary),'']
    if out['formal']:lines+=['## 视线、手势与Freeciv演示','',*table(out['formal']),'']
    if roadmap:lines+=['## 后续系统路线','',*table(roadmap),'']
    if out['RK']:lines+=['<details>','<summary>未完子检查（已包含在对应主任务中）</summary>','',*table(out['RK']),'','</details>','']
    artifact=dict(updated_at=now,source_ledger=source,source_formal_ledger=formal_ref,
        estimate_basis=estimates['basis'],estimate_source=ref(R/'PENDING_TASK_ESTIMATES.json'),
        current_main=ordinary,formal=out['formal'],system_roadmap=roadmap,RK_subchecks=out['RK'],
        acceptance_views_included_in_implementation_tasks=acceptance,
        field_test_view='PENDING_FIELD_TESTS.json',scheduling_source=ref(schedule_path) if schedule_path.is_file() else None)
    field_main=[x for x in field['main'] if x['scope']!='acceptance_view']
    field_main.sort(key=lambda x:(rank.get(x['id'],len(rank)),x['id']))
    test_lines=['# 待实测任务与预计时间','',f'更新时间：{now}。依据任务账本 v{ledger["revision"]}。','',
        '本页列已有软件/RTL/测试工具、剩余工作主要是目标板、实物或真人验证的项目。前置依赖未满足时继续等待，不计技术通过。需要继续改代码或补集成的项目见 [待完成任务单](PENDING_TASKS.md)。','',
        estimates['basis']+' 同轮验证共享时间，不将重叠项相加。','',
        '## FPGA、传输、屏幕与比赛实测','',*test_table([x for x in field_main if not x['id'].startswith('G')]),'',
        '## 游戏实机回归','',*test_table([x for x in field_main if x['id'].startswith('G')]),'']
    if field['formal']:test_lines+=['## 真人视线与手势','',*test_table(field['formal']),'']
    tests=dict(updated_at=now,source_ledger=source,source_formal_ledger=formal_ref,
        estimate_basis=estimates['basis'],scheduling_source=ref(schedule_path) if schedule_path.is_file() else None,
        current_main=field_main,formal=field['formal'],RK_subchecks=field['RK'],
        classification_does_not_grant_acceptance=True)
    development_ids={x['id'] for kind in out.values() for x in kind}
    field_ids={x['id'] for kind in field.values() for x in kind}
    assert not development_ids&field_ids,'A task must not appear in both views'
    assert ref(progress['full_task_ledger']['path'])==source
    replace(R/'PENDING_TASKS.json',(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    replace(R/'PENDING_TASKS.md','\n'.join(lines).encode('utf8'))
    replace(R/'PENDING_FIELD_TESTS.json',(json.dumps(tests,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    replace(R/'PENDING_FIELD_TESTS.md','\n'.join(test_lines).encode('utf8'))
    print(json.dumps(dict(status='REFRESHED_DEVELOPMENT_AND_FIELD_TEST_VIEWS',revision=ledger['revision'],current_main=len(ordinary),formal=len(out['formal']),system_roadmap=len(roadmap),RK_subchecks=len(out['RK']),field_main=len(field_main),field_formal=len(field['formal']),acceptance_views_not_duplicated=len(acceptance)),ensure_ascii=False))
if __name__=='__main__':main()
