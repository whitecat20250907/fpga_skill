# 构建、仿真和交付

2026-10-16物理时序命名经验：PH1打包后的路径终点名可能来自同一物理单元内另一个逻辑寄存器。
P3保存的place报告中，`X_ui_FDMA/fdma_wleft_cnt_reg[12]_syn_2.imb`最差两条setup实际捕获net是
`X_ui_dbuf/rfs_r1`，来源为显示vsync的reset/config门控锥；不能仅据单元名改FDMA计数器或判其复位错误。
应读launch→capture整段net注释，再用同一次gate DB导出网表追踪逻辑链。
P3自己的rfs/wfs各4级在UI时钟，前两级Q仅到下一级D，当前8级未带ASYNC_REG；
rfs来源同时含50MHz扫描/reset与10MHz配置完成，源端条件化和约束须专项处理，结构识别本身不签MTBF或STA。
只读复制保存DB后查每组100000端点，历史place有335 setup/34 recovery路径记录、364种endpoint/check对，
而默认每组10端点只显示54/23；二者都不代表仍在route的867 hold集合。
证据`projects/hci03_packet_pipeline_20261011/evidence/saved_place_review_v1`及`dbuf_sync_graph_v1`；
保持原native输入/进程，不能为这些诊断添加宽泛clock-group或reset例外。

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

2026-10-10本机复现更新：完整私有副本位于 C:/qianrushifpga/fpga_skill/projects/demo01_full_20261010 至 demo06_full_20261010。当前01全TD +33.003/+0.061ns、03 +32.845/+0.036ns、05 +7.808/+0.061ns、06v5 +0.837/+0.020ns，均TNS0。05删除了同时活动相关PLL输出之间的错误exclusive组，当前通过的是增加相关路径检查后的完整构建。06保持原root SDC/15个DDR IP端点例外，改用同一个真实MCU clock target，避免TD注册用户组后拒绝alias rename造成例外目标为空；没有扩大clock cuts。06完整139个staged依赖与146个输入核验；仍有5条DSI ODDR警告、98.86%覆盖及实际屏/颜色待验收。

02新增真实SCL divide502后，完整TD揭露reset removal -3.288ns。启用真正的route fix_hold high/fix_hold后v4 +0.781/+0.021ns/TNS0；未删SCL或以例外遮盖失败。现有CWC错误标志保持到复位，包含真实master缺ACK；旧清错故障复现，新九次事务模型读取通过，未冒充物理EEPROM。

04新增DFI域应用复位两拍释放，192次实际生产片段释放数字自检通过。v2严格gate属性检查为0而失败；同一gate DB只读原生导出确认两个真实AL_MAP_SEQ FF均存在，async_reg仅保留于向量NET。当前v3仅针对源码声明且已核实的两个FF，在gate mapping之后、place之前显式设置属性，检查精确名称/类型/数量，再继续gate/physical审计；完整结果仍待核验。不得标额外FF、修改输入DB或用属性数量代替MTBF。

TD本机staged.inputs.tsv可能使用GBK/GB18030；按UTF-8失败后严格解码GB18030，文件路径及SHA仍逐项核对。staged AL的Project Path重定位及LF转换属于模板规定的变化，应检查转换后的完整内容；其余依赖必须保持字节一致。原串行observer的解码/AL比对失败记录保留，独立复核与原TD返回值分开报告。主PCIe当前37仍仅验收9/13；这些例程静态结果不增加外设物理完成数。


### 2026-10-10 当前六例程原生构建与工具边界

01v2、02v4、03v1（独立staging复核）、04v8、05v2、06v5均完成完整本机TD/bit/TNS0；逐SHA核对源、staged依赖与AL预期重定位。actual_result为projects/pcie_imx415_fix_20261003/reports/demo_suite_current_20261010.json，不继承当前实机外设成功。

04发现initial elaborate前启用async_reg开关不足：中间IP/OOC/debugger初始化可还原开关。实际v7原生gate0/布局0，虽然post-map设置属性可观察到gate2，但布局不保留。v8在insert_debugger后、optimize_rtl前再次设置rtl directive:async_reg on和place async_reg on，实际原生gate2、实际布局配对LSLICE1并保持属性，完整STA+.691/.020ns通过。该开关位置已修正scripts/td_build_direct.tcl。cdc_attribute_restore_exact.tcl仅在place前核对AL_MAP_SEQ身份，不得在place后以旧名约束；布局后检查实际映射属性/拓扑。属性正确不等于MTBF/CDC签核。

