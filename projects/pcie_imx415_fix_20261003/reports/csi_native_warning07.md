# build07 原生 IDDR 警告审查

2026-10-05，只读核查冻结07源码、实际TD日志和RK串口证据；没有修改FPGA、驱动、板卡或启动TD。08结果尚未纳入本报告。

## 当轮事实

- `evidence/build07_direct_staged.log:1595`至1598四条 **SYN-6024 CRITICAL-WARNING**，分别针对CSI四lane的 `PH1_LOGIC_IDDRx2`。TD原文明确：没有reset、reset为常量或ASYNCRST为DISABLE可能导致PAD接收数据与其他PAD不同步，要求考虑重写。
- 真正冻结源在 `evidence/direct_build_20261005_050803_12488/uisrc/03_ip/mipi_csi_2/csi_rx_hs_data_phy.v`，行42–52为 `ASYNCRST("DISABLE")`及`rst(1'b0)`。SHA-256 `9623dbb888879c26043bd8ea4bed8141e25293b661c96e4ee803076b1585b8b2`，不能拿后来改动的main源解释已下载07bit。
- 07完整TD最终setup +0.534ns、hold +0.021ns，日志6167。正STA没有解除以上原生MapIO警告。
- `evidence/rk_serial.log:15443`实际07读取：MCLK测270001 edges/10ms，HS byte测11137546 edges/100ms，clock配置ready，`raw_packets=0`、calibration_done=false、best_window=0。15448再次读取，calibration_done=true但best_window仍0、raw_packets仍0（可能是手动完成标记，不能把它当自动眼窗通过）。因此相机07实测失败，既不是已通过的camera，也不能靠其它CRC计数全0当可靠RAW。

## 为什么既有数字等价不能豁免该警告

1. `tools/csi_fast6/tb_sampler_reset.sv:3–7`用一个3bit phase寄存器生成sclk/pclk/bclk，固定理想4:2:1关系；停钟冻结全部phase后按原phase继续。它没有例化真实两个 `PH1_PHY_LCLK_V2` 的复位/启动相位，也没有复现真实D-PHY LP/HS时钟恢复、PAD之间skew/jitter或物理mapping差异。
2. TB用官方功能模型比较旧reset-enabled与reset-free两份相同结构。在稳定假设下，流水被新采样覆盖后两者可相同；比较刻意排除reset释放后的前8个byte clock。这个范围验证了功能模型下的后续byte顺序，不能证明跨PAD重启/首次有效采样的物理同步。
3. 官方模型 `TD/sim_release/ph1/ph1_logic_io.v`确实说明DISABLE忽略外部reset，不是同步reset；采样/并串寄存器里未显式建模自由运行计数器。**功能模型没有计数器不等于TD MapIO的实际PAD同步规则不存在。** 原生综合警告来自工具对物理映射的规则检查，是不同证据层。
4. Byte align和word align只能在各lane采样正确且相对byte时序可对齐时恢复协议。四lane一起错位、重新分频相位或采样窗无有效同步时，后级复位/valid gate不能凭空修复。现有校准best0与零RAW至少说明那些必要条件没有在07实物得到满足；它与SYN-6024有相关风险，但本次证据没有单独证明唯一因果。

原数字PASS继续保留其声明范围；必须撤销任何“因为数字等价所以SYN-6024可忽略”的推论。07删除恢复时序路径确实让STA转正，仍未完成PHY功能验收，也不能沿用旧04的相机画面或数字回环作为07相机通过。

## 08与后续验收门槛

等待08真实reset/诊断候选，按新的冻结源码/bit SHA和版本分别记录：原生IDDR是否仍有SYN-6024、reset实际映射与端点、相关HS/pclk/byte setup/hold/recovery是否全部覆盖并通过、四lane同步和校准passing-window/selected tap、RAW包进展以及CRC/ECC/WC/overflow。

需要真实LP/HS启动、重新上电、启停/失钟恢复、720/1080完整帧及真实原色图案；单次best_len非0、一次有画面或全零错误计数仍不是连续图像认证。新物理reset方案不得用false path掩盖真实recovery，也不能为了消除警告随意降低目标891Mbps或更换tap单位。

双向FIFO传输不经过CSI PHY。因此可在相机07失败时单独测07的RK→FPGA→RK输运；回传旧04实际相机帧只证明这组字节在新transport里完整，必须记录camera source版本，不能叫07相机采集通过。
