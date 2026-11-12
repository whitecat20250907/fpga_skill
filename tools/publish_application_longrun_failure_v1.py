"""Preserve the real late capture failure and reopen its repair work."""
import copy
import datetime
import os
from pathlib import Path
import subprocess
import sys
from publish_video_running_v1 import R,Y,load,save,ref


def main():
    before=(R/'GOAL_PROGRESS.json').read_bytes();progress=load(R/'GOAL_PROGRESS.json');prior=progress['full_task_ledger']
    assert ref(prior['path'])==prior;ledger=copy.deepcopy(load(prior['path']));revision=ledger['revision']+1
    o=Y/'evidence/application_actual_v3';failure=load(o/'longrun_failure_01.json');end=failure['runtime_result']['capture_end']
    assert end['cleanup_errno']==110 and failure['runtime_result']['worker_alive'] is False
    ack_path=next(p for p in o.glob('rpc_*_sent.json') if load(p)['sequence']==19)
    ack=load(ack_path)['response'];assert not ack['ok'] and ack['phase']=='FAILED_RESOURCE_RETIRED_UNVERIFIED'
    after=load(o/'inspect_02.json')['files']['video_owner_state'];assert after['runtime'] is None and not after['main_handle_retained'] and not after['feature_session_retained']
    refs={k:ref(p) for k,p in dict(actual_failure=o/'longrun_failure_01.json',actual_pre_ack_empty_resources=o/'longrun_before_original_ack.json',
        actual_original_ack_refused_recovery=ack_path,actual_post_ack=o/'inspect_02.json',failed_CURRENT_selection=o/'longrun_failed_camera_selection.json').items()}
    event=dict(status='ACTUAL_LONGRUN_CAPTURE_FAILURE_NATIVE_CLEANUP_110_RECOVERY_NOT_YET_VALIDATED',references=refs,
        CURRENT=ref(R/'CURRENT_CAMERA.json'),capture_end=end,run_seconds=end['elapsed_ns']/1e9,
        sampled_rows_before_failure=failure['runtime_result']['samples'],board_ssh_alive=True,normal_runtime_PASS=False,
        original_main_returncode=1,auxiliaries_actually_waited=True,all_child_PIDs_and_device_FDs_absent=True,
        same_original_owner_retained=True,original_ack_called_once=True,original_failed_cleanup_preserved=True,
        late_hardware_recovery_gate_open=False,root_cause_proven=False,
        finding='C2H1 poll WB0/expected106 with MMIO completed106/idle; model-output timeout labeling can mask DMA read failure. Exact source/binary and interleaving audit in progress.',full_goal_complete=False)
    key=f'v{revision}_late_capture_failure_and_recovery_gate';ledger['evidence'][key]=event
    for task in ledger['tasks']:
        if task['id'] in ('T02','U01','U02','U03','U04','U05'):
            task.setdefault('evidence_keys',[]).append(key)
            task['current_state']='当前：第三代在约24.43分钟采集失败，native cleanup110原样保留，已由原ack回收真实Popen但恢复门禁拒绝，当前无健康模型。'+task['current_state']
    schedule=load(R/'TASK_SCHEDULING.json');estimates=load(R/'PENDING_TASK_ESTIMATES.json')
    for task_id in ('U01','U02','U03','U05'):
        row=schedule['entries'][task_id];row['prerequisites']='先修PCIe/模型包长期采集故障；'+row['prerequisites']
    schedule['entries']['U04']=dict(bucket='development',title='长测采集故障修复与孪生程序恢复',estimate='首版2–4小时（与T02共用）；真人随后30–90分钟',
        prerequisites='匹配SGDMA外模块独立构建与真实回收/强制quiesce证明；再受控启动并长测',basis='新应用24.43分钟后真实失败，需修复而非只等真人；UI/模型权重不随失败重做，非零cleanup不能伪造通过。')
    estimates['main']['U04']=[schedule['entries']['U04']['title'],schedule['entries']['U04']['estimate']]
    now=datetime.datetime.now(datetime.timezone.utc).isoformat();schedule['updated_utc']=now
    save(R/'TASK_SCHEDULING.json',schedule);save(R/'PENDING_TASK_ESTIMATES.json',estimates)
    ledger.update(revision=revision,previous_ledger=prior,updated_utc=now,publisher=ref(__file__),full_goal_complete=False)
    ledger['first_video_milestone']['actual_new_UI_application']=event
    ledger['next_safe_action']='保留同一空监督进程EX和失败cleanup110；验证独立teardown-only入口并原quiesce，再使用匹配头/源构建SGDMA修复。不得宣称已可拍或自动重启；游戏G01独立通过保持。'
    out=Path(prior['path']).parent.parent/f'goal_task_ledger_v{revision}';assert not out.exists();out.mkdir();save(out/'ledger.json',ledger)
    progress.update(observed_utc=now,full_task_ledger=ref(out/'ledger.json'),protected_CURRENT=ref(R/'CURRENT_CAMERA.json'))
    progress['active_work'].update(status='LONGRUN_PCIE_MODEL_CAPTURE_REPAIR',current_selected_runtime_is_live=False,actual_new_UI_application=event,next_action=ledger['next_safe_action'])
    progress['first_video_milestone']['actual_new_UI_application']=event
    progress['current_runtime_stop_rule']='原202401已执行一次真实ack并清child/session，当前仅空owner持EX，phase FAILED_RESOURCE_RETIRED_UNVERIFIED。cleanup110保留并阻止旧恢复窗；需新的经验证teardown-only恢复，不能复用旧已wait的Windows programmer或伪造正常close。'
    assert (R/'GOAL_PROGRESS.json').read_bytes()==before
    temp=R/'GOAL_PROGRESS.longrun_failure.tmp';save(temp,progress);os.replace(temp,R/'GOAL_PROGRESS.json')
    result=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(result.stdout);(out/'refresh.stderr').write_bytes(result.stderr);assert result.returncode==0
    for name in ('GOAL_PROGRESS.json','CURRENT_CAMERA.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json','TASK_SCHEDULING.json','PENDING_TASK_ESTIMATES.json'):
        source=R/name;(out/(source.stem+'_snapshot'+source.suffix)).write_bytes(source.read_bytes())
    save(out/'publication.json',dict(status=event['status'],revision=revision,full_goal_complete=False));print('LONGRUN_FAILURE_PUBLISHED',revision)


if __name__=='__main__':main()
