"""Close actual four-unit recruitment and correct bounded-log measurement."""
from collections import Counter,defaultdict
import copy
import datetime
import os
from pathlib import Path
import subprocess
import sys
from publish_video_running_v1 import R,Y,load,save,ref


def main():
    before=(R/'GOAL_PROGRESS.json').read_bytes();progress=load(R/'GOAL_PROGRESS.json');prior=progress['full_task_ledger']
    assert ref(prior['path'])==prior
    ledger=copy.deepcopy(load(prior['path']));revision=ledger['revision']+1
    game=R.parent/'freeciv-rk3576-gaze-demo'
    root=game/'evidence/game_recruit_regression_20261024_v1/raw/board_evidence'
    recruited=load(root/'v3/result.json');returned=load(root/'final_verification.json')
    assert recruited['passed'] and recruited['native_recruitment_passed'] and recruited['original_launcher_retained'] and recruited['pins_unchanged']
    assert not recruited['human_input'] and not recruited['camera_or_inference_started'] and not recruited['rules_or_gold_or_HP_modified']
    assert returned['status']=='PASS_NATIVE_RECRUITMENT_AND_NORMAL_MENU_RETURN' and returned['no_native_client_or_server_remaining']
    assert returned['source_commit']=='1153f731e6cc41d98f6f3a6a60090c256006a86d' and len(returned['pinned_files'])==38
    assert returned['state']['phase']=='menu' and returned['state']['awake'] is False
    assert len(recruited['cases'])==2
    for case in recruited['cases']:
        assert case['passed'] and case['before']['gold']-case['after_purchase']['gold']==case['price']
        assert case['after_purchase']['awake'] is False
        assert case['spawned'] and all(v['type_id']==case['type_id'] and v['role']==case['role'] for v in case['spawned'])
    battle=game/'evidence/demo_delivery_20261023_v1/board_battle_pass.json'
    assert ref(battle)['sha256']=='f992926d062b12561ebd90fddf6fcd643d4e96af40ad655d6a4d94533466889b'
    measurement=Y/'evidence/passive_measurement_v2/result.json';m=load(measurement)
    assert ref(m['tests']['path'])==m['tests']
    tests=load(m['tests']['path']);assert tests['status']=='PASS_OFFLINE_PASSIVE_MEASUREMENT_V2' and tests['tests']==19 and tests['failures']==tests['errors']==0
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    event=dict(status='FOUR_UNIT_NATIVE_RECRUITMENT_ACCEPTED_HUMAN_CONTROL_PENDING',
        references=dict(recruitment=ref(root/'v3/result.json'),normal_menu_return=ref(root/'final_verification.json'),prior_same_version_native_battles=ref(battle)),
        same_source_commit=returned['source_commit'],pinned_source_ELF_rules_files=38,
        prices=dict(Horsemen=48,Archers=81),new_native_unit_ids=[129,130],
        all_four_unit_purchase_and_spawn_covered=True,original_five_action_dynamic_target_interface=True,
        confirmation_returns_asleep=True,human_game_accepted=False,full_goal_complete=False)
    key=f'v{revision}_four_unit_native_recruitment';ledger['evidence'][key]=event
    for task in ledger['tasks']:
        if task['id']=='G01':
            assert task['status']=='PARTIAL';task['status']='DONE';task.setdefault('evidence_keys',[]).append(key)
            task['current_state']='同一1153f731源码/38份源ELF规则pins，原Legion/Catapult实际购买出兵加本次Horsemen/Archers原UDP动态目标回归，四类全部覆盖。Horsemen扣48生成129、Archers扣81生成130，确认后休眠、下一回合原生出兵；未改gold/HP/rules。原同一launcher正常回开始页。此项为游戏招募功能通过，真人视线/五手势继续归G04/M11/M12。'
    mk=f'v{revision}_passive_measurement_source_correction'
    ledger['evidence'][mk]=dict(status='PASS_FRESH_HEALTH_AND_STALE_HARDWARE_LOG_SEPARATION',reference=ref(measurement),tests=19,
        original_results_preserved=True,online_program_modified=False,first_two_windows_hardware_accepted=[700,690],
        additional_seconds=123.109871334,additional_software_received=4672,additional_software_enqueued=1208,
        additional_hardware_counters_available=False,additional_hardware_rate=None,valid_human_accepted=False)
    for task in ledger['tasks']:
        if task['id'] in ('U01','U02','U03','U04','U05'):
            task.setdefault('evidence_keys',[]).append(mk)
    counts=defaultdict(Counter)
    for task in ledger['tasks']:counts[task['scope']][task['status']]+=1
    ledger['scope_status_counts']={k:dict(v) for k,v in counts.items()}
    ledger['active_main_status_counts']=dict(Counter(t['status'] for t in ledger['tasks'] if t['status'] not in ('DEFERRED_BY_USER','REMOVED_FROM_SCOPE')))
    ledger.update(revision=revision,previous_ledger=prior,updated_utc=now,publisher=ref(__file__),full_goal_complete=False)
    ledger['next_safe_action']='保持新版孪生及游戏开始页；真人入镜后P1显式登记、三维随动/八轨迹/标定/五动作游戏。招募G01已完成移除；占点/增援/战斗边界及真人验收仍未完成。'
    out=Path(prior['path']).parent.parent/f'goal_task_ledger_v{revision}';assert not out.exists();out.mkdir();save(out/'ledger.json',ledger)
    progress.update(observed_utc=now,full_task_ledger=ref(out/'ledger.json'),protected_CURRENT=ref(R/'CURRENT_CAMERA.json'))
    progress['active_work'].update(native_recruitment_progress=event,passive_measurement_v2=ref(measurement),next_action=ledger['next_safe_action'])
    assert (R/'GOAL_PROGRESS.json').read_bytes()==before
    temp=R/'GOAL_PROGRESS.recruit_measurement.tmp';save(temp,progress);os.replace(temp,R/'GOAL_PROGRESS.json')
    result=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(result.stdout);(out/'refresh.stderr').write_bytes(result.stderr);assert result.returncode==0
    for name in ('GOAL_PROGRESS.json','CURRENT_CAMERA.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json'):
        source=R/name;(out/(source.stem+'_snapshot'+source.suffix)).write_bytes(source.read_bytes())
    save(out/'publication.json',dict(status=event['status'],revision=revision,full_goal_complete=False));print('RECRUITMENT_AND_MEASUREMENT_PROGRESS_PUBLISHED',revision)


if __name__=='__main__':main()
