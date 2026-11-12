"""Record the original failed-start ack and retained empty app39 owner."""
import copy
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from publish_app39_recovery_v3 import encoded, future_ref, load, ref, save_new, R, Y, O


def main():
    names = ('GOAL_PROGRESS.json', 'CURRENT_CAMERA.json')
    before = {name:(R / name).read_bytes() for name in names}
    progress, current = [json.loads(before[name]) for name in names]
    assert current['status'] == 'POINTER_ACTUAL_APP39_FAILED_NO_HEALTHY_MODEL'
    assert ref(current['selection']['path']) == current['selection']
    ack = load(O / 'rpc_0010_sent.json'); response = ack['response']
    assert ack['sequence'] == 10 and not ack['pending'] and response['action'] == 'ack_failed_start'
    assert response['ok'] is False and response['phase'] == 'FAILED_RESOURCE_RETIRED_UNVERIFIED'
    audit = load(O / 'post_ack_resource_audit.json')
    assert audit['owner']['pid'] == 233963 and audit['owner']['start_ticks'] == 66678019
    assert audit['all_children_absent'] and not audit['device_fds'] and not audit['kernel_dma_tasks']
    assert audit['native_cleanup_errno'] == 110 and audit['normal_runtime_PASS'] is False
    state = audit['state']
    assert state['runtime'] is None and not state['main_handle_retained'] and not state['feature_session_retained']
    assert state['phase'] == 'FAILED_RESOURCE_RETIRED_UNVERIFIED'
    assert audit['actual_original_request'] == ack['request']
    assert len(audit['kernel_other_matching_tasks']) == 8
    assert all(row['name'] == f'sgdma_poll_th{i}' for i,row in enumerate(audit['kernel_other_matching_tasks']))
    prior = progress['full_task_ledger']; assert ref(prior['path']) == prior
    ledger = copy.deepcopy(load(prior['path'])); revision = ledger['revision'] + 1; assert revision == 271
    out = Path(prior['path']).parent.parent / f'goal_task_ledger_v{revision}'; assert not out.exists()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    selected = copy.deepcopy(load(current['selection']['path']))
    selected.update(status='ACTUAL_APP39_FAILED_EMPTY_OWNER_AFTER_ORIGINAL_WAIT', observed_utc=now,
        previous_failed_selection=current['selection'], original_ack_called=True, original_ack_count=1,
        original_ack=ref(O / 'rpc_0010_sent.json'), actual_post_ack=ref(O / 'post_ack_resource_audit.json'),
        original_remote_post_ack=load(O / 'post_ack_resource_audit_reference.json')['pin'],
        phase=state['phase'], retained_runtime=None, original_Popen_and_session_retained=False,
        all_children_absent=True, device_fds_empty=True, milianke_stream_tasks_empty=True,
        loaded_driver_poll_threads=audit['kernel_other_matching_tasks'],
        limitation='Original seq10 really waited/cleared Popen/session but refused recovery because cleanup110. Empty233963 still holds the only EX;8 loaded-driver poll threads remain and must disappear during later reviewed quiesce/unload. No healthy model, no generic all-kernel-task-empty claim, no restart/programming or successful recovery.')
    out.mkdir(); save_new(out / 'failed_selection.json', selected); selected_ref = ref(out / 'failed_selection.json')
    pointer = dict(current, selection=selected_ref, scope=selected['limitation'])
    event = dict(status=selected['status'], observed_utc=now, selection=selected_ref,
        original_ack=selected['original_ack'], actual_post_ack=selected['actual_post_ack'],
        current_selected_runtime_is_live=False, normal_runtime_PASS=False, full_goal_complete=False)
    key = f'v{revision}_actual_app39_original_wait_and_empty_owner'
    ledger['evidence'][key] = event
    for task in ledger['tasks']:
        if task['id'] in ('T02','U01','U02','U03','U04','U05'):
            task.setdefault('evidence_keys',[]).append(key)
            task['current_state'] = '原seq10 ack已真实wait并清本代Popen/session；五子进程/设备FD/流任务均空，cleanup110仍拒绝恢复，空233963持唯一EX；8个驱动轮询线程须在后续quiesce卸载。' + task['current_state']
    ledger.update(revision=revision, previous_ledger=prior, updated_utc=now, publisher=ref(__file__), full_goal_complete=False,
        current_camera_selection=selected_ref,
        next_safe_action='验证新精确233963失败代handoff，退役空owner后新EX内先保存只读模型状态，再原quiesce/unload并恢复；不复用已消费ack或旧214978入口。游戏可在模型离线窗口独立维护，不触相机/PCIe。')
    save_new(out / 'ledger.json', ledger)
    progress.update(observed_utc=now, full_task_ledger=ref(out / 'ledger.json'), protected_CURRENT=future_ref(R / 'CURRENT_CAMERA.json', encoded(pointer)))
    progress['active_work'].update(status=selected['status'], current_selected_runtime_is_live=False, actual_new_UI_application=event, next_action=ledger['next_safe_action'])
    progress['first_video_milestone']['actual_new_UI_application'] = event
    progress['current_runtime_stop_rule'] = selected['limitation']
    values = dict(zip(names,(progress,pointer)))
    assert all((R / name).read_bytes() == data for name,data in before.items())
    for name,value in values.items():
        temporary=R / (name+'.app39_retired_v271.tmp')
        with temporary.open('xb') as stream: stream.write(encoded(value))
        assert (R / name).read_bytes() == before[name]
        os.replace(temporary,R / name)
    process=subprocess.run([sys.executable,'-X','utf8','-B',str(R / 'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(process.stdout); (out/'refresh.stderr').write_bytes(process.stderr); assert process.returncode==0
    for name in (*names,'PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json'):
        (out/('snapshot_'+name)).write_bytes((R/name).read_bytes())
    save_new(out/'publication.json',event); print('ACTUAL_APP39_ORIGINAL_WAIT_PUBLISHED',revision)


if __name__=='__main__':
    main()
