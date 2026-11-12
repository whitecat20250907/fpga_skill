"""Reopen the UI tasks on the user's explicit app/trajectory redesign."""
from collections import Counter, defaultdict
import copy
import datetime
import os
import subprocess
import sys
from publish_video_running_v1 import R, Y, load, save, ref

def main():
    before=(R/'GOAL_PROGRESS.json').read_bytes();p=load(R/'GOAL_PROGRESS.json');previous=p['full_task_ledger']
    assert ref(previous['path'])==previous
    old=load(previous['path']);l=copy.deepcopy(old);revision=old['revision']+1
    out=__import__('pathlib').Path(previous['path']).parent.parent/f'goal_task_ledger_v{revision}'
    assert not out.exists();out.mkdir()
    (out/'APP_UI_REDESIGN.md').write_bytes((Y/'APP_UI_REDESIGN.md').read_bytes())
    observation=dict(status='EXPLICIT_USER_APP_UI_REDESIGN_BASE_CHAIN_ONLY_ACCEPTED',
        source_thread='01a15e5a-9689-7322-9162-1543a077d1e7',source_kind='Direct human message actually read with read_thread',
        user_requirement='应用式美观布局；真实八轨迹、握拳/指向/绘制与识别；丰满渲染；取消双眼独立点线面板，改眼屏关系与投影；人物1/2分页、物理按键。只认可旧UI基础链路。两个对话分工，共同20小时首版。',
        plan=ref(out/'APP_UI_REDESIGN.md'),prior_live_chain_evidence=old['evidence'][f'v{old["revision"]}_live_relative_XYZ_twin_and_user_optical_confirmation'],
        old_visual_motion_is_new_UI_acceptance=False,full_goal_complete=False)
    key=f'v{revision}_explicit_application_UI_redesign';l['evidence'][key]=observation
    titles={'U01':'应用式项目主界面与真实八轨迹展示','U02':'人物、轨迹、手势状态与真实投影数据接入',
        'U03':'新版应用UI、物理按键分页与完整FPGA交付','U05':'人物分页、丰满手部与眼屏投影的实时孪生'}
    for t in l['tasks']:
        if t['id'] in titles:
            t['before_app_UI_redesign']=dict(title=t['title'],status=t['status'],current_state=t['current_state'],done_when=t['done_when'])
            t.update(title=titles[t['id']],status='IN_PROGRESS',current_state='用户明确大改UI；当前仅基础NPU→FPGA→MIPI链路已通过，新版布局/真实轨迹/丰满渲染/人物页和按键未完成。按新范围重新实现，旧骨架不签新UI通过。')
            t.setdefault('evidence_keys',[]).append(key)
            if t['id']=='U01':t['done_when']=['应用式层级/留白/圆角卡片和清楚状态，非通用算法示意','真实八轨迹/绘制/握拳指向与识别；不再独立双眼点线面板']
            elif t['id']=='U02':t['done_when']=['复用原手/脸/眼与现有轨迹分类，无另开相机或重复推理','真实来源/人物/手track/绘制状态与类别，未关联手明确未分配；未标定不伪造屏幕投影']
            elif t['id']=='U03':t['done_when']=['新版UI完整源正STA/资源/真实相机及NPU共存','物理键按真实手册/电路及现用系统核实后分页；不把RK引脚写入FPGA ADC；完整启动/停止/回退交付']
            else:t['done_when']=['真实XYZ驱动丰满掌面和手指渲染、实际轨迹与眼屏投影','人物1/2分页且旧人物不残留，未关联/未标定/无效状态真实显示；新版真实动作与连续性实测']
        elif t['id']=='U04':
            t['current_state']+=' 用户随后只认可基础链路，要求新版UI大改；旧骨架实屏不能签新版轨迹/分页/投影/渲染验收。'
    scopes=defaultdict(Counter)
    for t in l['tasks']:scopes[t['scope']][t['status']]+=1
    l['scope_status_counts']={k:dict(v) for k,v in scopes.items()}
    l['active_main_status_counts']=dict(Counter(t['status'] for t in l['tasks'] if t['status'] not in ('DEFERRED_BY_USER','REMOVED_FROM_SCOPE')))
    schedule=load(R/'TASK_SCHEDULING.json');est=load(R/'PENDING_TASK_ESTIMATES.json')
    times={'U01':'4–6小时（应用布局/完整RTL，与U05重叠）','U02':'2–4小时（原八轨迹/人物/投影真实出口）',
        'U03':'1–3小时（新UI与TDM合并、原生编译和交付；实现完成后）','U05':'2–4小时（丰满渲染/新布局映射，与U01重叠）'}
    for tid,title in titles.items():
        schedule['entries'][tid]=dict(bucket='development',title=title,estimate=times[tid],basis='用户新增应用式UI大改，旧基础链路通过保留；按统一20小时截止优先并行，实现工时不重复相加。')
        est['main'][tid]=[title,times[tid]]
    schedule['entries']['U04'].update(prerequisites='新版UI与真实轨迹/人物合同及完整位流；真人配合和物理键',estimate='30–90分钟首版；完整长测与其他任务共享窗口')
    save(R/'TASK_SCHEDULING.json',schedule);save(R/'PENDING_TASK_ESTIMATES.json',est)
    l.update(revision=revision,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),previous_ledger=previous,publisher=ref(__file__),task_scheduling=ref(R/'TASK_SCHEDULING.json'),full_goal_complete=False)
    l['first_video_milestone'].update(twin_live_first_version_accepted=False,basic_feature_chain_only_accepted=True,new_application_UI_required=observation)
    l['next_safe_action']='root实现新版应用UI/人物页/丰满手与轨迹；算法对话并行TDM与完整TD；保持旧基础视频，游戏与五动作同源接入并行。'
    save(out/'ledger.json',l)
    p.update(observed_utc=l['updated_utc'],full_task_ledger=ref(out/'ledger.json'))
    p['active_work'].update(status='NEW_APPLICATION_UI_TRAJECTORY_PAGES_AND_GAME_HIGHEST_PRIORITY',new_UI_scope=observation,next_action=l['next_safe_action'])
    p['first_video_milestone'].update(twin_live_first_version_accepted=False,basic_feature_chain_only_accepted=True,new_application_UI_required=observation)
    p['pending_task_view'].update(scheduling_source=ref(R/'TASK_SCHEDULING.json'),estimate_catalog=ref(R/'PENDING_TASK_ESTIMATES.json'))
    assert (R/'GOAL_PROGRESS.json').read_bytes()==before
    temp=R/'GOAL_PROGRESS.app_ui.tmp';save(temp,p);os.replace(temp,R/'GOAL_PROGRESS.json')
    q=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(q.stdout);(out/'refresh.stderr').write_bytes(q.stderr);assert q.returncode==0
    for name in ('GOAL_PROGRESS.json','TASK_SCHEDULING.json','PENDING_TASK_ESTIMATES.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json'):
        a=R/name;(out/(a.stem+'_snapshot'+a.suffix)).write_bytes(a.read_bytes())
    save(out/'publication.json',dict(status='USER_APP_UI_REDESIGN_REOPENED',revision=revision,reopened_ids=list(titles),old_evidence_retained=True,full_goal_complete=False))
    print('APP_UI_REDESIGN_REOPENED',revision)

if __name__=='__main__':main()
