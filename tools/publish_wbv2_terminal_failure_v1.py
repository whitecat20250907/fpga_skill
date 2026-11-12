"""Publish the actual WBv2 terminal failure without inferring its causal order."""
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
    o = Y / 'evidence/wbfix_actual_v2'
    failure = load(o / 'longrun_failure_01.json')
    report = failure['runtime_result']
    end = report['capture_end']
    assert report['worker_alive'] is False and end['cleanup_errno'] == 110
    assert end['elapsed_ns'] == 21061743377465 and report['samples'] == 631504
    assert 'stage=output_pipe_timeout' in report['worker_error']
    ack = load(o / 'rpc_0010_sent.json')
    assert ack['sequence'] == 10 and not ack['response']['ok']
    assert ack['response']['phase'] == 'FAILED_RESOURCE_RETIRED_UNVERIFIED'
    audit = load(o / 'post_ack_resource_audit.json')
    assert audit['all_children_absent'] and not audit['device_fds'] and not audit['kernel_dma_tasks']
    assert audit['owner']['pid'] == 214978 and audit['state']['runtime'] is None
    assert not audit['state']['main_handle_retained'] and not audit['state']['feature_session_retained']
    observer = load(o / 'longrun_35min_after_transport_gap/result.json')
    assert not observer['completed_requested_window'] and observer['samples'] == 35
    old = load(R / 'CURRENT_CAMERA.json')
    assert old['status'] == 'POINTER_ACTUAL_WBV2_APPLICATION_RUNNING_LONGRUN_PENDING'
    assert ref(old['selection']['path']) == old['selection']
    selected = load(old['selection']['path'])
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    refs = {name: ref(o / name) for name in ('binding.json','longrun_failure_01.json',
        'runtime_result_original.json','native_failure_full_report.json','rpc_0010_sent.json',
        'post_ack_resource_audit.json','inspect_03.json','longrun_35min_after_transport_gap/result.json',
        'longrun_35min_v2/result.json','same_generation_after_transport_gap.json','app38_symlink_audit.json')}
    next_action = 'Audit the actual native output-pipe and model-DMA causal order; prepare an exact new failed-generation handoff before any explicit recovery. Continue local software/game work; no automatic restart.'
    selection = dict(status='ACTUAL_WBV2_APPLICATION_FAILED_NO_HEALTHY_MODEL',observed_utc=now,
        previous_running_selection=old['selection'],FPGA_SRAM_bit=selected['FPGA_SRAM_bit'],
        original_programming_receipt=selected['original_programming_receipt'],
        Flash_written=False,FPGA_programming_performed=False,active_driver=selected['active_driver'],
        active_driver_build_id=selected['active_driver_build_id'],actual_failed_runtime=failure['state']['runtime'],
        empty_original_owner=audit['owner'],original_owner_EX_retained=True,
        normal_runtime_PASS=False,longrun_accepted=False,human_acceptance=False,
        original_cleanup_errno=110,references=refs,next_action=next_action)
    path = o / 'terminal_failed_camera_selection.json'
    assert not path.exists()
    save(path, selection)
    pointer = dict(status='POINTER_ACTUAL_WBV2_APPLICATION_FAILED_NO_HEALTHY_MODEL',selection=ref(path),
        scope='Native elapsed21061.743s before terminal capture/output failure; cleanup110 preserved. Original ack waited and cleared handles; only empty214978 retains EX. Sparse windows and SSH gap do not establish continuous longrun acceptance.')
    assert (R / 'CURRENT_CAMERA.json').read_bytes() == current_before
    save(R / 'CURRENT_CAMERA.json', pointer)
    event = dict(status=selection['status'],observed_utc=now,references=refs,CURRENT=ref(R / 'CURRENT_CAMERA.json'),
        native_elapsed_seconds=end['elapsed_ns']/1e9,logged_gaze_samples=report['samples'],
        completed_requested_longrun=False,original_ack_called_once=True,
        actual_empty_resources=True,native_cleanup_errno=110,root_cause_proven=False,
        kernel_observation=dict(channel='C2H1',writeback_count=1,expected_descriptors=3,
            MMIO_completed_descriptors=1,status='BUSY'),
        limitation='This is different from earlier WB0/complete-idle observations. Native stderr output_pipe_timeout, structured signal_stop and busy DMA abort lack a common sufficiently precise event trace; their causal order is unproven. No valid-human or effective-NPU-FPS acceptance.',full_goal_complete=False)
    key = f'v{revision}_actual_WBv2_terminal_failure_after_21061s'
    ledger['evidence'][key] = event
    for task in ledger['tasks']:
        if task['id'] in ('T02','U01','U02','U03','U04','U05'):
            task.setdefault('evidence_keys', []).append(key)
            task['current_state'] = ('当前WBv2累计21061.743秒后采集停止，原ack已真实wait，cleanup110保留；仅空214978持EX。需定位新output_pipe/BUSY-DMA因果并恢复，不能计长测通过。' + task['current_state'])
    ledger['first_video_milestone']['actual_new_UI_application'] = event
    ledger['next_safe_action'] = next_action
    schedule, estimates = load(R / 'TASK_SCHEDULING.json'), load(R / 'PENDING_TASK_ESTIMATES.json')
    schedule['entries']['U04'] = dict(bucket='development',title='采集长期运行故障定位、恢复与孪生整合',
        estimate='定位与受控恢复2–4小时；真人30–90分钟另列，长时稳定性仍需实测',
        prerequisites='保留本轮真实cleanup110、原wait/资源退出；新代精确handoff、全quiesce和真实字节检查',
        basis='WBv2本轮累计5小时51分钟后发生与旧WB0不同的BUSY/1-of-3及output_pipe_timeout，不能用短通过或去清零补丁宣称稳定。')
    estimates['main']['U04'] = [schedule['entries']['U04']['title'],schedule['entries']['U04']['estimate']]
    schedule['updated_utc'] = now
    save(R / 'TASK_SCHEDULING.json', schedule)
    save(R / 'PENDING_TASK_ESTIMATES.json', estimates)
    ledger.update(revision=revision,previous_ledger=prior,updated_utc=now,publisher=ref(__file__),full_goal_complete=False)
    out.mkdir()
    save(out / 'ledger.json', ledger)
    progress.update(observed_utc=now,full_task_ledger=ref(out / 'ledger.json'),protected_CURRENT=ref(R / 'CURRENT_CAMERA.json'))
    progress['active_work'].update(status=selection['status'],current_selected_runtime_is_live=False,actual_new_UI_application=event,next_action=next_action)
    progress['first_video_milestone']['actual_new_UI_application'] = event
    progress['current_runtime_stop_rule'] = '当前仅空214978持硬件EX，原seq10 ack已wait且拒绝cleanup110；禁止keep/normal-update/重复ack。仅在新精确失败代handoff验证后显式恢复；原9e82/f9程序员历史不改。'
    assert (R / 'GOAL_PROGRESS.json').read_bytes() == before
    temporary = R / 'GOAL_PROGRESS.wbv2_terminal.tmp'
    save(temporary, progress)
    os.replace(temporary, R / 'GOAL_PROGRESS.json')
    result = subprocess.run([sys.executable,'-X','utf8','-B',str(R / 'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out / 'refresh.stdout').write_bytes(result.stdout)
    (out / 'refresh.stderr').write_bytes(result.stderr)
    assert result.returncode == 0
    for name in ('GOAL_PROGRESS.json','CURRENT_CAMERA.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json','TASK_SCHEDULING.json','PENDING_TASK_ESTIMATES.json'):
        source = R / name
        (out / (source.stem + '_snapshot' + source.suffix)).write_bytes(source.read_bytes())
    save(out / 'publication.json',dict(status=selection['status'],revision=revision,full_goal_complete=False))
    print('ACTUAL_WBV2_TERMINAL_FAILURE_PUBLISHED', revision)


if __name__ == '__main__':
    main()
