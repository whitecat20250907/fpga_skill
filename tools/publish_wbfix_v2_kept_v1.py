"""Publish the actual non-EOP WBv2 runtime; keep tests and human acceptance distinct."""
import argparse
import copy
import datetime
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

from publish_video_running_v1 import R, Y, load, save, ref


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('under_test', 'kept'))
    args = parser.parse_args()
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
    b, cfg = load(o / 'binding.json'), load(o / 'config.json')
    verify = load(o / 'running_application_verification.json')
    assert verify['state']['phase'] == 'FEATURE_RUNNING' and verify['state']['supervisor'] == b['owner']
    assert b['active_driver_build_id'] == '36409b190ef2bcb99cbd7912a85af260b4bf4209'
    requests = [load(p) for p in o.glob('rpc_*_sent.json')]
    start = next(v for v in requests if v['response'].get('action') == 'start_candidate_feature')
    assert start['response']['ok'] and start['response']['value']['runtime'] == b['runtime']
    refs = dict(binding=ref(o / 'binding.json'), actual_complete_start=ref(next(p for p in o.glob('rpc_*_sent.json') if load(p)['response'].get('action') == 'start_candidate_feature')),
        source_bound_control=ref(o / 'running_application_verification.json'), actual_loaded_driver=ref(o / 'actual_loaded_driver_identity.json'),
        exact_previous_supervisor_exit=ref(o / 'supervisor_exit.json'), final_config=ref(o / 'config.json'),
        source_recovery_contract=ref(Y / 'handoff/failed_cleanup_recovery_v2/MANIFEST.json'),
        exact_non_EOP_reproduction=ref(R / 'projects/model_image_ops_board_20261023/evidence/sgdma_completion_independent_v2/result.json'))
    capacity = Y / 'evidence/overnight_capacity_v1/result.json'
    if capacity.exists():
        assert load(capacity)['status'] == 'PASS_ROOT_AND_USERDATA_OLD_RAW_OFFLOAD_WITH_FULL_PC_SHA_BACKUPS'
        refs['actual_separate_partition_capacity_and_backup'] = ref(capacity)
    for action in ('quiesce', 'retain_same_bit', 'capture_fpga', 'roundtrip'):
        path = next(p for p in o.glob('rpc_*_sent.json') if load(p)['response'].get('value', {}).get('action') == action or load(p)['response'].get('value', {}).get('status') == ('SAME_SRAM_RETAINED_NO_NEW_PROGRAMMING_CLAIM' if action == 'retain_same_bit' else 'UNUSED'))
        row = load(path)['response']
        assert row['ok']
        refs[action] = ref(path)
        if action == 'capture_fpga':
            image = row['value']['value']
            assert image['end']['errno'] == image['end']['cleanup_errno'] == 0
            assert len(image['same_frame_tensor_checks']) == 3
            assert all(v['face128_byte_exact'] and v['palm192_byte_exact'] for v in image['same_frame_tensor_checks'])
        if action == 'roundtrip':
            assert sum(v['iterations'] for v in row['value']['value']['images']) == 6
    kept = args.stage == 'kept'
    phase = 'FEATURE_KEEP_RUNNING' if kept else 'FEATURE_RUNNING'
    if kept:
        measurement = load(o / 'longrun_35min_after_transport_gap/result.json')
        assert measurement['completed_requested_window'] and measurement['actual_seconds'] >= 2100
        assert measurement['boot_id'] == b['boot_id']
        keep = next(v for v in reversed(requests) if v['response'].get('action') == 'keep_feature_running')
        assert keep['response']['ok'] and keep['response']['phase'] == phase
        assert keep['response']['value']['runtime']['owners'] == b['runtime']['owners']
        refs['longrun'] = ref(o / 'longrun_35min_after_transport_gap/result.json')
        refs['earlier_partial_window_transport_gap'] = ref(o / 'longrun_35min_v2/result.json')
        refs['actual_keep'] = ref(next(p for p in o.glob('rpc_*_sent.json') if load(p)['response'].get('action') == 'keep_feature_running'))
    s = importlib.util.spec_from_file_location('_publish_wbv2', Y / 'tools/execute_wbfix_actual_v2.py')
    a = importlib.util.module_from_spec(s)
    s.loader.exec_module(a)
    body = '''import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,'/home/linaro/pcie_fix_20261003/hft2_tdm_app_v3_20261023/owner');import profile_delivery_v1 as d
b=json.loads(Path(__BINDING__).read_text());c=d.load('_publish_wbv2_original_control',b['control_source']);status,stop=d.functions(c,b);live=status(b)
cfg=json.loads(Path(b['owner_config']['path']).read_text())
for row in cfg['files']:assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256'],row['path']
state=json.loads((Path(b['root'])/'lifecycle/video_owner_state.json').read_text());assert state['phase']==__PHASE__ and not state['feature_errors'] and state['tick_error'] is None
print(json.dumps(dict(status='ACTUAL_WBV2_SOURCE_BOUND_RUNTIME_VERIFIED',live=live,state=state,source_pins=len(cfg['files']))))
'''.replace('__BINDING__', repr(a.REMOTE + '/binding.json')).replace('__PHASE__', repr(phase))
    actual = a.remote('verify_publication_' + args.stage, body, timeout=35)
    actual_path = o / ('publication_verification_' + args.stage + '.json')
    assert not actual_path.exists()
    a.save(actual_path, actual)
    refs['actual_publication_verification'] = ref(actual_path)
    old = load(R / 'CURRENT_CAMERA.json')
    selected = load(old['selection']['path'])
    # Follow only the recorded historical chain to obtain real bit provenance.
    if 'FPGA_SRAM_bit' not in selected:
        selected = load(selected['previous_running_selection']['path'])
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    status = 'ACTUAL_WBV2_APPLICATION_KEPT_AFTER_LONGRUN' if kept else 'ACTUAL_WBV2_APPLICATION_RUNNING_LONGRUN_PENDING'
    selection = dict(status=status, observed_utc=now, boot_id=b['boot_id'], FPGA_SRAM_bit=selected['FPGA_SRAM_bit'],
        original_programming_receipt=b['candidate_programming_receipt'], Flash_written=False, FPGA_programming_performed=False,
        app=b['runtime']['app'], npu_package=cfg['profiles']['candidate']['npu_package'],
        runtime=b['runtime'], model_pid=next(v['pid'] for v in b['runtime']['owners'] if 'run_gaze.py' in v['cmdline']),
        capture_pid=next(v['pid'] for v in b['runtime']['owners'] if 'capture_native' in v['cmdline']),
        model_session=b['runtime']['csv'].rsplit('/', 1)[0], launcher=b['runtime']['launcher'],
        selected_live_launcher_directory=b['root'] + '/lifecycle', selected_launch_directory=b['root'] + '/lifecycle',
        backend='RK3576_NPU_existing_models', readonly_runtime_observation=refs['actual_publication_verification'],
        persistent_runtime_supervisor=ref(o / 'ready.json'),
        active_driver=b['active_driver'], active_driver_build_id=b['active_driver_build_id'],
        feature_controller=dict(root=b['root'], owner=b['owner'], remote=a.REMOTE, owner_remote=a.REMOTE,
            owner_source=b['owner_source'], owner_config=b['owner_config']['path'],
            remote_binding=a.REMOTE + '/binding.json', binding=ref(o / 'binding.json'),
            control=b['profile_control_source'], application_client=b['application_client_source']),
        feature_directory=b['feature_directory'], current_stop_request=b['runtime']['stop_request'],
        default_mode='visual', automatic_restart=False, original_Popen_and_EX_retained=True,
        longrun_accepted=kept, current_new_UI_optical_or_human_accepted=False,
        personal_calibration_effective_human_FPS_games_accepted=False,
        new_game_revision_acceptance=False, references=refs, previous_selection_historical_only=old['selection'],
        full_goal_complete=False)
    selection_path = o / ('current_kept_selection.json' if kept else 'current_running_selection.json')
    assert not selection_path.exists()
    save(selection_path, selection)
    pointer = dict(status='POINTER_' + status, selection=ref(selection_path),
        scope='Same9e82/app38/HAND2/SUPPORT2 and original model weights; private non-EOP WBv2 driver, original eight parameters. ' + ('35-minute same-generation observation passed; human tests deferred about12h by user.' if kept else 'Actual byte checks and full startup passed; longrun pending, no human acceptance.'))
    assert (R / 'CURRENT_CAMERA.json').read_bytes() == current_before
    save(R / 'CURRENT_CAMERA.json', pointer)
    event = dict(status=status, observed_utc=now, references=refs, CURRENT=ref(R / 'CURRENT_CAMERA.json'),
        current_selected_runtime_is_live=True, longrun_accepted=kept, human_nonempty_or_optical_accepted=False,
        original_models_and_app38_unchanged=True, Flash_written=False, new_game_revision_acceptance=False,
        full_goal_complete=False, limitation='Exact non-EOP branch gap is fixed in source and independently reproduced; no claim that the historical hardware interleaving was directly observed. Game build/backup IO may overlap this stability window; not an idle performance benchmark.')
    key = f'v{revision}_actual_non_EOP_WBv2_' + args.stage
    ledger['evidence'][key] = event
    descriptions = {
        'T02': '实际non-EOP模型通道WB处理已独立修正并上板；原参数不变，三组128/192张量和六幅RGB1080逐字节通过。' + ('同代35分钟持续运行通过。' if kept else '同代长测进行中。') + 'metadata/nonce等剩余同源集成仍按原门槛。',
        'U01': '新9e82应用UI完整TD/物理通过，当前同bit/app38与WBv2实际运行；新版卡片和丰满人物几何仍待真人/实屏验收，旧骨架随动确认不扩签新版。',
        'U02': '原手/头眼结果复用、producer身份与来源新鲜性门禁已实际接线；当前无人脸/手有效验收，未新增UI推理。',
        'U03': '本次真实cleanup110退出链、精确空owner退役、全quiesce/同SRAM保留及原启动已执行；无新JTAG/Flash。控制与后续回退必须取最新绑定，旧命令为历史。',
        'U04': ('实际WBv2/app38保持同代通过35分钟观察，已按用户请求留用visual；真人约12小时后配合。' if kept else '实际WBv2/app38已恢复visual，主/采集/手/relay均原owner持有，长测进行中；真人约12小时后配合。'),
        'U05': '真实相对XYZ手/头/双眼场景与人物注册/分页已部署；当前长测与后续真人验收分开，不签空间标定、操作者一致性或非空丰满孪生通过。',
    }
    for task in ledger['tasks']:
        if task['id'] in descriptions:
            task['current_state'] = descriptions[task['id']]
            task.setdefault('evidence_keys', []).append(key)
    schedule = load(R / 'TASK_SCHEDULING.json')
    estimates = load(R / 'PENDING_TASK_ESTIMATES.json')
    schedule['entries']['U04'] = dict(bucket='field_test' if kept else 'development',
        title='新版孪生、真人轨迹与光学联合验收' if kept else 'WBv2实际长测与持续运行交付',
        estimate='真人30–90分钟；首版拍摄5–10分钟（用户约12小时后配合）' if kept else '35分钟首轮长测、交付30–60分钟；随后保持运行',
        prerequisites='当前同代运行保持；真人正脸双眼及手入镜，按原P1登记/个人标定进行' if kept else '现用原owner及新driver保持同代，源序号/health/CSV持续进展；首错保留、不自动重启',
        basis='真实上板字节与启动已通过；真人尚未执行，软件就绪与项目通过分开。')
    estimates['main']['U04'] = [schedule['entries']['U04']['title'], schedule['entries']['U04']['estimate']]
    if args.stage == 'under_test':
        game = next(t for t in ledger['tasks'] if t['id'] == 'G02')
        game['current_state'] = '实际Watch收入+16及第9/15/21回合增援已有证据；两局Mine在攻城后被毁，收入+32未通过。经济据点保留修复a25ad69已独立编译启动，正进行新版本真实争夺/攻防；旧f992战斗证明不扩签新版本。'
        game['scheduling_bucket'] = 'development'
        schedule['entries']['G02'] = dict(bucket='development', title='经济据点保留修复与新版本完整攻防', estimate='修复部署及真实争夺/战斗1–3小时', prerequisites='新私有原生server/rules/scenario；矿点收入与易手归属、首都终局及两模式复验', basis='真实实测发现经济据点被摧毁而收入丢失，需产品修复，不能仅留待实测。')
        estimates['main']['G02'] = [schedule['entries']['G02']['title'], schedule['entries']['G02']['estimate']]
    schedule['updated_utc'] = now
    save(R / 'TASK_SCHEDULING.json', schedule)
    save(R / 'PENDING_TASK_ESTIMATES.json', estimates)
    ledger.update(revision=revision, previous_ledger=prior, updated_utc=now, publisher=ref(__file__), full_goal_complete=False)
    ledger['first_video_milestone']['actual_new_UI_application'] = event
    ledger['first_video_milestone']['human_availability'] = '用户最新明确：约12小时后才能配合；此前推进工程并保持程序运行，不把等待计为验收通过。'
    ledger['next_safe_action'] = '保持visual及同代运行；完成新游戏规则实战与交付，真人窗口再做P1/相对XYZ/轨迹/个人标定/游戏动作。' if kept else '完成同代长测并按真实结果留用；并行完成经济据点产品修复实战，暂不做真人验收。'
    out.mkdir()
    save(out / 'ledger.json', ledger)
    progress.update(observed_utc=now, full_task_ledger=ref(out / 'ledger.json'), protected_CURRENT=ref(R / 'CURRENT_CAMERA.json'))
    progress['active_work'].update(status=status, current_selected_runtime_is_live=True, actual_new_UI_application=event, next_action=ledger['next_safe_action'])
    progress['first_video_milestone']['actual_new_UI_application'] = event
    progress['first_video_milestone']['human_availability'] = ledger['first_video_milestone']['human_availability']
    progress['current_runtime_stop_rule'] = '当前214978持原Popen和唯一硬件EX，默认visual。所有操作先读CURRENT/binding核boot/PID/start/config；不得另开模型或重用旧owner/程序员。原完整stop退出当前owner；故障保留原失败与资源证据，不自动重启。'
    assert (R / 'GOAL_PROGRESS.json').read_bytes() == before
    temporary = R / ('GOAL_PROGRESS.wbv2_' + args.stage + '.tmp')
    save(temporary, progress)
    os.replace(temporary, R / 'GOAL_PROGRESS.json')
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(R / 'tools/refresh_pending_tasks.py')], cwd=R, capture_output=True)
    (out / 'refresh.stdout').write_bytes(result.stdout)
    (out / 'refresh.stderr').write_bytes(result.stderr)
    assert result.returncode == 0
    for name in ('GOAL_PROGRESS.json', 'CURRENT_CAMERA.json', 'PENDING_TASKS.md', 'PENDING_TASKS.json', 'PENDING_FIELD_TESTS.md', 'PENDING_FIELD_TESTS.json', 'TASK_SCHEDULING.json', 'PENDING_TASK_ESTIMATES.json'):
        source = R / name
        (out / (source.stem + '_snapshot' + source.suffix)).write_bytes(source.read_bytes())
    save(out / 'publication.json', dict(status=status, revision=revision, full_goal_complete=False))
    print('ACTUAL_WBV2_PUBLISHED', revision, args.stage)


if __name__ == '__main__':
    main()
