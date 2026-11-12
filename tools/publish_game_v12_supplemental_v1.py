"""Review/publish the exact standalone v12 G03 acceptance; never select runtime.

Default invocation only prints a read-only review. Publication requires explicit
--publish plus the reviewed current-ledger and CURRENT_CAMERA SHA256 values.
No SSH, application lifecycle, camera, game input or Git index operation exists.
"""
import argparse
import collections
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

R = Path(__file__).resolve().parents[1]
G = R.parent / 'freeciv-g03-v12-candidate_20261024'
OLD_G = R.parent / 'freeciv-rk3576-gaze-demo'
E = G / 'evidence/g03_v12_board_window_20261024_v1'
RECEIPT_SHA = '200c1d6c9be8adc94ce31a0afb7c017ec97229acc3eee6297cfffde857fbf904'
SOURCE = '1e4f3237cd723396c7e2cd871fd3e633a9457e31'
EVIDENCE_COMMIT = 'c702d3d604772712d4925554544a87b5e5442f90'
CLIENT = 'f027a7e6907fc152c66826679e332d3a31fa42de9fee746827b6e20b52922617'
SERVER = '5065562ce2ab47a11f7a7cc5f641bd8db3aadb723a5b54cbada34892a3487f6f'
V11_RECEIPT_SHA = 'd7408d9166befea7582cf0278b47f5162245ff744f4e060642967706eebafe1f'
NAMES = ('GOAL_PROGRESS.json', 'TASK_SCHEDULING.json', 'PENDING_TASK_ESTIMATES.json', 'CURRENT_CAMERA.json')
G03_DONE_WHEN = [
    '可行动范围与攻击候选符合原引擎规则，远程支援实际生效',
    '血量与预计胜率/风险来自当前状态，不能把胜率当结果保证',
]
LIMITS = [
    'Acceptance belongs only to native standalone v12 source1e4f/clientf027/server5065.',
    'The last directly verified default game was restored v11/a25/e67b/5065/d740 MENU; this publisher does not select or query a runtime.',
    'No v12/main-model parallel NPU latency, human gaze/gesture control, personal calibration or four-corner visual acceptance.',
    'Terrain/ZOC/map-edge rejection matrix is not exhaustive; the original G03 done_when does not require an exhaustive matrix.',
    'No new live application binding, camera selection, driver or FPGA change is granted by this ledger publication.',
]


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')


def ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def save_new(path, value):
    with Path(path).open('xb') as stream:
        stream.write(encoded(value))


def git_blob(repo, revision, relative):
    return subprocess.run(['git', 'show', revision + ':' + relative], cwd=repo,
                          capture_output=True, check=True).stdout


