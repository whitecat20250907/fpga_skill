"""Retire the stale RUNNING pointer after verified original resource closure."""
import copy
import datetime
import os
from pathlib import Path
import subprocess
import sys
from publish_video_running_v1 import R, Y, load, save, ref


def main():
    before = (R / 'GOAL_PROGRESS.json').read_bytes()
    old_current = ref(R / 'CURRENT_CAMERA.json')
    assert old_current['sha256'] == '77b36d023e0562ab4e968ee1968bd111a5455aac65f49a4f9a431b18c4523c78'
    progress = load(R / 'GOAL_PROGRESS.json')
    prior = progress['full_task_ledger']
    assert ref(prior['path']) == prior
    ledger = copy.deepcopy(load(prior['path']))
    revision = ledger['revision'] + 1
    out = Path(prior['path']).parent.parent / f'goal_task_ledger_v{revision}'
    assert not out.exists()
    root = Y / 'evidence/inactive_hft2_host_v1'
    paths = {name: ref(root / name) for name in (
        'failed_generation_resource_close.json', 'errored_supervisor_exit.json',
        'original_native_wait_reports_sources.json', 'MANIFEST.json', 'README.md')}
    retired = load(root / 'failed_generation_resource_close.json')
    assert retired['status'] == 'FAILED_GENERATION_RESOURCES_REAPED_SUPERVISOR_STILL_RETAINED'
    exited = load(root / 'errored_supervisor_exit.json')
    assert exited['status'] == 'ERRORED_SUPERVISOR_EXIT_RESOURCES_VERIFIED'
    assert exited['transaction_status'] == 'FAILED_GENERATION_RESOURCES_REAPED_AND_ERRORED_SUPERVISOR_TERMINATED'
    assert exited['owner_exited'] is True and exited['device_fds'] == []
    assert exited['normal_feature_close_PASS'] is False
    pointer = load(R / 'CURRENT_CAMERA.json')
    pointer.update(status='FAILED_GENERATION_RETIRED_NO_ACTIVE_CAMERA_OWNER', active_runtime=None,
        previous_running_pointer=old_current, failed_generation_retirement=paths['errored_supervisor_exit.json'],
        actual_full_bit_sha256='9bea494c217c081c21a730ed85b03e823eb02cdbfa33e5884ddd79eccb2802ce',
        scope='The selection is historical configuration/evidence only. Original app34/native/hand/relay resources were reaped after a real DMA failure. The errored supervisor was then terminated through its exact pidfd after original waits and empty-device-FD checks. No active camera owner or newly deployed UI is claimed. Full formal SRAM remains; Flash37 unchanged.')
    event = dict(status=pointer['status'], references=paths, prior_CURRENT=old_current,
        native_and_launcher_original_waits_verified=True, auxiliary_waits_and_threads_closed=True,
        errored_supervisor_terminated=True, normal_close_or_runtime_PASS_claimed=False,
        active_camera_owner=None, new_UI_deployed=False, full_goal_complete=False)
    key = f'v{revision}_failed_generation_retired_no_live_camera_owner'
    ledger['evidence'][key] = event
    ledger.update(revision=revision, previous_ledger=prior,
        updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        publisher=ref(__file__), full_goal_complete=False)
    ledger['first_video_milestone']['latest_runtime_retirement'] = event
    assert (R / 'GOAL_PROGRESS.json').read_bytes() == before
    assert ref(R / 'CURRENT_CAMERA.json') == old_current
    current_temp = R / 'CURRENT_CAMERA.failed_retirement.tmp'
    save(current_temp, pointer)
    os.replace(current_temp, R / 'CURRENT_CAMERA.json')
    event['CURRENT'] = ref(R / 'CURRENT_CAMERA.json')
    out.mkdir()
    save(out / 'ledger.json', ledger)
    progress.update(observed_utc=ledger['updated_utc'], full_task_ledger=ref(out / 'ledger.json'),
        protected_CURRENT=event['CURRENT'])
    progress['active_work'].update(status='NO_ACTIVE_CAMERA_OWNER_PREPARING_FULL_APPLICATION_RECOVERY',
        latest_runtime_retirement=event, current_selected_runtime_is_live=False)
    progress['first_video_milestone']['latest_runtime_retirement'] = event
    progress['current_runtime_stop_rule'] = '当前无相机运行owner；旧代已真实回收及退役，禁止再向旧binding发stop/start。新完整profile需以失败退役proof、明确新启动环境及新owner创建，不复用旧PID或裸模型。'
    temp = R / 'GOAL_PROGRESS.camera_retirement.tmp'
    save(temp, progress)
    os.replace(temp, R / 'GOAL_PROGRESS.json')
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(R / 'tools/refresh_pending_tasks.py')], cwd=R, capture_output=True)
    (out / 'refresh.stdout').write_bytes(result.stdout)
    (out / 'refresh.stderr').write_bytes(result.stderr)
    assert result.returncode == 0
    for filename in ('GOAL_PROGRESS.json', 'CURRENT_CAMERA.json', 'PENDING_TASKS.md',
                     'PENDING_TASKS.json', 'PENDING_FIELD_TESTS.md', 'PENDING_FIELD_TESTS.json'):
        path = R / filename
        (out / (path.stem + '_snapshot' + path.suffix)).write_bytes(path.read_bytes())
    save(out / 'publication.json', dict(status='STALE_RUNNING_POINTER_RETIRED', revision=revision,
        CURRENT=event['CURRENT'], full_goal_complete=False))
    print('FAILED_CAMERA_RETIRED', revision, event['CURRENT']['sha256'])


if __name__ == '__main__':
    main()
