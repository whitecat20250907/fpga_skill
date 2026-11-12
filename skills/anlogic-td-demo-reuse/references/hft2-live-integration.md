# HFT2真实人物、轨迹与运行代恢复

适用：当前相机/原手任务结果复用到HFT2 UI，尤其传递依赖、关键点越界、辅助失败或完整运行代交接。先从根CURRENT读取实际binding，不执行本文历史PID、目录或RPC。完整工程的面板准备仍见[hft-ui-panel-cold-start.md](hft-ui-panel-cold-start.md)。

## 启动检查必须覆盖实际消费者的传递导入

对独立复制的手部包，只验证主入口存在或少数模块能导入不够。2026-10-23第一轮真实app38中，手入口遗漏`pcie_preview_reader`，主程序和native虽启动，手任务在ready前退出。应在目标板原venv、实际工作目录、实际支持目录及原lazy import条件下检查真实入口与传递模块；检查时不创建额外摄像头或NPU context。模型权重/原手势合同无需因导入失败改变。

补依赖使用新私有目录/新manifest，保留旧失败和原源SHA。不要修改正在运行或冻结的包，不能只凭离线Python导入或主程序CSV进度签完整启动成功。完整成功还需实际hand、relay ready、新鲜producer绑定和同一owner的持续健康。

## 真实推理坐标可能越出画面

第二轮真实手任务运行约46.9秒后，`TrajectorySnapshot.observe`对越界指尖抛出异常；主采集正常退出，手返回1。即使ROI合法，回归模型的21点XY仍可能超出归一化[0,1]。新SUPPORT2复用原`MultiTrajectory`的整手XY有效性条件：拒绝该帧、取消受影响笔画、不分类、不截断坐标；下一有效帧可恢复。登记身份不因单帧越界重建，未受影响的已完成分类保持原结束时钟。

本轮已有65原合同与8边界反例共73项通过。第三代visual和trajectory空场景持续运行通过；未出现真实有效手，不能据此宣称真实边缘/遮挡反例已覆盖。真人实测要包含单手移到边缘、短暂遮挡再返回、登记保持和无误触。

8类轨迹继续用原`0/L/L_rev/L_up/L_rev_up/M/W/Z`及原分类权重。首笔惰性加载耗时单独记录；350ms姿态时效和1.2秒RESULT时效不能为掩盖冷启动迟到而放宽，更不能反复刷新原笔画结束时钟。若首笔结果实际丢失，先核`classifier_loads/calls`、`trajectory_ms`及新鲜度拒绝原因，再做独立修复。

## 主程序正常与整个特征代正常是不同结论

真实main/native返回0而hand返回1时，整个特征代仍是`FEATURE_CLOSED_WITH_FAILURES`。恢复代码不能把主程序正常证明改成整代PASS，也不能对已实际wait的主Popen再wait一次。

当前恢复入口区分两种原状态：main证明尚缺时调用原`ack_failed_start`；main已有原rc0/native-cleanup证明时，取消keep并调用原`stop_owned`完成辅助关闭，保留原错误。之后独立核验所有辅助实际wait、日志线程结束、原worker停止、native cleanup0及设备FD空，生成“失败代资源已回收”证明。同一owner保留EX后才允许新的formal编程窗口。资源回收证明不是正常功能通过。

如果历史监督进程在错误检查后卡住，先核实际原Popen wait和资源均空，再走精确PID/start的退役路径；内核/proc消失可能晚于pidfd可读。记录原请求、终态及只读确认，不因第一次/proc尚在而再次发信号。此路径只适用于已证实空资源的监督进程，不用于杀实际native或绕过清理。

## 交接发布与证据边界

第三代恢复使用原完整stop/handoff，旧owner实际退出后才启动唯一新owner；fresh编程回执绑定boot、owner、window及完整bit SHA，再reprobe、原start_panel、实际完整启动。最终keep前至少覆盖上次约47秒异常窗口的持续运行，并确认原producer身份、health、无新增协议错误；keep后的原完整stop会退出owner，未来不能复用旧RPC恢复。

CURRENT在交接窗口应明确无运行模型；运行后一起更新binding、主/采集PID、start tick、session/stop路径、launcher、控制源及完整cfg pins。旧选择只保留为历史。运行代配置不得继承前次`recovery_only`标记来伪装正常handoff。