def validate_evidence():
    battle_path = E / 'board_battle_pass.json'
    assert ref(battle_path)['sha256'] == RECEIPT_SHA
    relative = battle_path.relative_to(G).as_posix()
    assert hashlib.sha256(git_blob(G, EVIDENCE_COMMIT, relative)).hexdigest() == RECEIPT_SHA
    battle = load(battle_path)
    assert battle['status'] == 'PASS_RK3576_NATIVE_GAME_BATTLE_AND_HOTSEAT'
    assert battle['full_battle_passed'] and set(battle['tested_modes']) == {'campaign', 'hotseat'}
    assert (battle['source_commit'], battle['client_sha256'], battle['server_sha256']) == (SOURCE, CLIENT, SERVER)
    assert not battle['human_gaze_or_gesture_accepted'] and not battle['parallel_NPU_latency_measured']
    assert battle['actual_display'] == ':0' and not battle['Xvfb_or_namespace_used']
    assert not battle['actual_four_corner_tooltip_visual_test'] and len(battle['inputs']) == 38
    pins = dict(battle=ref(battle_path), original_v11_battle=ref(OLD_G / 'evidence/economic_sites_v11_20261024/board_battle_pass.json'))
    assert pins['original_v11_battle']['sha256'] == V11_RECEIPT_SHA
    for name, digest in battle['evidence'].items():
        path = (E / name).resolve()
        assert path.is_relative_to(E.resolve()), 'Evidence escaped its frozen root'
        assert ref(path)['sha256'] == digest, name
        assert hashlib.sha256(git_blob(G, EVIDENCE_COMMIT, path.relative_to(G).as_posix())).hexdigest() == digest, name
    final_pins_path = E / 'raw/g03_native_window_v1/candidate_final_pins.json'
    final_pins = load(final_pins_path)
    assert final_pins['source_and_ELFs_unchanged_after_all_native_tests']
    expected = dict(battle['inputs'], **{'build-arm64/freeciv-gtk3.22': CLIENT, 'build-arm64/freeciv-server': SERVER})
    assert final_pins['candidate_pins'] == expected
    source_equivalence = {}
    for name, digest in battle['inputs'].items():
        content = git_blob(G, SOURCE, name)
        assert hashlib.sha256(content).hexdigest() == digest, name
        assert battle['source_equivalence'][name]['board_sha256'] == digest
        assert battle['source_equivalence'][name]['git_blob_content_sha256'] == digest
        source_equivalence[name] = dict(committed_blob_sha256=digest, board_final_sha256=digest,
            local_worktree_bytes_equal=ref(G / name)['sha256'] == digest)
    native = git_blob(G, SOURCE, 'upstream/freeciv-3.2.6/client/gui-gtk-3.22/demo_control.inc').decode('utf8')
    calls = ('pft_fill_unit_parameter(', 'unit_can_move_to_tile(', 'action_prob_vs_stack(',
             'action_prob_vs_city(', 'unit_win_chance(', 'demo_city_entry_path(', 'send_goto_path(')
    assert all(call in native for call in calls), 'Native engine qualification integration changed'
    campaign = load(E / 'raw/actual_campaign_v12_v1/result.json')
    hotseat = load(E / 'raw/actual_hotseat_v12_v1/result.json')
    assert campaign['passed'] and campaign['full_battle_accepted'] and campaign['final']['game_over']
    assert campaign['final']['outcome'] == 1 and campaign['final']['turn'] == 11 and campaign['victory_log']
    assert (campaign['purchases'], campaign['attack_commands'], campaign['bombard_commands']) == (6, 2, 2)
    bombard = [row for row in campaign['cases'] if row['name'] == 'native_bombard']
    assert len(bombard) == 2 and all(row['actual_hp_reduced'] for row in bombard)
    for row in bombard:
        assert any(row['before'].get(str(enemy['id'])) == 10 and enemy['hp'] == 8 for enemy in row['after'])
    assert hotseat['passed'] and hotseat['native_full_battle_accepted'] and hotseat['final']['game_over']
    assert hotseat['final']['outcome'] == 1 and hotseat['final']['turn'] == 20 and hotseat['victory_log']
    assert hotseat['handoffs'] == 36 and len(hotseat['combats']) == 5 and hotseat['economic_three_way_transfer_accepted']
    case_paths = ('city_campaign_ui_v1_001.json', 'hotseat_city_entry_v1_001.json', 'native_risk_v12_v1_001.json')
    city, city2, risk = [load(E / 'raw/native_suite_v12_v1' / name) for name in case_paths]
    assert all(row['completed_without_error'] and row['pins_unchanged'] and all(c['passed'] for c in row['cases']) for row in (city, city2, risk))
    assert len(city['cases']) + len(city2['cases']) == 4 and len(risk['cases']) == 10
    comparisons = [c for c in risk['cases'] if c['case'].startswith('actual_HUD_risk_')]
    assert len(comparisons) == 2
    assert {c['target']['win_chance'] for c in comparisons} == {0.935234, 0.008903}
    assert all(abs(c['expected'] - c['actual']) < 1.1e-6 and c['state_after_image']['selection_ready'] for c in comparisons)
    assert ref(E / 'risk_legion_actual.png')['sha256'] == '08ea64ddf1a0d7ad920913b47cdc2a6ae1daec50a66710845988505315881d75'
    assert ref(E / 'risk_warrior_actual.png')['sha256'] == 'b95eeee9127946e8590781e8bec1631efacc56c022e99779afe4266e72db0629'
    window = load(E / 'raw/g03_native_window_v1/progress.json')
    assert window['status'] == 'V12_WINDOW_ENDED_V11_RESTORED'
    terminal = window['candidate_terminal']
    assert terminal['supervisor_original_Popen_waited'] and terminal['supervisor_returncode'] == 0
    assert terminal['launcher_terminal']['original_Popen_waited'] and terminal['launcher_terminal']['returncode'] == 0
    for row in battle['loaded_native_process_proofs']:
        actual = load(E / row['evidence'])
        assert ref(E / row['evidence'])['sha256'] == row['sha256']
        assert actual['boot_id'] == battle['boot_id'] and actual['owner']['launcher']['pid'] == 246609
        assert actual['processes'] == row['processes']
        assert {p['loaded_elf_sha256'] for p in actual['processes']} == {CLIENT, SERVER}
    restored = load(E / 'raw/g03_native_window_v1/restore_final_proof.json')
    endpoint = load(E / 'restored_app39_endpoint_v2.json')
    assert restored['source_commit'] == 'a25ad69da6dc0c9c46496ab1765e394f224f831a' and restored['state']['phase'] == 'menu'
    assert restored['candidate_supervisor_and_launcher_absent'] and restored['server_sha256'] == SERVER
    assert endpoint['counts']['gaze'] == endpoint['counts']['actions'] == 0 and endpoint['counts']['replies'] == 6
    assert endpoint['game_socket_owners'][0]['identity']['pid'] == restored['owner']['launcher']['pid'] == 248966
    pins.update(native_case_receipt=ref(E / 'result.json'), board_final_pins=ref(final_pins_path),
        native_campaign=ref(E / 'raw/actual_campaign_v12_v1/result.json'),
        native_hotseat=ref(E / 'raw/actual_hotseat_v12_v1/result.json'),
        restored_v11=ref(E / 'raw/g03_native_window_v1/restore_final_proof.json'),
        original_app39_endpoint=ref(E / 'restored_app39_endpoint_v2.json'),
        limitations_and_failure_report=ref(E / 'README.md'), tool_failures=ref(E / 'tool_failures.json'))
    for item in pins.values():
        path = Path(item['path'])
        if path.is_relative_to(G.resolve()):
            committed = git_blob(G, EVIDENCE_COMMIT, path.relative_to(G).as_posix())
            assert hashlib.sha256(committed).hexdigest() == item['sha256'], 'Uncommitted evidence drift: ' + str(path)
    acceptance = dict(G03_original_done_when=G03_DONE_WHEN, G03_accepted_for_exact_tested_v12=True,
        engine_calls_verified=list(calls), native_bombard_HP_changes=['10 -> 8', '10 -> 8'],
        standalone_modes={'campaign': 11, 'hotseat': 20}, friendly_city_cases=4,
        risk_and_input_cases=10, complete_risk_visuals_reviewed=True,
        human_input_accepted=False, parallel_NPU_latency_accepted=False,
        current_default_runtime_selected_by_this_tool=False, limitations=LIMITS)
    return pins, source_equivalence, acceptance


