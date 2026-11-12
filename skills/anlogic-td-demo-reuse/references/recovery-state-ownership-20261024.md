# RK3576／FPGA 恢复时的状态、进程归属与证据边界

适用：续接已有 owner 的失败回收、同 SRAM 保留、新代启动，以及审查“已恢复”是否有真实依据。以下是 2026-10-24 的具体经验，不授权额外停机、重烧或重试；控制者、PID 和路径必须从下一次真实证据重新确定。

## 本次已知状态

v6 实际启动了 app39：owner `250418/start67336261`，main250951、native251000、hand251016、relay250948。绑定 SHA 为 `d2f6a001f6d01fc5a6eb0db8cb917a6bd1a1c960bf1f2f04cfb0a56263fab32a`；配置 SHA 为 `47e0759e07caa7a5507ce2f159c616ed865c3e45e0994df3c31462f361f0dc98`。873 个源／依赖的真实预检查、完整 quiesce 后 8 个 poll 线程归零、三组同帧 tensor 比较、六整帧 RGB 比较均已完成，原 start 已进入 `FEATURE_RUNNING`。

**这不代表控制入口或长期稳定性已经修好。** 本代保持 visual，35 分钟只读观察在进行；原 `start_profile` 改变共享配置后，恢复 provider 的严格校验会拒绝 keep／交互。没有为此反复发 keep，也没有热改当前 owner。未来 app40 应使用独立、重新 pin 的 provider；当前最小隔离修复仅在本机离线验证。此前多代仍出现 cleanup110／C2H1 未完成，持续故障尚未根治。

## 必须保留的经验

| 容易混淆的对象 | 正确处理 |
| --- | --- |
| 事务配置与启动中的配置 | 原 `ProfileOwner.start_profile` 会更新 `npu_package`、`feature_config`、`feature_config_sha256`、`feature_trial_bit_sha256`。provider 必须持有 `copy.deepcopy(cfg)` 作为不可变事务快照，原 owner 继续使用自己的启动字典；不要删严格校验、忽略变化或改写原磁盘配置来“通过”。 |
| 历史 runtime 与当前失败 runtime | 原 v3 配置的 `cfg.runtime` 仍是214978/app38；233963/app39 的当前事实来自 `longrun_failure.state.runtime`。核 PID/start、boot、cmdline、路径和真实子句柄；`csv_bytes` 是变化的统计量，不是不可变身份。早期 binding 的2750字节不应与失败时完整 runtime 强行全字典相等。 |
| 文件内容 SHA 与路径闭包 | v5 在发信号前拒绝了40个祖先目录 symlink 产生的别名，虽然内容 SHA 全部正确。必须检查文件本身和祖先路径，分别证明 link text、resolved target、目标 pin。新 helper 只接受真实清点出的5个直接链接和40个别名，禁止全局放宽 `resolve()`。 |
| capture DMA task 与 SGDMA poll thread | `kernel_dma_tasks=[]` 不等于驱动已经安静。本次原 ack 后仍有8个 `sgdma_poll_th0..7`，它们可在退役监督进程前保留，但必须如实记录；完整 quiesce 后，还须证明 `kernel_other_matching_tasks=[]`、模块卸载、PCIe root unbind、设备／FD为空。 |
| 已退出与取证失败 | 233963 已真实执行一次身份绑定的 SIGTERM 并退出。SFTP 因 root0700 证据目录报 PermissionError，只说明普通用户不能读该文件；使用 root **只读**取回原字节并校验原 pin，不能再次 signal、重跑退役或重造 receipt。 |
| 仿真／假依赖测试与实机 | 离线夹具通过可以证明配置隔离、门禁、一次性语义；其中 native/history/FD/health 的替身不能输出成真实板端证据。即使运行了真实原函数代码，也不能签 DMA、NPU、真人、屏幕或游戏实机通过。 |

## 恢复事务的正确顺序

1. 固定真实失败代、原配置及原日志；保留 native 非零 cleanup、main rc1、原辅助子进程 wait／日志线程结果。只有原 owner 的真实 ack／wait 可以回收其 Popen；不能用另一进程猜测或接管句柄。
2. 保存原 ack 前后状态、全部旧子 PID／设备 FD／内核任务、pending RPC 和唯一 EX。区分“子进程已回收的空监督进程”和“硬件已 quiesce”，不要把前者当后者。
3. 发信号前完成全源／祖先链接／递归历史验证。原844 pins 保持原序前缀，仅 append 新唯一依赖；source 自身也要 pin。使用两个 prepared：pre-exit prepared 的 handoff 为 null，resources proof 不含 exit；真实 exit 产生后才构建 final handoff → final prepared → 新配置。配置不 self-pin，不回指造成哈希环。
4. 仅在真实空句柄、精确 PID/start、原 RPC 已完成和唯一 EX 核验后，用原 pidfd 对监督进程发一次 SIGTERM；保存真实退出与锁释放。失败或取证中断都不自动重试／强杀。
5. 新 EX owner 复用原完整 Application → Profile → Generation → VideoOwner 工厂，使用已批准的 fresh environment 和正式／候选各自 adapter。先停在 STOPPED：`programmed_profile=None`、`programming_receipt=None`、`drivers_ready=False`。旧 f9 receipt 保留真实 programmer202401，不能换成 retired233963 或新 owner；同 SRAM retain 也不是新烧写。
6. 明确操作只读 BAR 快照 → 原窗口／全 quiesce → same-bit retain → 原 reprobe／实际驱动 build-id和参数 → panel → 三组 face128/palm192 同帧字节比较 → 六整帧 RGB 比较。所有结果来自原 native Popen／result／close，任何失败保留现场，不自动启动。
7. 单次显式 start 后，除真实健康与资源采样，还必须用**真实原 `start_profile` 和 keep／交互路径**回归 provider。配置隔离应在新代离线闭合并重新 pin 后部署，不能为绕过本代门禁热改内存或冻结源。

