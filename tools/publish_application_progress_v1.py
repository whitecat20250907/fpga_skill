"""Publish independent game wins and tested UI implementation, retaining gaps."""
from collections import Counter,defaultdict
import copy
import datetime
import os
from pathlib import Path
import subprocess
import sys
from publish_video_running_v1 import R,Y,load,save,ref


def main():
    before=(R/'GOAL_PROGRESS.json').read_bytes();p=load(R/'GOAL_PROGRESS.json');prior=p['full_task_ledger']
    assert ref(prior['path'])==prior
    old=load(prior['path']);l=copy.deepcopy(old);revision=old['revision']+1
    out=Path(prior['path']).parent.parent/f'goal_task_ledger_v{revision}';assert not out.exists();out.mkdir()
    game=R.parent/'freeciv-rk3576-gaze-demo'
    refs={
        'same_function_successor':Y/'evidence/successor_actual_v1/result.json',
        'same_function_control':Y/'evidence/successor_actual_v1/MANIFEST.json',
        'game_battle':game/'evidence/demo_delivery_20261023_v1/board_battle_pass.json',
        'game_report':game/'BOARD_TEST_REPORT.md',
        'HFT2':Y/'evidence/hft2_app_v1/result.json',
        'registered_scene':Y/'evidence/app_scene_v2/result.json',
        'dashboard_pixels':Y/'ui_app_v1/dashboard/evidence/pixel_v4/result.json',
        'FPGA_overlay':Y/'ui_app_v1/fpga_delivery_v1/manifest.json',
    }
    battle=load(refs['game_battle'])
    assert battle['full_battle_passed'] is True and battle['tested_modes']==['campaign','hotseat']
    assert ref(refs['game_battle'])['sha256']=='f992926d062b12561ebd90fddf6fcd643d4e96af40ad655d6a4d94533466889b'
    observation=dict(status='NATIVE_BOTH_GAME_MODES_PASSED_NEW_UI_LOCAL_CONTRACTS_PASSED_FULL_INTEGRATION_PENDING',
        references={k:ref(v) for k,v in refs.items()},game_source_commit='1153f731e6cc41d98f6f3a6a60090c256006a86d',
        campaign_native_game_over_turn=11,hotseat_native_game_over_turn=14,hotseat_handovers=24,
        game_human_input_accepted=False,game_human_NPU_parallel_latency_accepted=False,
        new_UI_TD_or_hardware_accepted=False,full_goal_complete=False)
    key=f'v{revision}_both_native_game_modes_and_application_UI_progress';l['evidence'][key]=observation
    states={
        'G01':'v10四类生产卡实际选择；6次真实扣费和后续出兵覆盖Catapult/Legion。Horsemen/Archers有真实开局行动，尚缺本版各自购买出兵专项；保持PARTIAL。',
        'G02':'v10村庄真实占领收入+24/回合、第9回合敌方Horsemen增援、敌基地真实攻破胜利；Mine/Watch收入、第15/21波、夺点再失守和己方基地防守尚未专项验收，保持PARTIAL。',
        'G03':'v10原生寻路/近战HP与胜率候选已测；Bombard单人10→8/热座10→9且AP3→0。当前为相邻目标；2格/迷雾/ZOC负例矩阵和风险边界仍待测，保持PARTIAL。',
        'G04':'同一v10源码/规则/ELF：从开始页完成单人11回合与热座14回合原生game_over，24次交接，胜利后返回开始页通过。游戏静置/选点/战斗资源已测；真人视线五手势、个人标定和同步身份的主程序并行NPU延迟未测。',
        'U01':'新版应用式布局、丰满掌面/手指、八类结果卡、单眼→屏幕示意已实现；实际RTL五完整帧3072000像素/三周期无X通过。完整FPGA覆写包已冻结，尚待TDM全量TD/实屏。',
        'U02':'HFT2人物/手势/轨迹/模式元数据已实现，Python/native/真实接收器31输入通过；真实注册控制器与场景15项通过。固定原末笔结束时钟、个人标定和同runtime/track绑定；统一实际producer/owner接线仍集成中。',
        'U03':'8 HDL与4资源完整覆写包已冻结、完整twin_pcie_ui展开通过。页/几何同vblank、g3/g4正交和350ms/1200ms真实RTL测试通过；全量TD、K4实按、正式部署/完整恢复仍待。',
        'U05':'新版温暖掌面/粗手指、人物1/2页、真实轨迹与眼屏投影的host/RTL已实现并本机验证；当前实屏仍为先前已确认基础骨架，新版真人与双人页实测未签。',
    }
    for t in l['tasks']:
        if t['id'] in states:
            t['current_state']=states[t['id']];t.setdefault('evidence_keys',[]).append(key)
    scopes=defaultdict(Counter)
    for t in l['tasks']:scopes[t['scope']][t['status']]+=1
    l['scope_status_counts']={k:dict(v) for k,v in scopes.items()}
    l['active_main_status_counts']=dict(Counter(t['status'] for t in l['tasks'] if t['status'] not in ('DEFERRED_BY_USER','REMOVED_FROM_SCOPE')))
    l.update(revision=revision,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),previous_ledger=prior,publisher=ref(__file__),full_goal_complete=False)
    l['first_video_milestone']['native_game_both_modes_independently_accepted']=observation
    l['next_safe_action']='独占758b预处理实板窗口及完整formal恢复；新版UI+TDM完整TD并行准备，统一actor/轨迹/游戏owner接线后再安排新版实屏/真人。'
    save(out/'ledger.json',l)
    p.update(observed_utc=l['updated_utc'],full_task_ledger=ref(out/'ledger.json'))
    p['active_work'].update(application_progress=observation,next_action=l['next_safe_action'])
    p['first_video_milestone']['native_game_both_modes_independently_accepted']=observation
    assert (R/'GOAL_PROGRESS.json').read_bytes()==before
    temp=R/'GOAL_PROGRESS.app_progress.tmp';save(temp,p);os.replace(temp,R/'GOAL_PROGRESS.json')
    q=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(q.stdout);(out/'refresh.stderr').write_bytes(q.stderr);assert q.returncode==0
    for name in ('GOAL_PROGRESS.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json'):
        a=R/name;(out/(a.stem+'_snapshot'+a.suffix)).write_bytes(a.read_bytes())
    save(out/'publication.json',dict(status=observation['status'],revision=revision,statuses_not_overclaimed=True,full_goal_complete=False))
    print('APPLICATION_PROGRESS_PUBLISHED',revision)

if __name__=='__main__':main()
