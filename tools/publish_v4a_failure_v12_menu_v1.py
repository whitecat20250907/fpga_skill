"""Publish observed failure and the separately verified v12 menu; no device actions."""
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

R=Path(__file__).resolve().parents[1];Y=R/'projects/twb_feature_integration_20261023'
def read(p):return json.loads(Path(p).read_bytes())
def ref(p):return dict(path=str(Path(p).resolve()),sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest())
def write(p,v):
 with Path(p).open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def replace(p,v):
 tmp=Path(str(p)+'.failure_v12.tmp');write(tmp,v);os.replace(tmp,p)

progress=read(R/'GOAL_PROGRESS.json');old_ledger=progress['full_task_ledger'];assert ref(old_ledger['path'])==old_ledger
ledger=copy.deepcopy(read(old_ledger['path']));assert ledger['revision']==273
old_current=ref(R/'CURRENT_CAMERA.json');current=read(R/'CURRENT_CAMERA.json')
assert current['status']=='POINTER_ACTUAL_APP39_V4A_RUNNING_CONTROL_REPAIR_PENDING'
audit=read(Y/'evidence/application_recovery_actual_v6/postack_actual_v4a_reference_v1.json')
assert audit['pin']['sha256']=='1711747a59f5a84e83687cc247c2149205d94f98da3d33aeaa85be175dfc8acb'
assert audit['audit']['all_children_absent'] and audit['audit']['device_fds']==[] and audit['audit']['native_cleanup_errno']==110
game=read(Y/'evidence/game_v12_default_actual_v1/start_v12_result.json')
assert game['status']=='V12_DEFAULT_MENU_ACTUAL_SOURCE_AND_ENDPOINT_BOUND' and game['state']['phase']=='menu'
assert not game['human_control_accepted'] and not game['parallel_NPU_latency_measured']
evidence=dict(status='APP39_FAILED_HANDLES_REAPED_OWNER_EX_RETAINED_V12_MENU_RUNNING',
 postack=ref(Y/'evidence/application_recovery_actual_v6/postack_actual_v4a_reference_v1.json'),
 runtime_report=ref(R/'projects/model_image_ops_board_20261023/evidence/resume_actual_20261024_v1/runtime_result.json'),
 game_stop=ref(Y/'evidence/game_v12_default_actual_v1/stop_v11_result.json'),
 game_start=ref(Y/'evidence/game_v12_default_actual_v1/start_v12_result.json'),
 completed_35min=ref(Y/'evidence/application_recovery_actual_v6/longrun_35min_v4a/result.json'),
 camera_live=False,old_supervisor_ex_retained=True,new_app40_started=False,
 normal_camera_close_PASS=False,full_goal_complete=False)
assert evidence['runtime_report']['sha256']=='9eb1e867e916bed1b5c2ad4eb8a850c2bdae83346388914d58bb58e8850813db'
runtime=read(evidence['runtime_report']['path']);assert runtime['capture_end']['cleanup_errno']==110
evidence['runtime_seconds_before_failure']=runtime['capture_end']['elapsed_ns']/1e9
out=Path(old_ledger['path']).parent.parent/'goal_task_ledger_v274';assert not out.exists();out.mkdir()
current.update(status='POINTER_APP39_V4A_FAILED_V12_MENU_RUNNING_RECOVERY_PENDING',
 active_camera_runtime=None,retained_supervisor=dict(pid=250418,start_ticks=67336261,EX_held=True),
 actual_game_binding=game['binding'],previous_running_pointer=old_current,
 scope='App39 stopped delivering frames after about115 minutes and original cleanup returned110. Original ack11 reaped all model/native/hand/relay handles; exact supervisor250418 still holds EX. No live camera, app40 or successful fault recovery is claimed. v12 game alone is now selected at its real menu with source/endpoint binding. SRAM9e82 and Flash37 unchanged; human and NPU parallel acceptance pending.')
current['actual_failure_evidence']=evidence['postack']
replace(R/'CURRENT_CAMERA.json',current)
event_key='v274_actual_v4a_failure_and_v12_default_menu'
ledger['evidence'][event_key]=evidence
for task in ledger['tasks']:
 if task['id']=='U04':task['current_state']='App39实际约115分钟失流且cleanup110；原ack11回收句柄，旧owner仍持EX。修复并恢复app40后重做稳定性，不沿用先前35分钟检查签长测通过。'
 if task['id']=='U05':
  task['current_state']='手/头/双眼孪生实现保留；当前摄像头失流恢复优先，恢复app40配置隔离与新采集后整合。临时PC键鼠接管由独立输入适配实现，复用现有action/UI控制，后续统一手势；非空真人联动仍由U04等测试承接。'
  if '临时PC键鼠接管与原action/UI控制入口整合，保留返回手势控制' not in task['done_when']:task['done_when'].append('临时PC键鼠接管与原action/UI控制入口整合，保留返回手势控制')
 if task['id']=='G04':task['current_state']='v12已实际切为默认开始页，38源码及两ELF/UDP nonce/唯一端口owner绑定通过；主摄像头失流恢复中，有效NPU并行与真人视线/手势操控未测。'
ledger.update(revision=274,previous_ledger=old_ledger,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),publisher=ref(__file__),full_goal_complete=False)
ledger['first_video_milestone']['latest_actual_status']=evidence
ledger['first_video_milestone']['ready_for_human_recording']=False
write(out/'ledger.json',ledger)
progress.update(observed_utc=ledger['updated_utc'],full_task_ledger=ref(out/'ledger.json'),protected_CURRENT=ref(R/'CURRENT_CAMERA.json'))
progress['active_work'].update(status='RECOVER_FAILED_APP39_TO_APP40_V12_MENU_SELECTED',current_selected_runtime_is_live=False,latest_actual_status=evidence)
progress['first_video_milestone']['latest_actual_status']=evidence
progress['first_video_milestone']['ready_for_human_recording']=False
progress['current_runtime_stop_rule']='250418已原ack11清空句柄但仍持EX；不得重复ack、套用正常关闭证明或直接重启模型。新失败合同校验后精确退役空owner，新EX完整quiesce、保留同位流、重探测和字节核对，然后唯一app40启动。'
replace(R/'GOAL_PROGRESS.json',progress)
sched=read(R/'TASK_SCHEDULING.json');sched['entries']['U05'].update(bucket='development',title='孪生/游戏整合、失流恢复与临时PC键鼠接管',estimate='2–4小时（故障恢复、输入入口与联合运行；真人另列）',prerequisites='实际故障交接/唯一新owner；复用原PCIe输入、原NPU和原动作',basis='当前存在真实失流/cleanup110，不能用已实现界面代替稳定运行。PC接管整合到现有UI/action入口，之后改手势来源。');sched['updated_utc']=ledger['updated_utc'];replace(R/'TASK_SCHEDULING.json',sched)
proc=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
(out/'refresh.stdout').write_bytes(proc.stdout);(out/'refresh.stderr').write_bytes(proc.stderr);assert proc.returncode==0
for name in ('CURRENT_CAMERA.json','GOAL_PROGRESS.json','TASK_SCHEDULING.json','PENDING_TASKS.md','PENDING_FIELD_TESTS.md'):(out/name).write_bytes((R/name).read_bytes())
write(out/'publication.json',dict(status='ACTUAL_FAILURE_AND_V12_DEFAULT_MENU_PUBLISHED',CURRENT=ref(R/'CURRENT_CAMERA.json'),evidence=evidence))
print('PUBLISHED_ACTUAL_FAILURE_AND_V12_MENU_V274')
