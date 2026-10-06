# 开发板修复问题清单与顺序

发布附注（2026-10-06整理，2026-10-05交接状态）：10构建已中断在place，无活动TD进程/最终bit；最近下载09，当前串口与AL-LINK未枚举，SRAM保留未知。正文“正在构建”属于当时记录，以完整交接/仓库TASKS为当前状态。仍只推进#1。

更新：2026-10-05。按用户要求，每次只推进一个问题，通过该项验收后再进入下一项。证据等级分别记录为源文件检查、数字仿真、TD 编译/时序、实际板测，不相互替代。

最近已实际下载 FPGA 09 位流，驱动仍07。**09最终STA通过，但BAR运行时版本/宽/高读成0，尚未开始采集，不能作为可交付修复版。** 旧 FPGA 04 有画面但颜色错误，07曾实测无帧。尚未宣称所有例程、颜色或双向链路通过。

| 顺序 | 问题 | 当前事实 / 状态 | 该项完成条件 |
|---|---|---|---|
| 1 | 高速 CSI 接收无帧 | **唯一正在推进项。** 07 实测 INCK 27 MHz、HS byte clock 111.375 MHz；cal_done=1、best_window=0、RAW 包=0、采集超时。TD 四条 SYN-6024 明确提示常量复位 / ASYNCRST DISABLE 可能导致 PAD 不同步。08 候选恢复四路共同 PAD 复位，并添加接收诊断。 | 原语警告清除；实际 TD setup/hold 包括相关恢复路径通过；板上校准非零有效窗口，RAW 包及完整帧连续产生；接收 CRC/ECC/WC/timeout/overflow 无新增错误。颜色正确不属于此项的通过结论。 |
| 2 | RGB / Bayer 颜色错误 | **已确认、未修好。** 04 相机：橙色变绿，青色变紫。HDMI 九色块的实际 X11 像素已经验证。官方 GBRG 是候选，不能替代实拍。 | 对实拍九色块逐一核对 RGB 主通道、复色和中性灰；正确模式逐帧稳定，并记录裁切首行/首列及镜像对 CFA 的影响。 |
| 3 | 紫绿闪屏 / 异色条纹 | **尚未最终验收。** 不能凭一张正常截图或一段零错误计数判定不存在。 | 正确颜色配置下逐帧/逐行连续检测，保存异常原始帧；720p 和 1080p 达到约定帧数，无异常条纹、混帧或新增接收错误。 |
| 4 | 1080p 裁切越界 / 短帧 | **原因明确，数字修改通过、板测未通过。** 原 RAW 高度 1097，旧裁切只剩 1077 行，矩阵输出 1076 行。实机旧短帧 6197776 B 与数字 6197760 B 相差 16 B，这额外 16 B 尚不能归因已证。07 新裁切数字仿真输出完整 6220800 B。 | 最终位流实机多帧各 1920×1080×3 B，边界完整、无 short/rejected；4K 数字裁切通过不等于 PCIe x1 可连续承载 4K30。 |
| 5 | 分辨率切换 / 停止再启动 | **待板测回归。** 只支持 STOP/释放缓冲/改模式/重新分配/STREAMON，不支持任意帧中改宽度。 | 720p/1080p 交替采集 20 轮，首帧正确；停止后 12 秒无残留 poll timeout，DMA RUN/BUSY 为 0，CMA 无异常泄漏。 |
| 6 | FPGA→RK 图像传输 | **最终版本未验收。** 历史位流通过不能沿用到新位流。 | 最终位流连续整帧、长度/序号/统计正确；保存源版本、驱动/bit 哈希及原始数据。 |
| 7 | RK→FPGA→RK 双向整帧 | **最终版本未验收。** 当前已有测试入口；还未运行本轮板测。 | 已知图案与真实相机帧在多种 DMA 块长下逐字节相等，source/echo SHA 相等；实际 SIGTERM 中断后 mux/引擎恢复空闲，下一帧正确，无新增 AER/CMA 异常。 |
| 8 | PCIe 驱动取消 / 错误恢复 / 释放 | **已有修改，板测不足。** 07 负向测试 8/8 在旧 FPGA 04 上通过；旧 04 的 1080p 裁切使循环测试失败，不能算 20 轮通过。 | 最终组合完成取消、短帧、忙碌改格式及关闭恢复；不在硬件 BUSY 时释放 DMA 映射；保存实际模块哈希及板测日志。 |
| 9 | PCIe / Wi-Fi / USB 互斥 | **确认硬件限制。** PCIe1/SATA1/USB OTG1 复用，板上 Wi-Fi 所在 USB1 hub 会受影响；boot 修改不能让复用资源同时工作。已验证 CMA64 boot。独立 OTG0 外接设备未完成实测。 | 记录真实可用通路与设备树选择；独立 USB0 实物测试；明确无法同时恢复的 USB1/Wi-Fi，不能写成已修复共存。 |
| 10 | TD 时序 / CDC / MTBF | **不完整。** 07 setup +0.534 ns、hold +0.021 ns，通过不豁免 SYN-6024。独立 MTBF 最小入口仍触发 TD native crash，无合格 MTBF 报告。 | 最终 build 实际日志/覆盖/关键警告审查；CDC 属性与结构审查；若工具仍崩溃明确留存输入、dump 和未验证边界，不虚构通过。 |
| 11 | 六例程修改回归 | **不能统称全部修好。** 03 RTC 与 04 DDR 修订已有数字/TD 证据但新 bit 未板测；06 CSI/DSI 修订已有数字证据，完整 TD / 新 bit 板测尚缺。原六例程保留。 | 逐份清单记录源、仿真、完整 TD、bit、实际板测；保留原六例程基线和成功版本。 |
| 12 | skill 与交付归档 | **部分更新，尚未完成。** 失败、候选和通过项需分清。 | 将每项根因、修改、复用规则、验收命令及真实证据综合到 skill，校验原基线未改变；最终交付与实际加载版本一致。 |
| 13 | 继承的 BAR / AXI-Lite 译码与读应答 | **代码审查发现，尚未验证实际触发。** 原接口写只限定低16位且不检查 WSTRB[0]；读 mux 在 RREADY stall 时仍追踪 live ARVALID/ARADDR，可能违反 RVALID 期间 RDATA 稳定要求。本轮新增读映射已正确使用16位地址且排除0x128 IRQ别名；继承接口问题另行排队。 | 独立 AXI 事务自检覆盖读背压、上下地址别名、字节使能；修订后实际 PCIe BAR 控制回归。不能把 CPU 对齐32bit即时读正常等同任意AXI事务可靠。 |