def prepare():
    before = {name: (R / name).read_bytes() for name in NAMES}
    progress, schedule, estimates, pointer = [json.loads(before[name]) for name in NAMES]
    prior = progress['full_task_ledger']
    assert ref(prior['path']) == prior
    ledger = copy.deepcopy(load(prior['path']))
    assert not ledger['full_goal_complete'] and not progress['full_goal_complete']
    by_id = {row['id']: row for row in ledger['tasks']}
    assert by_id['G03']['done_when'] == G03_DONE_WHEN, 'Review changed acceptance criteria before publishing'
    assert by_id['G03']['status'] == 'PARTIAL', 'Already changed G03; do not publish a duplicate decision'
    assert by_id['G04']['status'] == 'IN_PROGRESS' and schedule['entries']['G04']['bucket'] == 'field_test'
    pins, source_equivalence, acceptance = validate_evidence()
    review = dict(status='READ_ONLY_REVIEW_READY_G03_EXACT_V12_DONE',
        publisher=ref(__file__), reviewed_prior_ledger=prior,
        reviewed_camera=ref(R / 'CURRENT_CAMERA.json'), camera_status_context_only=pointer.get('status'),
        root_inputs={name: ref(R / name) for name in NAMES}, evidence=pins,
        source_commit=SOURCE, evidence_commit=EVIDENCE_COMMIT, receipt_sha256=RECEIPT_SHA,
        acceptance=acceptance, status_changes={'G03': ['PARTIAL', 'DONE']},
        G04_status_and_bucket_unchanged=True, full_goal_complete=False,
        application_or_board_query_performed=False, camera_bytes_will_be_preserved=True)
    assert all((R / name).read_bytes() == before[name] for name in NAMES), 'Read-only review input raced'
    return before, progress, schedule, estimates, ledger, review, source_equivalence


