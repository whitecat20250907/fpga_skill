# 六例程复用影响与 06 修复迁移对照

2026-10-04，只读审查 `E:/qianrufpga/fpga-lab/examples` 六个正式目录和当前 PCIe 修复副本。原例程未修改，没有为本次审查创建 06 clone、启动 TD 或操作开发板。用户于 2026-09-23 确认前六例能上板运行，是历史功能事实，不表示本次已全面重新验收，也不表示合法节拍、参数边界和持续图像均没有缺陷。

结论：本次修复应迁移到独立 06 副本。**不能只复制 PCIe 工程里的同名 ISP 文件到旧 06，再称为可以运行或已经验证。** 原 06 的 CSI/PHY 实现与 PCIe 副本不同；它的 ISP 具有同源缺陷，同时顶层没有完整背压连接。接收端、裁切、ISP、RAM 依赖和顶层接口需要一起迁移，重新仿真、TD 编译/时序与 CSI→DDR→DSI 上板验收。01–05 不包含本次 CSI/ISP 模块，但其已知独立问题仍须单独处理。

## 六份基线的本次检查

用 skill 的 `td_reuse.py audit` 读取当前 `.al` 的显式依赖、IP 文件清单和直接 ADC 冲突，结果如下。该检查不是 HDL elaboration，零错误不能推出逻辑或时序正确。未使用 03 目录内嵌套的重复 demo。

| 基线 | 顶层 | .al 显式文件数 | 引用/直接引脚审查错误 | 本次 CSI/ISP 修复影响 |
|---|---|---:|---:|---|
| 01_uart_loop | uart_top | 5 | 0 | 无 CSI/ISP 同源模块；UART 忙时没有输入队列的结构不能用于任意多源遥测 |
| 02_i2c_eeprom | eeprom_test | 5 | 0 | 无 CSI/ISP 同源模块；与 RTC 共线集成仍要一个 I²C 主机和事务调度 |
| 03_iic_rtc | rtc_clock_ds1337 | 6 | 0 | 无 CSI/ISP 同源模块；串口发送边界有独立确定缺陷，见下文 |
| 04_ddr3_axi_fdma_test | example_top | 7 | 0 | 无 CSI/ISP 同源模块；测试范围/比较覆盖不足，不能当完整 DDR 正确性证明 |
| 05_tpg_dsi_7cun | system_top | 18 | 0 | DSI 输出可供 06 保留；不包含相机接收、AWB、demosaic，不能把相机问题归于 05 |
| 06_csi_2_dsi_imx415_7cun | system_top | 66 | 0 | 必须迁移同源 ISP 修复；CSI/RAW/PHY 是接口替换，需重新集成 |

01 的仿真路径仍有作者机器绝对路径警告；04、05、06 的广泛时钟排除需要新设计审查。六目录没有在本轮重新烧录；本报告未穷尽所有输入和参数组合。

### 01–05 的独立问题

- 01：`uisrc/01_rtl/uart_top.v` 将 `uart_rvalid` 直接接 TX 请求，TX busy 未连接，没有队列。在原串口回环节拍中能工作，不证明多发送者、持续突发或时钟误差下不丢字节。复用为遥测时增加仲裁/FIFO，并在实际接受时刻更新索引。
- 02：本次没有发现来自 CSI/PHY/ISP 的同源影响。EEPROM 的写周期等待、ACK/NACK 与地址边界仍属该模块自己的验收范围。
- 03：`uisrc/03_ip/uart_tx_block.v` 从 index 0 发送后，在状态 3 使用 `tx_index < TX_BYTES` 决定继续。顶层配置 `TX_BYTES=10`，因此发送完 index 9 后还进入 index 10，访问 `[80 +: 8]`，超出 80 bit 输入。这是确定的 off-by-one 源码缺陷；原“看见时间字符串”的确认没有覆盖这个额外字节。本轮未修改它。
- 04：顶层 `TEST_MEM_SIZE=2*1024*1024*1024`，实际 x16/2Gb DDR 为 256MiB。`fdma_test.v` 仅寄存并比较读数据低 16 bit，错误为即时组合量而非粘滞计数。即使历史 `test_error=0`，也不证明其余 112 bit 或全部物理地址正确。需要独立副本的合法地址范围、全宽比较、累计错误与完成计数；本轮未修改它。
- 05：本次仅确认它不实例化上述 ISP/CSI 接收模块；DSI 的时序、屏初始化 ROM、PHY 与原引脚应随完整基线保留，不能由 PCIe 图像测试替代 DSI 测试。