原生最小两级PH1A MTBF报告能生成，但100MHz接收域的settling2147492.892ns和MTBF8.218407e307异常，独立数值审核拒绝通过。settling与INT32_MAX ps换算加真实SWNS严格相同；内部原因未证实。只读移除async group仍同值，不支持该成因。复现完整包位于projects/td_mtbf_minimal_20261010_retry01/deliverables/native_mtbf_numeric_case_v1；未改原SDK/DB/bit/原约束，不能把最小例生成报告当生产37通过。

06独立颜色候选保留自己的crop/Bayer/传感器模式，迁移37的neutral-only AWB、zero gamma26端点、neutral tone及CCM。四RGB像素/拍实际wrapper颜色链1280像素及631拍背压整数oracle通过。Icarus只能编译原厂库公开原始基础模块，使用库中首个protected block前的逐字节prefix（含原版权头），不解密/替换/编辑SDK；mapped divider亦为原始模块。此为功能测试，仍不构成加密PHY/DDR/DSI或SDF模型验证。先前完整库语法失败及大用例观察超时均保留。


06颜色候选更新：完整当前源首次综合/布局/布线后发现hold -3.746ns（相机I2C复位removal）。重新audit生成配置时必须明确携带baseline中已验证的--fix-hold-high，不能因新clone默认0而丢失策略。保留失败bit/DB/SHA后，按SWUG105官方import当前route DB再fix_hold流程进行同轮物理修复；当前源/SDC不动，最终+.812/.020ns,TNS0,99.06%，实际6个配对同步单元属性前后均保持。源码入口配置已恢复high，准备脚本已补继承这一显式策略；后续重生配置仍使用--fix-hold-high。新生成bit逐次验证，不能借用旧bit结论。

实际完整RAW wrapper两帧16x3/24beats与黑色0通过；颜色链1280pixels/320beats/631stalledcycles通过。均一RAW1023下数学oracle fe8dfe只核对所选CCM运算，实际白色依自己的相机模式和屏幕拍摄验证。当前独立06颜色候选有真实新bit，仍未下载，5条保护DSI警告不清除/不计通过。

当前UART/DDR实板补充（2026-10-09T22:44:30.259011+00:00）：独立完整新版04修复原真实检查器的地址别名/短读漏检及AXI AW停顿/B响应未排空。141检查器场景、10真实桥接联合场景、9非法配置、实际UART原子快照/CRC/复位通过；完整TD setup+0.658/hold+0.020ns/TNS0/覆盖97.58%，79staged/85inputs一致。当前bit SHA0c62d110204b1f27bd80f2ca2ef16deb47a079db314ba9a29a74b33bd639885a。实际60秒595包序号2..596连续、106轮256MiB全容量读写通过，独立原始字节复核通过。初始39字节与末1字节半包保留，首次完整包之后无丢字节/CRC/错误。

01当前源/bit实际6边界字节与两段连续64KiB（共131072B）全速115200逐字节/SHA通过。首次50ms NUL无回传的失败保留，新1s neutral诊断六字节全对但初始非空而失败；第二次DTR/RTS=true打开初始安静且全速通过，不单独归因控制信号/重开/时限。真实原始两组收发与独立复核在demo01_full_20261010/evidence/independent_physical_uart_v2.json。

两个守护SRAM流程均恢复精确正式37并各抓32帧、核对当前元组、驱动/boot SHA与无客户端。最新板上仍0x56442501、SGDMA36/V4L2_37，RK IP192.168.8.197；当前无TD/BitWriter运行。原理图视觉/实际枚举确认板载FPGA UART COM4（U11 TX/V11 RX）和底板RTC/EEPROM（N14/U16），修正此前“无串口/需要RTC子卡”的推断。02 EEPROM数据备份后实测与恢复、03 RTC保留时钟实测、05/06自己的DSI屏与06RGB仍待验收；总数仍9/13，USB0、MTBF/SDF和整体交付尚未关闭。

当前EEPROM/RTC实板补充（2026-10-09T23:27:19.312518+00:00）：02受控工程完整原生setup+0.833ns/hold+0.020ns/TNS0/覆盖99.97%。默认未ARM不写EEPROM。主机两次读取全256B一致并将三份原数据fsync/SHA提交后，原真实监督状态机按500ms节拍完成地址与全位反码两轮，各256成功/0错误；两轮独立整片回读正确。按255个差异地址恢复原数据，双次全片回读SHA3d6876a0146de8576eb2395a858de1213d1b92c65b779df3a331cfd5a4584546与备份一致。596组真实请求/响应CRC/序号/计数、7次全片数据及所有恢复写入独立重放通过，初始/后续丢字节及CRC错误均0；RTC只有读取，闹钟/控制/状态不变。