def publish(data, expected_ledger, expected_camera):
    before, progress, schedule, estimates, ledger, review, source_equivalence = data
    assert review['reviewed_prior_ledger']['sha256'] == expected_ledger, 'Reviewed ledger changed'
    assert review['reviewed_camera']['sha256'] == expected_camera, 'Reviewed camera pointer changed'
    prior = review['reviewed_prior_ledger']
    revision = ledger['revision'] + 1
    out = Path(prior['path']).parent.parent / f'goal_task_ledger_v{revision}'
    assert not out.exists(), 'Do not overwrite another publication'
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    key = f'v{revision}_actual_v12_G03_native_fix_supplemental'
    event = dict(status='ACTUAL_V12_G03_NATIVE_FIX_AND_TWO_MODE_BATTLE_PUBLISHED',
        observed_utc=now, evidence=review['evidence'], source_commit=SOURCE,
        client_sha256=CLIENT, server_sha256=SERVER, evidence_commit=EVIDENCE_COMMIT,
        G03_accepted=True, G04_accepted=False, acceptance_scope=review['acceptance'],
        selected_application_unchanged=True, selected_camera_unchanged=True,
        runtime_selection_unchanged=True, last_verified_default_game='v11/d740 restored MENU',
        human_input_accepted=False, human_NPU_parallel_latency_accepted=False,
        full_goal_complete=False)
    ledger['evidence'][key] = event
    for task in ledger['tasks']:
        if task['id'] == 'G03':
            task.update(status='DONE', current_state='新v12源1e4f/clientf027/server5065已在RK真实:0独立验收：单人T11与热座T20原生胜利；原生可达范围/攻击资格/路径调用与AP拒绝有证据，弓兵两次实际使敌HP10→8。友城单人及双席共4case，确认休眠；完整风险UI与独立DP对照及拒绝输入共10case。原G03两条done_when已满足，仅签此v12实现；最后验证的默认游戏仍v11/d740，主程序新绑定/受控切换/真人及NPU并行由G04保留。四角实屏及地形/ZOC全矩阵未穷尽，不扩张验收。',
                acceptance_scope='Exact standalone RK3576 v12 source1e4f, clientf027, server5065 and receipt200c; does not claim selected v11 was fixed or accept human/parallel-NPU integration.',
                acceptance_validation=review['acceptance'])
            task.setdefault('evidence_keys', []).append(key)
        elif task['id'] == 'G04':
            task['current_state'] = '新v12源1e4f/clientf027/server5065已独立完成单人T11、热座T20原生胜利、三次Mine易手/收入、4友城与10风险/拒绝case；新收据200c与38源+2ELF已冻结，G03实现验收完成。原v11/d740仍是最后验证的默认MENU；本次发布不切游戏或主程序。待匹配新收据的主程序bundle、正常受控版本切换、真人个人标定/五手势/视线操控及有效NPU并行延迟；四角实屏未测，不计完整联合验收。'
            task.setdefault('evidence_keys', []).append(key)
    schedule['entries']['G03'].update(title='v12友城入口与完整风险提示（已实板完成）',
        estimate='已完成；真人/并行与部署联动由G04承接', prerequisites='',
        basis='原G03两条验收定义由实际v12原生范围/远程HP变化、当前风险与4友城/10门控证据满足；DONE自动从待完成/待实测视图移除。')
    schedule['entries']['G04'].update(
        prerequisites='匹配v12收据200c的主程序bundle与正常受控切换；用户入镜/个人标定；原模型原手势及有效NPU并行采样',
        basis='v12两模式原生战役与G03实现已实板验收；默认选择未由本发布改变，真人及有效NPU并行未测，原field_test/status保持。')
    estimates['main']['G03'] = [schedule['entries']['G03']['title'], schedule['entries']['G03']['estimate']]
    schedule['updated_utc'] = now
    scopes = collections.defaultdict(collections.Counter)
    for task in ledger['tasks']:
        scopes[task['scope']][task['status']] += 1
    ledger['scope_status_counts'] = {scope: dict(counts) for scope, counts in scopes.items()}
    ledger['active_main_status_counts'] = dict(collections.Counter(t['status'] for t in ledger['tasks'] if t['scope'] not in ('removed_by_user', 'deferred_by_user')))
    schedule_bytes = encoded(schedule)
    ledger.update(revision=revision, previous_ledger=prior, updated_utc=now, publisher=ref(__file__),
        full_goal_complete=False, task_scheduling=dict(path=str(R / 'TASK_SCHEDULING.json'), sha256=hashlib.sha256(schedule_bytes).hexdigest()))
    # Preserve current root recovery/FPGA priorities. Add only this game's next step.
    ledger['next_safe_action'] = ledger.get('next_safe_action', '') + ' 游戏后续：受控选择新v12并配匹配收据的主程序bundle，完成G04真人与有效NPU并行实测；本发布不选运行时。'
    out.mkdir()
    save_new(out / 'read_only_review.json', review)
    save_new(out / 'source_equivalence.json', source_equivalence)
    save_new(out / 'ledger.json', ledger)
    progress.update(full_task_ledger=ref(out / 'ledger.json'), observed_utc=now, full_goal_complete=False)
    progress['active_work']['game_v12_G03_supplemental'] = event
    values = {'GOAL_PROGRESS.json': encoded(progress), 'TASK_SCHEDULING.json': schedule_bytes, 'PENDING_TASK_ESTIMATES.json': encoded(estimates)}
    save_new(out / 'publication_prepared.json', dict(review=review, previous_ledger=prior, unchanged_camera=review['reviewed_camera']))
    assert all((R / name).read_bytes() == before[name] for name in NAMES), 'CAS input conflict'
    staged = {}
    for name, body in values.items():
        temporary = R / (name + f'.game_v12_supplemental_{revision}.tmp')
        with temporary.open('xb') as stream:
            stream.write(body)
        staged[name] = temporary
    assert all((R / name).read_bytes() == before[name] for name in NAMES), 'CAS publication conflict'
    for name, temporary in staged.items():
        assert (R / name).read_bytes() == before[name], 'Concurrent root publisher conflict'
        assert (R / 'CURRENT_CAMERA.json').read_bytes() == before['CURRENT_CAMERA.json']
        os.replace(temporary, R / name)
    process = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(R / 'tools/refresh_pending_tasks.py')], cwd=R, capture_output=True)
    (out / 'refresh.stdout').write_bytes(process.stdout)
    (out / 'refresh.stderr').write_bytes(process.stderr)
    assert process.returncode == 0
    assert (R / 'CURRENT_CAMERA.json').read_bytes() == before['CURRENT_CAMERA.json']
    views = [load(R / name) for name in ('PENDING_TASKS.json', 'PENDING_FIELD_TESTS.json')]
    assert 'G03' not in {row['id'] for view in views for row in view['current_main']}
    assert 'G04' in {row['id'] for row in views[1]['current_main']}
    for name in (*values, 'CURRENT_CAMERA.json', 'PENDING_TASKS.json', 'PENDING_TASKS.md', 'PENDING_FIELD_TESTS.json', 'PENDING_FIELD_TESTS.md'):
        (out / ('snapshot_' + name)).write_bytes((R / name).read_bytes())
    save_new(out / 'publication.json', dict(revision=revision, status=event['status'], G03_accepted=True,
        G04_accepted=False, full_goal_complete=False, unchanged_camera=ref(R / 'CURRENT_CAMERA.json')))
    print('ACTUAL_V12_G03_SUPPLEMENTAL_PUBLISHED', revision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--expected-ledger-sha256')
    parser.add_argument('--expected-camera-sha256')
    args = parser.parse_args()
    if args.publish and (not args.expected_ledger_sha256 or not args.expected_camera_sha256):
        parser.error('Publication requires both reviewed SHA256 guards')
    data = prepare()
    if not args.publish:
        print(encoded(data[5]).decode('utf8'), end='')
        return
    publish(data, args.expected_ledger_sha256, args.expected_camera_sha256)


if __name__ == '__main__':
    main()
