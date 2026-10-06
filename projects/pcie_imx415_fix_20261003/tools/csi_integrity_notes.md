# CSI 接收修复与验证记录

2026-10-04，独立排错项目中的最小修复。厂商材料目录与六份 examples 未改。

## 源码问题和修改

- `csi_rx_packet_handler.v` 原实现以每拍 4 字节累计 WC，进入结束状态前仍输出整拍，CRC 与尾部填充值进入 RAW 流；WC 小于 4 还被强制改为 4。现在按实际 WC 输出 `O_payload_bytes`（1–4）和 `O_payload_last`，将 CRC 两个字节独立取出，支持最后载荷与 CRC 共拍以及 CRC 跨拍。仅目标 VC 的 RAW10（DT 0x2B）送给解包，embedded/non-RAW 长包仍消费但不作图像。
- 新增流式 CRC-16 校验：FFFF 初始值，LSB 先行，反射多项式 8408，无最终异或。对照本地 06 的 `crc16_8b.v` 实际 RTL逐字节生成黄金校验值。CRC 失配、错误头 ECC、非法 RAW10 WC（零或不能被 5 整除）、输入有效超时各计数。
- `csi_rx_10bit_unpack.v` 只消费载荷实际字节数，每 5 字节输出四个 10 位像素，末组显式携带 `O_dout_last`。低 10 位为 P0，之后依次 P1、P2、P3。RAW10 的自然 valid 空拍不是行末。
- `csi_rx_vid2stream.v` 移除根据 valid 下降沿猜测 TLAST 的逻辑，使用显式解包末组标记；FS/帧起点锁存至第一组接受写入 FIFO。保持原厂 `mipi_sfifo`、RAM 和 Gray CDC；标准 AXI valid 不再等待 ready。FIFO 满时拒绝写入并明确计数。
- `mipi_csi_rx.v` 的 parser 保持运行以维持 PHY 字节对齐依赖的 `packet_done/sync_wait`；只有图像解包/FIFO 写入在校准完成同步后 gate，并且再等待一个新的 FS 才开始输出完整图像。校准扫描阶段的误码不进入图像诊断计数。

## 新增诊断接口

全部计数与 `O_csi_error_pulse` 属于 `O_hs_div_clk` 时钟域；上层必须采用握手快照，不能用每位独立 2FF 表示原子计数读值。复位来源是 PHY `w_reset_out`。

后续校准修复加入 parser 的 `I_count_enable`，由首次校准完成后的新 FS 放行，与协议运行的 `I_enable` 独立。表中计数因此针对已放行捕获期间；校准中的协议错误仍完成/取消包以驱动对齐，但不污染计数。

| 输出端口 | 单位与含义 |
|---|---|
| `O_csi_raw_packets[31:0]` | 目标 VC、RAW10、WC 合法且 CRC 正确的完成长包 |
| `O_csi_crc_errors[31:0]` | 目标 VC 完成长包 CRC 错误 |
| `O_csi_ecc_errors[31:0]` | 待接头状态中的 ECC 不匹配头 |
| `O_csi_wc_errors[31:0]` | RAW10 WC 为零或非 5 的整数倍；不是预设图像宽度比较器 |
| `O_csi_timeout_errors[31:0]` | 接收包中连续 64 解析时钟没有有效输入而取消 |
| `O_csi_fifo_overflows[31:0]` | FIFO 满时拒绝的四像素组数 |
| `O_csi_error_pulse` | parser 校验、解包形状、FIFO 丢弃事件的源域脉冲 |

## 自检结果

入口 `tb/csi_integrity.do`，证据 `evidence/csi_integrity_sim.log`。命令：

```powershell
# 工作目录为项目 tb/
& 'D:/Modelsim/soft/win64/vsim.exe' -c -do csi_integrity.do -l '../evidence/csi_integrity_sim.log'
```

ModelSim 10.5 编译 0 error/0 warning；仿真 0 error，保留 sfifo 原有 RAM 端口 `dib`、`doa` 未连接的 3 条工具警告。自检最终 3731 个四像素组逐像素匹配，4 SOF/12 TLAST；包含：

- 4、8、12、16、20 像素短行，覆盖 WC mod4 的所有情况及 CRC 共拍/跨拍；
- 1944 像素 / WC 2430（最后载荷仅 2 字节）、3888 / 4860、1920 / 2400、1280 / 1600；
- 输入 valid 空拍、异步视频时钟、随机 ready 停顿及 AXI stall 数据/标记保持断言；
- 人为 CRC/ECC 错误、非法 WC、无载荷超时、其他 VC 短包；
- 阻塞视频读端，9000 次组写入：FIFO 留存 8191 组、809 组丢弃有精确计数；复位恢复后 1944 像素完整行再次匹配；
- 最长 5 ms 仿真超时与 `$fatal` 非零失败出口。