空场景约30行/秒CSV、约10次/秒UI、hand推理耗时、`npu_called=false`分别记录；这些不是有效真人注视FPS。软件page2/1 accepted也不是K4实按或MIPI光学通过。游戏factory ready/空输入抑制不是五动作真人游戏成功；个人标定、同人登记与控制权仍需实测。

有界日志到上限后可能继续排空管道却不再落盘。第三代123秒追加窗口中，`relay.log`固定在1045493字节、尾部健康已过期，而独立新鲜`health.json`的source_updates增加4672、enqueued增加1208。测量不能从旧日志算软件0增量或硬件0Hz：软件计数用经过身份/新鲜度核验的实时健康文件，硬件计数只在窗口两端均有同代新鲜快照且时钟前向时计算，否则明确不可用。保留旧错误聚合及原始样本，再用新版本离线重算；不为修统计而热改在线owner/relay。

实际归档入口：`projects/twb_feature_integration_20261023/evidence/application_actual_v1`、`application_actual_v2`、`application_closed_recovery_v2`、`application_actual_v3`；本轮完整TD/13级物理与三次128/192字节、六次RGB1080往返各自留证。当前运行来源由根CURRENT决定，不由这些历史目录名决定。

## 长期DMA故障：先核实际通道模式，不能用错fixture签根因

第三代在约24.43分钟停止供帧；第一版WB私有候选短测通过后也在约9分54秒失败。两次C2H1的主机WB计数为0，而硬件寄存器已完成数分别为106和32、引擎idle，native实际cleanup110。这个可见症状不能单独证明设备未传输、stdout堵塞，或某一种CPU/device交错就是唯一原因。旧native把model-output DMA错误也可能标成`output_pipe_timeout`；手任务随后因`/proc/<capture>/cwd`消失而结束属于依赖故障，不能据此改手势权重或坐标处理。

测试驱动轮询函数之前，须从实际已部署FD打开源码、claim和transfer_init追踪模式。当前model C2H1按`O_RDONLY|O_CLOEXEC`打开，没有`O_TRUNC`，驱动据此采用non-EOP模式；V4L2 C2H0则明确claim EOP。第一版避免成功读取后清WB的条件还要求`eop_flush`，因此对model C2H1没有覆盖。原106描述符复现夹具误用了EOP模式，只证明其对应分支，不能签真实model通道已修。保留这些旧结果及失败，新增真实non-EOP/32与106描述符反例后才修改候选；不通过改打开标志、强开forceWB、延长超时或自动重启来掩盖通知丢失。

非零cleanup须保留。原owner只执行一次ack，实际wait后若仍拒绝恢复，应分别证明所有原PID/start、辅助wait/日志线程、worker、全设备FD、内核DMA任务与唯一EX状态；精确退役已空监督进程之后，新的显式恢复入口必须完成原quiesce及模块/root/PCI/FD全空核验，才允许同SRAM保留、reprobe、面板准备和字节比较。程序退役owner与旧真实编程receipt的owner可以不同，证明链须分别核实，不能篡改receipt冒充新下载。一次性恢复器不可套用到下一次不同PID的故障。

超过原故障时间的持续运行要保持同boot、同owner、同capture及全部PID/start，核实新鲜health、CSV字节数及源序号持续前进。稀疏15秒观察只报告源进度和采样资源，不能从尾部推算连续有效FPS、p95或端到端延迟；首窗发现程序已退出时，结果是0窗/0秒观察，不是程序只运行了观察器启动后的几秒，更不是完整35分钟通过。短字节比较、空场景稳定、真人光学与整项目完成是独立验收范围。

观察器也须使用真实schema验证。gaze CSV字段是`capture_sequence`，hand samples字段是`sequence`；后者已沿七份实际pin源码追溯至FPGA `frame_id`，不能误当为普通采样序号。首版长观察夹具将两者伪装成同名字段，离线合同虽过、实板首窗仍KeyError。新观察v2严格按来源分别读取并规范化，无任意字段fallback；加入真实首窗body重放和缺字段反例，保留旧失败及原工具。观察器解析失败不等于被观察程序失败。

## 长时留用前分别检查系统分区与数据分区

`/home/linaro`与`/userdata`可能在不同分区。2026-10-24备份把486MB临时tar放在/home，虽然/userdata仍约2GB余量，系统分区已经满，导致SFTP小文件只落0字节。须对每个实际目标和临时目录分别核`statvfs`/可用块，保留系统盘余量；不能只看/userdata或用root保留块冒充普通用户可写空间。

