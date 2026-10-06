# 04 DDR3 / FDMA 独立修复验证

2026-10-04；PH1A90SEG324-2。原例程历史上板成功不替代本修复验收。

## 已修改的行为与容量证据

- 核心板硬件使用手册PDF第12页写FPGA侧1片GigaDevice DDR3L、256MB、16bit（同时注明型号/大小随实物变化）。本例真实 ui_ddr.ipc 为2Gb/x16；ui_ddr.sv 为ROW14/COL10/BANK3/BG0/CS1、MC_DATA128。容量2^(14+10+3)×2=268435456字节=256MiB。
- DDR IP 的 AXI_ADDR_WIDTH=MC_ADDR_WIDTH+clog2(MC_DATA_WIDTH/8)-3=27+4-3=28，是**字节地址**。旧top写APP_ADDR_WIDTH+3=30并请求2GiB，使地址截断/物理alias发生；现 top 为APP_ADDR_WIDTH+clog2(DRAM_BYTE_NUM)=28，测试范围256MiB、offset0。IP/颗粒时序参数未改变。换板/BOM须重新核实，不能把本容量写死用于任意板。
- 每FDMA长度1024个128bit beat，地址步长16KiB；相对地址从0到256MiB-16KiB，完成最后一次读后回0，不再多测一burst。一般范围若非整burst会向下取完整burst；offset+请求范围超容量/地址跨度、零有效范围等报config_error并禁止请求。
- 旧数据各16bit lane重复并仅比低16bit。现在全128bit比较；模式含beat序号、burst字节地址折叠tag、每lane不同常数，能够检测lane交换及高位错误。比较数据与期望在同一接受拍锁存；错误粘滞至复位，累计错误、完成burst、完成轮数。
- 保留现有CWC13探针：probe5仍低16bit示例值，probe12现在粘滞test_error。新增三个32bit计数与config_error接口暂在顶层明确空连接，不宣称它们在最终硬件可见；需观察计数时更新CWC并重编译。

## 数字测试：实际 ModelSim 10.5

```powershell
Push-Location 'E:/qianrufpga/fpga-lab/projects/demo_repair_20261004/04_ddr3_axi_fdma_test/tb'
try { & 'D:/Modelsim/soft/win64/vsim.exe' -c -do 'do run_fdma.do' }
finally { Pop-Location }
```

进程exit0；编译与仿真0 errors / 0 warnings。真实 `ui_fdma_test`，ChipWatcher仅空接口壳；FDMA用户接口以事务driver+scoreboard内存模型驱动，**没有例化真实uiFDMA、DDR控制器/PHY或物理DDR**。

- 128bit、4beat/burst，测试容量256字节、offset16、请求200字节：只发地址16/80/144并回16，覆盖非整burst尾部与相对offset。
- 首6burst干净通过；后续分别注入bit0、15、16、63、127单bit错误；12burst/4轮，错误计数精确5，后续干净数据不清除粘滞错误。
- 有效信号间插入空拍，读写请求握手/连续完成；范围越容量的第二实例config_error=1、绝不产生流量。
- 复位后错误/计数全清、地址重新从offset开始；1ms超时保证不能假通过。

日志 `evidence/fdma_checker.log`；容量来源摘录 `evidence/ddr_capacity_sources.txt`。小范围数字测试证明地址管理和checker逻辑，**不证明真实256MiB全部硬件读写、DDR校准、电气时序或真实AXI wrapper的错误响应处理**。本pattern+顺序写后读也不是完整March/保留/刷新压力测试，不能称DDR全面诊断。

## 下次实机验收

TD检查真实IP 28bit地址连接、无截断、setup/hold和DDR约束；新bit观察init_done，probe12始终0且读写计数实际推进；至少一整轮256MiB、跨高地址和重新复位。新计数若需硬件验收，接入新的CWC/可读寄存器并匹配新debugbit。错误为0但未观测读写进度，不能认定DDR通过。

## 复现命令与构建边界

以下 ModelSim 命令在各 clone 的 `tb` 目录执行；各脚本遇到编译错误、断言失败或超时返回1，只有 test_done 为1才返回0。没有把进程启动等同通过。

实际TD重试完整构建通过：setup +0.745ns、hold +0.020ns、0TNS，新bit在 reports/direct_build_20261004_235718_32084/，真实DDR及CWC依赖已分析；未上板。证据：E:\qianrufpga\fpga-lab\projects\pcie_imx415_fix_20261003\evidence\demo04_ddr_actual_retry.log

当前源完整构建入口：

```powershell
& 'E:/qianrufpga/TD/bin/td_commands_prompt.exe' 'E:/qianrufpga/fpga-lab/projects/demo_repair_20261004/04_ddr3_axi_fdma_test/build_direct.tcl'
```

也保留 `build.tcl` 的原 managed run 流程。direct 全流程从当前源重新 elaborate，在 `reports/direct_build_时间_PID/` 输出独立新产物。不能复用原 examples 的旧 bit 当成此次修复 bit。01、03、04的实际TD分别记录，不是板测证明。schema2模板新加入完整source staging；旧bit结论仍对应其构建时的源/模板。

源文件保持厂商原字节编码和版权；没有重新生成 IP、修改许可证或引脚。04无fabric I2C，保留DDR IP派生时钟与约束。`audit.json` 仅证明活动 source/IP/直接引脚检查通过，不证明 Verilog elaboration、IP 内约束、电气接口或时序签核。新 `tb` 未注册为可综合工程源。原六例程基线 verify 六项 missing/added/changed 全为空，证据在上级 evidence/baseline_verify.json。

## 修复源 SHA-256

| 文件 | SHA-256 |
|---|---|
| `uisrc/01_rtl/system_top.v` | `fd0da0c93f2cf4660427c874c1042165361e6fb53707c79fa75ea4837205485a` |
| `uisrc/01_rtl/fdma_test.v` | `b156f63f60e19b6ebc1b348d9c0e1fe1a542f3fc533c4133a263ead50517a07d` |

## 厂商原始警告对照

CLKST-5093 DDR u_dfi_clk_bufg级联、RTCLK-5078 cwc_jtck 10个localclock route、RTCLK-5079 I_ddr_clk_dup_1 12个localclock route在本次及原04 phy_1/run.log均存在，不能删除约束或伪清掩盖。首次direct因cwd缺IP XML黑盒失败，重试真实DDR/CWC后生成上述新bit。
