# 构建、仿真和交付

## 目录

保留 examples，新任务默认 `E:/qianrufpga/fpga-lab/projects/<任务名>/`。初次复制保留供应商布局，避免破坏相对路径。

```text
<任务目录>/
  fpga_prj.al             工程，唯一顶层
  build.tcl              TD 构建入口
  uisrc/01_rtl/          业务 RTL/顶层
  uisrc/02_sim/          测试平台与脚本
  uisrc/03_ip/           完整 IP/RTL/生成依赖
  uisrc/04_pin/          主 ADC/SDC
  al_ip/                若基线有，保留
  README.md             接线、构建、下载、验收
  clone_manifest.json   来源记录
  audit.json            静态检查
  reports/validation.md 本目标验证证据
  fpga_prj_Runs/         TD 自动输出
```

项目名保持 fpga_prj，用外层目录区分；TOP_MODULE 匹配实际顶层。.al 有 TD 特有标签，不用通用 XML 格式化器整体重写。

## PowerShell 命令

```powershell
$tdReusePython = 'C:/Users/zjh13/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$tdReuseScript = 'C:/Users/zjh13/.codex/skills/anlogic-td-demo-reuse/scripts/td_reuse.py'
$tdReuseExamples = 'E:/qianrufpga/fpga-lab/examples'
& $tdReusePython $tdReuseScript verify --examples $tdReuseExamples
& $tdReusePython $tdReuseScript clone --examples $tdReuseExamples --demo 06 --dest 'E:/qianrufpga/fpga-lab/projects/camera_roi_v1'
& $tdReusePython $tdReuseScript audit --project 'E:/qianrufpga/fpga-lab/projects/camera_roi_v1/fpga_prj.al'
& 'E:/qianrufpga/TD/bin/td_commands_prompt.exe' 'E:/qianrufpga/fpga-lab/projects/camera_roi_v1/build.tcl'
```

移机先改工具与资料路径。helper 只用 Python 标准库。clone 拒绝覆盖目标和复制变化的基线；审阅差异后决定，不删用户目录、不为绕过错误自动 catalog。

保留 bin/db/mif/mem/txt 等潜在依赖，排除运行目录、位流、波形、日志、许可和重复嵌套 demo。include、readmemh/readmemb、自定义文件读取和仿真库仍需读源码与运行 TD 检查，audit 不是 HDL elaborator。

构建时关闭同一目标的 TD GUI，避免写同一运行目录。Tcl 路径用正斜杠/花括号，反斜杠可能被转义。脚本采用本机 TD Tcl 手册 SWUG105 的 import_device、open_project、launch_runs、wait_run，依次 syn_1、phy_1。器件 PH1A90SEG324，CLI speed 2 对应 -2。

CLI 把脚本路径作为位置参数，不能额外写 `-tcl`；该版本会将它误作 source 的参数并停在提示符。完整重编在 `launch_runs` 前执行 `reset_runs syn_1`（同时回退其 physical runs）。先将旧 Runs 归档到工程之外或 evidence，helper 不代替用户选择历史结果。Tcl 还须检查本轮 bit 时间，避免 CLI 退出正常但实际命令失败或旧 bit 被当成新产物。

## Direct 完整重编备用入口

`clone` 继续生成原来的 managed `build.tcl`，另生成 `build_direct.tcl` 调用器、`td_build_direct.tcl` 模板和 `build_direct_config.tcl`。运行管理器出现 `PRJ-8806`、而 worker 已完成 gate 时，可用 direct 入口从当前 `.al` 重新 elaborate、综合、布局、布线、bitgen；它不导入旧 gate/physical 数据库，不伪造 run 完成标记。不能只凭异常退出猜 license 故障，先看实际 worker 日志。

```powershell
& 'E:/qianrufpga/TD/bin/td_commands_prompt.exe' 'E:/qianrufpga/fpga-lab/projects/camera_roi_v1/build_direct.tcl'
# 修改 TOP、run、IP、约束或 .al 后，先重新生成配置：
& $tdReusePython $tdReuseScript audit --project 'E:/qianrufpga/fpga-lab/projects/camera_roi_v1/fpga_prj.al' --direct-config 'E:/qianrufpga/fpga-lab/projects/camera_roi_v1/build_direct_config.tcl'
```

