"""Publish actual app39 failure before original ack; no device/process actions."""
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from publish_app39_recovery_v3 import encoded, future_ref, load, ref, save_new, R, Y, O


def main():
    names = ('GOAL_PROGRESS.json', 'CURRENT_CAMERA.json', 'TASK_SCHEDULING.json', 'PENDING_TASK_ESTIMATES.json')
    before = {name: (R / name).read_bytes() for name in names}
    progress, current, schedule, estimates = [json.loads(before[name]) for name in names]
    assert current['status'] == 'POINTER_ACTUAL_APP39_HFT2_GAME_V11_KEPT_AFTER_LONGRUN'
    assert ref(current['selection']['path']) == current['selection']
    failure = load(O / 'longrun_failure_01.json')
    state, report = failure['state'], failure['runtime_result']
    assert failure['status'] == 'ACTUAL_APP39_TERMINAL_FAILURE_PRESERVED_BEFORE_ACK'
    assert state['phase'] == 'FEATURE_FAILED_RETAINED' and state['main_handle_retained'] and state['feature_session_retained']
    assert state['supervisor']['pid'] == 233963 and state['supervisor']['start_ticks'] == 66678019
    assert state['main_returncode'] == 1 and report['worker_alive'] is False
    assert report['capture_end']['cleanup_errno'] == 110 and not failure['device_fds']
    assert ref(O / 'runtime_result_original.json')['sha256'] == failure['runtime_result_pin']['sha256']
    longer = Y / 'evidence/app39_observation_until_human_v1/result.json'
    assert load(longer)['completed_requested_window'] is False
    assert load(O / 'longrun_35min_v3/result.json')['completed_requested_window'] is True
    prior = progress['full_task_ledger']; assert ref(prior['path']) == prior
    ledger = copy.deepcopy(load(prior['path'])); revision = ledger['revision'] + 1
    assert revision == 270
    out = Path(prior['path']).parent.parent / f'goal_task_ledger_v{revision}'
    assert not out.exists()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    selection = dict(status='ACTUAL_APP39_FAILED_NATIVE_CLEANUP110_RETAINED', observed_utc=now,
        current_selected_runtime_is_live=False, previous_kept_selection=current['selection'],
        binding=ref(O / 'binding.json'), actual_failure=ref(O / 'longrun_failure_01.json'),
        original_runtime_result=ref(O / 'runtime_result_original.json'), after_keep_observation=ref(longer),
        prior_completed_35minute_window=ref(O / 'longrun_35min_v3/result.json'),
        owner=state['supervisor'], retained_runtime=state['runtime'],
        original_Popen_and_session_retained=True, original_ack_called=False,
        original_cleanup_errno=110, automatic_restart=False, FPGA_programming_performed=False,
        full_goal_complete=False,
        limitation='The earlier bounded35-minute pass and original keep remain true history. Current app39 failed after native3728.482s; no healthy camera/model is selected. WB2/expected28 and MMIO completed2/BUSY are observations, not root-cause proof. Original ack/retirement/recovery have not yet occurred.')
    out.mkdir()
    save_new(out / 'failed_selection.json', selection)
    selected = ref(out / 'failed_selection.json')
    pointer = dict(status='POINTER_ACTUAL_APP39_FAILED_NO_HEALTHY_MODEL', selection=selected,
        scope='Actual terminal capture failure retained before original ack. Prior keep/35-minute observation preserved; current camera/model is not healthy.')
    key = f'v{revision}_actual_app39_terminal_failure_before_ack'
    event = dict(status=selection['status'], observed_utc=now, references=dict(selection=selected,
        actual_failure=selection['actual_failure'], original_runtime_result=selection['original_runtime_result'], after_keep_observation=selection['after_keep_observation']),
        native_elapsed_seconds=report['capture_end']['elapsed_ns'] / 1e9,
        original_ack_called=False, current_selected_runtime_is_live=False, full_goal_complete=False)
    ledger['evidence'][key] = event
    for task in ledger['tasks']:
        if task['id'] in ('T02', 'U01', 'U02', 'U03', 'U04', 'U05'):
            task.setdefault('evidence_keys', []).append(key)
            task['current_state'] = '当前app39运行约62分8秒后真实采集终止，cleanup110保留，原owner233963仍持Popen/session和EX；尚未ack/恢复，当前无健康模型。原35分钟观察仍为历史有界通过。' + task['current_state']
    schedule['entries']['U04'].update(title='app39采集故障定位、受控恢复及长时整合',
        prerequisites='先完成本代实际原ack/wait、资源审计及新的233963精确恢复合同；真人正脸/双眼/手仍待用户',
        basis='本代62分钟后再次失败，不能以35分钟或旧5h51分钟前正常签根因解决；没有自动重启。')
    schedule['updated_utc'] = now
    estimates['main']['U04'] = [schedule['entries']['U04']['title'], schedule['entries']['U04']['estimate']]
    ledger.update(revision=revision, previous_ledger=prior, updated_utc=now, publisher=ref(__file__), full_goal_complete=False,
        current_camera_selection=selected, task_scheduling=future_ref(R / 'TASK_SCHEDULING.json', encoded(schedule)),
        next_safe_action='先保留本代故障，再通过原ack完成真实wait并审计资源；准备新精确233963失败代恢复。FPGA候选仍需真实调度/TD，不复用旧214978恢复入口或健康newbit入口。')
    ledger['first_video_milestone']['actual_new_UI_application'] = event
    save_new(out / 'ledger.json', ledger)
    progress.update(observed_utc=now, full_task_ledger=ref(out / 'ledger.json'), protected_CURRENT=future_ref(R / 'CURRENT_CAMERA.json', encoded(pointer)))
    progress['active_work'].update(status=selection['status'], current_selected_runtime_is_live=False, actual_new_UI_application=event, next_action=ledger['next_safe_action'])
    progress['first_video_milestone']['actual_new_UI_application'] = event
    progress['current_runtime_stop_rule'] = '233963实际FEATURE_FAILED_RETAINED持原Popen/session和EX；保留cleanup110及所有原件，原ack仅可一次，随后核真实wait/资源。不得走健康normal update、旧214978恢复或自动启动。'
    values = dict(zip(names, (progress, pointer, schedule, estimates)))
    save_new(out / 'publication_prepared.json', dict(before={name:future_ref(R / name, body) for name,body in before.items()}, selected=selected))
    assert all((R / name).read_bytes() == body for name,body in before.items())
    for name,value in values.items():
        assert (R / name).read_bytes() == before[name]
        temporary = R / (name + '.app39_failure_v270.tmp')
        with temporary.open('xb') as stream: stream.write(encoded(value))
        assert (R / name).read_bytes() == before[name]
        os.replace(temporary, R / name)
    process = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(R / 'tools/refresh_pending_tasks.py')], cwd=R, capture_output=True)
    (out / 'refresh.stdout').write_bytes(process.stdout); (out / 'refresh.stderr').write_bytes(process.stderr)
    assert process.returncode == 0
    for name in (*names, 'PENDING_TASKS.md', 'PENDING_TASKS.json', 'PENDING_FIELD_TESTS.md', 'PENDING_FIELD_TESTS.json'):
        (out / ('snapshot_' + name)).write_bytes((R / name).read_bytes())
    save_new(out / 'publication.json', dict(status=selection['status'], revision=revision, original_ack_called=False, full_goal_complete=False))
    print('ACTUAL_APP39_TERMINAL_FAILURE_PUBLISHED', revision)


if __name__ == '__main__':
    main()