传输按新临时文件落地、实际长度/SHA核对、再原子发布；失败留下0字节时不继续运行该文件，也不覆盖原成功证据。先移走自生成临时包恢复系统空间，再继续部署。旧raw证据可按白名单完整备份到PC，整包与逐成员SHA一致、当前cfg与全局FD无引用后才释放板端副本；结构JSON/log/失败记录、模型环境、运行/回滚源保留。受限SSH helper不支持跨目录传输时，使用允许目录内的小块暂存并设实际分区余量底线，不改凭据或放开helper限制。备份和编译期的CPU/IO须注明，不能当作主程序空载性能窗口。


## 2026-10-24 WBv2 累计运行后新故障与软件包准备

本轮 native 累计 21061.743 秒后退出；中间存在 SSH 观察缺口，不把 native 的累计时长写成已完整观测的稳定通过。后续35分钟窗口只完成35个样本后停止。原 C2H1 终态为 WB=1、expected=3、MMIO completed=1、BUSY，与旧 WB=0/complete-idle 不同；禁止套用旧写回清零根因或将未完成 DMA 当成成功。

`capture_native.c` 的共享 `out.error` 同时承载 model DMA 失败和 stdout writer 失败。关闭时 `model_finish` 写 cleanup=110，已保存的局部 error/stage 仍可生成 signal_stop/errno0；`output_finish` 最后返回共享110，stderr 又统一标为 output_pipe_timeout。因此这组日志本身不能证明管道堵塞。原函数的77项确定性替身合同和真实源码的7168项描述符构造断言只说明代码反例、环边界护栏覆盖 C2H1；不是物理 PCIe 或真实 OS 管道压力试验。证据在 [独立审计](../../../projects/model_image_ops_board_20261023/evidence/native_partial_packet_audit_v1/README.md)。必须在未来诊断中分别记录 DMA read 与 writer 的第一失败来源、时间和实际 descriptor/result，不能仅更换标签便签根因修复。

FPGA packet 的 header、held payload 和 footer 受 ready 保持；停机后 BUSY/overflow 可能是次生。源端丢尾帧后 bundle busy/stickyerror 是待复现风险，缺失败前 BAR/AXIS 证据时不能认定。见 [本轮只读 RTL 审查](../../../projects/twb_feature_integration_20261023/evidence/c2h1_packet_static_audit_v1/REPORT.md)。

既有冻结正常更新器只适用于原完整健康且已 keep 的 owner。本轮真实 cleanup110 必须先由原 ack 实际 wait，再证明句柄、全部子进程/设备FD/流DMA任务为空；加载驱动的8个poll线程可以仍在，必须另列并在后续完整quiesce卸载时归零。精确空owner退役和新完整quiesce是独立失败恢复流程。不能调用normal-update或再次ack掩盖失败；健康但未keep的特殊前驱须使用另行审查的真实正常close与精确空owner退出合同。

app38 的四个模型权重实际是指向 app37 的符号链接。独立 app39 安装须核对每条 link 文本、resolved target 与权重 SHA，再物化相同字节的 regular 文件；不泛化放宽冻结更新器的 symlink 拒绝。`start.sh` 显式 GAZE_APP_DIR 也必须作一项精确路径替换，不能仅复制目录便认为入口已迁移。新 source-only builder 实际生成125个文件只签文件安装，未签 owner 启动或硬件验收。

原每秒已存在的 UI `sender.snapshot()` 可随同一次原子 health.json 落盘，无需新增 MMIO/线程/服务。`available=false` 必须带 snapshot=null；只按相同 boot/controller/relay/config/generation/capture_session 与 CLOCK_MONOTONIC 读取区间使用快照，不从旧 bounded stdout 补签硬件计数。计数增加仍不等于非空人体、物理扫描刷新率或光学验收。

## v4a恢复后的配置与证据边界

[恢复状态与进程归属经验](recovery-state-ownership-20261024.md)补充本轮实证：原844文件除5个最终链接外还有一个目录链接引出的40个文件，必须精确核祖先及既有目标pin；原start_profile会修改4个内存配置字段，源码校验provider应保留独立不可变副本；退出动作成功后的SFTP权限错误只补取原证据，不能重复signal。该文同时区分实际v4a运行、仅离线配置修复和仍未根治的长时停帧，不签当前keep/真人/新位流通过。