模板的 `argv` 是 `projectPath ?configurationPath?`；Windows TD CLI 只接收一个调用器脚本路径，由调用器设置 `argv`，不要直接向 exe 添加第二个项目参数。配置从当前 `.al` 读取活动 physical run 及其 synthesis run、顶层、同一 ConstraintSet 的用户 ADC/SDC；IP 的 model 名与约束来自 IPC 的 `GeneralConfig/inst`、`GeneratedFiles`。不要从旧 `*_Runs/settings.cfg` 猜当前源清单。其他器件生成的 IP 物理约束会排除并发出审阅提示，源码注册保留；混合器件 generate 分支必须确认。

当前schema2模板在新的reports/direct_build目录建立完整源快照，复制当前AL、所有注册source/IP目录依赖（包括内部ROM）和根目录ROM支持文件，列出路径/大小/mtime/SHA并检查复制字节一致。只重定位私有AL，所有TD阶段均以该新目录为cwd；原AL不变。04首次在reports打开原AL，实测PRJ-9210缺al_ip/cwc/cwc.xml及DDR/CWC黑盒；仅open时cd工程根、随后cd回reports虽04通过，仍在主PCIe elaborate暴露relative al_ip/al_pcie_ip.txt缺失，不能作为通用可靠方案。源变化重跑audit --direct-config；不复制旧Runs/波形/bit/license，不用stub替代真实核心。03/06最新模板均做实际Tcl staging smoke PASS（明确STAGING_ONLY_NOT_TD_BUILD，无TD命令）；03已进一步实际完整TD通过，06尚待新完整TD验收。

约束读取前检查非空、实际文件存在、映射路径与字节数，并打印 `DIRECT_BUILD_POST_ANALYSIS_ADC/SDC` 和 `DIRECT_BUILD_READ_ADC/SDC`。ADC按官方语法以结构化Tcl参数调用 `read_adc -file path`；SDC同样保留单个路径参数。实测旧native调用一度显示read_adc空、直接失败，不能把staging smoke视为实际约束已应用，也不能改为跳过缺失约束。新明确参数传递在03实际TD中恢复真实pin assignment与SCL时钟；精确native解析内部原因未单独证明。

若真实generated clock揭露严重hold违例，先审时钟/CDC/路径；不能删约束掩盖问题。需TD高强度物理修复时重新audit配置加入 `--fix-hold-high`，模板设置route fix_hold high并在route后显式fix_hold，再做最终update_timing/bitgen/负WNS拒绝验收。默认不改变厂商flow。03 divide252版曾在normal route跳过28条异常hold路径、WNS -2.770ns；该显式选项实际修至 +0.036ns。此结果只适用于03当前源与约束。

`load_run_param` 恢复现有 syn/phy 属性，默认 `optimize_gate -packarea` 与本机 DefaultFlow 一致。需要 map 阶段资源报告时，生成配置可用 `--area-option=-maparea`。不同 syn/phy ConstraintSet、特殊 flow hook、额外 ChipWatcher/备用 ADC 参数需定制并审查模板，不能沿用普通六例程配置推定正确。

模板按 SWUG105（2026.01，PDF 第 102 页）启用 `set_param rtl directive:async_reg on` 和 `set_param place async_reg on`，不带 `-run`；加载phy参数后再次启用两个开关，避免物理策略/OOC合并阶段丢失先前开关。该页明确 PH1A 支持 `report_mtbf`。普通 single-run 示例不要求逐步 `commit_param`。`report_param` 只打印 DB 的 public 非默认参数，不能用“all default”一句判断内部 `async_reg` 是否失效，应结合综合识别数量和最终报告判断。

每次输出到新的 `<工程>/reports/direct_build_时间_PID/`，记录阶段、配置和源 .al 哈希，检查新 DB、bit、最终 setup/hold 报告；若 WNS 为负，会保留诊断产物并以失败结束。压缩位流取决于现有 phy 参数。没有async_reg链的UART设计可能正常不生成MTBF文件；默认以 `cdc.status` 和控制台明确记录 `CDC_NOT_REPORTED`，不因此误判bit构建失败。目标明确要求MTBF报告时，重新生成配置加入 `--require-mtbf`，届时无报告为失败；不能把此要求默认为每个工程都成立。报告存在仅标 `CDC_REPORTED`，仍要查看UNDEFINED路径、覆盖和最终属性；MTBF、满足当前时序约束和生成bit均不代替CDC和上板验收。

