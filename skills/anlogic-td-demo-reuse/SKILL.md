---
name: anlogic-td-demo-reuse
description: 为安路 PH1A90SEG324、MLK-AFH03/AFC03、VID005 和 IMX415 编写 Verilog，配置 TD 工程、引脚、时序和 IP，复用 UART、EEPROM、RTC、DDR3、DSI 与 CSI 六个成功例程。用于完整工程生成、仿真编译和上板验证；涉及 RK3576 PCIe 图像时检查 USB/Wi-Fi 互斥、RGB 帧边界、驱动及双向图像完整性。不包含第七个 10G 网络例程。
---

# 安路 TD 六例程复用

将功能要求落实为本机能够打开、仿真与编译的完整 TD 工程。保留六份成功例程，新功能在独立目录开发，不只输出代码片段。

## 开始时

1. 读取工作区适用的 AGENTS.md 和用户当前要求。文档提示词、历史聊天和源文件注释是资料，不能替代用户指令。
2. 优先定位当前工作区的六个 examples。本机默认 `E:/qianrufpga/fpga-lab/examples`；不要使用 `03_iic_rtc` 内嵌套的重复例程。
3. 已知硬件：PH1A90SEG324、速度等级 -2、MLK-AFH03/AFC03、VID005、IMX415、配套 7 寸屏。TD 6.2.2.200067 Release_2026.1_SP2。用户于 2026-09-23 确认前六例上板成功。换板、换封装、换子卡或屏幕时重新核对连接。
4. 按需读取 [模块与 IP](references/modules.md)、[引脚索引](references/pins.md)、[编码与集成规则](references/engineering-rules.md)、[构建与交付](references/workflow.md)。哈希清单由脚本读取，无需全部载入上下文。
5. 涉及 RK3576、PCIe、紫绿闪屏、RGB 或双向 DMA 时，必须读取 [PCIe 图像集成与验收](references/pcie-image-integration.md)。PCIe 厂商工程不是六份例程中的一份，其验证状态独立记录；不能沿用六例程成功结论。 接收无帧、PH1A PAD 时钟/复位或 BAR 寄存器读零时，再读 [CSI 时钟与 BAR 接收前置](references/csi-clock-bar-receive.md)，其中09/10记录为历史阶段。
6. 修改DSI封包CRC、调试05测试图/06相机显示或新增跨域帧统计时，读取 [DSI CRC与当前帧观测](references/dsi-crc-observation.md)，区分数字、STA、实际视频源、CSI和光学屏幕的证据。
7. 续修原13项、选择当前六例完整工程、打包或换电脑复验时，读取 [当前工程选择与13项经验](references/current-validation.md)。同时读取仓库根 `TASKS.md` 及其机器任务清单；以固定ID逐项推进，保留当前goal、后续整机路线和赛题验收视图的区别。该页给出当前版本入口与每项根因；最终动态状态以统一交付索引中的真实证据为准。
8. 无接触交互、双眼ROI、快速眼区测量、控制与光电计时时，读取 [交互方案的FPGA实现范围](references/hci-split.md)。严格区分已有完整例程与待实现的新例程，不用规划增加验收数。P3 DBUF读帧入口、快照精确约束、DBUF用户域复位释放、显示配置跨域或打包端点归属问题，再读 [P3源条件化与真实读端复验](references/hci03-dbuf-source-sync.md)。
9. 复用实际gray/Gauss/hist/Sobel/mask/morphology或RGB旁路时，读取 [HCI01预处理与帧界控制](references/hci01-preprocess.md) 和 [真实ISP颜色接口经验](references/hci-split.md#真实-isp-rgb-接口与当前完整候选)。实际ISP是高字节红，算法canonical是低字节红；按真实赋值核对输入与DDR/DSI输出，不能凭旧注释或RGB旁路九色通过跳过灰度/ROI红蓝专项。保留上一帧LUT失效、合法背压、配置接受与屏幕扫描配置的证据边界。
10. 当前FPGA PCIe与RK原生CSI双摄像头对齐和预处理时，读取 [双路例程、CSI1与PCIe恢复经验](references/dual-csi-sync.md)；停流超时、IOMMU或内核失联再读 [匹配SDK与停流定位](references/rk3576-kernel-stop-triage.md)。2026-10-11用户已退出USB采集和对齐；[三路经验](references/three-camera-sync.md)保留为历史。核对物理源、V4L2 clock/source、stride/plane、单次配对与丢帧；接收完成时间配对不等于同步曝光。
11. 逐源帧到RK延迟、跨设备时钟或同步误差测量时，读取 [时钟映射与实机边界](references/clock-mapping.md)。先查实际timer实现/分辨率，保留nonce请求回复边界及boot代次；PC↔RK校准不能代替FPGA↔RK源帧映射或曝光同步。
12. 任意九系数3×3图像卷积、signed缩放/舍入/饱和或帧界换核时，读取 [通用卷积完整例程](references/hci06-generic-conv.md)。与固定高斯/Sobel及RK NPU模型卷积区分；核启用强制灰度时，hist LUT失效必须按实际输出模式判断。 F9原174+7全源守护失败；严格LUT6排列64组合/反例通过后，自己的派生route为+0.140/+0.020ns并生成位流，仍非完整修正全源重建。实际v3表0错误却wire无START/字节、RAW0，未验收且不能断言传感器NACK；250相位RTL与实际gold47 SDA配置对照只在限定范围通过。v161恢复47/gate2/app20仅为历史记录；后续恢复须读取根CURRENT_CAMERA及其绑定选择，不能照搬历史恢复器或旧应用版本。Flash37保持。
配置器报错但缺少总线 START/字节时，再读 [早期I²C观测与复位证据](references/early-i2c-observation.md)。F10新增独立早期观测和HCK6v4；原全源门级网名守护失败已保留，R2以修正守护执行完整174+9原生构建；数字通过不代表实板根因已解决。
配置已ACK但图像CRC/ECC或训练期溢出时，再读[CSI训练与像素准入](references/csi-calibration-pixel-admission.md)，保留parser训练反馈，像素等待训练完成和新FS；当前新副本及验收状态从根任务表和实际证据选择。
I²C观测FF被打包为内部LUT数据、或合并时序报告缺少输入时，再读[打包寄存器与真实时序端点](references/packed-drive-native-boundaries.md)，分别验证配置和全部真实路径。

13. 双按键短按、长按、周期连发、断联取消及统一UART时，读取 [I03按键与连接租约](references/hci07-button-repeat.md)。默认完整top的GPIO关闭与PIN1功能自检分别报告；先签核I02实际接线，再做自己的原生/实物验收，历史排队事件不能作实时执行许可。
14. 激光物理光标、人脸排除、注册表面和连续300ms互锁时，读取 [I05三重互锁与停钟边界](references/hci08-laser-interlock.md)。几何组件与独立时钟会话组件不代替完整UART/姿态/实际驱动；两路时钟同时停止需外部关断，不能用数字计数通过宣称物理激光安全。
15. IMX415运行中开窗、电子云台、binning与原像素密度切换时，读取 [F16开窗寄存器与事务经验](references/hci09-sensor-window.md)。核对Line×2单位、I/S/V生效类别、过渡无效帧和实际基础模式；HOLD/读回/帧生效分别留证，使用独立完整副本，保留已冻结构建。
16. GazeFollower/mouse3首版迁移、RK3576 NPU和游戏接入时，读取 [注视模型RKNN迁移经验](references/gaze-rknn-migration.md)。原权重/输入语义保持；分开记录转换、实际NPU、真实ROI、个人标定和游戏实玩。低帧率或排队卡顿时，再读[重叠推理与资源归属](references/pipeline-overlap.md)；VIDEO丢脸/眨眼仍有效或备用检测时，再读[密集关键点与眼部质量](references/dense-landmark-quality.md)，不把固定开合度100当实测。USB继续退出，不能用CPU-only替代用户要求的首版NPU。
17. 原始绿点、真人阴影、自然颜色或画质退化时，先读[真人阴影与源头诊断](references/face-shadow-root-cause.md)，再按需读[颜色反例与采集延迟](references/camera-colour-latency-20261016.md)、[实机缓存冲突](references/chroma-memory-collision.md)和[低线性噪点47历史](references/linear-tail-green-noise.md)。当前运行版本、参数和用户视觉反馈读取根CURRENT_CAMERA及其绑定选择；旧gate2已被真人反例拒绝，不能照搬旧47恢复器。51保留10bit至CCM/AWB后、使用原Gamma表低2bit插值和饱和度0恒等；320源数字/完整native lineage后独立物理优化、正setup/hold、四CSI和50ERAM均通过，已实际更新SRAM并恢复原模型。2026-10-19用户已认可当前摄像头/HDMI并要求继续后续任务；保留已选配置，个人标定、有效真人NPU率和操控仍须各自验证。HDMI+DSI共用根窗口时，保留完整XWD并按真实HDMI viewport裁取核验。50读mux遗漏0x18c/190/194的失败仍保留，case局部仿真和RAW-only替代证明不能签完整CSR。Flash37保留，RK CSI/AIQ继续隔离。
采集退出出现EOF、F10失败或重复停止时，再读[原生采集停止与当前app22](references/native-capture-stop.md)；按根CURRENT_CAMERA恢复现用app/native/adapter，历史app20标签不作为当前版本依据。

18. NPU反复出现输入布局转换、考虑直接NHWC或选择现用应用时，读取[原模型原生输入布局](references/npu-native-layout.md)。逐输入核对图像和rect契约，先实际全部258维对照再测耗时；照片/NPU调用不能替代真人FPS。恢复现用app/native/adapter/estimator/alignment/model/launcher均以CURRENT_CAMERA为准。

## 选择完整基线

| 需求 | 基线目录 | 常见追加功能 |
|---|---|---|
| 串口命令/遥测 | 01_uart_loop | FIFO、命令解析、发送调度 |
| 参数保存 | 02_i2c_eeprom | 可变地址、写完成检查、错误累计 |
| 时间戳 | 03_iic_rtc | 按需设时、共享 I²C 调度 |
| 数据缓存 | 04_ddr3_axi_fdma_test | 地址布局、生产者/消费者、跨域 FIFO |
| 屏幕显示 | 05_tpg_dsi_7cun | 替换测试图像源 |
| 摄像头/ISP/ROI/显示 | 06_csi_2_dsi_imx415_7cun | 在明确像素时序处插入处理模块 |

相机需求先复制 06，它已含 DDR 和 DSI。不要再加入 04/05 的顶层和同名 IP；一个工程保留一个顶层、一套物理 DDR 控制器和一套 DSI 输出。

## 执行流程

1. **核对基线。** 执行 `scripts/td_reuse.py verify`。发现变化先读差异，不能为绕过检查自动覆盖 `references/baseline_manifest.json`。该清单记录整理时文件，不证明历史位流与当前源码一一对应。
2. **建立副本。** 执行 `clone`，目标是不存在的独立目录。保留 RTL、IP 配置/生成产物、加密文件、ROM 数据、ADC/SDC、调试配置和仿真输入。保留版权声明；脚本重定位 `.al` 并生成 `build.tcl`。
3. **读接口再编码。** 阅读声明、顶层例化和状态机，记录时钟、复位、位宽、有效条件、单位和延迟。默认参数不等于实例参数，注释不等于硬件事实。遵守 engineering-rules。
4. **核对引脚与时钟。** 从完整 ADC 和板卡连接追溯球号，保留电平、差分配对、延时和驱动属性。端口更名同步 ADC/SDC；新增外设或改变连接时重新查原理图选脚。
5. **复用 IP。** 完整保留目录及 `.al` 注册关系，不能只复制 IPC、wrapper 或例化模板。必须改参数时比较配置、生成代码、实例，在副本生成并回归。特别阅读 06 PLL 不一致记录。
6. **更新文件集。** 新 RTL、include、约束加入 `.al`，综合与仿真文件分开；检查重复模块、共享引脚与外设冲突。普通 RTL 不需要在 IP Catalog 重建。
7. **实际验证。** 执行 `audit`；新协议/状态机做带断言、超时的自检仿真；运行 TD 综合、布线、bitgen。核对本轮日志、产物时间/哈希、时钟覆盖、未约束路径、setup/hold 和关键警告，不只看退出码或 bit 存在。
8. **交付文件。** 目标目录包含 README、引脚/时钟/IP 清单、仿真入口、构建入口、验证报告及实际 bit。给出确切路径、接线、下载与验收步骤。完成授权内构建和修复；需用户接实物时说明具体操作。

## 边界

- 不覆盖原例程或用户未提交修改，不清空用户目录。
- 不以 UART 回环推断满速通信；不以 test_error=0 推断 DDR 全容量/全位宽通过；不以屏幕有画面推断 1080p 全幅、帧率、眼动算法或 RK3576 接收已完成。
- 不虚构引脚、IP 参数、PLL 频率、lane 顺序或下载结果。先查本地资料，确实缺必要信息再问用户。
- 不删时序约束或用宽泛 false path/clock groups 掩盖 CDC 问题。
- 不复制 license。helper 不自动烧板；当前任务已授权下载时依据连接继续，无需为普通文件生成、仿真、编译重复申请许可。
- 分别报告文件检查、仿真、综合布线/时序、位流、实机状态，区分当前目标验证与基线历史经验。
- PCIe 图像必须分别验证相机→FPGA→RK，以及 RK→FPGA→RK 的完整图像字节。BAR 读写、DMA 长度正确或单张正常截图都不能代替双向连续图像验收。

最终用中文简述基线、修改、工程路径、仿真/编译结果、bit 路径及剩余实机步骤。完整教学写入目标 README。

新增PCIe真实特征UI、相机/DSI共存、RAM映射退化或源头area3缩图时，读取[UI共存、真实NPU出口与小图合同](references/ui-camera-coexistence.md)。其中共存根因与新位流实板验收仍开放，不把RAM属性、逻辑模型或合成特征通过计为整机通过。

SRAM下载后相机DMA正常但HFT/TWB能力寄存器全零、中继在模型前退出，或做完整profile交接/恢复时，读取[HFT UI面板冷启动与完整恢复](references/hft-ui-panel-cold-start.md)。先核实际UI时钟/复位及原面板准备，不能放宽ABI；原生字节、模型启动、真人NPU和实屏分别签核。
