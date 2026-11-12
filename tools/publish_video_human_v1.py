"""Close the relative-XYZ twin integration item on actual human/optical evidence."""
from collections import Counter, defaultdict
import copy
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from publish_video_running_v1 import R, Y, load, save, ref

def main():
    before=(R/'GOAL_PROGRESS.json').read_bytes();progress=load(R/'GOAL_PROGRESS.json')
    previous=progress['full_task_ledger'];assert ref(previous['path'])==previous
    old=load(previous['path']);ledger=copy.deepcopy(old);revision=old['revision']+1
    out=Path(previous['path']).parent.parent/f'goal_task_ledger_v{revision}';assert not out.exists()
    watch=Y/'evidence/live_human_watch_v2/result.json'
    assert ref(watch)['sha256']=='f651906d5f3bf2a7becc2021dc7748e9b7d092f02efb64c3e361726475cc3d97'
    measured=load(watch);assert measured['gaze']['valid_rows']==1197 and measured['hand']['has_hand_rows']==835
    assert ref(R/'CURRENT_CAMERA.json')==measured['CURRENT_before']
    optical=Y/'evidence/current_video_observed_v1/user_optical_confirmation.json'
    assert load(optical)['answer']=='界面正常，骨架随动作变化'
    out.mkdir();(out/'BOARD_VIDEO_REPORT.md').write_bytes((Y/'BOARD_VIDEO_REPORT.md').read_bytes())
    key=f'v{revision}_live_relative_XYZ_twin_and_user_optical_confirmation'
    observation=dict(status='REAL_RELATIVE_XYZ_TWIN_RUNNING_HUMAN_AND_VISIBLE_MOTION_CONFIRMED',
        measurement=ref(watch),user_optical_confirmation=ref(optical),report=ref(out/'BOARD_VIDEO_REPORT.md'),
        current=ref(R/'CURRENT_CAMERA.json'),status_client=ref(Y/'evidence/video_status_deployed_v1/result.json'),
        full_goal_complete=False,game_joint_accepted=False,
        limits=['Not calibrated metric 3D or gaze accuracy','Hand-to-person association remains R01/R11',
                'Left-hand full loss/recovery not covered in this window','No source-to-optical latency or long-run acceptance'])
    ledger['evidence'][key]=observation
    for t in ledger['tasks']:
        if t['id'] in ('U01','U02','U03','U04','U05'):
            t.setdefault('evidence_keys',[]).append(key);t['actual_live_human_video']=observation
        if t['id']=='U05':
            t['prior_status_before_real_human_video']=t['status'];t['status']='DONE'
            t['current_state']='首版模型相对XYZ手/头/双眼三维孪生已实际整合上板并持续运行；用户实屏确认界面正常、骨架随动作变化。61.74秒1197条有效注视/835条有手结果、FPGA新增595包且协议错误增量0；右手、头、双眼失效与恢复已观测。仅完成本项相对三维映射与实时整合；标定空间/操作者关联由R01/R11、更多场景和长测由U04继续。'
        elif t['id']=='U01':
            t['current_state']='正式项目手/头/双眼UI已在MIPI实屏运行，用户确认骨架随动；五组均出现真实有效。首版可拍，原始图/质量语义及更全面界面验收仍保留，不以相对骨架签真实空间标定。'
        elif t['id']=='U02':
            t['current_state']='现用app34外层主脸与原共享图像手部NPU出口持续进入FPGA；真实非空五组及右手/头眼失效恢复、协议错误增量0已测。无额外UI推理；左手单独失效恢复及更完整来源/人手身份语义仍开放。'
        elif t['id']=='U04':
            t['status']='PARTIAL';t['current_state']='用户已确认MIPI界面正常骨架随动；61.74秒有效注视1197条=19.39/s、有手835=13.52/s，FPGA新增595包/错误增量0，进程身份稳定。有效注视样本年龄p95=250.81ms、有手年龄p95=101.19ms；只是日志年龄。更多遮挡/左手失效恢复、游戏分场景联合资源/操控、光学时延及长测仍待。'
    changed=[t['id'] for t,a in zip(ledger['tasks'],old['tasks']) if t['status']!=a['status']]
    assert set(changed)=={'U04','U05'}
    scopes=defaultdict(Counter)
    for t in ledger['tasks']:scopes[t['scope']][t['status']]+=1
    ledger['scope_status_counts']={k:dict(v) for k,v in scopes.items()}
    ledger['active_main_status_counts']=dict(Counter(t['status'] for t in ledger['tasks'] if t['status'] not in ('DEFERRED_BY_USER','REMOVED_FROM_SCOPE')))
    ledger.update(revision=revision,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),previous_ledger=previous,
        publisher=ref(__file__),current_camera_selection=ref(R/'CURRENT_CAMERA.json'),full_goal_complete=False)
    ledger['first_video_milestone'].update(twin_live_first_version_accepted=True,game_joint_accepted=False,first_video_board_run_accepted=False,evidence=observation)
    ledger['next_safe_action']='保持已确认孪生可拍，完成Freeciv真实射击/攻城/胜负和同板双人；新合并候选离线原生验证并行，不抢当前硬件。'
    save(out/'ledger.json',ledger)
    progress.update(observed_utc=ledger['updated_utc'],full_task_ledger=ref(out/'ledger.json'))
    progress['active_work'].update(status='LIVE_TWIN_FIRST_VERSION_CONFIRMED_GAME_AND_JOINT_INPUT_IN_PROGRESS',actual_live_human_video=observation,next_action=ledger['next_safe_action'])
    progress['first_video_milestone'].update(twin_live_first_version_accepted=True,game_joint_accepted=False,evidence=observation)
    assert (R/'GOAL_PROGRESS.json').read_bytes()==before
    temp=R/'GOAL_PROGRESS.video_human.tmp';save(temp,progress);os.replace(temp,R/'GOAL_PROGRESS.json')
    p=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(p.stdout);(out/'refresh.stderr').write_bytes(p.stderr);assert p.returncode==0
    for name in ('GOAL_PROGRESS.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json'):
        q=R/name;(out/(q.stem+'_snapshot'+q.suffix)).write_bytes(q.read_bytes())
    save(out/'publication.json',dict(status='U05_REAL_HUMAN_INTEGRATION_COMPLETED_OTHER_TASKS_REMAIN',revision=revision,
        changed_status_ids=changed,full_goal_complete=False,game_joint_accepted=False))
    print(json.dumps(dict(status='U05_COMPLETED_ON_REAL_BOARD',revision=revision)))

if __name__=='__main__':main()
