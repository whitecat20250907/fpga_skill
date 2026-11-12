"""Apply the user's RK-CSI deferral and separate implementation from field tests."""
import collections
import copy
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

R=Path(__file__).resolve().parents[1]
DEFER={'K01','K04','K05','K06','K07','K08','S01','S02','S03','S04','S05'}


def load(p):return json.loads(p.read_text(encoding='utf8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def ref(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def main():
    progress_path=R/'GOAL_PROGRESS.json';before=progress_path.read_bytes();progress=load(progress_path)
    previous=progress['full_task_ledger'];assert ref(Path(previous['path']))==previous
    old=load(Path(previous['path']));ledger=copy.deepcopy(old);revision=old['revision']+1
    out=Path(previous['path']).parent.parent/f'goal_task_ledger_v{revision}';assert not out.exists()
    out.mkdir();now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    save(out/'before_pointer.json',progress)
    entries={}
    def field(id,title,estimate,prerequisites,basis):
        entries[id]=dict(bucket='field_test',title=title,estimate=estimate,prerequisites=prerequisites,basis=basis)
    field('L11','05/06例程7寸DSI实际画面确认','0.5–1小时','现场看屏；记录测试图和相机画面','数字/CRC与现有构建证据已留存，仅缺光学外观确认。')
    for id,title,estimate,prerequisite in [
        ('G01','招募面板、四兵种购买/出兵与规则回归','2–4小时','现用新版Freeciv'),
        ('G02','占点收入、持续增援与基地攻防回归','3–6小时','现用新版Freeciv；与G04同局'),
        ('G03','远程扣血、移动/攻击边界与战斗风险回归','3–6小时','现用新版Freeciv；与G04同局'),
        ('G04','单/双人完整胜负、资源与真人并行延迟','4–8小时','G01–G03回归；真人延迟待个人标定')]:
        field(id,title,estimate,prerequisite,'新版功能已实现并在ARM编译、部分原生回合/动作通过；当前缺口为完整规则/战役及性能回归，失败则转回修复清单。')
    for id,title,estimate,prerequisite in [
        ('T01','无损压缩高熵输入、回退与解压实测','4–8小时','T04可上板版本；与T05同轮'),
        ('T03','FPGA CSI压缩通路容量、CDC与背压实测','4–8小时','T04可上板版本'),
        ('T05','RK解包后完整ROI的颜色、像素和包校验','4–8小时','T04整链可运行；原始帧/解包对照'),
        ('T06','同一压缩图像的RK NPU检测正例','2–4小时','T05通过；已知测试目标'),
        ('T07','压缩链300–600秒稳定长测','1–2小时','T05、T06通过'),
        ('T10','源SOF到RK接收逐帧延迟实测','2–4小时','T08时钟查询与T05通过'),
        ('U04','MIPI实时孪生实屏、主程序并行与长测','4–8小时','U02/U03完整接入；真实人脸、双眼和手'),
        ('D01','赛项3–6实测指标、资源/压缩率/时延报告','4–8小时','T06、T07、T10；共用实测数据')]:
        field(id,title,estimate,prerequisite,'当前账本已有对应算法/协议/接收或测量工具证据；本项剩余是同一整链的实机验证或实测报告，依赖未通过不表示已可执行。')
    for id,title,estimate,prerequisite in [
        ('M05','真人ROI与当前PCIe到NPU输入验证','1–2小时','完整人脸/双眼入镜；现用模型'),
        ('M08','个人标定、20点留出精度与稳定性','2–4小时','用户配合，光照与姿态稳定'),
        ('M11','真人视线、五手势与Freeciv联合试玩','2–4小时','M08；可选入口正常启停验证'),
        ('M12','真人游戏成功率、误触、延迟与报告','2–4小时','与M11同轮，不重复计工时')]:
        field(id,title,estimate,prerequisite,'原模型、标定/游戏适配及评测路径已实现；真人/生产入口行为尚未验证，未计验收通过。')
    for id,title,estimate in [
        ('T04','压缩完整工程的剩余物理审查与可上板交付','0.5–1工作日（物理审查与交付准备）'),
        ('F10','非空形态学候选的完整TD、时序与验证接入','4–8小时（完成自身布线/位流和非空采样接入）'),
        ('M13','工作站旧游戏残留清理与可选入口维护收尾','1–2小时（真人实测分列M11/M12/G04）'),
        ('R01','同源人脸/关键点跟踪与操作者ID','1–2工作日（当前PCIe图像，不依赖副摄恢复）'),
        ('R03','同源手部21点、捏合滞回、遮挡与手势整合','2–4工作日（当前PCIe图像，真人验证另计）')]:
        entries[id]=dict(bucket='development',title=title,estimate=estimate,
            basis='仍有集成、修复、清理或实现缺口；仅相关实测部分进入待实测单。')
    schedule=dict(updated_utc=now,user_request='RK端CSI相关暂不做；软件完成只待实测的任务分成独立清单；整合重复工作。',
        classification_does_not_grant_acceptance=True,
        default_bucket='development',deferred_main_ids=sorted(DEFER),
        deferred_subchecks='RK_camera_subchecks: all excluded from current views, historical evidence preserved',
        formal_M13_scope='Only implementation/cleanup remainder appears here. Human game tests are M11/M12/G04; M13 remains the historical parent.',
        entries=entries)
    save(R/'TASK_SCHEDULING.json',schedule)
    changed=[]
    for task in ledger['tasks']:
        tid=task['id']
        if tid in DEFER:
            assert task['status'] not in {'DONE','WAIVED','REMOVED_FROM_SCOPE'}
            task['deferred_by_user']=dict(date='2026-10-23',previous_status=task['status'],previous_scope=task['scope'],
                reason='用户要求RK端CSI相关全部移出当前待完成清单，暂不开展。',resume_requires_user=True)
            task['status']='DEFERRED_BY_USER';task['scope']='deferred_by_user';changed.append(tid)
        if tid=='R01':
            task['previous_secondary_CSI_dependency']=task.get('depends_on',[])
            task['depends_on']=[x for x in task.get('depends_on',[]) if x not in DEFER]+['U02']
            task['current_state']='保留人脸关键点、跟踪与操作者身份功能，统一使用当前FPGA→PCIe同源图像；不再以RK直连CSI或双摄恢复为前置。现有NPU检测/主脸出口已有证据，真实身份关联及完整控制权逻辑仍待。'
        if tid=='R03':
            task['done_when']=[x.replace('真实副摄关键点','当前PCIe同源图像关键点') for x in task['done_when']]
            task['current_state']='保留现有NPU手部关键点与原手势定义，使用当前PCIe同源图像；捏合滞回、遮挡和完整手势控制整合仍须核对，不等待RK直连CSI。'
        if tid=='D03':
            task['deferred_dependency_removed']=sorted(set(task.get('depends_on',[]))&DEFER)
            task['depends_on']=[x for x in task.get('depends_on',[]) if x not in DEFER]
        if tid in entries:task['scheduling_bucket']=entries[tid]['bucket']
    assert set(changed)==DEFER
    for check in ledger['RK_camera_subchecks']:
        check['scheduling_status']='DEFERRED_BY_USER';check['scheduling_reason']='2026-10-23用户暂缓RK直连CSI及双摄路线；历史验证状态不改。'
    for a,b in zip(old['tasks'],ledger['tasks']):
        assert a['id']==b['id']
        if a['id'] not in DEFER:assert a['status']==b['status']
    active=[t for t in ledger['tasks'] if t['status'] not in {'REMOVED_FROM_SCOPE','DEFERRED_BY_USER'}]
    ledger['active_main_task_count']=len(active)
    ledger['active_main_status_counts']=dict(collections.Counter(t['status'] for t in active))
    ledger['scope_status_counts']={scope:dict(collections.Counter(t['status'] for t in ledger['tasks'] if t['scope']==scope)) for scope in sorted({t['scope'] for t in ledger['tasks']})}
    ledger['deferred_main_task_count']=len(DEFER)
    scope=dict(status='CURRENT_SCOPE_RK_DIRECT_CSI_AND_DUAL_CAMERA_DEFERRED',date='2026-10-23',
        previous_scope=old['current_scope'],deferred_main_ids=sorted(DEFER),
        historical_main_tasks=94,active_main_tasks=len(active),removed_main_tasks=8,deferred_main_tasks=len(DEFER),
        retained='FPGA CSI/PCIe主链、压缩/NPU/游戏/手头眼孪生、多屏/语音/多人和高阶交互。',
        resume_rule='RK直连CSI及双摄只有用户明确恢复后再开展；隔离配置继续保留。')
    save(out/'current_scope.json',scope)
    ledger.update(revision=revision,updated_utc=now,previous_ledger=previous,publisher=ref(Path(__file__)),
        current_scope=ref(out/'current_scope.json'),task_scheduling=ref(R/'TASK_SCHEDULING.json'),full_goal_complete=False)
    key=f'v{revision}_user_RK_CSI_deferral_and_two_task_views'
    ledger['evidence'][key]=dict(user_scope_change=True,deferred_main_ids=sorted(DEFER),
        task_scheduling=ref(R/'TASK_SCHEDULING.json'),technical_acceptance_granted=False,
        no_hardware_or_process_changes=True,previous_goal_turn='PROGRESS',previous_commit='1e837aa3971f6d249579b58477beaab5af4e7dd1')
    save(out/'ledger.json',ledger)
    estimates_path=R/'PENDING_TASK_ESTIMATES.json';estimates=load(estimates_path)
    for id in ('R01','R03','T04','F10'):
        estimates['main'][id]=[entries[id]['title'],entries[id]['estimate']]
    estimates['formal']['M13']=[entries['M13']['title'],entries['M13']['estimate']]
    save(estimates_path,estimates)
    with (R/'PROJECT_SCOPE.md').open('a',encoding='utf8') as stream:
        stream.write('''

## 2026-10-23 当前执行范围与清单分离

用户明确暂不开展RK直连CSI相关工作。K01、K04–K08、S01–S05共11项未完主任务及全部RK摄像头细项移出当前清单，标为DEFERRED_BY_USER；K02/K03历史通过记录、已移出的K09及全部故障证据保留，不计为新增完成。恢复须由用户明确提出，既有CSI/AIQ隔离继续保持。

当前保留FPGA摄像头→PCIe的主图像链、人脸/手/眼与NPU、压缩、Freeciv、实时数字孪生、多屏、语音、多人及高阶交互。R01/R03使用当前同源PCIe图像；经验整理不再被暂缓双摄长测阻塞。

PENDING_TASKS.md只列仍需开发、修复、集成或交付的工作；PENDING_FIELD_TESTS.md列已有软件/RTL和工具、剩余主要为实物/目标板/真人验证的工作，并明确前置条件。分类不修改验收结论；测试失败需要改代码时回到开发清单。TASK_SCHEDULING.json维护分类，refresh_pending_tasks.py同时生成两份MD/JSON，避免后续账本刷新恢复旧混排。
''')
    with (R/'AGENTS.md').open('a',encoding='utf8') as stream:
        stream.write('''

## 2026-10-23 用户暂缓RK直连CSI并拆分清单

- RK直连CSI及双摄路线K01、K04–K08、S01–S05和RK_camera_subchecks暂缓，不出现在当前待完成或待实测清单；DEFERRED_BY_USER不计完成，不恢复摄像头/AIQ，只有用户明确恢复后再开展。已通过的K02/K03和原取消K09保留历史。
- FPGA CSI/PCIe主链继续推进。人脸/手势等保留功能使用当前PCIe同源图像，不能因暂缓副摄把多屏、语音、多人或完整项目范围删除。
- TASK_SCHEDULING.json区分development和field_test。PENDING_TASKS.md只显示开发/修复/集成/交付；PENDING_FIELD_TESTS.md显示软件已实现、等待实机/真人的验证及其前置条件。两份JSON同名生成，分类不改变原验收状态；失败需改实现则移回development。
- 每次更新账本仍运行tools/refresh_pending_tasks.py，同时维护两份清单。M13父任务的真人联动由M11/M12/G04测试视图承接，不把同轮测试重复累加工时。
''')
    progress['scope_counts'].update(active_main_tasks=len(active),deferred_main_tasks=len(DEFER))
    progress.update(observed_utc=now,full_task_ledger=ref(out/'ledger.json'),current_scope=ref(out/'current_scope.json'),full_goal_complete=False)
    progress['pending_task_view'].update(path=str(R/'PENDING_TASKS.md'),json_path=str(R/'PENDING_TASKS.json'),
        generator=ref(R/'tools/refresh_pending_tasks.py'),estimate_catalog=ref(estimates_path),
        field_test_path=str(R/'PENDING_FIELD_TESTS.md'),field_test_json_path=str(R/'PENDING_FIELD_TESTS.json'),
        scheduling_source=ref(R/'TASK_SCHEDULING.json'))
    progress['active_work']['task']='T02 independent checks on existing A3F1 channel; genuine-feature UI integration'
    progress['active_work']['RK_direct_CSI_deferred_by_user']=True
    progress['active_work']['user_task_view_reorganization']=key
    assert progress_path.read_bytes()==before,'Another publisher changed the pointer; retain evidence and rebind'
    temp=R/'GOAL_PROGRESS.task_views.tmp';save(temp,progress);os.replace(temp,progress_path)
    run=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(run.stdout);(out/'refresh.stderr').write_bytes(run.stderr);assert run.returncode==0,run.stderr.decode(errors='replace')
    dev=load(R/'PENDING_TASKS.json');tests=load(R/'PENDING_FIELD_TESTS.json')
    ids=lambda a:{t['id'] for key in ('current_main','formal','system_roadmap','RK_subchecks') for t in a.get(key,[])}
    dids,tids=ids(dev),ids(tests)
    assert not dids&tids and not (dids|tids)&DEFER
    assert not dev['RK_subchecks'] and not tests['RK_subchecks']
    assert {'T02','T04','U02','U03','R09','R10','R11'}<=dids
    assert {'L11','G01','G02','G03','G04','U04','M05','M08','M11','M12'}<=tids
    expected={t['id'] for t in ledger['tasks'] if t['status'] not in {'DONE','WAIVED','REMOVED_FROM_SCOPE','DEFERRED_BY_USER'} and t['scope']!='acceptance_view'}
    formal=load(Path(ledger['additional_formal_goal']['path']))['tasks']
    expected|={t['id'] for t in formal if t['status'] not in {'DONE','WAIVED'}}
    assert dids|tids==expected,(sorted(expected-(dids|tids)),sorted((dids|tids)-expected))
    for name in ('GOAL_PROGRESS.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json','PENDING_TASK_ESTIMATES.json','TASK_SCHEDULING.json','PROJECT_SCOPE.md','AGENTS.md'):
        path=R/name;(out/(path.stem+'_snapshot'+path.suffix)).write_bytes(path.read_bytes())
    save(out/'publication.json',dict(status='PUBLISHED_TWO_DISJOINT_TASK_VIEWS_RK_DIRECT_CSI_DEFERRED',revision=revision,
        implementation_tasks=len(dids),field_test_tasks=len(tids),deferred_main_tasks=len(DEFER),
        remaining_active_task_ids_preserved=True,technical_acceptance_granted=False,full_goal_complete=False))
    print(json.dumps(dict(revision=revision,implementation=len(dids),field_tests=len(tids),deferred=len(DEFER),status='TWO_TASK_VIEWS_VALIDATED')))


if __name__=='__main__':main()
