"""Record independent real-source verification without touching another run."""
import copy
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

R=Path(__file__).resolve().parents[1];S=R/'projects/rgb_area3_stream_20261022'


def ref(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def load(p):return json.loads(p.read_text(encoding='utf8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def main():
    files=dict(branch=S/'evidence/existing_branch_metadata_v2/result.json',
        guard=S/'evidence/a3f1_host_guard_v1/result.json',audit=S/'evidence/dual_stream_readonly_audit_v1/result.json')
    branch=load(files['branch']);guard=load(files['guard'])
    assert branch['all_original_inputs_unchanged'] and branch['unmodified_actual_registered_RTL']
    assert branch['full_resolution_C_reference_executed'] and len(branch['cases'])==5
    assert not branch['top_CSR_logic_or_atomic_nonce_proved'] and not branch['preview_and_model_common_identity_proved']
    full=[x for x in branch['cases'] if x['width']==1920 and x['height']==1080]
    assert len(full)==1 and len(full[0]['valid_packets'])==2
    assert all(p['RGB_exact'] and p['CRC_exact'] and p['bytes']==691200 for p in full[0]['valid_packets'])
    assert guard['execution']['checks']==24 and guard['execution']['legacy_backwards_ID_accepted']
    assert guard['original_source_files_unchanged'] and not guard['live_project_patched']
    assert not guard['real_worker_thread_or_ARM_or_DMA_test']
    assert all(ref(Path(v['path']))==v for v in guard['own_files'])
    report=S/'transport/PROGRESS_20261023.md';assert not report.exists()
    report.write_text('''# 已有A3F1双通道的独立复核

本轮复用model_image_ops_board_20261023的真实注册RTL和原A3F1协议，不另造小图传输。未访问板端、CAD或硬件，也未修改该开发流程的源文件或进程。

## 实际通过

- 1920×1080两帧、随机输出背压，完整640×360 RGB逐字节与重新编译执行的原C area3参考一致。源SOF ID/tick、session epoch、125MHz单位及CRC一并验证。
- 四组小尺寸正常/溢出/unsupported切换/禁用换epoch测试通过。溢出和模式中断留下的旧前缀以无效status8结束（432/384字节），下一完整帧恢复。主机仍须完整长度和有效状态才提交；当前接收任务遇坏包会退出，不能由RTL恢复推断应用自动恢复。
- 旧worker接受ID9后再收到ID8、tick却递增的反例已真实复现。新增独立guard保留原包与CRC检查，以32位serial arithmetic拒绝重复/倒退/半范围歧义，允许跳帧和前向wrap；tick必须递增，epoch非零且会话固定。24个C检查通过，拒绝不修改已提交历史和输出。
- 精确候选补丁git apply --check通过，但未应用。部署前需要在新的独立接收器版本完成ARM编译、真实工作线程和DMA/正常停止测试。

## 仍未证明

epoch按现有packet准入锁存，正确用法依赖“仅禁用且packet idle时改epoch，禁用清支路”。本轮验证正确次序的RTL，不包含完整top CSR原子性、剩余credit、跨重启nonce唯一性。预览V4L2 sequence与模型source ID还不能作为共同曝光身份配对。

CRC只保护payload；当前A3F1的ID/tick未纳入CRC。新增guard加强顺序检查，没有改变协议，也没有声称任意元数据损坏均可检测。

--preview-fps只限制共享内存预览发布，未减少C2H0收帧流量。两路60fps纯像素合计414.720MB/s，必须实测SGDMA竞争、FIFO峰值和溢出。timestamp_ns/dequeue_ns明确是DMA完成；另列FPGA source_tick/hz/epoch，未做跨设备映射前不能把当前app样本年龄当ISP SOF或曝光端到端延迟。

另一开发流程的buffered_v3完整native已自行终态失败（1716.343秒、输入未变、未触板），不是本轮验证通过的整机时序证据。其后续源版本/构建/上板由原拥有者处理；本轮不启动第二个native、不用组件通过补签该失败。

证据：../evidence/existing_branch_metadata_v2/result.json、a3f1_host_guard_v1/result.json、dual_stream_readonly_audit_v1/result.json。保留首版测试超时不足的失败，第二版只调整测试预算。完整范围仍以根账本和两份任务清单为准。
''',encoding='utf8')
    with (S/'INTEGRATION_CONTRACT.md').open('a',encoding='utf8') as stream:
        stream.write('''

## 实际双通道实现的复用（2026-10-23）

另一个开发流程已在model_image_ops_board_20261023实现C2H0原预览+C2H1 A3F1小图及实际接收器。优先复用，独立核对见transport/ACTUAL_DMA_AUDIT.md和PROGRESS_20261023.md。本轮全1080p两帧的RGB、CRC、来源SOF id/tick和正确换epoch屏障已独立验证；接收顺序guard有24个C检查和未部署补丁。

实际内部FIFO/area3仍沿用历史端口名source_ns，但载荷作为原样tick标签传递，包头明确125MHz，主机输出fpga_source_tick/hz；外部没有把它解释成Linux纳秒。复用时必须保留这一单位声明。当前实现使用禁用/idle/清支路屏障保持epoch，而非每个像素beat携带epoch；本轮不把正确顺序的验证扩大为top CSR原子性/剩余credit或跨重启nonce证明。预览与小图共同源身份仍须补齐。
''')
    with (S/'README.md').open('a',encoding='utf8') as stream:
        stream.write('\n已对现有A3F1双C2H实现完成独立全幅RGB/来源/CRC和异常恢复核对，并交付未部署的接收顺序加固补丁；详见 [本轮进度](transport/PROGRESS_20261023.md)。不重复实现现有协议；整机时序、并行预览和DMA/NPU收益仍未验收。\n')
    phase=load(R/'TASK_SCHEDULING.json')
    changes={
        'U02':('主脸、手部与眼部真实结果的统一接口接入','2–4小时（出口合并、服务接线与来源归属；真实动作见U04/M05）'),
        'U03':('FPGA项目UI、真实特征与现用工程整合交付','0.5–1工作日（当前工程整合、接口与交付；实屏验证见U04）'),
        'U05':('手部、头部及双眼3D映射与实时孪生整合','1–3工作日（3D映射、操作者关联与整合；真人实测见U04）'),
        'T02':('A3F1接收加固、同源标签与小图/预览整合','1–2工作日（接收补丁、配对身份与完整工程集成）'),
        'F11':('可配置3×3卷积接收对齐修复与完整重建','1–3工作日（接收根因、换核接口和可验证位流）'),
        'F16':('FPGA侧IMX415运行中开窗与I²C事务守护','2–4工作日（需CAM005/VID005同步信号原理图）'),
        'F17':('FPGA摄像头4K30/裁切模式与传输格式','1–3工作日（模式/格式实现、整链构建）')}
    estimates=load(R/'PENDING_TASK_ESTIMATES.json')
    for id,(title,estimate) in changes.items():
        phase['entries'][id]=dict(bucket='development',title=title,estimate=estimate,
            basis='仍有明确的代码/接口/整合或可交付构建缺口；真实动作和实屏测试由单独实测项承接。')
        estimates['main'][id]=[title,estimate]
    save(R/'TASK_SCHEDULING.json',phase);save(R/'PENDING_TASK_ESTIMATES.json',estimates)
    progress_path=R/'GOAL_PROGRESS.json';before=progress_path.read_bytes();progress=load(progress_path)
    previous=progress['full_task_ledger'];assert ref(Path(previous['path']))==previous
    old=load(Path(previous['path']));ledger=copy.deepcopy(old);revision=old['revision']+1
    out=Path(previous['path']).parent.parent/f'goal_task_ledger_v{revision}';assert not out.exists()
    observation=dict(status='ACTUAL_REGISTERED_A3F1_FULL_RGB_METADATA_VERIFIED_GUARD_PATCH_NOT_DEPLOYED',
        references={k:ref(p) for k,p in files.items()},report=ref(report),
        full1080_frames=2,exact_RGB_metadata_and_CRC=True,host_C_cases=24,
        original_backward_ID_counterexample=True,host_patch_deployed=False,
        full_TD_or_real_DMA_or_NPU_benefit_accepted=False,no_board_or_CAD_or_other_owner_access=True)
    key=f'v{revision}_existing_A3F1_reuse_full_metadata_and_receiver_guard'
    for task in ledger['tasks']:
        if task['id']=='T02':
            task['previous_state_before_A3F1_reuse']=task['current_state']
            task['current_state']='复用另一开发流程现有A3F1/C2H1实现。本轮独立执行真实注册RTL：全1080p两帧、随机背压、小图逐RGB与新执行原C一致，源SOF ID/tick、正确epoch屏障和CRC通过；溢出/模式中断旧前缀无效并在下一完整帧恢复。真实旧worker倒退ID反例已复现，24项C检查及精确未部署加固补丁通过。完整top nonce/credit屏障、预览与小图共同身份、整机时序/实板双流/NPU收益尚未验；buffered_v3自身native失败不补签。'
            task['actual_registered_A3F1_contract_and_host_guard']=observation
            task['source_preview_split_implemented']=True
            task['preview_model_common_source_identity_proved']=False
            task['host_receiver_guard_deployed']=False
            task['actual_complete_source_tap_and_metadata_contract']=ref(S/'INTEGRATION_CONTRACT.md')
            task.setdefault('evidence_keys',[]).append(key)
    assert all(a['id']==b['id'] and a['status']==b['status'] for a,b in zip(old['tasks'],ledger['tasks']))
    ledger.update(revision=revision,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        previous_ledger=previous,publisher=ref(Path(__file__)),task_scheduling=ref(R/'TASK_SCHEDULING.json'),full_goal_complete=False)
    ledger['evidence'][key]=observation;out.mkdir();save(out/'ledger.json',ledger)
    progress.update(observed_utc=ledger['updated_utc'],full_task_ledger=ref(out/'ledger.json'))
    progress['active_work'].update(status=observation['status'],T02_independent_reuse_observation=observation,
        next_action='推进未部署的A3F1接收加固ARM/真实线程验证，以及同源预览身份与top nonce/credit屏障；RK直连CSI和双摄继续暂缓，真人/实屏按独立待实测单执行。')
    progress['pending_task_view'].update(generator=ref(R/'tools/refresh_pending_tasks.py'),
        estimate_catalog=ref(R/'PENDING_TASK_ESTIMATES.json'),scheduling_source=ref(R/'TASK_SCHEDULING.json'))
    assert progress_path.read_bytes()==before
    temp=R/'GOAL_PROGRESS.transport_checks.tmp';save(temp,progress);os.replace(temp,progress_path)
    p=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(p.stdout);(out/'refresh.stderr').write_bytes(p.stderr);assert p.returncode==0
    for name in ('GOAL_PROGRESS.json','PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json','PENDING_TASK_ESTIMATES.json','TASK_SCHEDULING.json'):
        path=R/name;(out/(path.stem+'_snapshot'+path.suffix)).write_bytes(path.read_bytes())
    save(out/'publication.json',dict(status=observation['status'],revision=revision,technical_statuses_unchanged=True,
        RK_direct_CSI_still_deferred=True,full_goal_complete=False))
    print(json.dumps(dict(revision=revision,status=observation['status'])))


if __name__=='__main__':main()
