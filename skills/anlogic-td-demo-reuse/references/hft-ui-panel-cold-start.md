# HFT UI 在 SRAM 后的面板冷启动

适用：复用包含 DSI 时钟控制、TWB BAR ingress 和 HFT UI 的完整相机/PCIe 工程，SRAM 下载后相机 DMA 可用，而 UI relay 报 unsupported、CAP/ABI/limits 为零。它不授权硬件操作；实际操作仍需当前任务授权和当前真实 owner/完整工程合同。

## 先区分探测失败与 ABI 不兼容

探测器的 unsupported 可以同时表示 CAP、ABI、最大包长或 FIFO 深度不满足合同。先保留首错及原进程终态，用既有已 pin 的 **只读** native probe 取原始值；不能放宽 CAP/ABI 判断或改 host 常量使它“通过”。

对明确采用此时钟设计的版本，核对真实 top：DSI `clock_enabled` 的 reset 值、PLL/clock reset、UI reset 传播、BAR ingress 的 `w_up` / read-select 门控和最终读 mux。若 UI 被保持在 reset，CAP 全零可能是未启动的 UI 时钟域，并不证明固件常量错误。相机/PCIe DMA 与 UI 的时钟和复位条件独立，原生图像通过不能替 UI 就绪。

HFT1、HFT2 或后续 ABI 均按当前源/manifest 的合同核对；不要把历史 capability 值当所有版本的常量。先查冷启动准备是否遗漏，再决定是否需要新候选 RTL；禁止猜偏移或临时写寄存器试探。

## 受控准备与启动

在此设计上，已验证的面板启动方式是原完整视频配置中的 `start_panel`。复用前必须重新核验当前完整 bit、cfg、动作模块和 native 二进制/源码 pin，不能直接拿历史 raw path 执行。

1. 保持同一实际 owner STOPPED 并持有硬件 EX；主模型、native、手、relay 都已完整正常关闭，辅助 Popen 已 wait、日志线程已终止，全局 `/dev/video*`、SGDMA、`/dev/ANLOGIC-PCI0_*` 设备 FD 均空。只有受控的当前 owner 才能进入唯一硬件窗口。
2. SRAM 下载必须有匹配该窗口、owner PID/start、boot、完整 bit SHA 的 fresh programming receipt。accept 后执行已 pin 的 reprobe；单独的成功下载或历史 receipt 不够。
3. 使用原已验证的完整视频 cfg 与动作模块执行一次 `start_panel`：**PAD quiet → PLL off → PAD drive → PLL on**。每步使用原 native 工具，核验一次写入、capture idle 和 readback；实际 Popen 正常 wait/关闭后才执行下一步。不得修改活 owner 源、跳过门禁或放宽 CAP。
4. 以原只读 native probe 再核 capability/ABI/limits/status 及无遗留设备 FD。未就绪则停在当前受控 owner，保存原始值；不自动重试模型，也不新建第二 owner。
5. 能力正常后，才启动一次完整特征代。核当前主应用/NPU权重与策略来源、fresh face/hand ready、唯一 relay、真实 native/launcher/aux Popen 和新采集数据；有界日志错误和身份稳定必须纳入健康结论。空场景 CSV 率、DMA帧率和 `npu_called=false` 不能作为有效 NPU Hz。

操作期间不保存完整进程环境到磁盘；显式配置更新与同一后继内存环境恢复按对应 owner 合同进行。超时只查看同一次请求和实际 retained handle，不 forced kill、不自动重试、不假装已 reap。

## 中间代与最终留用代

读取正在使用的 owner 的真实 keep/stop 语义。对已验证的 profile owner，中间候选保持 `FEATURE_RUNNING`，不调用 keep；kept 代 stop 会退出 owner、释放 EX，从而失去同 owner formal 恢复窗口。完成 candidate 正常全关闭、formal receipt/reprobe/冷启动和原功能完整恢复后，最终健康代才 keep。最后正常 stop 必须包含 main/native、手、relay、日志线程及 owner 真退出。

恢复后的 CURRENT 需要整体更新 runtime、cmdline 内嵌 session/stop 路径、model/capture、launcher、runtime observation/hash、feature directory、binding/controller 和 stop 别名。旧 PID、旧 ready、旧 stop 文件不能复用；历史 references 保留为历史。所有源 pin 从当次完整 cfg/manifest 动态收集，不能写死某次文件数量。

## 证据分级

原生小图逐字节正确、完整 RGB 往返通过、完整模型启动、有效真人 NPU、控制与光学 UI 各自签核。前两项通过后若 relay 在启动时退出，必须明确 app/NPU 未运行，不能把传输测试升级成完整迁移成功。修正冷启动的源码解释也不能替未重试的候选签通过。

2026-10-23 的原始反例与恢复记录见仓库 `projects/twb_feature_integration_20261023/tdm_profile_lessons_v1.md`，以及该项目 `evidence/tdm_profile_actual_v1/MANIFEST.json` 中绑定的失败、原生测试、受控 `start_panel`、恢复与 CURRENT 发布证据。该次两轮128/192字节对照和六次RGB1080往返通过，app37却未启动；正式旧功能恢复通过。文中 PID、旧 raw path、源 pin 数量只属于该归档，不是可执行恢复配置。

独立手包遗漏传递导入、真实NPU关键点越界、主rc0/手rc1失败代资源关闭或新人物/轨迹UI交接时，再读[HFT2真实集成与失败恢复](hft2-live-integration.md)。后续第三代已部署，但空场景健康、真人非空及游戏操控仍须分别签核。