03完整原生setup+33.452ns/hold+0.029ns/TNS0/覆盖99.79%；默认INITIALIZE_TIME0保留现有PT7C4337时间，实板40个10字节HH-MM-SS CRLF均逐秒连续，21-23-32至21-24-11（39秒），原始数据/位流/完整原生与恢复日志独立复核通过。默认不写时间/日历/控制，现有12/24小时模式在FPGA中转换显示，真实NACK及非法BCD明确输出错误。初次hold-3.325ns失败记录保留，highhold物理修复后合格；不由连续走时推断日期准确或电池保持。

02、03两个守护流程各已精确恢复正式37并复验32帧，核对SGDMA36/V4L2_37、boot SHA与空闲；原六例程逐文件SHA仍无变化。当前板上0x56442501、192.168.8.197，无TD/BitWriter进程。01UART、02EEPROM、03RTC、04DDR实物子项均通过，05/06自己的DSI屏及06RGB待验收，USB0/MTBF/SDF与整体交付仍未关闭；整项完成数仍9/13。

当前UART输入CDC修订（2026-10-09T23:58:43.043245+00:00）：在独立完整demo01_uart_cdc_20261010与demo02_service_cdc_20261010中保留原vendorUART/I2C/EEPROM监督/CWC与ADC/SDC，前置两个空闲高电平专用同步FF。实际gate天然2FF；place/route同一PH1双寄存器LSLICE，两通道同钟/常开/SET初始化。三阶段完整网表独立核对raw只接一级D、一级Q只接二级D、vendor只接二级Q；无属性setter假补同步器。01完整TD setup+34.573/hold+0.117ns/TNS0/覆盖99.59%，数字128相位+256连续/32波特率相位场景通过，当前实板6字节+131072B115200全速逐字节/SHA通过（DTR/RTS=false，初始安静）。02完整TD setup+0.695/hold+0.020ns/TNS0/覆盖99.97%，真实UART/I2C联合数字仿真和当前两轮256全地址各成功256/错误0、独立整片图样回读/原数据恢复双读/RTC只读控制状态不变通过。

02首轮即时打开无状态回复发生在backup/ARM之前，3个纯STATUS请求没有EEPROM写入；原失败及恢复37证据保留。只读诊断重加载/200ms等待/初始读取后，四种DTRRTS/字节间隔组合12个CRC/序号/空闲状态全部正确，初始1636B旧ASCII保留。新版主机增加等待、记录初始数据并先只读握手；完整新版实板证据独立复核，未单独归因控制信号、重开、重载或等待。每轮守护均恢复精确37并抓32帧，原数据恢复SHA仍3d6876a0146de8576eb2395a858de1213d1b92c65b779df3a331cfd5a4584546。

nativewrite_verilog忽略文档中的指定文件名；helper现按默认真实产物逐阶段复制，v1观察不足与v2完整快照分开，原日志不动。原六例程SHA未变。当前板上37/SGDMA36/V4L2_37/boot/空闲正确，IP192.168.8.197，无后台TD/BitWriter任务。UART输入拓扑修复和通讯验证未代替定量MTBF/SDF；整项仍9/13，USB0、05/06自己的DSI/RGB、工具MTBF/SDF和全13交付仍待收口。

MTBF不同物理单元对照（2026-10-10T00:16:02.859796+00:00）：完整控制工程td_mtbf_opposite_edge_20261010保持25MHzsource/100MHzsample与原ADC/SDC，第一级负沿/第二级正沿，实际两个独立PH1同步单元、5ns半周期，完整native setup+4.047ns/hold+2.165ns/TNS0/覆盖100%。只读report_mtbf返回0并识别2级/100MHz，但settling2147487.694ns恰等INT32MAXps换算+4.047ns，MTBF8.218407e307years被独立复核拒绝。该错误可在独立物理单元发生，samecellpacking不是必要条件；边沿和布局同时改变，未确认SDK实现原因。报告前后源/约束/DB/bit完全一致，诊断bit未下载，生产37及合格例程不替换。复现包C:\qianrushifpga\fpga_skill\projects\td_mtbf_opposite_edge_20261010\deliverables\native_mtbf_distinct_cells_numeric_v1\native_mtbf_distinct_cells_numeric_v1.tgz，1896553B，SHA-256 da762d6f5bec1a6510466b1c4aa2e1ccaf75e776801507d7ac5a747e61757036，156文件/158成员逐字节核验。整项仍9/13，MTBF/SDF未关闭。