验证状态（2026-10-04）：六例程配置解析检查通过；01独立clone已实际执行通用模板TD全流程，退出0，setup WNS +33.003ns、hold WNS +0.061ns，新bit已生成。该UART没有async_reg链，明确记录CDC_NOT_REPORTED，未把它当作构建失败。日志 `E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/evidence/skill_direct_uart_actual.log`；产物 `E:/qianrufpga/fpga-lab/projects/skill_direct_uart_candidate_20261004/reports/direct_build_20261004_231542_19088/`。这只验证通用模板与01本次TD构建，不表示其他五例已新编译、UART已本轮上板或六例已全面修好。项目专用direct和各目标完整结果另记验证报告；避免并发抢许可或写同一工程。

## 编译验收

- 确认顶层、器件、输入、约束；排查 unresolved module、多驱动、latch、截断和未连接等影响功能的错误/警告。
- 本轮 syn_1/run.log、phy_1/run.log 完成 route/bitgen，bit 非空且确为本轮生成，记录时间/SHA-256。原地重编先归档旧结果，避免失败后拿旧 bit。
- 检查 Setup/Hold WNS 与 TNS，还查时钟覆盖、例外、未约束路径、IO 定位。满足现有约束不是完整接口时序的证明。
- 位流 `<项目>/fpga_prj_Runs/phy_1/fpga_prj.bit`，压缩版 fpga_prj_compress.bit；CWC 常在 phy_1/cw/compiled.bit，须与探针匹配。

## UART 自检

先用 demo 01 clone 成 uart_v1，再执行；原 run.do 的失败/超时退出 1。

```powershell
Push-Location 'E:/qianrufpga/fpga-lab/projects/uart_v1/uisrc/02_sim/verified'
try {
  & 'D:/Modelsim/soft/win64/vsim.exe' -c -do 'do run.do; quit -code 0 -force'
} finally {
  Pop-Location
}
```

确认逐字节比较通过与 test_done，不能只看进程启动。加密 IP 仿真需安路器件库/模型，全 X 不是通过；模块级与整机仿真分开报告。

## 下载与调试

确认供电、JTAG、子卡、串口；FMC/CSI/DSI 断电插拔。BitWriter Refresh 识别 PH1A90，使用已配置 AL-LINK-FT (Local Host)，初试 PROGRAM_SRAM、5 MHz。5 MHz 为 JTAG 速率，不是系统时钟。添加当前 bit、Run、查成功提示，再验实际功能。SRAM 掉电失效，Flash 固化按需求另做。

ChipWatcher 波形区加号添加显示信号，Trigger Setup 加号添加触发条件；只能显示当前调试 bit 已编入的探针。新信号要配置 CWC、重编译、下载。看触发次数、有效信号和数据，按采样时钟换算窗口，不能把放大后平线当系统不运行。

## 验证报告

reports/validation.md 包含需求、来源/哈希、修改理由、工具/器件、引脚时钟来源、IP 差异、仿真命令/覆盖、编译/时序/警告、bit 路径/时间/SHA、实机现象/操作者、未验证项和下一步。

克隆只写“原基线已上板、目标待验证”；编译后写“目标已生成 bit”；实际操作或用户确认后才写“目标实机通过”。不能将基线成功当新设计成功。

本轮独立修复见 E:/qianrufpga/fpga-lab/projects/demo_repair_20261004 下03/04/06的 reports/validation.md。03/04已分别实际TD生成bit；03最新source staging+SCL divide252+真实high hold修复版exit0、setup +32.845ns/hold +0.036ns，产物 reports/direct_build_20261005_045937_38024/，日志上级evidence/demo03_scl_high_hold_20261005.log。04此前 +0.745ns/+0.020ns。均未本轮上板。06目前frontend、完整ISP wrapper与DBUF实际ModelSim数字通过，保留PH1加密PHY/INDEL20，新TD/板测仍待验收。不能写成六例重新上板全部通过。
