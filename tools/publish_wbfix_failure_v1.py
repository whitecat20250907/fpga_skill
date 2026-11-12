"""Publish the actual second DMA failure, preserving short tests and failed cleanup."""
import copy
import datetime
import os
from pathlib import Path
import subprocess
import sys

from publish_video_running_v1 import R, Y, load, save, ref


def main():
    before = (R / 'GOAL_PROGRESS.json').read_bytes()
    current_before = (R / 'CURRENT_CAMERA.json').read_bytes()
    progress = load(R / 'GOAL_PROGRESS.json')
    prior = progress['full_task_ledger']
    assert ref(prior['path']) == prior
    ledger = copy.deepcopy(load(prior['path']))
    revision = ledger['revision'] + 1
    out = Path(prior['path']).parent.parent / f'goal_task_ledger_v{revision}'
    assert not out.exists()
    o = Y / 'evidence/wbfix_actual_v1'
    failure = load(o / 'longrun_failure_01.json')
    end = failure['runtime_result']['capture_end']
    assert end['cleanup_errno'] == 110 and failure['runtime_result']['worker_alive'] is False
    ack_path = next(p for p in o.glob('rpc_*_sent.json') if load(p)['sequence'] == 10)
    ack = load(ack_path)['response']
    assert not ack['ok'] and ack['phase'] == 'FAILED_RESOURCE_RETIRED_UNVERIFIED'
    after = load(o / 'inspect_02.json')['files']['video_owner_state']
    assert after['runtime'] is None and not after['main_handle_retained'] and not after['feature_session_retained']
    audit = load(o / 'post_ack_resource_audit.json')
    assert audit['all_children_absent'] and not audit['device_fds'] and not audit['kernel_dma_tasks']
    assert audit['native_cleanup_errno'] == 110 and audit['normal_runtime_PASS'] is False
    short = load(o / 'initial_trajectory_120s/result.json')
    assert short['seconds'] >= 120 and short['gaze']['valid_rows'] == 0
    observer = load(o / 'longrun_35min/result.json')
    assert not observer['completed_requested_window'] and observer['samples'] == 0
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    refs = {k: ref(p) for k, p in dict(
        actual_failure=o / 'longrun_failure_01.json',
        full_failure_readonly=o / 'actual_failure_full_readonly_02.json',
        same_generation_short_measurement=o / 'initial_trajectory_120s/result.json',
        observer_first_window_refusal=o / 'longrun_35min/result.json',
        independent_local_audit=Y / 'evidence/wbfix_failure_audit_v1/audit.json',
        actual_original_ack=ack_path,
        actual_empty_resources=o / 'post_ack_resource_audit.json',
        actual_post_ack=o / 'inspect_02.json',
    ).items()}
    previous = load(R / 'CURRENT_CAMERA.json')
    assert previous['status'] == 'POINTER_ACTUAL_WBFIX_CANDIDATE_RUNNING_UNDER_LONGTEST'
    assert ref(previous['selection']['path']) == previous['selection']
    selected = load(previous['selection']['path'])
    selection = dict(
        status='ACTUAL_WBFIX_APPLICATION_FAILED_NO_HEALTHY_MODEL', observed_utc=now,
        previous_running_selection=previous['selection'],
        FPGA_SRAM_bit=selected['FPGA_SRAM_bit'],
        original_programming_receipt=selected['original_programming_receipt'],
        Flash_written=False, FPGA_programming_performed=False,
        active_driver=load(o / 'binding.json')['active_driver'],
        actual_failed_runtime=failure['state']['runtime'],
        empty_original_owner=audit['owner'], original_owner_EX_retained=True,
        normal_runtime_PASS=False, longrun_accepted=False, human_acceptance=False,
        original_cleanup_errno=110, references=refs,
        next_action='Validate a new explicit cleanup handoff and a transfer-checked completion-notification repair; no automatic restart.',
    )
    selected_path = o / 'longrun_failed_camera_selection.json'
    assert not selected_path.exists()
    save(selected_path, selection)
    pointer = dict(status='POINTER_ACTUAL_WBFIX_APPLICATION_FAILED_NO_HEALTHY_MODEL',
        selection=ref(selected_path),
        scope='Actual native cleanup110 retained after 594.430s; original ack reaped handles. Empty supervisor retains EX. Short byte comparisons passed; WB candidate did not establish longrun stability. No new FPGA programming or Flash.')
    assert (R / 'CURRENT_CAMERA.json').read_bytes() == current_before
    save(R / 'CURRENT_CAMERA.json', pointer)
    event = dict(
        status=selection['status'], observed_utc=now, references=refs,
        CURRENT=ref(R / 'CURRENT_CAMERA.json'),
        native_run_seconds=end['elapsed_ns'] / 1e9,
        actual_logged_gaze_samples=failure['runtime_result']['samples'],
        actual_native_cleanup_errno=110, original_main_returncode=1,
        original_ack_called_once=True, all_children_and_device_FDs_absent=True,
        kernel_DMA_tasks_absent=True, original_empty_supervisor_EX_retained=True,
        driver_no_clear_patch_sufficient=False, root_cause_proven=False,
        short_tensor_and_RGB_byte_tests_preserved=True,
        full_goal_complete=False,
        limitation='WB0 with MMIO completed32/idle recurred. Hardware writeback cause and precise pipe/DMA causal ordering are not proven. Sparse observer rejected terminal phase at its first sample; it did not measure a 35-minute window. No valid face/hand or gaze-NPU calls in the 120-second short sample.')
    key = f'v{revision}_wbfix_actual_failure_and_empty_resource_handoff'
    ledger['evidence'][key] = event
    state = ('当前：WB候选实际加载并通过128/192张量及六次RGB1080逐字节检查，'
             '同代120.533秒空场景采样通过，但native运行594.430秒后再次供帧失败、cleanup110。'
             '原ack已wait并清空句柄，当前仅空209770持EX；新通知处理候选及恢复入口待验证。')
    for task in ledger['tasks']:
        if task['id'] in ('T02', 'U01', 'U02', 'U03', 'U04', 'U05'):
            task.setdefault('evidence_keys', []).append(key)
            task['current_state'] = state + task['current_state']
    ledger['first_video_milestone']['actual_new_UI_application'] = event
    ledger['next_safe_action'] = selection['next_action']
    schedule = load(R / 'TASK_SCHEDULING.json')
    estimates = load(R / 'PENDING_TASK_ESTIMATES.json')
    schedule['entries']['U04'] = dict(bucket='development', title='DMA完成通知修复与孪生长期运行恢复',
        estimate='候选修复及板测1–3小时；真人随后30–90分钟（与T02共用）',
        prerequisites='当前cleanup110真实资源退出证明；新私有候选完成反例验证、原流程quiesce/字节检查与超过既往故障时长的持续运行',
        basis='去除poll清零候选仍在9分54秒失败，不能把短测试或用户旧基础骨架确认计为新版稳定性通过。')
    estimates['main']['U04'] = [schedule['entries']['U04']['title'], schedule['entries']['U04']['estimate']]
    schedule['updated_utc'] = now
    save(R / 'TASK_SCHEDULING.json', schedule)
    save(R / 'PENDING_TASK_ESTIMATES.json', estimates)
    ledger.update(revision=revision, previous_ledger=prior, updated_utc=now,
        publisher=ref(__file__), full_goal_complete=False)
    out.mkdir()
    save(out / 'ledger.json', ledger)
    progress.update(observed_utc=now, full_task_ledger=ref(out / 'ledger.json'), protected_CURRENT=ref(R / 'CURRENT_CAMERA.json'))
    progress['active_work'].update(status='LONGRUN_DMA_COMPLETION_NOTIFICATION_REPAIR',
        current_selected_runtime_is_live=False, actual_new_UI_application=event,
        next_action=ledger['next_safe_action'])
    progress['first_video_milestone']['actual_new_UI_application'] = event
    progress['current_runtime_stop_rule'] = '209770仅空监督进程持EX；seq10真实ack已wait并清句柄，cleanup110原样拒绝恢复。不得复用旧202401恢复器或已退出programmer；需验证本次独立handoff后显式全quiesce。'
    assert (R / 'GOAL_PROGRESS.json').read_bytes() == before
    temporary = R / 'GOAL_PROGRESS.wbfix_failure.tmp'
    save(temporary, progress)
    os.replace(temporary, R / 'GOAL_PROGRESS.json')
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(R / 'tools/refresh_pending_tasks.py')], cwd=R, capture_output=True)
    (out / 'refresh.stdout').write_bytes(result.stdout)
    (out / 'refresh.stderr').write_bytes(result.stderr)
    assert result.returncode == 0
    for name in ('GOAL_PROGRESS.json', 'CURRENT_CAMERA.json', 'PENDING_TASKS.md', 'PENDING_TASKS.json', 'PENDING_FIELD_TESTS.md', 'PENDING_FIELD_TESTS.json', 'TASK_SCHEDULING.json', 'PENDING_TASK_ESTIMATES.json'):
        source = R / name
        (out / (source.stem + '_snapshot' + source.suffix)).write_bytes(source.read_bytes())
    save(out / 'publication.json', dict(status=event['status'], revision=revision, full_goal_complete=False))
    print('WBFIX_ACTUAL_FAILURE_PUBLISHED', revision)


if __name__ == '__main__':
    main()
