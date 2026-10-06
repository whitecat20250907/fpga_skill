# PHY09b SDF 验证：真实注入完成，旧仿真器崩溃，零字节执行

结论是 **SDF_TOOL_BLOCKED_NO_DATA**。不能写 SDF timing PASS、布线后字节 PASS、8 相位 PASS，也不能把仿真器崩溃归为 FPGA 设计失败。三份生产候选和原网表/SDF 均保持冻结 SHA；真实原语功能 golden 和 tiny 内部 STA 属于独立证据。

## 同一 route 的真实出口及模型

route 目录：`evidence/td_route_20261005_071009_40084/`。原网表 `csi09_phy_sim.v` 自动 `$sdf_annotate` 指向同目录 `csi09_phy_sim.sdf`，未编辑网表/厂商模型或替换 clock/PAD；没有重复外部注入。网表已有 `glbl`，额外顶层只加载 `PH1_PHY_GSR`。

原厂模型为 `E:/qianrufpga/TD/sim_release/common/al_phy_glbl.v`、PH1 的 CONFIG_V2.sv/GSR/GCLK_V2/SCLK_V2/HR_BANKREF/PAD/LCLK_V2/LSLICE，以及 PAD 内部需要的 `ph1_logic_io.v`。第一次未加入 logic_io 的 elaboration 缺 48 个 IDDR/ODDR 依赖，日志 `evidence/sdf_20261005_072622_31816/` 保留，不能算注入。补齐之后模型和测试编译均为 0 errors/0 warnings。

原厂全库的初次编译停在无关 MSLICE，已停止并改用网表实际类型及其真实依赖集。没有用 stub 代替未编译模型。

匹配 SDF 是 1 ps 单位，确有非零延迟，例如：

| 真实对象 | min:typ:max（ps） |
|---|---|
| DIV2 `clkin→clkdivout` | 275:309:309 |
| DIV2 local `clkin→clkout` | 621:707:707 |
| DIV4 `clkin→clkdivout` | 275:309:309 |
| DIV4 local `clkin→clkout` | 345:398:398 |
| PAD `ipclk/isclk→diq` | 235:269:269 |

两次实际注入摘要相同：1877 module path delays，2720 timing checks，2572 scalar MIPD；读取 1877 IOPATH、2573 INTERCONNECT、1112 SETUPHOLD、248 RECREM。没有 instance/celltype/port 不匹配的 SDF error。这证明真正读取和匹配了非零路径文件；**仿真未进入 run，尚未动态观测这些延迟的效果**，不能把文件有延迟改写成动态延迟数据通过。

## 两次有界运行及结果

| 模式 | 证据 | 结果 |
|---|---|---|
| `-novopt +maxdelays +sdf_verbose +delayed_timing_checks +ntc_warn` | `evidence/sdf_20261005_072835_14388/simulation.log`、`vsim_stacktrace.vstf` | time 0 native SIGSEGV，exit 211，未到 `run -all` |
| `-novopt +maxdelays +sdf_verbose +ntc_warn`，默认 checks | `evidence/sdf_20261005_073212_15080/simulation.log`、`vsim_stacktrace.vstf` | time 0 native SIGSEGV，exit 211，未到 `run -all` |

第二轮仅去掉显式 delayed-check 选项，保留 ModelSim 默认负值检查，作为一次控制；结果一致，至此停止工具探针。两次没有 `nospecify`、`notimingchecks`、`+no_neg_tchk`、`+ntcnotchks`、SDF warning/error 抑制，未手动归零负值或改模型。

`local_clock09_sdf.do` 是可复现入口，默认第二模式；设置环境变量 `CSI09_EXPLICIT_DTC=1` 可重现第一模式。当前 ModelSim 为 SE-64 10.5（2016.02），原模型与 TD 出口为 2026.1 SP2。恢复测试需要兼容该模型/负值检查的仿真环境或厂商支持；不能通过关检查获得通过结论。

## Warning 审计

每轮 17748 个 warnings，均在初始化 time 0，分类如下：

| ID | 数量 | 直接来源及边界 |
|---|---:|---|
| 8891 | 1 | `-novopt`，为保留真实加密 LCLK 所需；不是电气/时序通过证据 |
| 3017 | 509 | 原生导出原语仅连接所用端口，模型定义更多端口；too few port connections |
| 3722 | 15266 | 上述原生 primitive 的未连接端口逐项提醒；不能把所有 optional 端口都算缺少生产模块 |
| 3016 | 25 | 官方 LSLICE 模型对 `ima`/`cea`/`ceb` 等连接报告 port type incompatible；例如 `packet_done_reg_syn_3.ima`。未擅改 netlist/model，兼容性仍需厂商环境核查 |
| 12070 | 2 | 官方加密 CONFIG_V2 内部变量-select force 提醒；不是 TB 对 routed clock/data 的 force |
| 8756 | 1 | PAD911：负值 timingchecks 的模型未提供 delayed copies |
| 3448 | 248 | 对 SDF RECREM 的负值（例如 −545 ps）由 simulator 归零；**不是人为处理，也不能据此认证这些检查** |
| 3004 | 1696 | negative delayed nets 无解，simulator 自动归零；含四 PAD 的911/956及 LSLICE759..798 |

每轮 `unannotated_0.txt` 保留 481613 bytes 的未注入 specify 对象报告，主要包含模型全部功能的未用路径/端口和未用检查。不能把注入摘要解读成模型所有 specify 已覆盖，更不能越过 3448/3004 的负值语义缺口。

PAD 的原模型使用独立 `$recovery/$removal` 和不带 delayed-signal 参数的 `$setuphold`；日志显示本环境负值检查不兼容。RECREM 可匹配独立 recovery/removal 本身是合法语法，不能仅因原模型没有 `$recrem` 就猜测 SDF 格式错误。

## 仍有效与仍待验证

- 真原语功能模型：83 完整测试包、8320 lane 字节以及共同 reset/停钟/override golden 已通过；是无布线插入延迟的数字证据。
- 真 tiny route：setup +0.174 ns、hold +0.022 ns，local PAD PCLK、全部 related reset 和 raw→n0→n1→byte 路径受约束，SYN6021/6024=0；是当前 tiny 几何下的 STA 证据。
- 本 SDF TB 计划覆盖 B8+24 编码字节、8 个独立 POR/HS 启动相位、50 ns 包中暂停和 nonzero clock insertion，但 **实际执行字节=0，已完成相位=0**。
- 25 拍 wrapper scheduler 只是 tiny sink，永远不能替代真实 CSI parser、WC/ECC/CRC、自动校准窗口和整帧验证。
- 完整工程 STA、真实板上 `best_len>0`、有效包/无错计数和持续图像采集仍由主任务独立验收。本目录没有生成或下载位流。
