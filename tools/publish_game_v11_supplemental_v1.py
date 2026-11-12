"""Publish frozen actual v11 game tests without changing the selected runtime."""
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
G = R.parent / 'freeciv-rk3576-gaze-demo'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')


def ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def save(path, value):
    with Path(path).open('xb') as stream:
        stream.write(encoded(value))


def main():
    names = ('GOAL_PROGRESS.json', 'TASK_SCHEDULING.json', 'PENDING_TASK_ESTIMATES.json', 'CURRENT_CAMERA.json')
    before = {name: (R / name).read_bytes() for name in names}
    progress, schedule, estimates, pointer = [json.loads(before[name]) for name in names]
    assert pointer['status'] == 'POINTER_ACTUAL_APP39_HFT2_GAME_V11_RUNNING_LONGRUN_PENDING'
    assert ref(pointer['selection']['path']) == pointer['selection']
    prior = progress['full_task_ledger']
    assert ref(prior['path']) == prior
    ledger = copy.deepcopy(load(prior['path']))
    assert ledger['revision'] == 267
    revision = ledger['revision'] + 1
    out = Path(prior['path']).parent.parent / f'goal_task_ledger_v{revision}'
    assert not out.exists()
    frozen = {
        'battle': (G / 'evidence/economic_sites_v11_20261024/board_battle_pass.json', 'd7408d9166befea7582cf0278b47f5162245ff744f4e060642967706eebafe1f'),
        'economy_defense': (G / 'evidence/game_watch_defense_regression_20261024_v1/result.json', 'c05b8b78f8033429e634a6ab62d489d048ed817975314fe7d44ef94ff9f45e8c'),
        'risk_and_input': (G / 'evidence/game_risk_guard_regression_20261024_v1/result.json', 'bfadb77c5145d43403aa8bd809aeb34df1ca6093b118fc586eebbc4a3c1e1e9d'),
    }
    pins = {}
    for key, (path, sha) in frozen.items():
        pins[key] = ref(path)
        assert pins[key]['sha256'] == sha, key
    battle, economy, risk = [load(frozen[key][0]) for key in frozen]
    assert battle['full_battle_passed'] and set(battle['tested_modes']) == {'campaign', 'hotseat'}
    assert not battle['human_input_accepted'] and not battle['human_npu_parallel_latency_accepted']
    assert economy['watch_income16']['passed'] and economy['actual_reinforcements']['passed']
    assert economy['actual_reinforcements']['turns'] == [9, 15, 21, 27]
    assert economy['actual_northern_defense']['passed'] and economy['actual_northern_defense']['script_attack_orders'] == 0
    assert economy['normal_return_menu']['actual_same_dialog_yes_settlement'] is True
    assert risk['status'] == 'PARTIAL_NATIVE_CASES_PASS_PRODUCT_GAPS_REMAIN'
    assert len(risk['actual_risk_comparisons']) == 2 and len(risk['native_gate_cases']) == 6
    assert all(row['passed'] for row in risk['native_gate_cases'])
    assert risk['actual_UI_frames']['risk_text_readable'] is False
    assert risk['menu_return']['passed'] and len(risk['remaining_product_work']) == 2
    assert len({v['boot_id'] for v in (economy, risk)}) == 1
    # Verify the exact source/rules used in the actual battle receipt; no new
    # private game candidate or untested build can inherit this acceptance.
    source_equivalence = {}
    for relative, sha in battle['inputs'].items():
        blob = subprocess.run(['git', 'show', battle['source_commit'] + ':' + relative],
            cwd=G, capture_output=True, check=True).stdout
        assert hashlib.sha256(blob).hexdigest() == sha, relative
        source_equivalence[relative] = dict(committed_blob_sha256=sha,
            local_worktree_bytes_equal=ref(G / relative)['sha256'] == sha)
    source = G / 'scenario/campaign.lua'
    assert ref(source)['sha256'] == battle['inputs']['scenario/campaign.lua']
    assert 'keep.owner==enemy and count<8' in source.read_text(encoding='utf8')
    pins['campaign_source'] = ref(source)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    key = f'v{revision}_actual_v11_economy_defense_risk_supplemental'
    event = dict(status='ACTUAL_V11_SUPPLEMENTAL_TESTS_PUBLISHED', observed_utc=now,
        evidence=pins, source_commit=battle['source_commit'],
        game_source_and_ELFs_unchanged=True, selected_application_unchanged=True,
        G02_accepted=True, G03_accepted=False, human_input_accepted=False,
        human_NPU_parallel_latency_accepted=False, full_goal_complete=False,
        limitations='Native input tests use real UDP and server state; they do not validate human gaze/gesture. AI assault/base survival is observed, not proof the absent enemy was killed. Risk labels are clipped and friendly-city movement remains a product gap. No new battle receipt or game owner switch.')
    ledger['evidence'][key] = event
    descriptions = {
        'G02': '现用v11实际单人T10及热座T21完整胜利，Mine易手与归属收入已核对；补测Watch第5回合+16、Watch+Mine+基地第10–20回合+68，AI夺矿后降为36，失Watch后为0。原生第9/15/21/27回合持续增援；冻结Lua仅在敌军count<8时补1队。第28→29回合AI攻击北部守军，Archer血量10→1且基地仍归己方；不声称敌军已被杀或玩家反击。此功能验收完成，友城入口和风险文字缺陷由G03继续修复。',
        'G03': 'v11两种当前状态战斗风险已与独立DP对照：0.935234/0.008903；过期/NaN/重复旧事件/目标外/丢视线/AP耗尽六类原生门禁通过，原测试器类型误判及只读纠正证据保留。实板仍有友城目标覆盖合法移动、风险文字裁切两项产品缺陷；地形/ZOC/地图边缘矩阵未穷尽。新v12仅私有修复，未替换现用v11，不计本项完成。',
        'G04': '现用v11同源码/规则/ELF已完成开始页→单人T10及热座T21实际原生胜利→返回开始页；招募/收入/远程/增援/基地守卫/攻城实测已存，旧热座等待器false保留并由零追加事件晚结算核实。资源为已测场景范围，真人个人标定、五手势、视线操控及主程序有效NPU并行延迟尚未测；G03缺陷继续修复，完整联合验收仍未完成。',
    }
    for task in ledger['tasks']:
        if task['id'] in descriptions:
            task['current_state'] = descriptions[task['id']]
            task.setdefault('evidence_keys', []).append(key)
            if task['id'] == 'G02':
                assert task['status'] == 'PARTIAL'
                task['status'] = 'DONE'
                task['acceptance_scope'] = 'Exact frozen v11 native economy, bounded periodic reinforcement and campaign base defense; no human control or v12 acceptance.'
    schedule['entries']['G02']['basis'] = 'v11实际收入/易手/持续增援/基地防守与整局攻城均已有冻结证据；DONE从两份待办视图移除，历史保留。'
    schedule['entries']['G03'].update(title='友城入城目标与风险文字裁切修复',
        estimate='私有修复/编译1–3小时；受控实板与边界回归1–2小时',
        prerequisites='新私有v12；现用v11保持，切换需原模型/游戏维护流程和新版本实际验收',
        basis='真实数值风险与六类拒绝已测，仍有两处产品缺陷，继续development。')
    schedule['entries']['G04'].update(title='真人游戏操控、有效NPU并行与新版联合验收',
        estimate='2–4小时（含个人标定，与M11/M12共享）',
        prerequisites='G03实板修复回归；用户入镜及个人标定；原模型原手势',
        basis='v11单/双人战役及经济防守已实测；真人操控和有效NPU并行尚未测，不以空场景时序代替。')
    for task_id in ('G03', 'G04'):
        row = schedule['entries'][task_id]
        estimates['main'][task_id] = [row['title'], row['estimate']]
    schedule['updated_utc'] = now
    scopes = collections.defaultdict(collections.Counter)
    for task in ledger['tasks']:
        scopes[task['scope']][task['status']] += 1
    ledger['scope_status_counts'] = {scope: dict(counts) for scope, counts in scopes.items()}
    ledger['active_main_status_counts'] = dict(collections.Counter(t['status'] for t in ledger['tasks'] if t['scope'] not in ('removed_by_user', 'deferred_by_user')))
    schedule_bytes = encoded(schedule)
    ledger.update(revision=revision, previous_ledger=prior, updated_utc=now, publisher=ref(__file__), full_goal_complete=False,
        next_safe_action='保持当前app39/9e82与游戏v11；完成35分钟同代观察后原keep；独立修G03及FPGA坏帧恢复，用户方便后做真人孪生/标定/五动作与并行测量。',
        task_scheduling=dict(path=str(R / 'TASK_SCHEDULING.json'), sha256=hashlib.sha256(schedule_bytes).hexdigest()))
    out.mkdir()
    save(out / 'source_equivalence.json', source_equivalence)
    save(out / 'ledger.json', ledger)
    progress.update(full_task_ledger=ref(out / 'ledger.json'), observed_utc=now)
    progress['active_work']['game_v11_supplemental'] = event
    values = {'GOAL_PROGRESS.json': encoded(progress), 'TASK_SCHEDULING.json': schedule_bytes, 'PENDING_TASK_ESTIMATES.json': encoded(estimates)}
    save(out / 'publication_prepared.json', dict(evidence=pins, unchanged_camera=ref(R / 'CURRENT_CAMERA.json'), previous_ledger=prior))
    assert all((R / name).read_bytes() == before[name] for name in names), 'CAS input conflict'
    for name, body in values.items():
        assert (R / name).read_bytes() == before[name], 'CAS publication conflict'
        temporary = R / (name + f'.game_v11_supplemental_{revision}.tmp')
        with temporary.open('xb') as stream:
            stream.write(body)
        assert (R / name).read_bytes() == before[name]
        os.replace(temporary, R / name)
    assert (R / 'CURRENT_CAMERA.json').read_bytes() == before['CURRENT_CAMERA.json']
    process = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(R / 'tools/refresh_pending_tasks.py')], cwd=R, capture_output=True)
    (out / 'refresh.stdout').write_bytes(process.stdout)
    (out / 'refresh.stderr').write_bytes(process.stderr)
    assert process.returncode == 0
    for name in (*values, 'CURRENT_CAMERA.json', 'PENDING_TASKS.json', 'PENDING_TASKS.md', 'PENDING_FIELD_TESTS.json', 'PENDING_FIELD_TESTS.md'):
        (out / ('snapshot_' + name)).write_bytes((R / name).read_bytes())
    assert 'G02' not in {t['id'] for view in ('PENDING_TASKS.json', 'PENDING_FIELD_TESTS.json') for t in load(R / view)['current_main']}
    save(out / 'publication.json', dict(revision=revision, status=event['status'], G02_accepted=True, G03_accepted=False, full_goal_complete=False))
    print('ACTUAL_V11_SUPPLEMENTAL_PUBLISHED', revision)


if __name__ == '__main__':
    main()