## 原 06 的 CSI/RAW 问题与证据

下面的行号和相对路径均指原 06，根目录为 `E:/qianrufpga/fpga-lab/examples/06_csi_2_dsi_imx415_7cun/`。

| 位置 | 读取到的行为 | 影响与迁移要求 |
|---|---|---|
| `ui_csi_raw/ui_csi_unpacket_4lane.v:61` | 用 `I_hs_valid` 上升沿认包头；以高字节作为 Data ID | 它依赖原 encrypted aligner 的输出顺序和每包有效间隔。新 parser 的第一个协议字节在低位，不能只把新 parser 接在旧 wrapper 后面而省略字节顺序适配 |
| 同文件 `:91` | WC 右移 2，按整拍截断，未保留尾部实际有效字节数 | WC=2430 只计 607 个 4-byte word，不精确表达最后 2 bytes；RAW10 lookahead 仍可能消费无效下一拍。1920/WC2400 的整除场景没有暴露全部尾部问题，不能推广到1944/WC2430 |
| 同文件 `:119` | `S_data_en` 时输出输入数据，不检查这一拍 `I_hs_valid`；没有 ECC/CRC/VC 诊断 | 合法输入空拍不能直接当载荷。要按实际接受字节计数、只把 RAW10 有效载荷交给 unpack；CRC 仅作诊断不自动撤回已输出数据 |
| `ui_csi_raw/ui_raw10_unpacket_4lane.v:63` | 状态在任意 valid 低拍重置，且组装读取当前拍/下一拍两个字 | 没有 actual-byte-count/explicit-last 接口，不能处理任意载荷停顿或尾部 CRC 混拍。新 unpack 的 reservoir 与显式末组标记应成套迁移 |
| `ui_csi_raw/ui_image_correction.v:81` | 连续 10 拍无效后猜一行结束；宽度硬编码480个四像素组 | RAW10 的单拍 valid 洞通常不会触发，但10拍空洞、接收恢复或不同消隐会改变行号；这不是 CSI 包尾事实。新 crop 应由真实 TLAST 更新行号，保留 crop 原点语义并验证 Bayer 奇偶 |
| 同文件 `:65` 与 top `:376–413` | 有隐式 `I_raw_tready` 赋值，但顶层未接 correction ready/dest，ISP输入 ready也未接回；不能停止流水线 | 新矩阵末行 flush 会主动拉低 ready，若仍沿用这个顶层，数据会丢失。crop→BLC→demosaic→AWB→后处理→DDR 写入端必须完整连回 ready |

原 `hs_rx_wrapper.sv:79` 反向合并 lane 字节；原 RAW10 的内部高位 P0 最终在 `ui_raw10_unpacket_4lane.v:134–136` 再换序，所以**其最终低10bit同样是P0**。新 core 输出低10bit=P0，不能因为两个 packet handler 的字节布局不同而把像素再 reverse 一次。RAW8 窗口内部高字节=P0，RGB 输出低32bit=P0 `{0,R,G,B}` 是另外两个明确接口约定。

### PHY 不属于同一实现

