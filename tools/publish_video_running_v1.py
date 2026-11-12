"""Record the actual continuous video deployment; do not grant human acceptance."""
import copy
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
Y = R / 'projects/twb_feature_integration_20261023'

def load(p):
    return json.loads(Path(p).read_text(encoding='utf8'))

def save(p, v):
    Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

def ref(p):
    p = Path(p)
    return dict(path=str(p.resolve()), sha256=hashlib.sha256(p.read_bytes()).hexdigest())

def main():
    before = (R / 'GOAL_PROGRESS.json').read_bytes()
    progress = load(R / 'GOAL_PROGRESS.json')
    previous = progress['full_task_ledger']
    assert ref(previous['path']) == previous
    old = load(previous['path'])
    ledger = copy.deepcopy(old)
    revision = old['revision'] + 1
    out = Path(previous['path']).parent.parent / f'goal_task_ledger_v{revision}'
    assert not out.exists()
    actual = load(Y / 'evidence/video_board_actual_v2/result.json')
    assert actual['status'] == 'REAL_FEATURE_VIDEO_RUNNING_WAITING_HUMAN_AND_OPTICAL_CHECK'
    assert actual['video_owner_hardware_EX_lease_retained']
    assert ref(R / 'CURRENT_CAMERA.json') == actual['CURRENT_after']
    observation = dict(
        status=actual['status'], observed_utc=actual['completed_utc'],
        evidence=ref(Y / 'evidence/video_board_actual_v2/result.json'),
        report=ref(Y / 'BOARD_VIDEO_REPORT.md'), current=ref(R / 'CURRENT_CAMERA.json'),
        real_source_to_FPGA_UI_running=True, human_nonempty_or_optical_accepted=False,
        first_video_board_run_accepted=False, full_goal_complete=False,
        known_limit='Empty scene only; human actions, optical screen and valid gaze latency remain open.')
    key = f'v{revision}_actual_continuous_project_twin_video'
    ledger['evidence'][key] = observation
    states = {
        'U01': '项目手/头/双眼界面已使用正式v12自身完整源位流上板；现有真实NPU出口持续接入。MIPI外部像素、非空骨架和本人动作待实测，不以空场景状态签光学通过。',
        'U02': '现用app34外层主脸观察器、既有共享图像手部消费者及真实结果relay已持续运行，FPGA实际接受118次更新且CRC/格式/序号错误0。当前12秒708行均无人脸；来源非空、丢跟踪恢复及手脸身份仍待验证，未新增UI推理。',
        'U03': '正式v12自己的完整源、正STA及有限相机共存证据保留；本轮已实际下载SRAM、恢复PCIe、依正确LP顺序启动MIPI并持续运行原app34和手/脸relay。原Popen正常保留，当前仍需完成可审查的启动/停止/回退交付；光学及真人由U04验证。',
        'U04': '真实原主模型、既有手部NPU消费者和正式v12已在同一板持续运行，空场景12秒来源约59行/秒、有效眼动0；样本年龄p50/p95=69.83/132.28ms。已通知用户入镜，待非空头眼手/实际MIPI像素/有效NPU与游戏联合延迟/长测。',
        'U05': '真实相对XYZ编码、手/头眼三维图元及正式FPGA渲染链已持续部署，当前只差本人非空动作、连续性、失跟踪和光学实屏验证；未签标定空间重建或手与主脸身份关联。用户已同意部署就绪后配合，现已通知。',
    }
    for task in ledger['tasks']:
        if task['id'] in states:
            task['current_state'] = states[task['id']]
            task.setdefault('evidence_keys', []).append(key)
            task['actual_continuous_video_deployment'] = observation
    assert [(x['id'], x['status']) for x in old['tasks']] == [(x['id'], x['status']) for x in ledger['tasks']]
    schedule = load(R / 'TASK_SCHEDULING.json')
    for tid, title in {
        'U01': '项目手/头/眼主界面的实际MIPI显示验收',
        'U02': '已部署真实特征来源、有效/失效与恢复验收',
        'U05': '已部署手部、头部与双眼3D孪生真人动作验收',
    }.items():
        schedule['entries'][tid] = dict(bucket='field_test', title=title,
            estimate='与U04同轮，约30–90分钟首版验证；完整长测另计',
            prerequisites='当前连续服务保持；正脸、双眼和一只手入镜，能观察MIPI屏',
            basis='代码和正式位流已实际持续部署；目前剩余为真人/实屏验证，未计技术通过。身份扩展仍由R01/R11承接。')
    schedule['entries']['U03'].update(estimate='1–2小时（正常停止、回退交接与启动交付）',
        basis='实际板端整合已运行；剩余可交付的正常停止/回退路径，真人和光学由U04承接。')
    save(R / 'TASK_SCHEDULING.json', schedule)
    ledger.update(revision=revision, updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        previous_ledger=previous, publisher=ref(__file__), task_scheduling=ref(R / 'TASK_SCHEDULING.json'), full_goal_complete=False)
    out.mkdir()
    save(out / 'ledger.json', ledger)
    progress.update(observed_utc=ledger['updated_utc'], full_task_ledger=ref(out / 'ledger.json'))
    progress['active_work'].update(status=actual['status'], actual_continuous_video_deployment=observation,
        next_action='已通知用户入镜；验收真实手/头/双眼MIPI动态与NPU延迟，游戏独立战斗及交付回退并行。')
    progress['first_video_milestone'].update(actual_deployment=observation, first_video_board_run_accepted=False)
    progress['pending_task_view']['scheduling_source'] = ref(R / 'TASK_SCHEDULING.json')
    assert (R / 'GOAL_PROGRESS.json').read_bytes() == before
    temporary = R / 'GOAL_PROGRESS.video_running.tmp'
    save(temporary, progress)
    os.replace(temporary, R / 'GOAL_PROGRESS.json')
    p = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(R / 'tools/refresh_pending_tasks.py')], cwd=R, capture_output=True)
    (out / 'refresh.stdout').write_bytes(p.stdout)
    (out / 'refresh.stderr').write_bytes(p.stderr)
    assert p.returncode == 0
    for name in ('GOAL_PROGRESS.json', 'TASK_SCHEDULING.json', 'PENDING_TASKS.md', 'PENDING_TASKS.json', 'PENDING_FIELD_TESTS.md', 'PENDING_FIELD_TESTS.json'):
        path = R / name
        (out / (path.stem + '_snapshot' + path.suffix)).write_bytes(path.read_bytes())
    save(out / 'publication.json', dict(status='ACTUAL_VIDEO_RUNNING_RECORDED', revision=revision,
        task_acceptance_statuses_unchanged=True, moved_implementation_complete_to_field_test=['U01','U02','U05'], full_goal_complete=False))
    print(json.dumps(dict(status='ACTUAL_VIDEO_RUNNING_PUBLISHED', revision=revision)))

if __name__ == '__main__':
    main()
