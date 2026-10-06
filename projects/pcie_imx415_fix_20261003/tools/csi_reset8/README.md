# CSI reset08 独立候选

本目录只解决当前问题 1：27 MHz MCLK 下 CSI 自动校准无有效眼窗、相机无帧。它不是完整工程、不是可下载位流，也没有上板验收。主 FPGA 源、板卡、驱动及原例程未由本任务修改。

## 已知失败与修复依据

- 板上 07 的 MCLK 监测为 270001 edges/10 ms，HS byte 监测为 11137544 edges/100 ms；主动运行 12 秒后，校准 done=1、best_len=0、RAW 包数=0。时钟频率正确不代表 CSI 数据接收正常。
- 07 实际 TD 日志 `evidence/build07_direct_staged.log` 给出四条 `SYN-6024 CRITICAL-WARNING`：PH1 IDDR 无有效 rst 或 `ASYNCRST=DISABLE` 可能导致各 PAD 接收数据不同步。旧连续采样的数字相等测试不能否定这个真实器件要求。07 连续 PAD 采样方案不能作为已修复基线。
- 这条警告是必须修复的事实，但尚不能唯一证明它就是本次所有 tap 失败的原因；物理 lane、延迟范围及真实高速时钟相位仍需新位流诊断。

## 两个候选 RTL

`csi_rx_phy.v` 增加一条共同的 HSx4 时钟域 3FF 复位释放链，四 lane 使用同一个 `sampler_reset_n`。断钟、外部 reset、接收关闭使复位异步置位；复位只在三次真实 HSx4 上升沿后释放。原 byte 域两级复位释放及字节对齐/协议复位保持原接口与行为。禁止给四个 lane 分别生成释放链。

`csi_rx_hs_data_phy.v` 增加 `I_sampler_reset_n`，PH1 PAD 原语恢复 `ASYNCRST="ENABLE"` 与 `.rst(~I_sampler_reset_n)`。后续 nibble、byte 拼接寄存器保持连续采样，不增加不必要的高速复位扇出。PH2 分支不改变。

诊断端口和规则：

| 端口 | 契约 |
|---|---|
| `I_override_enable` | 已经以完整命令快照送入 byte 域；1 选择外部 tap。X/Z 在仿真回退原自动模式。 |
| `I_override_tap[5:0]` | 同一命令快照；PH1 仅低 5 位，物理 32 taps。不能以裸多位同步器跨域。 |
| `O_dbg_raw_bytes` | 未对齐四 lane 的连续采样 byte，lane0 位于最低 8 位；不是 packet-valid 或 CRC 证明。 |
| `O_sampler_reset_n` | 共同 PAD 复位状态；异域诊断必须同步后读取。 |

override 的优先级高于原物理按钮。启用、tap 改变时各产生一个 byte 拍的加载脉冲；稳定命令不反复加载。关闭 override 恢复自动当前 tap 并加载一次，清除旧按钮手动模式。持续的命令在复位恢复后重新加载。`O_auto_delay_done` 在手动 override 下可以为 1，`O_dbg_best_len` 始终保留真实自动扫描结果；手动绕过 gate 不能被验收脚本当作自动校准通过。原自动扫描继续运行，没有伪造眼窗长度。

## 实际数字验证

入口：`D:/Modelsim/soft/win64/vsim.exe -c -do E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/tools/csi_reset8/reset8.do`。

实际日志：`evidence/modelsim_20261005_060541_40052/simulation.log`。0 errors、0 warnings，黄金数据 PASS：

- 使用实际安路 `PH1_LOGIC_IDDRx2`、`PH1_LOGIC_DYNAMIC_IDELAY`、`PH1_PHY_GSR` 模型和本项目真实字节对齐/clock-detector RTL。
- 8 组相关 4:2:1 时钟相位；LSB-first 序列中的绝对 `0xB8` 与四 lane 不同编码 payload，83 个完整包、8320 个逐字节黄金数据比较（8300 个完整包字节，20 个随后被 reset 取消的包中已接受字节）。
- 66 次短复位（含包中复位）、8 次停钟复位、1 次 clock loss、1 次非零 payload 中停钟与恢复；58520 次共同 reset/三拍释放检查。
- override 启用、高位 mask、单拍 load、稳定命令、修改 tap、关闭恢复 auto、X/Z fallback、真实 best_len=0 的 8 项定向检查。

本机没有 `PH1_PHY_LCLK_V2` 功能模型，所以 testbench 只替换时钟分频器为明确的 4:2:1 相关时钟；没有用 stub 替换 PAD、IDELAY、复位链或字节对齐。原厂 IDELAY 功能模型的 `indly_en` 行为也不能模拟真实眼图或证明持续 tap 的物理时序。数字 PASS 不等于真实 LCLK 相位、891 Mbps 采样裕量、TD recovery/removal 或板上校准通过。

## 独立 TD 检查与剩余验收

`td_reset8.tcl` 仅分析、elaborate、RTL/gate optimize、原语合法化与导出 gate DB。不 place、route、bitgen，也不下载。试验 wrapper 只复用已核实相机 PAD 引脚，未提供完整输出引脚，禁止把它当可烧录工程。

实际独立 TD 日志 `td_launcher3.log` 与 `evidence/td_20261005_060734_34412` 已完成：Map IO 阶段 `SYN-6024` 为零，两个原生 LCLK 保留，19 个 gate `ASYNC_REG` cells 中包括共同 sampler 的完整 3FF 链。仍有一条 `SYN-6021 CRITICAL-WARNING`：102/102 逻辑 ports 没有 user location，尽管脚本读取了只含 6 条相机输入的 ADC，这些约束在该 standalone 上下文没有实际生效。这是未配置完整物理 wrapper 的明确局限；不能用本轮 trial 证明真实板卡球位、物理 PAD packing 或时序。没有重开 TD 探针，也没有启用 `bitgen unconstr_io`。前两次入口错误（分批 analyze 覆盖文件集、read_adc 需明确 -file）日志保留，不计为验证 PASS。

主集成仍必须保留真实 HS 时钟和派生时钟约束，重新核对共同复位到四 PAD 的路径以及所有 setup/hold。不能用 false path 或放宽频率隐藏同域失败。之后在新位流实测：自动校准 done=1 且 best_len>0，主动 FS/RAW/有效 payload 计数进展，CRC/ECC/WC/溢出为零，1080/720 连续完整帧及重复 start/stop 均通过。若自动仍 best_len=0，使用 byte 域一致的手动 tap 与未 gate 诊断逐 tap 查找，不能继续从 gated 错误全零推断链路正常。
