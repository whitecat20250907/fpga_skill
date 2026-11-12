"""Record the real retained capture failure; do not promote stale CURRENT."""
import copy
import datetime
import os
from pathlib import Path
import subprocess
import sys
from publish_video_running_v1 import R, Y, load, save, ref


def main():
    before = (R / 'GOAL_PROGRESS.json').read_bytes()
    progress = load(R / 'GOAL_PROGRESS.json')
    prior = progress['full_task_ledger']
    assert ref(prior['path']) == prior
    ledger = copy.deepcopy(load(prior['path']))
    revision = ledger['revision'] + 1
    out = Path(prior['path']).parent.parent / f'goal_task_ledger_v{revision}'
    assert not out.exists()
    failure = Y / 'evidence/inactive_hft2_host_v1'
    evidence = {name: ref(failure / filename) for name, filename in {
        'retained_runtime_failure': 'retained_failure_readonly.json',
        'actual_native_and_kernel': 'failed_native_poll_source_kernel.json',
        'original_stop_RPC_once': 'failed_generation_stop_rpc_once.json',
        'native_source': 'actual_app34_capture_native.c',
        'native_log': 'native_main_tail.txt',
        'kernel_log': 'kernel_tail.txt',
    }.items()}
    stop = load(failure / 'failed_generation_stop_rpc_once.json')
    assert stop['sequence'] == 17 and stop['owner_exists_after'] is True
    assert stop['value']['ok'] is False
    key = f'v{revision}_original_capture_DMA_timeout_retained_failure'
    event = dict(status='ORIGINAL_CAPTURE_DMA_TIMEOUT_FAILED_GENERATION_RETAINED',
        references=evidence, original_owner=dict(pid=194160, start_ticks=62617246),
        original_capture=dict(pid=195668, start_ticks=62763436),
        capture_frames=84625, captured_frames=84704, native_cleanup_errno=0,
        kernel_DMA_timeout_count=3, main_returncode=1, hand_returncode=1,
        relay_returncode=0, original_stop_RPC_sequence=17,
        original_stop_RPC_completed_successfully=False,
        complete_resource_retirement_accepted=False,
        native_errno_11_is_not_a_proven_poll_syscall_errno=True,
        failure_before_inactive_payload_extraction=True,
        new_application_installed_or_started=False, new_UI_deployed=False,
        last_CURRENT_is_historical_not_live_health=True,
        preserved_CURRENT=ref(R / 'CURRENT_CAMERA.json'),
        full_goal_complete=False)
    ledger['evidence'][key] = event
    for task in ledger['tasks']:
        if task['id'] in ('U03', 'U04', 'T02'):
            task.setdefault('evidence_keys', []).append(key)
            task['current_state'] += ' 2026-10-23原app34连续约23.6分钟后C2H0三次DMA超时，native/main退出；手势源随之退出，旧owner原stop因rc1保留。旧界面用户随动确认仍是历史基本链证据，当前运行/长稳未通过；先真实失败回收与整套恢复。'
    ledger.update(revision=revision, previous_ledger=prior,
        updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        publisher=ref(__file__), full_goal_complete=False)
    ledger['next_safe_action'] = '核对原launcher/native/aux真实wait与FD后退役失败前任；显式白名单新完整profile恢复；修复游戏桥合法延迟fence活锁并重新冻结，再完成新UI+TDM时序与实板验收。'
    ledger['first_video_milestone']['latest_runtime_failure'] = event
    out.mkdir()
    save(out / 'ledger.json', ledger)
    progress.update(observed_utc=ledger['updated_utc'], full_task_ledger=ref(out / 'ledger.json'))
    progress['active_work'].update(status='CAPTURE_DMA_FAILURE_RETIREMENT_AND_UNIFIED_APPLICATION_RECOVERY',
        latest_runtime_failure=event, current_selected_runtime_is_live=False,
        next_action=ledger['next_safe_action'])
    progress['first_video_milestone']['latest_runtime_failure'] = event
    progress['current_runtime_stop_rule'] = '历史CURRENT绑定的原stop_owned序列17因非零launcher失败，禁止重复stop/裸模型重启；按实际原句柄wait与FD证据退役失败owner，再创建新完整运行代。'
    assert (R / 'GOAL_PROGRESS.json').read_bytes() == before
    temp = R / 'GOAL_PROGRESS.runtime_failure.tmp'
    save(temp, progress)
    os.replace(temp, R / 'GOAL_PROGRESS.json')
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(R / 'tools/refresh_pending_tasks.py')],
        cwd=R, capture_output=True)
    (out / 'refresh.stdout').write_bytes(result.stdout)
    (out / 'refresh.stderr').write_bytes(result.stderr)
    assert result.returncode == 0
    for filename in ('GOAL_PROGRESS.json', 'CURRENT_CAMERA.json', 'PENDING_TASKS.md',
                     'PENDING_TASKS.json', 'PENDING_FIELD_TESTS.md', 'PENDING_FIELD_TESTS.json'):
        path = R / filename
        (out / (path.stem + '_snapshot' + path.suffix)).write_bytes(path.read_bytes())
    save(out / 'publication.json', dict(status='ACTUAL_CAPTURE_FAILURE_RECORDED_NO_STALE_HEALTH_PROMOTED',
        revision=revision, full_goal_complete=False))
    print('APPLICATION_RUNTIME_FAILURE_RECORDED', revision)


if __name__ == '__main__':
    main()