正式37当前SDF材料（2026-10-10T00:37:17.755817+00:00）：同一合格prDB导出匹配44.57MB物理网表/60.68MB SDF，独立核对28632 CELL及360126互连端点，CSI时钟+四路PAD和2个LCLK时序记录匹配。原119个无CELL物理单元完整列出，无动态仿真/注入覆盖/字节通过推断。v1重写旧辅助clock_collections报告的边界保留；v2重定向该SDC诊断输出，317源与全部原native构建文件SHA一致。当前101库源和18原语的实际模型路径/SHA已记录，本机未找到vsim，旧ModelSim10.5 time0崩溃记录仍属09b。真实GSR/相机I2C初始化/使能条件下的当前动态TB、相位/角/完整golden验收须在可用许可仿真器内继续。材料目录evidence/current37_sdf_export_v2；整项仍9/13。

统一当前交付入口（2026-10-10T00:55:35.167100+00:00）：deliverables/current_delivery_index_v1/README.md与index.json将6个当前工程对应到9份交付包；原生源/产物SHA再次核对，并从实际压缩包读取6例当前bit、正式37bit及6份运行文件共13个选定成员核对原字节。06当前bit的包内路径为native_current_hold_repair_v2/fpga_prj.bit，失败hold父版保留且明确不选。05独立完整包125文件/127成员，SHA 8cd32a3884f5d3139b882f9cde730ef9c2fb80b1a61f4f337f632a71c4c72392，完整TD与5条加密ODDR复位警告明确保留，实屏待验。正式37实际RK运行文件包77文件/79成员、532347B、SHA 162eb029bbc5f0e9dd486cab5454ae58ffddffff1251e2b589bb6f91ac558129，补齐两实际ko/3个AArch64工具/当前setup和完整runtime源；另传回部署与37构建两份相同Module.symvers（2216B、SHA 6cdeb64fd0d7d37a926b52a06dac785fc71ccfb71b83caea116552c65f311bbc）。首次只读helper位置误判在传输前失败保留，未修改远程文件。当前只读实际37/模块/boot/参数/空闲及无client正确，USB0仍not attached/同一2a210000.pcie控制器的20桥和21端点存在；原六例程未改，无本轮下载/Flash/boot/module/gadget变化，整项仍9/13。

完整当前37物理归档交付（2026-10-10T01:04:47.219358+00:00）：deliverables/current37_physical_archives_v1包含10个原tgz的25份64MiB以内原样分片（总1209745416B）及87份原生/源同一性/独立验收/protocol raw证明。现有原压缩包SHA均匹配旧两端/全成员复核；新分片独立顺序重算25片与10整包SHA，离线工具实际重组全部10份后再次读新磁盘文件核验，原证据未改。统一索引现包含原始选帧、完整行单元统计/内核日志、九色/同屏ROI/HDMI源、暂停/循环/回环/异常恢复数据完整入口。没有再抓帧、下载bit、改SDK/许可/驱动/gadget/boot/Flash，未增加功能通过数，整项仍9/13。

实际独立联网与PCIe角色复核（2026-10-10T01:27:47.676625+00:00）：当前SSH到192.168.8.121经end1，RK源192.168.8.197；end1是2a230000.ethernet/rk_gmac-dwmac平台网口，up/carrier1/1000Mbps/full，无PCI/USB父路径，与2a210000.pcie FPGA路径独立。20:00.0为pcieport桥/class060400，21:00.0为FPGA memory endpoint/class050000/1edb:abcd/Anlogic-pcie，匹配实际sgdma源的驱动名/ID，链路Gen2x1且共享一个2a210000控制器。以前“两个根”说法已改正，旧压缩包/原始snapshot字节不改；旧pcie_endpoints键只是未分类PCI函数列表，helper保留兼容别名并新增准确pci_functions键。第9项独立联网子项有实际证据，但USB0仍not attached；设备/sink角色、既有gadget绑定、adbd进程/FFS ep0/1/2存在，当前无typec partner/orientation unknown/UDC suspended，不能由软件绑定认定实体USB通过，仍需J4实际主机连接。没有改变role/gadget/adbd/驱动/DT/boot，整项仍9/13。

USB0实体验收入口：版本查询/既有gadget绑定不是USB通过。实际UDC未configured时在ADB和板端写入前退出；后续使用-d核对唯一USB serial、固定transport_id，再核对SSH machine-id及新目录随机nonce，防止同序列号或TCP目标误匹配。生成的远端Python先compile再执行，每次保留入口源码快照；4MiB push/pull禁用压缩、全字节/SHA和SSH SHA一致后再核对正式37/模块/boot/空闲。当前仅本机工具版本、未连接早退及源码语法验证，正向分支尚未执行，24文件准备包不替代实体USB验收。