原 06 使用 `al_ip/mipi_rx/mipi_dphy_rx_over_lvds_wrapper.v`、`data_lane_rx_wrapper.enc.v`、`channel_aligner_wrapper.enc.sv`，器件字符串为 `"PH1"`，ADC 的四条数据 lane 使用固定 `INDEL=20`。PCIe 修复副本是 `mipi_csi_rx`/`csi_rx_phy`，器件字符串为 `"PH1A"`，用动态延迟扫描、Gray 时钟存在检测和 HS 域同步复位释放。原 06 没有本次修过的 `auto_delay_ctl.v`、`csi_rx_clock_det.v`，不能说其加密 PHY 已证明同样存在64tap wrap或旧1.67us丢时钟问题。

替换整个 receiver 时才能复用新 PH1A 的32物理tap选择、手动31→0、全PASS不wrap、parser与校准反馈独立、新FS才放行等行为。原 ADC `INDEL=20` 与新动态 IDELAY 的资源/属性兼容性必须在独立副本用 TD 实现报告确认，不能盲保留或盲删。保留 E13/C14/D14/A15/G17、LVDS18 等实物接线事实，核对差分负端专用配对，不复制 PCIe 顶层的端口名覆盖旧 DSI/DDR 引脚。

## 同源 ISP 文件迁移对照

目标原路径相对 `06/uisrc/03_ip/ui_isp/`；修复来源相对 `projects/pcie_imx415_fix_20261003/fpga/uisrc/03_ip/ui_isp/`。依据包含源码和 [ISP 审查记录](isp_review.md)，不是依据文件名推断全部相同。

| 原 06 目标 | 修复来源 | 迁移内容/接口差异 |
|---|---|---|
| `ui_BLC/ui_BLC.v` | `ui_BLC.v` | 保存 dest，增加真正 elastic CE，端口维持；须把 ready 接回 crop |
| `ui_demosaic/ui_top_demosaic.v` | `ui_top_demosaic.v` | 原 `IMG_WIDTH/IMG_HEIGHT` module parameters 改为 `I_img_width/I_img_height[12:0]`；06固定模式可接13'd1920/1080，不能保留旧不存在的参数例化 |
| `ui_demosaic/ui_raw_matrix_3x3_buffer.v` | `ui_raw_matrix_3x3_buffer.v` | 以接受拍组织邻域，valid洞不清窗口、SOF同拍、边界mirror-101、真实末行flush；尺寸改为输入端口；flush时ready拉低 |
| `ui_demosaic/ui_bilinear_interpolation.v` | `ui_bilinear_interpolation.v` | 四Bayer模式统一中心行奇偶与CE流水线；不能靠试改Bayer参数掩盖坐标或lane错误 |
| `ui_demosaic/ui_zhenghe.v` | `ui_zhenghe.v` | 取消首行时钟跨度猜长度，成为兼容标记延迟；新矩阵不再例化它；尺寸接口有变化，不可用旧例化直接替换 |
| `ui_demosaic/ui_line_buffer_demosaic.v` | `ui_line_buffer_demosaic.v` | 改为真实接受拍、同址read-before-write、SOF地址0；新矩阵不再使用该辅助模块；旧compat接口有运行时宽度差异，逐项核对 |
| `ui_demosaic/ui_ram_demosaic/ui_ram_demosaic.v` | `ui_ram_demosaic/ui_ram_demosaic.v` | 新矩阵实际例化源文件内的 `ui_ram_demosaic_eram_infer` 两次，每次2048×32，带同步读CE。原06 wrapper仅提供33bit `PH1_LOGIC_ERAM`，不含这个helper；必须带完整修复来源文件，不能只复制matrix或重新生成旧IPC覆盖helper |
| `ui_awb/ui_awb.v` | `ui_awb/ui_awb.v` | 原每个divider done直接改变四路增益；新整帧统计、pending增益、仅新SOF切换、限制gain并elastic。新增 `I_img_width/I_img_height` 输入；原divider_gate.v字节完全相同，module `divider` 接口可保留 |
| `ui_image_cut/ui_image_cut.v` | 同相对路径 | 新增运行时宽高，坐标/掩码/标记以同一接受拍更新，ready真正保存输出；SKIP_COLS仍是四像素组单位 |
| `ui_gamma/ui_gamma.v` | 同相对路径 | pipeline CE；Gamma0.8负数钳0，避免黑变白；本次所有LUT表与原06逐字节相同 |
| `ui_contrast_adj/ui_contrast_adj.v` | 同相对路径 | pipeline CE；signed差/乘积/钳位，修复奇数系数符号边界，当前140行为有黄金回归 |
| brightness、saturation文件 | 同相对路径 | 数据与所有标记统一CE停顿，当前参数算法保留 |
| `ui_data128_96.v` / `ui_data96_128.v` | 同相对路径 | 两文件与原06逐字节相同，可以保留；拆/加每像素padding，不变通道或像素顺序 |
| `ui_demosaic/ui_mipi_to_raw_converter.v` | `ui_mipi_to_raw_converter.v` | 两文件逐字节相同，确认低10bit=P0→RAW8高字节=P0；新矩阵在自身输入组装RAW8，不再依赖此模块，不能把它多接一级造成重复转换 |

