"""Publish actual app39 recovery; longrun, game binding and human tests differ.

This tool never starts/stops models or sends owner RPCs. Its only board action
is an original complete source-bound status plus file/sysfs health reads.
"""
import argparse
import copy
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from publish_video_running_v1 import R, Y, load, ref

O = Y / 'evidence/application_recovery_actual_v4'
BINDING_SHA = '1bbaa07aa09445607b4dd92ffc410f0357adebfc186f684724742ee000f494f3'
CONFIG_SHA = 'bdc62741cb5d023e7962923766ce89640564e3007887c1cff862913d7fc47f5a'
BIT_SHA = '9e82d8cd50510a8480afe6a49f0e3cd61ef3194334fe225d65fb7bd7265c0e59'
BATTLE_SHA = 'd7408d9166befea7582cf0278b47f5162245ff744f4e060642967706eebafe1f'
BUILD_ID = '36409b190ef2bcb99cbd7912a85af260b4bf4209'
RUNNING = 'ACTUAL_APP39_HFT2_GAME_V11_RUNNING_LONGRUN_PENDING'
KEPT = 'ACTUAL_APP39_HFT2_GAME_V11_KEPT_AFTER_LONGRUN'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')


def save_new(path, value):
    with Path(path).open('xb') as stream:
        stream.write(encoded(value))


def future_ref(path, body):
    return dict(path=str(Path(path).resolve()), sha256=hashlib.sha256(body).hexdigest())


