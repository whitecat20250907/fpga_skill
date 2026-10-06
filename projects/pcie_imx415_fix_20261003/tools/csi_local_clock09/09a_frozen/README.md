# CSI local-clock09 候选与小工程实证

范围仅当前问题 1（相机 CSI 无帧）。主工程和 reset08 候选未修改；没有操作板卡或生成本目录的位流。

## 官方依据和实际失败

08 完整布线的 `evidence/direct_build_20261005_061224_37468/final_timing.rpt` 有 5 条负路径：共同 sampler reset 到 PAD 的一条 recovery −0.082 ns、四条 removal 最差 −0.362 ns。PCLK 经自动 GCLK/SCLK 后比本地 SCLK 晚约 1.7 ns，单纯缩短复位数据路由会恶化 removal。这些失败都是真实时序，不能切除约束，也不能通过换成半周期复位来假定修复。

官方本地资料 `E:/qianrufpga/TD/doc/UG910_PH1A_Libraries_Guide_for_HDL_Designs.pdf` §19，印刷页 48–49：`PH1_PHY_LCLK_V2` 的 `clkdivout` 可供全局网及逻辑/IP 使用；`DIV=2..8` 时，`LCLK="DIV2TO8"` 使 `clkout` 输出同一分频值。基于此，09 保留两个 LCLK：

| 原语分支 | 本地 `clkout` | 全局 `clkdivout` |
|---|---|---|
| DIV2，DIV2TO8 | 仅四 PAD 的 pclk，222.75 MHz | fabric nibble 时钟，222.75 MHz |
| DIV4，BYPASS | PAD sclk + 共同 sampler 3FF，445.5 MHz | byte 时钟，111.375 MHz |

其他器件分支保持原功能。lane PHY 增加常量参数 `SEPARATE_PAD_PCLK`，默认 0 时仍用原 `I_rxclk_div_x2`；新 PH1A 实例显式设为 1 并接 `I_pad_pclk`。旧实例未连接新 PAD clock 时不使用 X 输入，不引入运行时 clock mux。

同时把 byte 打包改为同一 fabric PCLK 的相邻 n0/n1：`n0<=raw_iddr; n1<=n0; byte<={n0,n1}`。新增总计 16 个 FF、增加一个 nibble 拍延时，仍保持每 byte 拍输出一个字节。raw local Q 只被 n0 接收，不能再把 local raw 与 global previous nibble 直接混到 byte 寄存器。

## 实际数字结果

使用本机真实加密 `E:/qianrufpga/TD/sim_release/ph1/ph1_phy_lclk_v2.v`、IDDRx2、IDELAY、GSR 模型；没有 clock 或 PAD stub。先前按明文 module 名查找漏掉了加密 LCLK 文件，不能据此回溯升级 reset08 的 stub-clock 验证。

`local_clock09.do` 实际使用 `-novopt`，因为旧 ModelSim 10.5 的 vopt 在真实加密 LCLK 优化阶段停滞；失败/停止日志保留。最终日志 `evidence/modelsim_20261005_065614_2640/simulation.log`：0 errors、1 warning（8891，仅说明关闭优化）。83 完整包、8320 个绝对 LSB-first `0xB8`/四 lane 编码 payload 黄金字节，66 短复位、8 停钟复位、1 clock-loss 恢复、1 包中 pause、1 包中取消；58372 次共同 reset 检查与 58229 次 DIV2 local/global 同沿检查通过。8 个测试迭代改变外部 reset 释放时机；不能把它写成手工分频 stub 的 8 组物理相位证据。

这是原厂功能模型中的同源相位及字节序验证。功能模型没有实际 GCLK/SCLK 插入延时，不能单独证明 routed n0/n1/byte 的时序行为；真实 SDF 仿真和物理采集仍待完成。

## 实际 tiny route 结果（仍 FAIL）

`td_local09.tcl` 在 proc 内保存 task-specific 路径，native 日志明确回显真实 ADC/SDC 绝对路径。此前 tiny08 空 ADC 参数是顶层变量被 native Tcl 改写，不能归咎于引脚配置本身。

本轮输出 `evidence/td_route_20261005_070137_41408`。只使用真实 sys_clk、HS clock、四 data 与 UART 标量输出，共 7 个端口，全部有本板真实 ADC。UART 标量只是内部 checksum/counters 的保持输出，不是 UART 协议；本小工程绝不 bitgen/download。

- 实际 route 时钟路径显示 `DIV2.clkout → local net fo4 → PAD.ipclk`，没有 GCLK/SCLK 中转；fabric 分支是 `DIV2.clkdivout → GCLK/SCLK → nibble FF`。
- `SYN-6021`、`SYN-6024` 均为零。place 前两条 `PHY-5049` 提醒 clkdivout 尚未有 buffer；最终 route 报告证明 fabric 分支已插入 GCLK。
- 原四 PAD PCLK removal 已全部为正，最差 +0.565 ns；PAD SCLK removal 最差 +0.739 ns。
- raw→n0、n0→n1、n0/n1→byte 的相关 setup/hold 均在真实时钟约束下通过，整体 hold +0.028 ns。所有 CSI 相关分频在同一 related group，未切这些路径。
- 仍有一条共同 reset 的 recovery −0.091 ns（lane3），经过一个反相 LUT、1.050 ns net 延时，skew 0.192 ns。整体 setup 仍失败，因此本轮不能认定可用工程、不能直接下载。
- `check_timing` 仍标记四串行输入无 input delay、UART 标量无 output delay；常量 tap0 wrapper 的 `indly_en` 被优化为无效节点。这些不证明高速外部采样裕量，须最终板上校准和完整采集验证。

后续仅在明确授权的新候选中评估复位极性/路由，保存本轮失败。外部异步时钟组只用于独立系统参考与 CSI 源；不能把 PAD recovery/removal 或 n0/n1/byte 数据路径切掉来获得绿色 STA。