新AWB不再依赖旧50-cycle信号delay RAM对齐像素；原06可保留旧IP文件作为资料，但从新活动pipeline退役，避免不必要RAM和重复模块。旧兼容RAM、zhenghe模块保留源并不表示仍实例化。实际资源以新TD层级/ERAM报告为准。

## 独立 06 副本的最小完整迁移方案

这是下一步实施清单，本轮未创建或生成该工程。

1. 用正式06完整clone保留 DDR/FDMA、DSI TX、屏ROM、PLL、原ADC、版权与依赖。保留原目录的历史成功，不在原 examples 内打补丁。
2. 带入已修完整 `mipi_csi_2/` receiver依赖；改 top 的旧 wrapper→CSI解包→RAW解包段为 `mipi_csi_rx #(.MIPI_LAN(4),.DEVICE("PH1A"))`。删除/退役旧活动 `rx_clk_gen.v` 注册，或有明确改名适配，因为新旧都定义 `rx_clk_gen`；不能留两个同名模块给TD任意选择。
3. 顶层旧CSI接口绑定新端口：`I_clk_hs_p→I_clk_hs_rx_p`，四正端数据→`I_hs_data_p`；`I_reset_n` 为明确源域复位，`I_enable` 在PLL/配置可用后放行；debug_button未用时接高。新PHY无需旧LP输入端口，板上连接仍保留，不可把其球号另作输出。`I_ref_clock` 从已有稳定PLL输出选择并核对实际频率和presence时间单位，不能把旧 `S_clk_70m` 名字当70MHz或把PCIe的150MHz当06已有事实。
4. 将 `m_axis_video_aclk/aresetn` 接到选定ISP视频域及该域同步释放复位。这样PHY HS域与ISP/DDR前端由真实sfifo CDC隔离；`O_hs_div_clk` 只作为HS观测/诊断域，不能在frame内直接跨域读取计数。40bit RAW、真实TLAST、首接受组TUSER和ready送给新crop。
5. 替换旧猜行的 `ui_image_correction` 为修复副本 `image_correction.v`。显式接 `I_v_start/I_v_end/I_h_end`，输入dest接10'd0，所有输出dest/ready连通。新crop采用排除边界（y>start、y<end、x>0、x<h_end），不能把旧top的480组/1080行常数随意照搬：须确认真实RAW1944/3888宽高、有效区原点和每行组数，再使输出恰有1920×1080或目标尺寸。Bayer依据实际选中原点奇偶确认。
6. 更新 `ui_isp_top` 封装，统一接固定或运行时宽高给 demosaic、AWB、cut；带完整新RAM helper及上述修复文件。完整反向ready链：DDR/dbuf写入口→saturation→brightness→contrast→gamma→cut→AWB→demosaic→BLC→crop→receiver。不能沿用旧 `.I_tready()`、未驱动 `O_raw_tready` 的top。
7. 保留原 128bit RGB→DDR/dbuf写入、三缓冲、DSI 1024×600读出链与画面格式。确认 dbuf ready的真实意义并接入或设置明确缓冲/丢帧政策。1920×1080四像素组一行480组，FDMA写stride/size仍按封装单位核对，屏读区域不等于自动全幅缩放。不要把PCIe的紧密RGB字节packer直接插入DDR的每像素32bit布局。
8. 新CSI六计数及错误脉冲若用UART/ChipWatcher读取，采用HS→观测域握手快照。CRC完成前载荷已进入ISP；只统计CRC并不会自动保证错误帧不显示。有限FIFO下连续无背压摄像头仍可能溢出，应有丢弃/恢复和可见计数。
9. 更新 `.al` 实际source、唯一top和约束层级，保留完整IP数据，排除重复module。重新审查06 PLL IPC/生成参数/SDC命名不一致和广泛exclusive组；新MIPI时钟及派生关系按实际lane速率与TD报告约束，不填假数值。

