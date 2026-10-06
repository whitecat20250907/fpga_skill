# ISP 源码审查与自检（2026-10-04）

范围为开发副本的 `fpga/uisrc/03_ip/ui_isp`。没有修改六个历史成功 examples、厂商原始材料、AWB 核或板卡器件参数。本报告不表示位流已下载或摄像头实机已通过；实机验收以主报告所列 bit 哈希及连续采集为准。

## 已证明的错误

1. `ui_zhenghe` 以首行起止之间的时钟数推测行长，随后从 RAM 按连续时钟输出。RAW10 输入包含 valid 洞时，时钟跨度并不等于接受的数据拍数。它还在下一帧 SOF 才更新估计，导致数据与标记随帧间节拍而变化。
2. `ui_raw_matrix_3x3_buffer` 在任意无效拍将三行移位邻域清零；计数器在未延迟的 `zhenghe_tuser` 重置，而像素在 `valid_d1` 才使用，帧起点坐标与像素相差两个寄存器阶段。首拍重复首组作右邻，最后拍不用当前最后组，末组被丢弃；中心行实际取上一行，但最开始额外输出一次第一行，真正最后一行没有排空。
3. Bayer 插值各分支的 `bayer_ypos` 含义不统一：RGGB 将 0 解释为偶数行 R 起点，BGGR 将 1 解释为偶数行 B 起点。不能通过随机改变相机 Bayer 参数掩盖坐标错位。
4. `image_correction` 的行计数使用延迟 TLAST 而不检查同拍 valid；原始 SOF 同时影响延迟像素坐标。无效 TLAST 可移动行计数。旧接口也在下游背压时继续更新像素和标记。
5. BLC 原本无视 ready，每拍移动标记；`O_tdest` 未驱动。其余 image_cut、gamma、contrast、brightness、saturation 同样只把 ready 连回上游而不停止内部流水线。输出 FIFO 满时这样会覆盖等待的数据。
6. image_cut 用原始 SOF 复位坐标、使用延迟 valid 更新坐标，数据又延迟两级，边界掩码未与像素保持统一接受时刻。
7. Gamma 0.8 的低 LUT 值减去 2048 后为负，原有负数分支返回 255，使黑色变成白色；修为负数钳 0。contrast_level 为奇数时，原来的无符号 `(pixel−128)` 乘法在截断后可能翻转符号；改为显式有符号差、乘积与饱和，不改变当前 level 140 的黄金输出。

同一位置编码 RAW 黄金图送入保存的旧源码，在 16×6、valid 洞测试中，972 ns 首个有效输出未携带期望 SOF，断言失败，运行返回 1。证据为 `evidence/isp_baseline_failure.log`；修前源码完整保存在 `evidence/isp_before/`。这个失败证明旧链路不能正确处理该合法节拍，不直接证明每一张实机紫色帧都由单一 ISP 错误造成。

## 实施的修复

| 文件 | 行为 |
|---|---|
| image_correction.v | 用当前接受拍的坐标裁切；有效 TLAST 才增加行；独立帧起点可在 RAW 数据前到达；单级弹性输出保存 data、dest 与标记。保留原 v_start/v_end/h_end 排除边界及跳过第 0 RAW 组的规则。 |
| ui_BLC.v | 四路 RAW10 减各自 offset、负值钳 0 的算法与像素顺序不变；保存 dest；所有输出在 valid 且 !ready 时保持。 |
| ui_raw_matrix_3x3_buffer.v | 两个 2048×32 同步行 RAM，按实际接受数据组织坐标；输入 y 行时输出 y−1 行，一组右邻 lookahead；帧尾主动读取 RAM 输出真实最后行；有效洞不清邻域。首末边界使用 mirror-101 保留 Bayer 奇偶。 |
| ui_bilinear_interpolation.v | 保持输入/输出端口及四像素格式，四种 Bayer 模式统一使用实际中心行奇偶；五级带 CE 的通用双线性插值，显式 9/10 bit 两项/四项和及除数延迟。 |
| ui_zhenghe.v | 保留兼容接口，变为标记与数据同拍延迟，保留 valid 洞，不再猜测时钟跨度。新矩阵不再实例化此整合模块。 |
| ui_line_buffer_demosaic.v | 保留厂商 33 bit RAM IP，按实际有效拍写读同一地址、read-before-write；SOF 当前拍使用地址 0。新矩阵不再实例化此辅助模块。 |
| ui_image_cut/ui_image_cut.v | 单级弹性掩码，输入接受坐标与当前像素同拍；保持四个跳边参数和拍单位。 |
| gamma、contrast、brightness、saturation | 保留当前工程色彩算术、LUT 数值、参数及目录，各级寄存器和标记统一由 `!O_valid || O_ready` 使能。Gamma LUT 原本就是组合查表，无需门控时钟或更改 IP。 |
| gamma / contrast 参数边界 | Gamma 负数钳 0；contrast 改成 9 bit signed 差和 41 bit signed 乘积，算术右移、加 128 后钳 0–255。当前 140 系数与旧正常行为一致，奇数系数按真实数学含义处理。 |

原厂完整版权头保留。混合编码文件采用 ASCII 字节等价修改（Latin-1 解码/编码往返），不重写厂商注释。修复脚本在 tools，测试文件未加入 TD 综合文件集。TD 文件集仍引用原同名模块，不需要新建 IP。