def unique_rpc(rows, *, action=None, native=None):
    found = []
    for path, row in rows:
        response = row.get('response', {})
        value = response.get('value') or {}
        match = response.get('action') == action if action else (
            value.get('action') == native or native == 'retain_same_bit' and
            value.get('status') == 'SAME_SRAM_RETAINED_NO_NEW_PROGRAMMING_CLAIM')
        if not match:
            continue
        assert row['pending'] is False and response['ok'] is True
        assert response['sequence'] == row['sequence'] and response['request_sha256'] == row['request']['sha256']
        found.append((path, row))
    assert len(found) == 1, 'Exactly one successful original RPC required: ' + str(action or native)
    return found[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('running', 'kept'))
    args = parser.parse_args()
    kept = args.stage == 'kept'
    phase = 'FEATURE_KEEP_RUNNING' if kept else 'FEATURE_RUNNING'
    status = KEPT if kept else RUNNING
    shared_names = ('GOAL_PROGRESS.json', 'CURRENT_CAMERA.json', 'TASK_SCHEDULING.json', 'PENDING_TASK_ESTIMATES.json')
    before = {name: (R / name).read_bytes() for name in shared_names}
    progress, old, schedule, estimates = [json.loads(before[name]) for name in shared_names]
    expected_pointer = 'POINTER_' + RUNNING if kept else 'POINTER_ACTUAL_WBV2_APPLICATION_FAILED_NO_HEALTHY_MODEL'
    assert old['status'] == expected_pointer, 'Current selected generation changed'
    assert ref(old['selection']['path']) == old['selection']
    previous_selection = load(old['selection']['path'])
    prior = progress['full_task_ledger']
    assert ref(prior['path']) == prior
    ledger = copy.deepcopy(load(prior['path']))
    revision = ledger['revision'] + 1
    out = Path(prior['path']).parent.parent / f'goal_task_ledger_v{revision}'
    assert not out.exists()
    assert ref(O / 'binding.json')['sha256'] == BINDING_SHA
    assert ref(O / 'config.json')['sha256'] == CONFIG_SHA
    b, cfg = load(O / 'binding.json'), load(O / 'config.json')
    assert b['owner']['pid'] == 233963 and b['owner']['start_ticks'] == 66678019
    assert b['owner_config']['sha256'] == CONFIG_SHA and len(cfg['files']) == 844
    assert b['active_driver_build_id'] == BUILD_ID
    assert b['candidate_programming_receipt']['sha256'] == 'f9f0a0900ef3de8c37bef7a1f1a92b8cc04c423410072380523ff503d2644dcd'
    assert b['new_game_battle_acceptance']['sha256'] == BATTLE_SHA
    assert b['new_game_bridge_revision_bound'] is True
    assert b['runtime']['app'] == cfg['profiles']['candidate']['app'] == '/userdata/gaze_model_migration_v1_20261014/app_v39_hft2_tdm_20261024'
    assert cfg['profiles']['candidate']['bit_sha256'] == BIT_SHA
    if kept:
        assert previous_selection['feature_controller']['binding'] == ref(O / 'binding.json')
    verification = load(O / 'running_application_verification.json')
    assert verification['state']['phase'] == 'FEATURE_RUNNING'
    assert verification['state']['runtime'] == b['runtime'] and verification['state']['supervisor'] == b['owner']
    assert verification['source_pins'] == 844 and verification['human_accepted'] is False
    exited = load(O / 'supervisor_exit.json')
    assert exited['owner']['pid'] == 214978 and exited['owner_exited'] is True and exited['normal_runtime_PASS'] is False
    rows = [(path, load(path)) for path in sorted(O.glob('rpc_*_sent.json'))]
    start_path, start = unique_rpc(rows, action='start_candidate_feature')
    assert start['response']['supervisor'] == b['owner'] and start['response']['value']['runtime'] == b['runtime']
    refs = dict(binding=ref(O / 'binding.json'), final_config=ref(O / 'config.json'),
        actual_complete_start=ref(start_path), source_bound_start_verification=ref(O / 'running_application_verification.json'),
        exact_previous_supervisor_exit=ref(O / 'supervisor_exit.json'),
        source_recovery_contract=ref(Y / 'handoff/failed_cleanup_recovery_v3/MANIFEST.json'),
        preserved_previous_failure=ref(Y / 'evidence/wbfix_actual_v2/longrun_failure_01.json'),
        preserved_previous_native_and_kernel=ref(Y / 'evidence/wbfix_actual_v2/native_failure_full_report.json'),
        source_only_target_install=ref(Y / 'evidence/sourceonly_target_install_v1/result.json'))
    assert refs['source_recovery_contract']['sha256'] == 'ad7349515f785d6b6c4360d9fcbdd34638fd43828bc5214ac3456f821a6f6608'
    for action in ('quiesce', 'retain_same_bit', 'reprobe', 'start_panel', 'capture_fpga', 'roundtrip'):
        path, row = unique_rpc(rows, native=action)
        assert row['response']['supervisor'] == b['owner']
        refs[action] = ref(path)
        value = row['response']['value']
        if action == 'retain_same_bit':
            assert value['bit_sha256'] == BIT_SHA and value['original_programming_receipt'] == b['candidate_programming_receipt']
            assert value['FPGA_programming_performed'] is False and value['normal_runtime_PASS'] is False
        elif action == 'capture_fpga':
            image = value['value']; end = image['end']
            assert image['status'] == 'PASS_ACTUAL_DUAL_STREAM_NATIVE_AND_CLEAN_CLOSE'
            assert end['errno'] == end['cleanup_errno'] == 0 and end['captured_frames'] == end['frames'] + end['software_dropped_frames']
            assert len(image['same_frame_tensor_checks']) == 3
            assert all(v['face128_byte_exact'] is True and v['palm192_byte_exact'] is True for v in image['same_frame_tensor_checks'])
        elif action == 'roundtrip':
            images = value['value']['images']
            assert value['value']['status'] == 'PASS_FULL_RGB1080_H2C_FPGA_C2H_BYTE_COMPARE' and len(images) == 2
            assert {v['chunk_bytes'] for v in images} == {65536, 1048576}
            assert all(v['iterations'] == 3 and v['bytes_per_image'] == 6220800 and v['returncode'] == 0 for v in images)
    measurement = None
    if kept:
        measurement = load(O / 'longrun_35min_v3/result.json')
        assert measurement['completed_requested_window'] is True and measurement['actual_seconds'] >= 2100
        assert measurement['status'] == 'LONGRUN_HEALTHY_OBSERVED_SPARSE' and measurement['error'] is None
        assert measurement['boot_id'] == b['boot_id'] and measurement['binding']['sha256'] == BINDING_SHA
        assert measurement['binding']['path'] == str(Path(b['owner_config']['path']).parent / 'binding.json').replace('\\', '/')
        assert measurement['owner_generation'] == b['root'].rsplit('/', 1)[-1] + ':' + b['feature_directory'].rsplit('/', 1)[-1]
        assert measurement['capture_session'] == f"{b['boot_id']}:{next(v for v in b['runtime']['owners'] if 'capture_native' in v['cmdline'])['pid']}:{next(v for v in b['runtime']['owners'] if 'capture_native' in v['cmdline'])['start_ticks']}"
        keep_path, keep = unique_rpc(rows, action='keep_feature_running')
        response = keep['response']
        assert keep['sequence'] > start['sequence']
        assert response['supervisor'] == b['owner'] and response['phase'] == phase
        assert response['value']['runtime']['owners'] == b['runtime']['owners'] and response['value']['keep_feature'] is True
        refs.update(longrun=ref(O / 'longrun_35min_v3/result.json'), actual_keep=ref(keep_path))
    spec = importlib.util.spec_from_file_location('_app39_publication_actual_api', Y / 'tools/execute_application_recovery_actual_v4.py')
    api = importlib.util.module_from_spec(spec); spec.loader.exec_module(api)
    remote_binding = api.REMOTE + '/binding.json'
    body = r'''import hashlib,json,struct,sys,time
from pathlib import Path
binding_path=Path(__BINDING__);assert hashlib.sha256(binding_path.read_bytes()).hexdigest()==__BINDING_SHA__
b=json.loads(binding_path.read_text());config_path=Path(b['owner_config']['path'])
assert hashlib.sha256(config_path.read_bytes()).hexdigest()==__CONFIG_SHA__
cfg=json.loads(config_path.read_text());assert len(cfg['files'])==844
for row in cfg['files']:assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256'],row['path']
sys.path.insert(0,cfg['recovery_owner_source_root']);import profile_delivery_v1 as d
c=d.load('_app39_publication_original_complete_control',b['control_source']);status,stop=d.functions(c,b);live=status(b)
state=json.loads((Path(b['root'])/'lifecycle/video_owner_state.json').read_text())
assert state['phase']==__PHASE__ and state['supervisor']==b['owner'] and state['runtime']==b['runtime']
assert not state['feature_errors'] and state['tick_error'] is None and state['application_start_error'] is None
assert state['main_handle_retained'] is True and state['feature_session_retained'] is True
assert state['main_returncode'] is None and state['automatic_restart'] is False
assert state['keep_feature'] is __KEEP_BOOL__
assert all(v['waited'] is False and v['returncode'] is None and v['log_thread_alive'] is True for v in state['auxiliary_children'].values())
app=json.loads(Path(state['application_health_path']).read_text());now=time.monotonic_ns()
assert 0<=now-app['timestamp_ns']<=3000000000 and app['controller']=={k:b['owner'][k] for k in ('pid','start_ticks')}
assert app['config_sha256']==__APPLICATION_SHA__ and app['boot_id']==b['boot_id']
assert app['game_error'] is None and app['game_factory_ready'] is True and app['battle_acceptance']==b['new_game_battle_acceptance']
assert app['battle_acceptance']['sha256']==__BATTLE_SHA__ and app['camera_created'] is False and app['inference_created'] is False
gh=app['game_bridge'];assert gh['closed'] is False and gh['fatal_error'] is None
assert all(gh[k]==app[k] for k in ('owner_generation','capture_session'))
assert all(gh[k] is False for k in ('camera_created','inference_created','feature_socket_created'))
raw=Path('/sys/module/anlogic_pci/notes/.note.gnu.build-id').read_bytes();n,z,kind=struct.unpack_from('<III',raw);start=12+((n+3)//4)*4
assert kind==3 and raw[12:12+n].rstrip(b'\0')==b'GNU' and raw[start:start+z].hex()==__BUILD_ID__
expected=json.loads(Path(cfg['recovery_driver_identity']['path']).read_text())
parameters={p.name:p.read_text().strip() for p in Path('/sys/module/anlogic_pci/parameters').iterdir()};assert parameters==expected['parameters']
print(json.dumps(dict(status='ACTUAL_APP39_SOURCE_BOUND_PUBLICATION_VERIFIED',live=live,state=state,application=app,source_pins=len(cfg['files']),actual_loaded_build_id=raw[start:start+z].hex(),parameters=parameters,human_accepted=False,read_only=True)))
'''
    values = dict(BINDING=remote_binding, BINDING_SHA=BINDING_SHA, CONFIG_SHA=CONFIG_SHA, PHASE=phase,
        APPLICATION_SHA=verification['application']['config_sha256'], BATTLE_SHA=BATTLE_SHA, BUILD_ID=BUILD_ID,
        KEEP_BOOL=kept)
    for key, value in values.items():
        body = body.replace('__' + key + '__', repr(value))
    actual = api.remote('verify_app39_publication_' + args.stage, body, timeout=45)
    actual_path = O / ('publication_verification_' + args.stage + '.json')
    save_new(actual_path, actual)
    refs['actual_publication_verification'] = ref(actual_path)
    bit = previous_selection['FPGA_SRAM_bit']
    assert bit['sha256'] == BIT_SHA
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    model = next(v for v in b['runtime']['owners'] if 'run_gaze.py' in v['cmdline'])
    capture = next(v for v in b['runtime']['owners'] if 'capture_native' in v['cmdline'])
    selection = dict(status=status, observed_utc=now, boot_id=b['boot_id'], FPGA_SRAM_bit=bit,
        original_programming_receipt=b['candidate_programming_receipt'], Flash_written=False, FPGA_programming_performed=False,
        app=b['runtime']['app'], npu_package=cfg['profiles']['candidate']['npu_package'], runtime=b['runtime'],
        model=model, capture=capture, model_pid=model['pid'], capture_pid=capture['pid'],
        model_session=b['runtime']['csv'].rsplit('/', 1)[0], launcher=b['runtime']['launcher'],
        selected_live_launcher_directory=b['root'] + '/lifecycle', selected_launch_directory=b['root'] + '/lifecycle',
        backend='RK3576_NPU_existing_models', readonly_runtime_observation=refs['actual_publication_verification'],
        persistent_runtime_supervisor=ref(O / 'ready.json'), active_driver=b['active_driver'], active_driver_build_id=BUILD_ID,
        feature_controller=dict(root=b['root'], owner=b['owner'], remote=api.REMOTE, owner_remote=api.REMOTE,
            owner_source=b['owner_source'], owner_config=b['owner_config']['path'], config=b['owner_config'],
            remote_binding=remote_binding, binding=ref(O / 'binding.json'), control=b['profile_control_source'],
            complete_control=b['control_source'], application_client=b['application_client_source']),
        feature_directory=b['feature_directory'], current_stop_request=b['runtime']['stop_request'],
        default_mode='visual', observed_requested_mode=actual['application']['requested_mode'], automatic_restart=False,
        original_Popen_and_EX_retained=True, longrun_accepted=kept,
        newbridge_bound=True, new_game_bridge_bound=True, new_game_battle_acceptance=b['new_game_battle_acceptance'],
        game_independent_battle_accepted=True, new_game_revision_acceptance=False, new_game_human_control_accepted=False,
        current_new_UI_optical_or_human_accepted=False, personal_calibration_effective_human_FPS_games_accepted=False,
        DMA_root_cause_fixed=False, historical_cleanup110_preserved=True,
        references=refs, previous_selection=old['selection'], previous_selection_historical_only=old['selection'],
        full_goal_complete=False)
    selection_path = O / ('current_kept_selection.json' if kept else 'current_running_selection.json')
    save_new(selection_path, selection)
    pointer = dict(status='POINTER_' + status, selection=ref(selection_path),
        scope='Actual app39 and original NPU/models/native with same9e82/WBv2; newv11 battle receipt and five-action factory bound. ' +
            ('Same-generation35-minute sparse observation passed; longer stability/root cause and all human tests remain open.' if kept else 'Full byte checks and original startup passed; longrun pending, no human acceptance.'))
    current_bytes = encoded(pointer)
    current_pin = future_ref(R / 'CURRENT_CAMERA.json', current_bytes)
    event = dict(status=status, observed_utc=now, references=refs, CURRENT=current_pin,
        current_selected_runtime_is_live=True, longrun_accepted=kept, newbridge_bound=True,
        game_independent_battle_accepted=True, new_game_human_control_accepted=False,
        human_nonempty_or_optical_accepted=False, original_models_native_and_gesture_policy_unchanged=True,
        DMA_root_cause_fixed=False, previous_cleanup110_preserved=True, Flash_written=False, FPGA_programming_performed=False,
        full_goal_complete=False,
        limitation='The prior5h51m terminal failure remains failed history. A new startup or35-minute window does not prove its DMA root cause fixed, continuous12h stability, valid-human NPU FPS, physical UI pixels, personal calibration or gaze/gesture game control.')
    if measurement is not None:
        event['longrun_seconds'] = measurement['actual_seconds']
        event['hardware_UI_counters_available'] = measurement['UI']['available']
    key = f'v{revision}_actual_app39_recovery_' + args.stage
    ledger['evidence'][key] = event
    descriptions = {
        'T02': '新app39在同9e82/WBv2下完成实际全quiesce、原SRAM保留、三组128/192张量及六次RGB1080逐字节检查并启动。旧5小时51分钟故障保留；metadata/nonce全链和长期安全启停仍需开发，不计DMA根因修复。',
        'U01': '新版应用UI现随app39实际运行，卡片/丰满手头眼/八轨迹实现已部署；新人脸、手、光学像素和八轨迹首笔仍待真人，不扩签旧骨架随动确认。',
        'U02': '复用原手/脸/眼NPU出口和原身份门禁；新app39源年龄提前拒绝及新relay原快照持久化已实际接线，无新增推理。非空关联/个人标定/真实轨迹仍待真人。',
        'U03': '214978真实cleanup110/原wait/精确空owner退出及完整新quiesce已保留；新233963持原Popen与唯一EX、同SRAM无JTAG/Flash。控制仅取本代绑定；K4实按和新版光学待测。',
        'U04': ('新app39同代35分钟只读观察通过并经原keep留用；' if kept else '新app39已恢复默认visual并开始本代长测；') + '旧5小时51分钟采集故障首因未定，仍属开发/故障定位；更长运行与真人共存/刷新/有效NPU时延均未验收。',
        'U05': '丰满手/头/双眼相对XYZ、人物登记/分页及八轨迹已随新app39部署；未签真实空间重建、操作者关联、投影标定、遮挡恢复或真人非空效果。',
    }
    if not kept:
        descriptions['G03'] = '实板发现友方城市格的移动目标被DEMO_CITY招募目标覆盖，需修复目标优先/类型及入城移动，保留明显招募和五动作；正常/拒绝路径、远程范围与风险独立对照仍待完整回归。'
    for task in ledger['tasks']:
        if task['id'] in descriptions:
            task['current_state'] = descriptions[task['id']]
            task.setdefault('evidence_keys', []).append(key)
            task['scheduling_bucket'] = 'development' if task['id'] in ('T02', 'U04', 'G03') else 'field_test'
    schedule['entries']['U04'] = dict(bucket='development',title='采集长时故障定位与孪生持续运行整合',
        estimate='故障定位及受控修复2–4小时有效工时；更长稳定性另需实际运行，真人30–90分钟另列',
        prerequisites='新233963同代持续运行与失败前诊断；真人正脸双眼和手；保留此前5小时51分钟cleanup110',
        basis='新代完整启动与字节检查已通过；即使本代35分钟通过也不能判定旧DMA故障根因解决，U04继续开发。')
    if not kept:
        schedule['entries']['G03'] = dict(bucket='development',title='友城入城目标覆盖修复与战斗规则回归',
            estimate='修复与实板回归2–4小时；风险数值独立对照1–2小时（共享战役）',
            prerequisites='当前原生Freeciv目标构造/选择逻辑；移动入友城与招募并存，五动作及拒绝路径不得改状态',
            basis='已出现真实友方城格被DEMO_CITY覆盖的实现问题，需从待实测移回开发；不把此前远程扣血或胜利结算扩签全部边界。')
    for task_id in ('U01', 'U02', 'U03', 'U05'):
        schedule['entries'][task_id]['bucket'] = 'field_test'
    schedule['entries']['T02']['bucket'] = 'development'
    for task_id in (('U04',) if kept else ('U04', 'G03')):
        estimates['main'][task_id] = [schedule['entries'][task_id]['title'], schedule['entries'][task_id]['estimate']]
    schedule['updated_utc'] = now
    next_action = '保持本代visual及原EX/Popen；继续采集长时故障定位、G03目标覆盖修复和游戏回归。用户方便后再做P1登记/光学/八轨迹/个人标定/五动作真人验收。'
    ledger.update(revision=revision, previous_ledger=prior, updated_utc=now, publisher=ref(__file__), full_goal_complete=False,
        current_camera_selection=current_pin, next_safe_action=next_action)
    ledger['first_video_milestone']['actual_new_UI_application'] = event
    ledger['first_video_milestone']['human_availability'] = '用户约12小时后配合；此前继续工程，不将等待或空场景计为真人通过。'
    ledger['task_scheduling'] = future_ref(R / 'TASK_SCHEDULING.json', encoded(schedule))
    out.mkdir()
    save_new(out / 'ledger.json', ledger)
    progress.update(observed_utc=now, full_task_ledger=ref(out / 'ledger.json'), protected_CURRENT=current_pin)
    progress['active_work'].update(status=status, current_selected_runtime_is_live=True, actual_new_UI_application=event, next_action=next_action)
    progress['first_video_milestone']['actual_new_UI_application'] = event
    progress['current_runtime_stop_rule'] = '当前233963持原Popen与唯一硬件EX，默认visual；以最新CURRENT/binding核boot/pid/start/config。不得另开模型、重用旧214978恢复入口或重复native动作；正常stop走原完整入口，故障保留并另行明确恢复，不自动重启。'
    new_values = {'TASK_SCHEDULING.json': schedule, 'PENDING_TASK_ESTIMATES.json': estimates,
        'CURRENT_CAMERA.json': pointer, 'GOAL_PROGRESS.json': progress}
    expected = {name: future_ref(R / name, before[name]) for name in shared_names}
    save_new(out / 'publication_prepared.json', dict(status='SOURCE_BOUND_PUBLICATION_PREPARED',stage=args.stage,
        expected_before=expected, selected_after=current_pin, full_goal_complete=False))
    # Compare all shared inputs before the first mutation, then compare each
    # immediately before its atomic replace. On conflict retain this journal;
    # never overwrite a concurrent publisher or silently rebase its ledger.
    assert all((R / name).read_bytes() == before[name] for name in shared_names), 'Publication inputs changed; no shared files written'
    applied = []
    for name in ('TASK_SCHEDULING.json', 'PENDING_TASK_ESTIMATES.json', 'CURRENT_CAMERA.json', 'GOAL_PROGRESS.json'):
        target = R / name
        assert target.read_bytes() == before[name], 'Publication CAS conflict; inspect journal, do not retry'
        temporary = R / (name + f'.app39_v{revision}_{args.stage}.tmp')
        with temporary.open('xb') as stream:
            stream.write(encoded(new_values[name]))
        assert target.read_bytes() == before[name], 'Publication CAS conflict before replace'
        os.replace(temporary, target)
        applied.append(name)
        save_new(out / ('applied_' + str(len(applied)) + '.json'), dict(applied=applied, latest=ref(target)))
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(R / 'tools/refresh_pending_tasks.py')], cwd=R, capture_output=True)
    (out / 'refresh.stdout').write_bytes(result.stdout); (out / 'refresh.stderr').write_bytes(result.stderr)
    assert result.returncode == 0
    for name in ('GOAL_PROGRESS.json', 'CURRENT_CAMERA.json', 'PENDING_TASKS.md', 'PENDING_TASKS.json', 'PENDING_FIELD_TESTS.md', 'PENDING_FIELD_TESTS.json', 'TASK_SCHEDULING.json', 'PENDING_TASK_ESTIMATES.json'):
        source = R / name
        (out / (source.stem + '_snapshot' + source.suffix)).write_bytes(source.read_bytes())
    save_new(out / 'publication.json', dict(status=status, stage=args.stage, revision=revision,
        current_selected_runtime_is_live=True, longrun_accepted=kept, new_game_human_control_accepted=False,
        DMA_root_cause_fixed=False, full_goal_complete=False))
    print('ACTUAL_APP39_RECOVERY_PUBLISHED', revision, args.stage)


if __name__ == '__main__':
    main()