可保持的验证资产是数字模块黄金TB及其证据，**不能保留旧06的“已通过”状态作为迁移后工程认证**。新core的RTL/时序约束更换后，ADC定位和电气采样均需新TD/实机结果。

## 必须带走的验证资产与未验证项

- CSI协议：`tb/csi_integrity.do`、`tb/csi_calibration.do`、`tb/csi_capture_gate.do` 与对应 evidence，覆盖实际WC尾部/CRC、RAW组序、FIFO背压、32tap/64tap边界和新FS放行。协议TB保留厂商FIFO/RAM/Gray RTL；calibration/gate对PHY电气块用行为壳。它们没有证明原06加密PHY或真实D-PHY信号质量。
- ISP：`tb/run_isp_golden.do`、`run_isp_interfaces.do`、`run_isp_elastic.do`、`run_isp_parameters.do`，对应 [ISP记录](isp_review.md)。黄金包含四Bayer、首末像素/行、valid洞、背靠背帧、末行flush与背压；不能省略新RAM helper/前端弹性连接后直接宣称移植仿真通过。
- 新06整链TB仍需证明：sensor packet→crop真实尺寸/原点→RGB四像素→dbuf/FDMA地址/stride→DSI像素与标记。TD要证明活动helper落ERAM、时钟覆盖、reset/CDC和setup/hold；实机要证明连续画面、错误计数、重新上电/重新校准/停止恢复。
- 当前PCIe工程的双向DMA图像完整性证据属于该项目，不能代替DSI显示验收。01–05各自UART/EEPROM/RTC/DDR/屏的测试也不能省略。

## 可进入 skill 的事实建议

建议在 `references/modules.md` 的06条目和 `references/engineering-rules.md` 图像规则引用本报告/后续迁移工程，并使用以下明确表述：

1. “历史06能够显示画面，但CSI解析仅WC>>2整拍、无CRC/ECC；裁切猜valid空洞行界；ISP在valid洞、SOF/末行及ready停顿下存在已识别同源缺陷。新项目不得无检查复用这些链路。”
2. “原06PHY为PH1加密wrapper，新修复PHY为PH1A动态32tap实现，不能同名文件直接替换；迁移receiver需完整source集合、字节序、reset、CDC、constraint和rx_clk_gen去重。”
3. “RAW低10bit=P0，RAW8内部高字节=P0，RGB低32bit=P0 {0,R,G,B}。按坐标黄金验证，禁止凭画面试reverse或盲改Bayer。”
4. “新矩阵末行flush会施加背压，crop/BLC/AWB/后处理和DDR入口必须完整连接ready，有限FIFO溢出需可见；不能只更换插值文件。”
5. “保留 original examples；缺陷补丁进入独立维护基线/修复副本。接口迁移、模块仿真、TD实现和新位流实机分别记录，不写‘原六已全面修好’。”
6. “RTC uart_tx_block的TX_BYTES边界/读完成后报告、DDR低16bit比较/测试范围是独立缺陷；已在03/04独立修复clone数字验证，不能因为PCIe/ISP已修而省略，也不能把数字结果当新位流实机通过。”

