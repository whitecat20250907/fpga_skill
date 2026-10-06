# 03 RTC / UART 独立修复验证

2026-10-04；PH1A90SEG324-2。原例程历史上板成功不替代本修复验收。

## 已修改的行为

- `uart_tx_block.v` 的旧条件 index<TX_BYTES 导致多发送一个索引越界字节；改成 index<TX_BYTES-1，并使用 max(1,clog2(TX_BYTES)) 索引宽度。请求接受时保存整个消息，发送过程中外部缓冲变化不改变本包。
- RTC 旧状态3在请求读之前保存 rd_data，而周期 t_en 同时启动UART，打印的是前次读值。现在必须先观察本次读 busy 上升，再等待其下降，保存完成的 rd_data 并产生报告脉冲。UART下一拍取到新时间的完整快照。
- 保留初始化12:00:00、每1000ms读取/报告、DS1337地址0xD0、起始寄存器0及原 I2C 实现（源码旧“500ms”注释与真实SYSCLKHZ-1计数不符，以参数/逻辑为准）。报告为 `HH-MM-SS\r\n`，精确10字节。UART核心本身和引脚未变。

## 数字测试：实际 ModelSim 10.5

```powershell
Push-Location 'E:/qianrufpga/fpga-lab/projects/demo_repair_20261004/03_iic_rtc/tb'
try {
  & 'D:/Modelsim/soft/win64/vsim.exe' -c -do 'do run_uart.do'
  & 'D:/Modelsim/soft/win64/vsim.exe' -c -do 'do run_rtc.do'
} finally { Pop-Location }
```

两进程均 exit0，编译与仿真0 errors / 0 warnings：

| 测试 | 真实 RTL / 模型范围 | 判据与结果 |
|---|---|---|
| UART block | 真实 ui_uart_tx_block + ui_uart_tx；按串口起始位/8数据位/停止位解码 | TX_BYTES=1/10/16，各2包，共54字节；精确数量/顺序/内容，运行中外部buffer变化不改变包；发送后等待并断言无第N+1字节，全部PASS |
| RTC poll | 真实rtc_clock_ds1337 + 两个UART模块；仅 ui_i2c 为事务行为模型 | 核对地址/寄存器/5字节初始化/2写3读、20,000clk读busy；两次BCD123456/123457完成后收到精确20字节，无未完成读提前UART及旧值，PASS |

日志：`evidence/uart_block.log`、`evidence/rtc_poll.log`；脚本含1ms/10ms超时。RTC测试缩放SYSCLKHZ/baud和时间，验证顺序，不测晶振误差。I2C模型没有证明SCL/SDA物理时序、NACK/异常设备恢复或实际RTC走时。UART模块仍没有向用户导出busy；本例1000ms周期远长于10字节115200bps传输，但一般复用必须保证请求间隔/排队。

## 下次实机验收

当前新bit串口115200、8N1，每报告10字节；上电初始化、连续时间递增和RTC真实完成读；不要因数字stub或TD通过把I2C硬件标为通过。

## 复现命令与构建边界

以下 ModelSim 命令在各 clone 的 `tb` 目录执行；各脚本遇到编译错误、断言失败或超时返回1，只有 test_done 为1才返回0。没有把进程启动等同通过。

实际TD首次完整构建通过：setup +34.345ns、hold +0.150ns，新bit在 reports/direct_build_20261004_234327_17776/。该次尚未包含后来补充的I2C generated SCL divide252，因此不是当前约束版时序签核。证据：E:\qianrufpga\fpga-lab\projects\pcie_imx415_fix_20261003\evidence\demo03_rtc_actual.log

2026-10-05，当前完整source staging、真实ADC/SDC与SCL divide252版已实际完成全TD。第一次真实覆盖SCL后暴露hold WNS -2.770ns、HTNS -69.851ns；normal route明确跳过28条小于-1ns的异常hold路径，保留诊断bit但入口返回失败，没有通过false-path忽略它们。采用模板显式可选 `--fix-hold-high`，从当前源全新重编并运行真实物理hold修复，最终setup +32.845ns、hold +0.036ns，STNS/HTNS均0，进程exit0。SCL周期10080ns、43个真实fanout，4项真实pin assignment生效；未改引脚或删除时序约束。

当前签核产物：`reports/direct_build_20261005_045937_38024/fpga_prj.bit`，2026-10-05 05:00:51，4,850,278字节，SHA-256 `bb5051ac351a8f9455756ba7470d204b8ecb1035660131bf94dec51dea554f56`。完整日志：`../evidence/demo03_scl_high_hold_20261005.log`；最终报告在同一新目录 `final_timing.rpt`。生成AL SHA-256 `ddfacdd3350d5a524658b7ec9d5036100971f6b8255cee37c008fc72a7e9ab66`，源AL未改变。hold裕量36ps较小，是当前约束下的数字实现结果；本轮未上板。无async_reg链而正常没有MTBF文件，明确记录CDC_NOT_REPORTED，不把它当新CDC证明。

当前源完整构建入口：

```powershell
& 'E:/qianrufpga/TD/bin/td_commands_prompt.exe' 'E:/qianrufpga/fpga-lab/projects/demo_repair_20261004/03_iic_rtc/build_direct.tcl'
```

也保留 `build.tcl` 的原 managed run 流程。direct 全流程从当前源重新 elaborate，在 `reports/direct_build_时间_PID/` 输出独立新产物。不能复用原 examples 的旧 bit 当成此次修复 bit。01、03、04的实际TD分别记录，不是板测证明。schema2模板新加入完整source staging；旧bit结论仍对应其构建时的源/模板。

源文件保持厂商原字节编码和版权；没有重新生成 IP、修改许可证或引脚。03补真实fabric SCL generated clock（CLK_DIV250/SCL_DIV125/divide252），不伪清setup/hold。`audit.json` 仅证明活动 source/IP/直接引脚检查通过，不证明 Verilog elaboration、IP 内约束、电气接口或时序签核。新 `tb` 未注册为可综合工程源。原六例程基线 verify 六项 missing/added/changed 全为空，证据在上级 evidence/baseline_verify.json。

## 修复源 SHA-256

| 文件 | SHA-256 |
|---|---|
| `uisrc/03_ip/uart_tx_block.v` | `e662899eddeed8b4804b470a1b1eaeeaa91c65d28a6ab95c7b2a5abf827e7a48` |
| `uisrc/01_rtl/rtc_clock_ds1337.v` | `7a3aa3e1d285c5328b1701ef4a3eb0f766f7e4bbc796ffcec761fd2e910668d3` |
