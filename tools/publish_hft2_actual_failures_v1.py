"""Record full new-UI physical success separately from two real app failures."""
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
    out=Path(prior['path']).parent.parent/f'goal_task_ledger_v{revision}';assert not out.exists()
    a=Y/'evidence/application_actual_v1';b=Y/'evidence/application_actual_v2';p=R/'projects/model_image_ops_board_20261023'
    refs={name:ref(path) for name,path in {
        'complete_build_and_physical_manifest':p/'delivery/combined_app_trial_v1/MANIFEST.json',
        'new_UI_physical':p/'evidence/combined_app_final_review_v4/result.json',
        'inactive_install':Y/'evidence/application_inactive_install_v2/result.json',
        'actual_ARM_import_validation':Y/'evidence/application_inactive_install_v2/actual_inert_validation.json',
        'new_bit_native_tensors':a/'rpc_0006_sent.json',
        'new_bit_six_full_images':a/'rpc_0007_sent.json',
        'first_hand_import_failure':a/'first_start_failed_logs.json',
        'first_full_formal_recovery':a/'formal_recovery_publication.json',
        'HAND2_inert_validation':p/'evidence/hand_dependency_install_v2/result.json',
        'second_actual_full_start':b/'rpc_0006_sent.json',
        'second_hand_bounds_failure':b/'first_start_failed_logs.json',
        'second_original_full_close':b/'rpc_0008_sent.json',
        'second_resource_exit':b/'failed_supervisor_exit.json',
        'bounds_fix_source':p/'ui_runtime_support_v2/MANIFEST.json',
        'bounds_fix_73_contracts':p/'evidence/trajectory_bounds_v2/result.json',
    }.items()}
    assert load(p/'evidence/combined_app_final_review_v4/result.json')['status']=='PASS_FULL_NEW_UI_PHYSICAL_AUDIT'
    assert load(b/'rpc_0008_sent.json')['response']['value']['status']=='FEATURE_CLOSED_WITH_FAILURES'
    current=ref(R/'CURRENT_CAMERA.json')
    event=dict(status='FULL_HFT2_UI_PHYSICAL_PASSED_ACTUAL_RUNTIME_BLOCKED_BY_HAND_BOUNDARY',references=refs,CURRENT=current,
        full_bit_sha256='9e82d8cd50510a8480afe6a49f0e3cd61ef3194334fe225d65fb7bd7265c0e59',
        full_TD_completed=True,final_setup_ns=.004,final_hold_ns=.020,TNS=0,physical_stages_passed=13,
        actual_tensor_128_192_byte_comparisons=3,actual_full_RGB1080_roundtrip_images=6,
        first_start_failure='Missing transitive pcie_preview_reader module in independent hand package; preserved then full formal/app34 recovery.',
        second_start_initially_succeeded=True,second_hand_samples=1290,second_hand_seconds=46.88798957702238,
        second_failure='Actual out-of-range index fingertip raised in trajectory UI snapshot and ended existing hand consumer.',
        second_original_main_wait_returncode=0,second_native_cleanup_errno=0,second_hand_returncode=1,
        second_failed_feature_status_preserved=True,second_supervisor_retired_after_resource_checks=True,
        current_camera_owner=None,current_actual_SRAM='9e82d8',sole_Windows_programmer_retains_formal_rollback=True,
        bounds_fix_contracts_passed=73,bounds_fix_deployed=False,
        new_UI_human_or_game_accepted=False,full_goal_complete=False)
    key=f'v{revision}_new_UI_full_physical_and_actual_application_failures';ledger['evidence'][key]=event
    for task in ledger['tasks']:
        if task['id'] in ('U01','U02','U03','U04','U05'):
            task.setdefault('evidence_keys',[]).append(key)
            task['current_state']+=' 新HFT2+TDM全量TD与13项最终物理审查通过，实际新位流128/192字节及6整帧往返通过。首启漏Python传递依赖已独立补齐；第二代实际整链启动并处理1290手样本后被指尖越界异常中止。当前资源已回收，新73项边界修复待独立部署，不能签新版真人/轨迹/游戏或持续运行通过。'
    ledger.update(revision=revision,previous_ledger=prior,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),publisher=ref(__file__),full_goal_complete=False)
    ledger['first_video_milestone']['actual_new_UI_application']=event
    ledger['next_safe_action']='优先以真实失败close/exit证明恢复完整app34；独立support2拒绝越界而不崩溃，补齐已正常main-reap但手失败的恢复门禁；再一次部署新UI，稳定后通知真人登记/轨迹/游戏。'
    out.mkdir();save(out/'ledger.json',ledger)
    progress.update(observed_utc=ledger['updated_utc'],full_task_ledger=ref(out/'ledger.json'),protected_CURRENT=current)
    progress['active_work'].update(status='HFT2_BOUNDARY_REPAIR_AND_COMPLETE_RECOVERY',current_selected_runtime_is_live=False,actual_new_UI_application=event,next_action=ledger['next_safe_action'])
    progress['first_video_milestone']['actual_new_UI_application']=event
    progress['current_runtime_stop_rule']='当前旧代199739已实际原stop回收并退役；无相机owner。SRAM为9e82，同一Windows programmer保留恢复通道。不得向旧binding重复请求；按新恢复owner的fresh窗口恢复，不能伪造hand rc1为正常通过。'
    assert (R/'GOAL_PROGRESS.json').read_bytes()==before
    temp=R/'GOAL_PROGRESS.hft2_failures.tmp';save(temp,progress);os.replace(temp,R/'GOAL_PROGRESS.json')
    result=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(result.stdout);(out/'refresh.stderr').write_bytes(result.stderr);assert result.returncode==0
    for name in ('GOAL_PROGRESS.json','CURRENT_CAMERA.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json'):
        source=R/name;(out/(source.stem+'_snapshot'+source.suffix)).write_bytes(source.read_bytes())
    save(out/'publication.json',dict(status=event['status'],revision=revision,full_goal_complete=False));print('HFT2_ACTUAL_PROGRESS_RECORDED',revision)


if __name__=='__main__':main()