数据协议：CSI 解包的低 10 bit 是 P0，再依次 P1/P2/P3；内部四 RAW8 字节高位先放 P0，以对应窗口 `[71:24]` 的 x−1…x+4 六像素。RGB 输出的低 32 bit 是 P0，格式 `{8'b0,R,G,B}`，后面依次为 P1/P2/P3。没有翻转 lane、像素或 Bayer 参数。

## 存储、吞吐和边界

两个行 RAM 共 131,072 bit，替代原矩阵两个 2048×33 RAM 加 cadence 整合 RAM。每行的四像素组数由宽度/4 给出，当前 720p/1080p 是 320/480 组。帧内吞吐可达每接受时钟四像素。输出最初延迟一行、一个四像素右邻组及 RAM/插值寄存器，不再使用 50 个时钟猜测数据到齐。

最终行读取需要 width/4 次 RAM 读取及流水线排空；该期间 I_ready 拉低，BLC 和 crop 已修为弹性，所以合法无消隐背靠背输入也必须遵守 ready，不能凭相机消隐够长推断通用正确。物理 CSI 相机无法无限暂停，需要前端 FIFO 容量和溢出计数；它们的验收属于 CSI 与系统集成报告。真正无限下游背压不可能由有限 FIFO 保证。

内部 `malformed_frame` 检查 TLAST 是否出现在约定的最后组。异常行不伪造完整帧，下一合法 SOF 清除该帧状态；需要在系统报告中结合前端 CRC/字数/溢出和驱动短包计数观察，不可把丢弃当作链路没有错误。

## 实际仿真

ModelSim SE-64 10.5：

- `tb/run_isp_golden.do`：RGGB/BGGR/GRBG/GBRG，每个模式测试 4×1（3 帧）、8×2（3 帧）、16×6（4 帧）、20×7（3 帧）、1280×720（2 帧）、1920×1080（2 帧）。位置/通道编码 RAW 与独立整数黄金插值逐像素比较，覆盖全部首末行、首末四像素、背靠背帧、valid 洞、随机背压，输出停顿稳定断言。后续回归还在矩阵前加入弹性 BLC（offset 0）检验行排空期间上游保持。
- `tb/run_isp_interfaces.do`：crop 3 帧、36 个选中组；在无效拍故意拉 TLAST，以及数据前独立 SOF；带输入洞和输出停顿。行 RAM 3 帧、36 个前驱行组，含 SOF 邻接上一帧末拍。返回 0，0 错/0 警告。
- `tb/run_isp_elastic.do`：cut→gamma22→contrast140→brightness+5→saturation130 完整后处理链，10 帧、1280 组；黄金值直接读取原厂 256 项 LUT 后独立计算。包含 valid 洞及连续 32 拍背压。另对 BLC 做 1000 组，覆盖 0/1023、各路不同 offset、dest 和 marker。返回 0，0 错/0 警告。
- `tb/run_isp_parameters.do`：Gamma 0.8 覆盖全部 0–255 输入，contrast 系数 1/3/139/140/255 各覆盖全部 0–255；含标记和背压。修复后还重复当前工程后处理链黄金测试，避免改变已接受的 RGB 行为。

日志在 evidence。仿真 do 使用停止后完成标志检查，使断言或超时失败返回非零；不能只依赖 ModelSim 遇 `$fatal` 的默认进程返回值。

## 只读 PCIe PLL 审查

PLL 初始 `.FIN("62.500")` 与运行 Gen2 的 125 MHz 不矛盾。实际厂商 `*_pcie_clock_ctrl.v` 先执行 INIT_GEN1、DBI 和链路训练，再在 10 µs 时间窗根据 core 计数判断档位：550–700 对应 62.5 MHz，1100–1300 对应 125 MHz。识别 Gen2 后写 PLL 的 DRP 预设，随后等待锁定才发布 user_link。

TD 官方 `sim_release/ph1/ph1_phy_pll.v` 指定 DRP 地址 0x24 是 CLKC0 DUTY_INT，0x27 是 CLKC0 DIV−1。Gen1 写 0x0c/0x0f，因此 DIV16/DUTY12，25% duty；Gen2 写 0x06/0x07，因此 DIV8/DUTY6，25% duty。使用外部 CLKC0 feedback，输出 user 与 core 为 1:1，同一运行态为 62.5 或 125 MHz。配置表明确固定，不应为了消除静态 FIN 告警手改 PLL 或动态表。

当前 Gen2 `create_clock -period 8` 与生成时钟 1:1/25%符合运行态。静态参数检查只认识初始 62.5 MHz，可能留下两条频率检查告警，必须记录动态切换证据，不能声称无告警。需要完整训练态 STA 时另建 16 ns master、1:1/25% 的独立分析场景；Gen1/Gen2 是同一硬件的互斥运行模式，不能当作同时活动时钟，也不能以全域 false_path 避免分析。是否能在 TD 一次报告中准确建模动态 DRP，应依据该版本支持的多模式约束功能验证。

源码依据：项目 `al_ip/PH1_LOGIC_PCIE_ph1_pcie_clock_ctrl.v`、`al_ip/PH1_LOGIC_PCIE_ph1_pcie_core_pll.v`（以及同名 ph1a90 生成副本）、厂商 PCIe SDC、TD 官方 PLL 仿真模型。最终参数和 SDC 的选择还需结合综合解析后的实际 IP 层级及实机链路速率，不把未使用模板当活动配置。
