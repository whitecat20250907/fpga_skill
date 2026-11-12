"""Publish completed component evidence without signing complete integration."""
import copy
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

R=Path(__file__).resolve().parents[1]
S=R/'projects/rgb_area3_stream_20261022'


def ref(p):
    p=Path(p)
    return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def main():
    source_files={
        'ARM_build':S/'evidence/a3f1_receiver_build_ARM_v1/result.json',
        'ARM_worker':S/'evidence/guarded_worker_ARM_v1/result.json',
        'ARM_artifacts':S/'evidence/a3f1_ARM_artifacts_v1/result.json',
        'top_nonce':S/'evidence/source_bound_nonce_credit_v3/result.json',
        'preview_pairing_counterexample':S/'evidence/preview_source_pairing_v1/result.json',
        'preview_eof_counterexample':S/'evidence/preview_eof_loss_v1/result.json',
        'preview_design':S/'evidence/preview_source_design_v1/result.json',
        'component_report':S/'transport/ARM_COMPONENT_PROGRESS_20261023.md',
    }
    arm=load(source_files['ARM_build']);worker=load(source_files['ARM_worker']);artifacts=load(source_files['ARM_artifacts'])
    assert arm['architecture']=='aarch64' and arm['guard_cases']['checks']==24
    assert arm['original_main_identities_retained'] and not arm['devices_opened']
    assert worker['status']=='PASS_ARM_14_REAL_GUARDED_WORKER_START_FINISH_MEMFD_CASES'
    assert len(worker['cases'])==14 and all(x['status']=='PASS' and x['invalid_publications']==0 for x in worker['cases'])
    assert not worker['hardware_accessed'] and worker['original_main_identities_retained']
    assert worker['CURRENT_unchanged'] and arm['CURRENT_unchanged']
    assert artifacts['actual_ARM_execution'] and not artifacts['default_installed']
    assert ref(artifacts['archive']['path'])==artifacts['archive']
    assert all(ref(p['path'])==p for p in artifacts['binaries'])
    progress_path=R/'GOAL_PROGRESS.json';before=progress_path.read_bytes();progress=load(progress_path)
    previous=progress['full_task_ledger'];assert ref(previous['path'])==previous
    old=load(previous['path']);assert old['revision']==250
    ledger=copy.deepcopy(old);revision=251
    out=Path(previous['path']).parent.parent/f'goal_task_ledger_v{revision}';assert not out.exists()
    observation=dict(
        status='ARM_RECEIVER_24_GUARD_AND_14_LINUX_WORKER_COMPONENTS_PASSED_INTEGRATION_PENDING',
        references={k:ref(p) for k,p in source_files.items()},
        ARM_guard_cases=24,ARM_Linux_worker_memfd_cases=14,
        guard_receiver_default_installed=False,real_DMA_or_camera_or_NPU_benefit_accepted=False,
        blocked_real_DMA_cancel_proved=False,nonce_guard_live_integrated=False,
        preview_common_source_identity_implemented=False,full_goal_complete=False,
    )
    key='v251_ARM_receiver_components_and_separate_pending_views'
    for task in ledger['tasks']:
        if task['id']=='T02':
            task['previous_state_before_ARM_components']=task['current_state']
            task['current_state']='复用已有A3F1双通道。独立完整接收器在RK3576编译为AArch64，24项协议/顺序及14项真实Linux worker/memfd场景通过；候选包与实际二进制已归档、未替换默认。top真实控制区间已验证credit/busy并复现零/半写/重复nonce启用，独立guard正反例通过。原预览序号错误配对、丢EOF后同长度补零均有真实RTL反例。尚需同源metadata全链、nonce/guard完整工程接入与真实DMA安全启停，完整TD及实板/NPU收益未签；RK直连CSI/双摄暂缓。'
            task['ARM_guarded_receiver_components']=observation
            task['host_receiver_guard_ARM_component_tested']=True
            task['host_receiver_guard_deployed']=False
            task.setdefault('evidence_keys',[]).append(key)
    assert [(t['id'],t['status']) for t in ledger['tasks']]==[(t['id'],t['status']) for t in old['tasks']]
    schedule=load(R/'TASK_SCHEDULING.json');estimates=load(R/'PENDING_TASK_ESTIMATES.json')
    title='预览/模型同源身份、nonce守护与完整接收链集成'
    eta='1–2工作日（同源metadata、完整工程与真实DMA安全启停；ARM接收组件已完成）'
    schedule['entries']['T02'].update(title=title,estimate=eta,
        basis='ARM编译、24项guard与14项Linux worker/memfd已完成；仍缺共同来源全链、完整工程接线和真实DMA启停，不移入纯实测。')
    schedule['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    estimates['main']['T02']=[title,eta]
    save(R/'TASK_SCHEDULING.json',schedule);save(R/'PENDING_TASK_ESTIMATES.json',estimates)
    ledger.update(revision=revision,updated_utc=schedule['updated_utc'],previous_ledger=previous,
        publisher=ref(Path(__file__)),task_scheduling=ref(R/'TASK_SCHEDULING.json'),full_goal_complete=False)
    ledger['evidence'][key]=observation
    out.mkdir();save(out/'ledger.json',ledger)
    progress.update(observed_utc=ledger['updated_utc'],full_task_ledger=ref(out/'ledger.json'))
    active=progress['active_work']
    if 'latest_selected_runtime' in active:
        active['historical_selected_runtime_before_other_owner_trials']=active.pop('latest_selected_runtime')
    if 'no_active_CAD_owner' in active:
        active['historical_no_active_CAD_owner_observation']=active.pop('no_active_CAD_owner')
    # Another owner updates CURRENT independently. This is a local observation,
    # never a claim of current board health or permission to reuse old PIDs.
    current=load(R/'CURRENT_CAMERA.json')
    assert ref(current['selection']['path'])==current['selection']
    active['local_selected_runtime_pointer_observation']=dict(
        observed_utc=ledger['updated_utc'],selection=current['selection'],
        live_board_health_rechecked=False,historical_runtime_PIDs_must_not_be_reused=True)
    active.update(status=observation['status'],T02_ARM_component_observation=observation,
        next_action='按待完成单推进共同来源metadata、完整nonce/接收链和真实DMA启停；待实测单独执行。RK直连CSI/双摄继续暂缓，真人按用户稍后配合。')
    progress['pending_task_view'].update(estimate_catalog=ref(R/'PENDING_TASK_ESTIMATES.json'),
        scheduling_source=ref(R/'TASK_SCHEDULING.json'),generator=ref(R/'tools/refresh_pending_tasks.py'))
    assert progress_path.read_bytes()==before,'Root progress changed; do not overwrite another update'
    temp=R/'GOAL_PROGRESS.ARM_components.tmp';save(temp,progress);os.replace(temp,progress_path)
    p=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(p.stdout);(out/'refresh.stderr').write_bytes(p.stderr);assert p.returncode==0
    dev=load(R/'PENDING_TASKS.json');field=load(R/'PENDING_FIELD_TESTS.json')
    dids={x['id'] for k in ('current_main','formal','system_roadmap','RK_subchecks') for x in dev[k]}
    fids={x['id'] for k in ('current_main','formal','RK_subchecks') for x in field[k]}
    deferred=set(schedule['deferred_main_ids'])
    assert len(dids)==27 and len(fids)==17 and not dids&fids
    assert not (dids|fids)&deferred and not dev['RK_subchecks'] and not field['RK_subchecks']
    assert set(f'R{i:02}' for i in range(1,13))<=dids
    assert 'T02' in dids and {'G01','G02','G03','G04','M05','M08','M11','M12'}<=fids
    for name in ('GOAL_PROGRESS.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json','PENDING_TASK_ESTIMATES.json','TASK_SCHEDULING.json'):
        path=R/name;(out/(path.stem+'_snapshot'+path.suffix)).write_bytes(path.read_bytes())
    result=dict(status=observation['status'],revision=revision,development_tasks=len(dids),field_test_tasks=len(fids),
        overlap=[],deferred_RK_main_tasks=len(deferred),RK_subchecks_in_current_views=0,
        acceptance_statuses_unchanged=True,full_goal_complete=False)
    save(out/'publication.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