这次仿真使用真实原厂 FIFO、RAM/Gray CDC RTL与本地 DSI checksum RTL，没有 PHY、PLL、IO 延迟或 PCIe 模型。只有协议输入在数字接口产生；不能由此宣称实际相机紫绿闪屏已消除或 MIPI 信号质量合格。

## 验证边界

CRC 为流式诊断：在包尾得到结果以前，载荷已经推进到 ISP，因此它不会自动撤回或消除坏帧。上层可用错误脉冲标记/取消当帧，或后续增加双行校验缓存。RAW 1944/3888 的双行字节缓存分别约 4860/9720 字节，需评估实际映射 ERAM、重放吞吐与校准前后行为后实现。没有引入整帧缓存。

WC 诊断检测 RAW10 编组完整性，尚未检查同一帧每行宽度/行总数或传感器期望宽高；完整 CRC 也不能证明 Bayer 奇偶、裁切原点或 ISP 顺序正确。仍须根任务进行 TD 综合/时序和新位流实机连续图像验收。

`tools/fix_csi_integrity.py` 保存原四文件字节到 `tools/csi_before_*.txt` 后安装本补丁，保留原头注释；父任务进一步修改集成文件后不要无比较再次运行覆盖。

## PHY 后续发现与最小修复

实际 `csi_rx_hs_data_phy.v` 的 PH1A 分支实例 `PH1_LOGIC_DYNAMIC_IDELAY.WIDTH=5`，只使用 `I_delay_value[4:0]`。因此只有 **32 个物理 tap**；旧 0–63 扫描重复扫描每个 tap，fallback 32 在 PH1A 实际变成 tap0。旧 `cur_len/best_len` 6 位还使 64 个 tap 全部通过时长度从63回0，误报没有 eye。

- `auto_delay_ctl.v` 增加物理 `TAP_COUNT`，由 PH1A PHY 选32，扫描0–31、fallback16；其他64tap实现保留支持。
- `cur_len/best_len` 为7位，真实64tap全通过能保存64；6位 debug接口对64饱和显示63，PH1A最大32则精确显示32。内部选定中点使用完整长度。
- 扫描计数按参数确定宽度，计入最后一次测试样本；wait参数16777216表示真实2^24周期，旧 `wait_cnt[23]` 实际仅2^23周期，与旧注释不符。各时间都是字节时钟周期，不能把150MHz参考周期用于换算。
- `csi_rx_phy.v` 中新参考域时钟存在判断的复位请求在 HS 字节时钟域使用两级寄存器同步释放、异步断言；root 的 Gray clock detector源文件未由本子任务改动。
- 手动 tap 模式继承自动选定 tap，PH1A在31后回0，不再在debug中显示32但器件实际取0。校准完成仅表示流程结束；best_len=0仍为fallback，不能当作眼图质量通过。
- parser 禁用会让 `sync_wait` 永久为1，byte_align的超时计数会周期性清空 valid，改变校准统计。因此 parser继续运行，校准/新FS gate仅作用于图像和计数，保留独立真实对齐反馈。

新增自检：

| 入口/证据 | 已验证范围 |
|---|---|
| `tb/csi_calibration.do` / `evidence/csi_calibration_sim.log` | 32tap全PASS、中央窗、两端同长窗、tap0/tap31单点、全FAIL、64tap全PASS不wrap、真实PHY手动控制40步与复位；0 error/0 warning |
| `tb/csi_capture_gate.do` / `evidence/csi_capture_gate_sim.log` | 实际word_align、gearbox、parser、unpack、vendor FIFO链；校准前parser仍有反馈；done在帧内出现后不输出余帧，等新FS后4组/1SOF/2TLAST与2个CRC-good包；0 error，保留vendor FIFO 3 warnings |

校准测试仅对电气clock/IO block使用行为壳，真实控制/reset/manual RTL运行；gate测试从byte_align输出注入B8同步字和协议字。**没有证明真实pad delay、IDDR位采样、时钟相位或信号完整性。** word_align在真实byte_align的首个有效B8后输出header，其首次有效对齐不能凭直觉改成保留B8。

本工程PLL实际100MHz输入、C0=150MHz用于presence参考，C2=24MHz。PH1A MIPI时钟/4得到字节时钟，字节频率是lane bit rate/8，与150MHz参考无需同频。仍需通过新增HS采样与传感器真实时钟配置核对速率和SDC；top从24MHz toggle产生12MHz MCLK，是否为VID005实际摄像头时钟源也需结合硬件线路确认。
