"""Record real TDM byte tests, retained app-start failure and full recovery."""
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
    root=Y/'evidence/tdm_profile_actual_v1';actual=load(root/'result.json')
    assert actual['status']=='PASS_NATIVE_TDM_BYTE_TESTS_AND_FORMAL_VIDEO_RESTORATION_CANDIDATE_APP37_NOT_ACCEPTED'
    current=ref(R/'CURRENT_CAMERA.json')
    assert current['sha256']=='77b36d023e0562ab4e968ee1968bd111a5455aac65f49a4f9a431b18c4523c78'
    paths={
        'actual_TDM_and_full_restoration':root/'result.json','actual_manifest':root/'MANIFEST.json',
        'failed_candidate_relay':root/'failed_relay_readonly.json',
        'formal_panel_setup':root/'external_formal_panel_start_v1.json',
        'current_runtime_selection':root/'current_camera_selection.json','current_binding':root/'binding.json',
        'sole_current_control':root/'CONTROL.md',
        'host_source_bundle':Y/'ui_app_v1/host_delivery_v1/FREEZE.json',
        'host_bundle_verification':Y/'ui_app_v1/host_delivery_v1/verification/result.json',
        'relay_and_game_integration':Y/'ui_app_v1/game_bridge/integration_v1/evidence/round1/result.json',
        'original_owner_application_hooks':Y/'evidence/owner_app_session_v2/result.json',
    }
    observation=dict(status=actual['status'],references={k:ref(v) for k,v in paths.items()},CURRENT=current,
        current_runtime=actual['runtime'],current_owner=actual['owner'],current_feature_directory=actual['feature_directory'],
        selected_full_bit_sha256='9bea494c217c081c21a730ed85b03e823eb02cdbfa33e5884ddd79eccb2802ce',
        candidate_full_bit_sha256='758b08226b4039b63880b0316dc72d206f87371ed1ccfe7bba842fb49b9261a4',
        native_tensor_bytes_128_192_passed_twice=True,RGB1080_roundtrip_frames_passed=6,
        app37_started=False,app37_NPU_performance_accepted=False,new_UI_deployed=False,
        reason='SRAM复位后漏启原DSI面板时钟，CAP/ABI/LIMITS/status为0；原pin四步start_panel恢复正式视频。新profile须将此步骤放在relay probe前；未放宽ABI或改RTL。',
        current_sample_human_valid=False,old_failures_retained=True,Flash_written=False,full_goal_complete=False)
    key=f'v{revision}_actual_TDM_bytes_and_formal_video_restoration';l['evidence'][key]=observation
    for t in l['tasks']:
        if t['id']=='U03':
            t['current_state']+=' 另完成两轮TDM原生字节/6整帧往返和正式全链恢复；app37首启被未启面板时钟挡住，未启动主模型，不计NPU通过。新UI完整TD正执行。'
            t.setdefault('evidence_keys',[]).append(key)
        elif t['id']=='U02':
            t['current_state']+=' 当前同源relay/game桥47项、原session应用hook12项全过，67文件host源包已冻结；真实inactive安装/新owner分页和游戏现场接线仍未部署。'
            t.setdefault('evidence_keys',[]).append(key)
    l.update(revision=revision,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),previous_ledger=prior,publisher=ref(__file__),full_goal_complete=False)
    l['first_video_milestone']['actual_preprocessing_and_source_delivery']=observation
    l['next_safe_action']='继续新UI+TDM完整TD/物理复核；构建ARM TWS2库并完成inactive app38/唯一UI profile，先mandatory panel初始化再relay probe；上板后通知真人做登记/标定/游戏五动作。'
    save(out/'ledger.json',l)
    p.update(observed_utc=l['updated_utc'],full_task_ledger=ref(out/'ledger.json'),protected_CURRENT=current,last_readonly_board_proof=ref(root/'result.json'))
    p['active_work'].update(status='APPLICATION_UI_FULL_BUILD_AND_INACTIVE_UNIFIED_DEPLOYMENT',
        current_runtime_observation=observation,source_delivery=observation['references']['host_source_bundle'],next_action=l['next_safe_action'])
    p['first_video_milestone']['actual_preprocessing_and_source_delivery']=observation
    p['current_runtime_stop_rule']='只用CURRENT绑定的profile_delivery status/stop；实际owner194160持Popen/EX，完整stop后该最终keep owner退出。新硬件需新代正常交接，禁止复用历史PID/RPC。'
    assert (R/'GOAL_PROGRESS.json').read_bytes()==before
    temp=R/'GOAL_PROGRESS.tdm_progress.tmp';save(temp,p);os.replace(temp,R/'GOAL_PROGRESS.json')
    q=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(q.stdout);(out/'refresh.stderr').write_bytes(q.stderr);assert q.returncode==0
    for name in ('GOAL_PROGRESS.json','CURRENT_CAMERA.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json'):
        a=R/name;(out/(a.stem+'_snapshot'+a.suffix)).write_bytes(a.read_bytes())
    save(out/'publication.json',dict(status='ACTUAL_TDM_AND_CURRENT_FULL_VIDEO_RESTORATION_RECORDED',revision=revision,full_goal_complete=False))
    print('TDM_AND_SOURCE_PROGRESS_PUBLISHED',revision)

if __name__=='__main__':main()