## 工作约束

- 当前只处理 #1；#2–#13 保留排队，不同时上板更换多组变量。
- 每次新候选独立保存 source manifest、TD 输出、bit 哈希和板测记录；07 冻结证据不改写。
- #1 内的 PAD 复位修正和 PHY 诊断是定位同一接收故障的必要工作，不扩展颜色、驱动或设备树范围。
- #13 是审查新增发现，登记后排队；不插入当前 #1 修改。
- 下一项开始前写清本项实际结果。发现新故障先登记证据及所属项，不直接插入未经说明的并行修改。

## 当前关键证据

- `evidence/build07_sources.json`、`evidence/direct_build_20261005_050803_12488/`：07 冻结源及真实 TD 输出。
- `evidence/build07_direct_staged.log`、`reports/csi_native_warning07.md`：四条 SYN-6024 和不能由理想数字仿真豁免的原因。
- 板端 `evidence/diagnose07_active.jsonl`、`evidence/bayer_chart07/0_RGGB.stderr`：实际有时钟、无校准窗口和无帧。
- `evidence/hdmi_actual_x11_colour.json`、`evidence/hdmi_actual_x11_colour.png`：显示端像素证据，不是相机颜色通过证据。
- `tools/crop_height07/physical_crop.log`：实际 RAW 高度约束下的数字裁切验证。

本清单是当前唯一修复队列。`reports/validation.md` 及 skill 中的历史记录保留其版本与时间，不作为本轮全部通过结论。

## #1 当前进度

08 仅变更共同 PAD 复位、接收诊断及版本号，共6份生产源，290份源文件冻结；未改驱动、boot、Bayer/ISP或裁切行为。冻结清单 `evidence/build08_sources.json` SHA256 `9a0275222b13f5b8ca6d96f4ccdd6d2ff50aa3ca51b1dda93532d7e4f5e9b14f`。

原语级数字验证覆盖83完整包与包中取消；小型TD原语规则检查四条SYN-6024消失，但其不含真实完整引脚和布线，不能替代完整工程STA和板测。

**完整08 TD完成但验收失败，未下载。** 真实输出 `evidence/direct_build_20261005_061224_37468/`：setup -0.082 ns、hold -0.362 ns，两项TNS非零。四条SYN-6024和引脚未分配警告消失，全部CSI数据引脚按实际ADC映射为DDRX2，但1条recovery和4条removal仍未通过；所有负路径均为共同sampler复位→PAD.rst，没有转入其它问题修复。流程输出了诊断bit，但末尾验证返回失败，**bit存在不代表通过，也未加载这份bit**。

最终路径发现PCLK被fabric寄存器用户促成GCLK/SCLK分支后，比本地SCLK晚约1.7 ns。仅缩短复位数据路径会改善recovery却恶化removal，不能盲目追加寄存器或删除时序约束。下一候选仅处理同一问题的时钟分支：按本机官方 `UG910_PH1A_Libraries_Guide_for_HDL_Designs.pdf` §19，通过LCLK原语合法的分频本地输出给PAD PCLK，另一路全局输出继续给fabric；先验证真实原语、分频相位及物理路径，再决定完整构建。

