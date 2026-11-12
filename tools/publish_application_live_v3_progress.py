"""Move completed UI implementation to field verification without granting acceptance."""
import copy
from collections import Counter,defaultdict
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
    o=Y/'evidence/application_actual_v3';p=R/'projects/model_image_ops_board_20261023'
    live=load(o/'live_publication.json');assert ref(R/'CURRENT_CAMERA.json')==live['CURRENT']
    bw=load(p/'evidence/combined_app_programmer_v3/result.json')
    assert bw['original_Popen_waited'] and bw['returncode']==0 and bw['candidate_kept'] and not bw['formal_restored'] and not bw['Flash_written']
    visual=load(o/'stability_visual_70s/result.json');trajectory=load(o/'stability_trajectory_70s/result.json')
    refs={name:ref(path) for name,path in {
        'actual_live_publication':o/'live_publication.json','current_binding':o/'binding.json',
        'actual_current_full_control':o/'final_application_verification.json',
        'visual_stability':o/'stability_visual_70s/result.json','trajectory_stability':o/'stability_trajectory_70s/result.json',
        'empty_game_gate':o/'game_empty_gate_12s/result.json','page2_control':o/'rpc_0013_sent.json',
        'page1_control':o/'rpc_0014_sent.json','final_same_owner_keep':o/'rpc_0015_sent.json',
        'actual_source_bound_ui_CLI':o/'actual_ui_cli_status.json',
        'third_programmer_terminal':p/'evidence/combined_app_programmer_v3/result.json',
        'third_inactive_package':p/'evidence/runtime_support_install_v3/result.json',
        'bounds_fix_and_73_contracts':p/'evidence/trajectory_bounds_v2/result.json',
        'real_prior_full_close':o/'inspect_00.json',
    }.items()}
    event=dict(status='ACTUAL_NEW_HFT2_APPLICATION_RUNNING_IMPLEMENTATION_READY_HUMAN_TEST_PENDING',references=refs,
        CURRENT=ref(R/'CURRENT_CAMERA.json'),owner=load(o/'ready.json')['supervisor'],
        bit_sha256='9e82d8cd50510a8480afe6a49f0e3cd61ef3194334fe225d65fb7bd7265c0e59',
        original_models_and_weights_retained=True,Flash_written=False,drivers_source_modified=False,
        visual_seconds=visual['seconds'],trajectory_seconds=trajectory['seconds'],
        visual_UI_updates=visual['UI']['counters_delta'],trajectory_UI_updates=trajectory['UI']['counters_delta'],
        valid_face_rows=visual['gaze']['valid_rows']+trajectory['gaze']['valid_rows'],
        valid_hand_rows=visual['hand']['valid_rows']+trajectory['hand']['valid_rows'],
        empty_scene_rates_are_not_human_NPU_FPS=True,source_bound_UI_CLI_passed=True,
        software_page_switch_passed=True,K4_device_opened=True,K4_physical_press_tested=False,
        game_factory_ready=True,game_mode_gate_and_empty_input_suppression_tested=True,
        new_UI_human_or_optical_accepted=False,eight_real_strokes_accepted=False,
        personal_calibration_accepted=False,human_game_accepted=False,full_goal_complete=False)
    key=f'v{revision}_actual_new_application_kept_implementation_ready';ledger['evidence'][key]=event
    states={
        'U01':'新应用式HFT2布局与八轨迹结果卡已完整TD、13项物理审查并随9e82部署。显示/轨迹模式各71秒稳定采样、总1390次UI更新及CRC/格式/序号0错误；当前无有效真人，不签八类真实笔画/光学效果。余项归待实测，失败则重开修复。',
        'U02':'真实同源face/hand/filtered出口、人物显式登记、8类原分类器与投影合同已接入当前app38/HAND2/SUPPORT2；源绑定CLI和游戏factory就绪。指尖越界拒帧修复已部署，73离线合同通过。真人登记关联、八笔分类首笔载入时效及个人投影未测。',
        'U03':'新UI+TDM全量TD及13级物理审查通过，setup/hold +0.004/+0.020ns；新9e82已实际SRAM下载、面板冷启动、正常完整owner交接。原生三组128/192张量、六次RGB1080往返已测；第三代page2/1控制实际accepted，K4已打开但未实按，光学仍待。',
        'U04':'旧HFT1用户确认骨架随动作变化，仅作基础链路通过。当前新HFT2第三代已稳定留用，前两代真实依赖/边界失败分别保留；非空三维、边缘/遮挡、物理K4、真人并行延迟和长测仍待。',
        'U05':'丰满手掌/手指、头眼几何、人物1/2分页与眼到屏示意已在新位流和统一owner部署。页2/1软件命令通过；未标定明确示意，未把相对XYZ作绝对标定。真人三维随动、左右手、双人登记/关联与投影需实测。',
    }
    for task in ledger['tasks']:
        if task['id'] in states:
            task['current_state']=states[task['id']];task['status']='PARTIAL';task.setdefault('evidence_keys',[]).append(key)
    counts=defaultdict(Counter)
    for task in ledger['tasks']:counts[task['scope']][task['status']]+=1
    ledger['scope_status_counts']={k:dict(v) for k,v in counts.items()}
    ledger['active_main_status_counts']=dict(Counter(t['status'] for t in ledger['tasks'] if t['status'] not in ('DEFERRED_BY_USER','REMOVED_FROM_SCOPE')))
    schedule=load(R/'TASK_SCHEDULING.json');estimates=load(R/'PENDING_TASK_ESTIMATES.json')
    values={
        'U01':('新版应用界面与八类真实轨迹实屏','20–40分钟（与U02/U04同轮）','真人正脸/单手入镜，原八轨迹逐笔完成，检查分类首笔载入和RESULT时效'),
        'U02':('人物登记、轨迹分类与标定投影实测','30–60分钟（与U04/U05同轮）','单人后双人，原手势/八轨迹；个人标定后验证投影'),
        'U03':('新版MIPI光学与K4物理分页实测','10–20分钟（与U04同轮）','现场看屏并按K4；软件分页已测，不代替实按'),
        'U04':('新版孪生真人随动、并行延迟与长测','首版5–10分钟；完整30–90分钟','新版已运行；正脸、双眼、单手入镜，真实动作及失效恢复'),
        'U05':('丰满手头眼三维、双人分页与投影实测','20–40分钟（与U02/U04同轮）','显式登记人物1/2、左右手与遮挡/恢复；投影需个人标定'),
    }
    for task_id,(title,estimate,prerequisites) in values.items():
        schedule['entries'][task_id]=dict(bucket='field_test',title=title,estimate=estimate,prerequisites=prerequisites,
            basis='当前完整实现、TD/物理、真实安装及有界持续运行已通过；剩余为真人/光学/物理按键验证，发现实现问题立即移回development，不计验收完成。')
        estimates['main'][task_id]=[title,estimate]
    now=datetime.datetime.now(datetime.timezone.utc).isoformat();schedule['updated_utc']=now
    save(R/'TASK_SCHEDULING.json',schedule);save(R/'PENDING_TASK_ESTIMATES.json',estimates)
    ledger.update(revision=revision,previous_ledger=prior,updated_utc=now,publisher=ref(__file__),full_goal_complete=False)
    ledger['first_video_milestone']['actual_new_UI_application']=event
    ledger['next_safe_action']='保持当前唯一owner和新界面，等待已通知的真人入镜；显式P1登记后先拍三维/头眼随动与失效恢复，再八轨迹、个人标定、五动作游戏及P2/K4。禁止为无人场景采样计有效NPU率。'
    out.mkdir();save(out/'ledger.json',ledger)
    progress.update(observed_utc=now,full_task_ledger=ref(out/'ledger.json'),protected_CURRENT=ref(R/'CURRENT_CAMERA.json'))
    progress['active_work'].update(status='HFT2_V3_LIVE_WAITING_HUMAN_FIELD_TEST',current_selected_runtime_is_live=True,actual_new_UI_application=event,next_action=ledger['next_safe_action'])
    progress['first_video_milestone']['actual_new_UI_application']=event
    progress['current_runtime_stop_rule']='当前唯一202401原owner已keep；只用CURRENT的新binding/profile控制或经验证的完整后继handoff。完整正常stop会退出owner，不得复用旧RPC、PID或恢复器。'
    assert (R/'GOAL_PROGRESS.json').read_bytes()==before
    temp=R/'GOAL_PROGRESS.application_live_v3.tmp';save(temp,progress);os.replace(temp,R/'GOAL_PROGRESS.json')
    result=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(result.stdout);(out/'refresh.stderr').write_bytes(result.stderr);assert result.returncode==0
    for name in ('GOAL_PROGRESS.json','CURRENT_CAMERA.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json','TASK_SCHEDULING.json','PENDING_TASK_ESTIMATES.json'):
        source=R/name;(out/(source.stem+'_snapshot'+source.suffix)).write_bytes(source.read_bytes())
    save(out/'publication.json',dict(status=event['status'],revision=revision,full_goal_complete=False));print('ACTUAL_APPLICATION_LIVE_PROGRESS_PUBLISHED',revision)


if __name__=='__main__':main()