以上为原只读审查时的迁移建议；后续已授权实施独立03/04/06修复。原六基线未修改，当前状态以以下更新及各自报告为准。

## 审查后的03/04独立修复（2026-10-04）

正式skill baseline verify六项missing/added/changed全为空；独立clone位于 `E:/qianrufpga/fpga-lab/projects/demo_repair_20261004/`。原六例程没有原地补丁。

- [03 RTC验证报告](../../demo_repair_20261004/03_iic_rtc/reports/validation.md)：修TX_BYTES多发1字节/索引宽度/消息快照；RTC先观察读busy再等待完成后保存数据并报告。真实UART数字解码54字节和RTC事务模型两次报告20字节全部自检PASS，ModelSim exit0、0 errors/0 warnings。没有把I2C事务壳当物理SCL/SDA验证。
- [04 DDR验证报告](../../demo_repair_20261004/04_ddr3_axi_fdma_test/reports/validation.md)：手册PDF第12页为FPGA侧单片256MB/x16、实际IPC 2Gb/x16，真实IP地址28bit；修top旧30bit和2GiB范围，测试256MiB、全128bit带lane/address模式、粘滞错误/计数、最后完整burst后wrap。12burst/4轮、bit0/15/16/63/127五次故障、非整burst/offset/复位/非法容量自检PASS。事务driver未例化真实FDMA/DDR控制器和PHY，不能宣称真实256MiB读写已验证。

03/04保留真实引脚/IP/CWC与managed/direct入口；已分别实际TD生成新bit。03最新source staging+真实ADC/SDC+SCL divide252版实际先揭露hold -2.770ns，启用显式物理fix_hold high后全新重编通过setup+32.845ns/hold+.036ns、STNS/HTNS=0；产物03/reports/direct_build_20261005_045937_38024/、日志demo_repair_20261004/evidence/demo03_scl_high_hold_20261005.log，未删除SCL约束或虚假cut。04setup+.745/hold+.020。均未新上板。04原DDR级联/localclock warnings与原baseline完全同类，未伪清约束；源/约束和验收状态见各自validation.md。


## 06独立修复实施更新（2026-10-05）

[06迁移与验证报告](../../demo_repair_20261004/06_csi_2_dsi_imx415_7cun/reports/validation.md) 为最新已落盘实现。保留原PH1加密PHY及INDEL20 ADC，字节SHA一致，**没有采用上文整套替换PH1A PHY的候选方案**。旧PHY高字节协议顺序由显式adapter调整，精确WC/CRC/ECC/RAW10末组TLAST、Gray/FIFO稳定域、crop接受拍、完整ISP及真实DBUF背压已成套迁移，DDR地址28bit修正。

三个实际ModelSim自检均exit0：frontend包含WC30尾2字节/CRC混拍、洞、1周期包间空隙、crop、GrayCDC/停顿及CRC/ECC计数；完整ISP wrapper保留原divider_gate和官方primitive/glbl，两16×3帧24个四像素组黑/白及标记精确；DBUF保留真实异步FIFO/RAM，48完整128bit字/6burst精确、almost-full背压85周期，首SOF不丢。测试范围未包含DDR/DSI/MIPI电气PHY，不能写成新整机仿真或实物通过。

SDC纠正C0/C1名称（实际C0=75MHz，C1=25MHz），补I2C divide250，PLL相关域继续计时；仅独立PLL/DDR/CSI家族异步。CSI445.5MHz输入是目标891Mbps约束而不是相机实测。模板最新schema2把注册源/IP目录及ROM完整stage到独立新目录，所有TD阶段cwd一致；03/06实际Tcl staging smoke通过，尚未证明最新06完整TD/上板。

CRC尾部诊断不能撤回已输出坏行；有限FIFO不能无限背压。实际WC/行数/Bayer/MCLK、固定INDEL窗口、ERAM落点、完整时钟/IO约束、DSI连续画面和错误计数仍是待验收事项。原六verify再次执行missing/added/changed均为空，没有用历史原bit冒充修复bit。