09a 窄工程已完成真实7引脚 ADC 和实际布线，输出 `tools/csi_local_clock09/evidence/td_route_20261005_070137_41408/`。PAD PCLK 确认来自 DIV2.clkout 的本地分支，fabric PCLK 来自 DIV2.clkdivout 的全局分支；原4条 removal 均转正，PAD PCLK 最差 +0.565 ns，SCLK 最差 +0.739 ns。相关 nibble 数据路径亦为正。但共同复位至 lane3 PAD 仍有一条 recovery -0.091 ns，故仍是 **STA 失败候选，未完整构建、未下载**。

下一小候选仅将共同3级复位寄存器改为 active-high 存储，保持相同异步断言和相同释放边沿，争取消除 PAD.rst 前的反相 LUT。先做真实原语等价验证，再检查真实布线，不添加时序豁免。窄工程的时序或数字仿真不替代最终完整工程和上板接收验收。

09b 小候选已通过真实原语数字黄金验证（83完整包、8320绝对 lane 字节比较；warning仅ModelSim关闭优化8891）及真实7IO布线（setup +0.174 ns、hold +0.022 ns、TNS均0）。独立审查确认PAD复位路径为Q直连，反相LUT消失，所有四lane恢复/保持检查和local PAD→fabric nibble→byte路径仍受STA约束。相关ADC/SDC未放宽。匹配的SDF和网表已实际导出，但时序仿真仍进行中，不能写成已经注入通过。

09正式集成相对08仅5份生产源：三份PHY/clock源、本地时钟分支的SDC关联和版本号 `0x56440901`。没有集成小工程测试顶层。290份源冻结 `evidence/build09_sources.json`，SHA256 `0984970bb9f626f7c572aa8a82cb82a12b998c4a1117a54a9a599fa2f16158cb`。完整fresh TD正在进行，日志 `evidence/build09_direct_staged.log`。当前板上仍07，没有提前下载09。

09b 时序仿真入口已真实匹配1877条IOPATH、2572条scalar MIPD和2720项timingcheck。但本机ModelSim10.5与厂家物理模型在time0出现负值检查兼容性警告并两次native SIGSEGV（exit211）；没有执行一个字节。保留原始网表/SDF/模型与全部检查，未人为关闭或归零。该验证标记为 **SDF工具阻塞、无数据验收**，不是设计通过或失败。记录 `tools/csi_local_clock09/sdf_validation09b.md` 和 `sdf09b_acceptance.json`；数字黄金、真实STA及后续板测仍分别记录。

完整09已完成并通过CSI静态门槛：setup +0.067 ns、hold +0.020 ns、TNS均0；8项PAD recovery与8项removal完整受约束、全为正，local PAD→fabric→byte路径仍分析。实际bit SHA256 `82554d7fde3a72545d417813b27fdcbd7fec4a8f3a8ef3f5e6af664f6054b8fc`。独立报告 `reports/csi_full09_static_review.md` 保留时序覆盖99.96%、外部delay/PLL警告、MTBF未验收边界。

09 SRAM下载实际成功（18.423秒），RK重绑定后PCIe Gen2 x1正常，但**接收前置寄存器检查失败，未开始采集**：readonly版本、宽、高/状态均0，98为setup写入的100。板端记录 `evidence/receive09_first/{setup.log,pre_capture.stderr,bar_repeat.jsonl}`。新增08读selector要求ARADDR高16位为0，是错误的地址契约假设；实际userdev对应BAR0 `0x21200000..0x212fffff`、1MiB对齐，CQ桥直接转发请求地址，内部SGDMA减基址行为加密、不可凭猜测认证。当前只修正这个接收诊断前置的读地址范围，PHY09候选保持不变。候选按实测1MiB BAR0归一化低20位offset、保留16位范围且排除0x128 IRQ；先自检旧错误/新候选，再完整构建和实际寄存器复验。#13继承的写别名/WSTRB和读背压问题仍单独排队，没有同时修改。

10读地址小候选真实ModelSim自检通过268项（production读selector与寄存器块直接提取编译，不是复写行为模型），旧guard在非零base实际产生168项不匹配并触发预期Fatal。覆盖base0、真实21200000、FFF00000、CQ26残余01200000，56个寄存器与边界；IRQ128及64KiB/0x80000高偏移不被误当video寄存器。此证据只针对即时读地址解析，不是完整AXI背压/PCIe/PHY验收。

10相对09仅2份源变动：top读范围判断及版本号 `0x56440a01`。PHY09/时序约束/驱动/boot/Bayer/裁切全部不变。源冻结 `evidence/build10_sources.json` SHA256 `3567b631de4585f8984cf24a744743d72bf6f4088ab8c9518d6cd2a91ff0cd2a`；完整fresh TD进行中，日志 `evidence/build10_direct_staged.log`。板上仍最近下载的09，V4L2已卸载防止使用0尺寸；没有绕过版本前置开始采集。