独立观察器应固定 boot、owner/capture 与所有 PID-start、binding／collector hash，并检查新鲜 health、source 时间／sequence、CSV 单调增长。稀疏15秒尾样本只证明持续活跃；不能据此计算有效 NPU FPS、端到端延迟或真人精度。过期的有界 relay 日志应报告硬件计数不可用，不能把零冒充停流。

## 可追溯证据

链接指向仓库内的原始证据；SHA 是本次固定记录，后续运行不能沿用身份。

| 证据 | 入口与范围 |
| --- | --- |
| v6 全依赖预检查及绑定 | [真实预检查](../../../projects/twb_feature_integration_20261023/evidence/application_recovery_actual_v6/validated_final_config.json)、[binding pin](../../../projects/twb_feature_integration_20261023/evidence/application_recovery_actual_v6/binding_reference.json)、[实际启动健康](../../../projects/twb_feature_integration_20261023/evidence/application_recovery_actual_v6/rpc_0010_sent.json)。873源、原844前缀保留；启动健康不等于 keep 通过。 |
| 原退休只发生一次 | [原 supervisor exit](../../../projects/twb_feature_integration_20261023/evidence/application_recovery_actual_v6/supervisor_exit_original.json)、[取证结清](../../../projects/twb_feature_integration_20261023/evidence/application_recovery_actual_v6/exit_collection_settlement.json)。原 exit SHA `19fd28231ae606f273a9965bc463732ad3f8c4a7d3301f10bbb9b6e50c4712cf`，原字节取回，无二次 signal。 |
| v5 路径拒绝与独立闭包 helper | [拒绝诊断](../../../projects/twb_feature_integration_20261023/evidence/application_recovery_actual_v5/source_closure_rejection_diagnostic.json)、[844 ancestry inventory pin](../../../projects/twb_feature_integration_20261023/evidence/application_recovery_actual_v5/actual_ancestry_inventory_reference.json)、[独立 helper](../../../projects/model_image_ops_board_20261023/source_closure_ancestry_v1/source_closure.py)。inventory SHA `26eeed4362dc6afd808c8600d1cecdd672082bbb6bf99d980bb2a7729e7d4db0`；helper SHA `d2a908fa63784f0e5192cb3798dc08b46728212b7923f9ec01638b5294532973`。 |
| 最小配置隔离修复，尚未部署 | [隔离说明](../../../projects/model_image_ops_board_20261023/failure_live_config_isolation_v1/README.md)、[单行 diff](../../../projects/model_image_ops_board_20261023/failure_live_config_isolation_v1/minimal.diff)、[离线原函数回归](../../../projects/model_image_ops_board_20261023/failure_live_config_isolation_v1/tests_isolation.py)。候选 source SHA `6e3681efa77c7e2f7c2918af56c68ee18436f9364f7914f131dabfae32e24f93`；4项离线测试，不含真实 source closure／设备操作。 |
| 失败事实与首因限制 | [app39 本代失败](../../../projects/twb_feature_integration_20261023/evidence/application_recovery_actual_v4/longrun_failure_01.json)、[native 双路径审查](../../../projects/model_image_ops_board_20261023/evidence/wbv2_native_dualpath_audit_v1/REPORT.md)、[C2H1 静态审查](../../../projects/twb_feature_integration_20261023/evidence/c2h1_packet_static_audit_v1/REPORT.md)。`output_pipe_timeout` 可能来自共享错误码；停后 BUSY／overflow 可是次生，不能替代首因证据。 |
| v6 持续观察 | [观察目录](../../../projects/twb_feature_integration_20261023/evidence/application_recovery_actual_v6/longrun_35min_v4a)。写作时仍在进行，不预签35分钟通过；更不能据此覆盖此前约5小时51分后失败。 |

旧版用户“骨架随动作变化”的确认不扩签当前新版；三 tensor／六 RGB 字节通过不等于真人孪生精度；游戏 factory／空输入门禁准备就绪不等于真人联动游戏成功。对外报告须分别写清代码／离线、真实板端、真人光学与操控验收。
