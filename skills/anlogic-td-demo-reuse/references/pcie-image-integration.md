# RK3576 / PH1A90 PCIe 图像集成

更新提示：以下版本表主要是至07阶段的历史记录。09完整STA已通过但BAR前置实测失败，10读地址候选未完成完整TD/板测；接收相关任务同时读取 [CSI时钟与BAR接收前置](csi-clock-bar-receive.md)。不得把旧句“待构建”或历史板测当最新状态。

用于此板的 PCIe 工程、CSI/ISP/RGB 排错与双向图像验收。六个 examples 的历史成功不覆盖本链路。记录更新至2026-10-05：build04短采集的长度正常但真实颜色失败，首次真实1080p采集也失败；FPGA5完成route后时序为负且未产出新bit，FPGA6构建为纠正裁切而中止。驱动06/07已实际加载并各过8项负测，但07+04bit的20轮计划在第2轮1080p失败。FPGA7裁切修正及27MHz/runtime Bayer/连续PH1采样仍是待验收候选。必须按各自日志、源/bit/模块hash分开验收，不能称为全部修复或把旧实测转给新候选。

## 区分历史结果与本轮候选

| 版本/证据 | 已证明 | 不可外推 |
|---|---|---|
| 旧 build03 相机实测 | 1000 帧长度/序号正常仍有3紫、2绿可疑；1500帧有17紫、3绿可疑，异常原图已检查。已有AWB帧锁后仍失败。 | 满长度、STA或AWB单项修复不能证明颜色正确；不可交付为相机修复版。 |
| 旧位流完整 RGB 回环 | 20/50 帧逐字节零差异，证明当时所测 bit/驱动的 H2C→FPGA→C2H 字节传输。 | 不证明相机 CSI/ISP 颜色，也不认证本轮新候选。 |
| build04 + 驱动05 | 同源checkpoint补high-hold后Setup +0.253ns、Hold +0.020ns、TNS=0，压缩bit下载；两轮各120帧720p长度/序号正确，有效采集期间RAW最高128664包、CRC/ECC/WC/timeout/overflow均0；约26.669fps。 | 用户确认实体橙色卡在`quick04_scene_last.png`显示绿色，**颜色明确失败**；另一轮一首帧20.8%紫。颜色筛查为0也不证明真色。STREAMOFF十秒后仍有poll timeout，驱动05非最终版。 |
| FPGA5实际route | 源含27MHz/startup/metadata CDC/快速计数；最终Setup −1.960ns、TNS −7.222ns、Hold +0.020ns。四条负路径均为byte域reset→HS IDDR异步reset recovery。 | 未通过STA；随后`report_mtbf -cdc_sink_pin`发生native crash，未产出新bit，**不是可交付版本**；CRC/header/payload并非该报告的负路径。 |
| FPGA6/7候选 | 06版本0x56440601含D8/DC帧锁Bayer与PH1连续采样；全TD在gate阶段被主动中止，保留`build06_direct_staged.log`。07修1080p首行16、末行1095；720p不变；完整CSI包尺寸边界数字已通过，见crop_height07。 | 06无最终route/bit；07新fullTD/bit与物理验收仍待完成。真实GBRG、PLLlock/输出频率、物理校准、正确颜色和新双向图像均待验证。 |
| 驱动06/07 + build04实机 | 两版实际加载后负测各8/8；07在RK编译/加载RC0。07循环cycle0取得8帧720p。 | cycle1真实1080p为0/8帧，报6197776+16字节短包、792次拒收；这是已证实的裁切边界错误，不只是假设模式切换问题。停止RUN0/BUSY0及CMA回收不等于整个20轮通过。 |
| CMA64 boot 历史验证 | 已读回并重启确认，kernel 不变；补丁工具另做离线审计。 | boot 成功不证明图像路径；内容 hash 不等于 RSA 签名验证。 |

## 先确认板级资源

- RK3576 的 PCIe1、SATA1、USB OTG1 在总线层互斥，**连 OTG1 的 USB2 也不能保留**。只关闭 SuperSpeed、修改 comboPHY 或 `maximum-speed="high-speed"` 无法让 USB1 与 PCIe1 共存。依据：[Rockchip RK3576 USB 开发指南](https://docs.bit-brick.com/pdf/rk/usb/Rockchip_RK3576_Developer_Guide_USB_CN.pdf)，USB 控制器章节。
- 此 AFC03 底板的 AIC Wi-Fi/蓝牙和 USB-A 外设经 USB1 hub，启用 PCIe1 后会消失。独立 USB OTG0 Type-C 不受此互斥影响；仍要结合实际接线与角色验证。需要网络时改用独立通路，不能承诺修改 boot.img 恢复同一 hub。
- 失去 Wi-Fi 前保留 RK 调试串口或独立网口。RK 调试串口和 FPGA AL-LINK 是不同设备。本次 RK J3/CH9102F 为 1500000 baud；COM 号随电脑变化，不能写死。
- boot.img 补丁必须基于该板原镜像：先备份并哈希，核对 FIT/FDT/resource 中的所有 DTB 副本，更新相应 SHA1/SHA256，确认 kernel/logo 内容不变，刷写后做分区哈希和重启实测。本机试验项目中的 `boot_pcie_usb2.img` 是失败历史，不能复用。补丁拒绝源目标同一路径，验证外置 payload 边界及与 FIT metadata 的重叠。
- 当前 FIT signature 节点虽有 algo/key 等属性却没有非空 `value`，只做过内容 hash 验证。遇到实际非空签名值，拒绝仅改 hash，转入具备密钥的完整签名流程；不能把未填值模板称为 RSA 验证通过。
- 本次板上原默认 CMA 仅 16 MiB，1080p RGB24 多缓冲分配失败；64 MiB CMA 镜像已读回并重启确认。4 个 1080p 缓冲至少需 24,883,200 字节，另有其他 CMA 消耗；按实际负载预算。

## 独立开发副本

2026-10-03 排错项目：`E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003`。保留厂商材料和原examples，修改在`fpga/`副本。先读`reports/validation.md`、`isp_review.md`、`boot_driver_audit.md`、`poll_cancel_review.md`、`driver06_independent_review.md`、`driver_probe_error07.md`、`camera_clock_startup_digital.md`、`csi_snapshot_reset5.md`及`tools/csi_integrity_notes.md`中与任务相关的项，核对源hash、最终构建阶段和实测版本。中间报告的“尚未TD”可能早于实际新日志；不能只看陈旧文字或进程退出码。脚本用于复现冻结版，进一步集成后不能无比较重跑覆盖新修改。

**复用修复模块选择维护副本，原example只保留历史基线。** 不原地改六份原例程，不更新baseline manifest来掩盖差异；也不能只把同名文件搬入旧06后继承它的通过标签。

| 修复副本（根：`E:/qianrufpga/fpga-lab/projects/demo_repair_20261004/`） | 当前证据 | 仍须验证 |
|---|---|---|
| `03_iic_rtc` | UART长度/消息快照、RTC读完成后报告；54字节UART+20字节RTC数字自检。最新source staging+真实ADC/SDC+SCL divide252版实际完整TD exit0，Setup +32.845ns/Hold +0.036ns，STNS/HTNS0，bit在`reports/direct_build_20261005_045937_38024/`，repair上级证据`evidence/demo03_scl_high_hold_20261005.log`。真实SCL曾揭露hold -2.770ns，显式物理fix_hold high修复，没有删约束。旧+34.345/+0.150版仅保留历史。 | 新bit实际串口/I²C/RTC走时；数字I²C事务壳不证明电气接口，36ps hold裕量只属于当前约束下实现。 |
| `04_ddr3_axi_fdma_test` | 28bit字节地址、256MiB边界、全128bit checker/粘滞计数；12burst/4轮/5故障自检。实际TD retry bitgen，Setup +0.745ns/Hold +0.020ns，bit在`reports/direct_build_20261004_235718_32084/`，证据`evidence/demo04_ddr_actual_retry.log`。 | 新bit真实DDR校准、完整一轮256MiB/高地址/复位；事务模型没例化真实FDMA/DDR PHY。 |
| `06_csi_2_dsi_imx415_7cun` | 独立迁移副本及`migration_applied.json`；`evidence/frontend.log`验证旧高字节PHY适配/WC尾部/洞/裁切/CDC/stall（0error/0warning），`isp_wrapper.log`验证完整ISP两16×3帧/24beat/标记/黑白/背压；实际异步FIFO/RAM的DBUF自检48个128bit字、6burst逐字相同、85周期almost-full背压、0丢失/重复（保留13条厂商未用端口警告）。 | 尚无新TD/新bit/CSI→DDR→DSI实机认证；保留06自身加密PH1 PHY和INDEL20，不能拿PCIe的32tap PHY测试替代。 |

03/04 TD均记录`CDC_NOT_REPORTED`，不把bitgen或正WNS写成CDC/MTBF通过。各副本`reports/validation.md`、PCIe项目`reports/demo_reuse_impact.md`与新日志一起读。06有完整接收/ISP/ready/DDR布局适配，PCIe紧密RGB24 packer不能直接代替06每像素32bit的DDR布局。

完整依赖包含 SGDMA 加密核、PCIe PHY/bridge、PLL、CSI PHY/自动延迟、RAW10 解包与 ISP、FIFO、打包/门控/帧补齐、ADC/SDC，以及 `deploy/sgdma_drv`、`deploy/v4l2_drv`。不能只复制 top.v 或 `.ipc`。原文件混有 GB18030 与 UTF-8，修改时保留原字节或使用确认后的编码，保留厂商版权声明。

## CSI、RAW10 与校准候选

- **WC 是线上负载字节数，不是裁切后宽度。** 此 IMX415 的 1944/3888 像素对应 RAW10 WC2430/4860，最后载荷2字节与CRC2字节可共用一个32bit beat。旧按四字节向上取整会把 CRC/padding 当像素；输出1920/1280不意味着输入 WC2400/1600。
- 候选 `csi_rx_packet_handler` 显式输出 `O_payload_bytes=1..4`、`O_payload_last`，独立消费两字节 CRC，覆盖共拍/跨拍。CRC16 初值FFFF、LSB-first、反射多项式8408、无 final xor；只将目标VC的 RAW10 DT=0x2B 送图像，其他长包按协议消费。非零且为5倍数的 WC 检查只证明 RAW10 编组，不证明整帧宽高。
- 每五字节解出 P0..P3：byte0..3 各为像素高八位，byte4 bit1:0 是 P0 低两位并依次递增。总线 `[9:0]=P0`、`[19:10]=P1`、`[29:20]=P2`、`[39:30]=P3`。候选解包输出**显式 RAW TLAST**；valid 空洞不是行末，不能用下降沿猜 EOL、无 golden 翻转像素顺序或 Bayer。
- `vid2stream` 的 valid 不等 ready 才出现，FS pending 保持到第一组真正写入 FIFO。该 vendor FIFO 可用8191个四像素组；满时拒绝并精确计数。物理 CSI 无法无限暂停，弹性接口不等于无限缓存；审查实际最大停顿和溢出恢复。
- PH1A `PH1_LOGIC_DYNAMIC_IDELAY.WIDTH=5` 只有**32个物理tap**，扫描0..31、无窗 fallback16。旧0..63重复扫描，fallback32实际是tap0。其他64tap器件支持独立保留；窗长用7bit防64全通过回绕，6bit debug对64饱和为63。手动继承自动tap、31后回0；done仅表示流程结束，`best_len=0` fallback不是采样眼合格。
- 扫描计入最后样本；等待16777216为真实2^24个**字节时钟**周期，旧wait_cnt[23]只有2^23。不要拿150MHz presence参考换算字节域等待。
- 校准时 parser继续运行，保留 packet_done/sync_wait 对 byte_align 的反馈；禁用parser会让sync_wait常1并周期性清valid，污染校准。图像/计数另 gate：同步校准done后还要等**新FS**，done在帧中出现不能放行余帧冒充完整帧。
- 候选 clockdet 在源域**注册Gray**再两级同步；组合binary→Gray在进位时可能多位毛刺，异步时钟电平采样也不能证明活动。150MHz参考当前 LOSS_CYCLES=15000000（100ms）容忍行/帧消隐，确认活动后释放；换参考/传感器须重算阈值并检查有限位计数的采样条件。HS域复位异步断言、同步释放，不让短blank清RAW/Bayer状态。
- CSI计数在字节域产生，用整组握手快照跨域，不把每位2FF当原子读取。记录 RAW-good/CRC/ECC/WC-shape/timeout/FIFO overflow；timeout为包中64个连续无输入解析周期，overflow单位是拒绝的四像素组。
- **CRC目前是流式诊断**：尾部判错前像素已进入ISP，不能声称自动撤回坏帧。若需提交前保证，另评估双行校验缓存：1944/3888像素约4860/9720字节；ERAM、吞吐和错误帧行为须实际验证。不能隐藏错误或丢弃来宣称修复。

- FPGA5快速计数候选把协议判定事件先寄存、下一拍更新32bit计数，**事件时捕获I_count_enable资格**，不能下一拍再用live gate丢事件/重计。payload、CRC、FS/packet_done协议时序保持；计数可见晚一拍。`tools/csi_packet_fast.do`的3731组完整协议回归及451拍event/gate/reset等价自检通过（保留FIFO3warnings）；这不是Fmax或新bit采样质量证明。

数字证据：`tb/csi_integrity.do`（3731组golden、4SOF/12TLAST、WC2430/4860/2400/1600、短行/错误注入/洞/异步读与反压、9000写中8191留存/809丢弃、复位恢复）；`tb/csi_calibration.do`（32tap窗/端点/全失败、64tap全通过、手动/复位）；`tb/csi_capture_gate.do`（实际align/parser/unpack/FIFO，新FS gate）。保留 vendor FIFO 的3条未连接RAM端口警告及解释。测试不覆盖真实pad delay、IDDR、PLL相位或信号完整性。

## IMX415 MCLK、启动与诊断候选

- build04 top由UI24MHz触发器翻转输出12MHz，当前binning表有效INCK字段匹配**27MHz/891Mbps**族；24MHz有不同寄存器族，不能只凭“传感器支持24M”继续沿用27M表。[Linux主线IMX415](https://github.com/torvalds/linux/blob/master/drivers/media/i2c/imx415.c)
- build04有效HS诊断约4,950,010边沿/100ms=49.5001MHz字节钟，配26.669fps，与12/27缩放相符；这是源码与实测互证，VID005/CAM002最后MCLK选择段仍缺本地原理图，必须测实际sensor INCK，不能凭FMC A18/H7段证明完整子卡连线。
- FPGA5手动`cam_pll27.v`：FIN25、REF1、FB1、C0DIV54经BUFG反馈25MHz、C1DIV50输出27MHz，PFD25/VCO1350在DS900官方范围内。GMC/ICP/CAP/RES=1/11/2/3来自本地PFD25生成样本；INTPI1从VCO1200样本推断到1350，**非新wizard生成、非1350模拟参数已认证**。独立elaborate只证明接口/数值导入，最终PLLlock、输出频率/脉冲和CSI须板测。原UI150/24保持，I²C仍24MHz。
- `update_pll_param`探针对不变官方UI_PLL的FB3也报`[1,2,4]`、unity报`DPLL_FEED_TYPE`缺失；它在该PH1调用不适用。UG910允许REF/FB1..128；不能把探针错误当器件合法集合、添加假DPLL参数或冒充模拟参数重算。配置/原始日志在`tools/cam27_ip_trial/README.md`。
- `camera_clock_startup.v`用24MHz稳定控制钟、局部复位同步及锁稳定资格：XCLR低≥10µs，XCLR高≥2µs再请求MCLK，同频27MHz由下降沿锁存gate转发，确认ACK稳定后再等待≥50µs才释放cfg。失锁/全局reset重新清除并初始化；电源有效必须由实际硬件满足，lock不能证明电源。禁止把27MHzposedge翻转成13.5MHz或直接`clk & raw_lock`门控。数字自检五次启动/窄lock/失锁/停控制钟/无源钟通过，不能替代引脚占空比/模拟PLL验证。[Sony IMX415数据手册](https://dl.khadas.com/products/add-ons/cameras/imx415/datasheet/imx415-datasheet.pdf)
- `cam_clock27_monitor.v`源域注册Gray、3级目的同步，25MHz基准每10ms期望270000边沿±544；同时核对lock/window valid。29窗口数字测频覆盖27/12MHz、失锁、停钟/恢复。它测内部源钟，不能证明MCLK输出引脚或sensor实际采用它。
- `csi_stats_snapshot.v`可复用到HS→user CSI计数、UI24→user `{ae_write_cnt,bus_error}`、user→UART25 framecount。`src_stats`必须属于源域，整组held数据保持到ACK同步后采样；request/ack各2FF；共享复位断言，但源/目的各自**3FF异步断言、同步释放**，停源复位后只能等源恢复ACK，不伪造新快照。status为sequence+busy，首个post-reset clock_delta=0；源停时保留最后已完成快照并busy，100ms PERIOD不等于停源仍100ms更新。
- 只给多位数据各位2FF或共享raw reset直接释放都不满足上项。实际helper原TB及新增短pulse/在途三阶段/源与目的停钟/恢复/精确bundle与delta自检通过，共53快照，两真实近似clock比，0errors/0warnings；证据`evidence/csi_snapshot_actual5.log`、`csi_snapshot_reset5.log`。数字仿真不模拟亚稳态，reset须满足器件最小脉宽；held-bus路由及Gray skew/CDC时序约束另审查。
- 27MHz/891Mbps族应核对HS445.5MHz、byte111.375MHz；不用旧400/100MHz标称签核新频率。FPGA5源清单`evidence/build05_sources.json`；初次`build05_direct.log`因`al_ip\al_pcie_ip.txt`相对ROM路径在elaborate失败，完整staging重跑见`evidence/build05_direct_staged.log`。实际route报告`evidence/direct_build_20261005_002919_8820/final_timing.rpt`覆盖99.96%，WNS −1.960ns/TNS −7.222ns/Hold +0.020ns；四条负recovery分别为−1.960/−1.881/−1.707/−1.674ns，均byte域`hs_reset_sync_reg[1]`到四个HS IDDR reset，最差一层反相器、fanout653、skew1.978ns。byte自身setup +1.438ns，user setup +0.382ns；**不得为消负数false-path这两个有4:1关系的域，也不能误称CRC路径失败而随意加流水**。报告周期2.244/8.976ns的SDC舍入不可能消除1.960ns。未覆盖项仍另审查。
- `tools/csi_fast6/README.md`候选只在PH1A原生IDDRx2关闭`ASYNCRST`并将rst接0，持续采样；PH2不改，byte域协议/对齐/校准/新FS gate仍正常reset。UG910及实际PH1 primitive库证明DISABLE表示忽略rst，不是同步reset；该IDDR只有采样/反序列寄存，无内部除频/相位计数。实际TD primitive + 四串行lane/byte-align自检3828拍（2964非零）、844个有效lane-byte，12次不同相位reset、5次停钟恢复，0error/0warning；无额外RAM/延迟。初始/非有效窗口不承诺输出清零，旧未qualified align数据差异日志保留。仿真停钟保持相位，不代表真实LP/HS转换；新TD须确认reset常量与相关时序消除，新bit仍须物理采样/CRC/完整图及复位恢复验收。root已纳入06，后因裁切问题主动停06构建准备07，不能把数字PASS写成新STA/上板PASS。

**原生MapIO警告不能用功能等价豁免。** 实际07在`build07_direct_staged.log:1595`至1598对四个PH1 IDDR报SYN-6024 CRITICAL-WARNING：reset常量/缺失或ASYNCRST DISABLE可能使各PAD接收不同步。07 STA +0.534/+0.021ns不能解除此警告；`rk_serial.log:15443/15448`实测MCLK约27MHz、HS byte约111.375MHz但best_window=0、RAW包0，因此07相机失败。`tb_sampler_reset.sv`由单一phase计数产生理想4:2:1钟，停钟保持phase且比较排除复位后前8byte，未例化真实LCLK启动/LP-HS/PADskew；功能模型无自由计数器不等于原生PAD同步规则不存在。数字PASS只保留其原范围，不能用来跳过SYN-6024或称物理同步已证明。详见[原生警告07审查](../../../projects/pcie_imx415_fix_20261003/reports/csi_native_warning07.md)。等待08新的冻结源/bit、reset映射、相关recovery/setup/hold及实机眼窗/RAW/连续原色证据；新双向FIFO通过亦不能代替CSI PHY认证。

## ISP、Bayer 与 RGB 候选

1. 明确接口中 RGB/BGR 字节顺序、4 像素并行格式、字节填充、TLAST 是行末还是帧末、TUSER 是帧起点。当前矩阵内部 RAW 字节高位为P0，RGB128低32bit为P0、每像素 `{0,R,G,B}`，再P1/P2/P3；去每像素填充后按主机约定紧密RGB24。不要把内部RAW高位顺序与输出RGB低位顺序混为一谈。
2. 最后数据 beat 携带 EOF，不能额外发零 beat，也不能等下一帧 SOF 才判断上一帧 EOF。720p 和 1080p 的本实现无行填充，期望帧长分别为 2,764,800 / 6,220,800 字节；其他宽度重新核算，不能照抄。
3. **按 `valid && ready` 接受拍推进坐标、统计和标记**，不按时钟跨度/延迟valid配原始SOF。裁切支持有效洞、SOF先于像素、背靠背帧；只在有效TLAST更新行。裁切原点或区域改变须核对Bayer奇偶。每级 `valid && !ready` 保持数据/SOF/TLAST/tdest。
4. 旧zhenghe猜行长，旧矩阵有效洞清邻域、SOF早于valid_d1复位、首组右邻错误、末组/末行未排空。候选矩阵两个2048×32行bank按接受行奇偶写，复用 `ui_ram_demosaic_eram_infer` 的SDP/read-before-write/读CE，不改vendor IP；当前行覆盖y−2 bank前同步读取。**不要将RAM读寄存放进带异步reset的大状态块，或用第二次组合RAM读搬运上一行**：TD曾将该推断全部映为distributed RAM，需在综合日志确认两bank实际ERAM，不能只凭 `ram_style` 宣称资源。zhenghe兼容寄存延迟不再猜节拍，矩阵不依赖它。
5. 矩阵输出实际center_y奇偶，四种Bayer统一；一组右邻前看，mirror101边缘保持奇偶。帧末主动读RAM **flush真正最后行** 后才能接新帧；720/1080约320/480次RAM读，125MHz约2.56/3.84μs加流水。排空期间ready拉低，上游须弹性保持，不依赖下一帧或“IMX消隐应该够”。存储逻辑需求131072bit，build04两bank已确认8 ERAM；后续新集成仍查实际映射/块数，不能只继承标签。像素/center_y/标记与显式扩位求和同使能对齐。宽高寄存器异步复位为常量0、第一接受SOF装载尺寸；不能在异步reset分支装载变化的输入宽高，TD会报异步set/reset实现不确定。
6. BLC保持四RAW黑电平减法/负数钳0，修tdest未驱动；image_cut、gamma、contrast、brightness、saturation候选以 `!O_valid || O_ready` 冻结全流水。旧只连ready却继续移动内部数据会覆盖等待拍。全链有限stall仍须预算物理CSI FIFO，不能声称无限反压。
7. Gamma0.8低LUT减2048为负，旧返回255使黑变白，候选钳0。contrast以9bit signed的pixel−128、足够宽signed乘积、算术右移、加128/限幅，修奇数level符号翻转；golden覆盖输入0..255及level1/3/139/140/255，默认140保持原结果。
8. AWB用接受四像素统计，除法结果下一帧SOF **原子更新活动增益**，不帧内改变；验证零除数、黑帧、饱和/定点宽度/stall。行为除法模型只证明控制，不替代厂商IP/上板；build03已有帧锁AWB仍失败，不将它当唯一原因。
9. 满长度仍可能色错。检查长度/序号/错误/丢弃计数，保存原始帧并看通道、行/上下半帧和真实画面。颜色启发式只筛疑似帧，真实紫绿场景也会触发。依次定位RAW/Bayer起点、裁切奇偶、有效字节、CSI头/CRC、ISP标记/增益、FIFO、RGB和主机显示格式，不抹掉坏帧后宣布成功。

数字证据：`tb/run_isp_golden.do` 全像素golden，四Bayer、短/奇数行、1280×720/1920×1080、首末行/首末四像素、洞、背靠背及随机stall；`run_isp_interfaces.do` 裁切/行RAM/SOF先于像素；`run_isp_elastic.do` BLC与cut→gamma→contrast→brightness→saturation的golden/长stall；`run_isp_parameters.do` gamma0.8/奇数contrast穷举。2026-10-04 双bank与尺寸常量reset调整后完整golden重跑返回0、0error/0warning，最终证据 `evidence/isp_golden_banked_constreset.log`；build04已确认两bank实际8 ERAM且完成同源hold修复/bit下载；FPGA5新集成仍须重新确认并重跑。旧ISP同一golden失败证据不能唯一归因所有实机紫绿帧。

## 真实颜色与帧锁 Bayer 标定

- build04 bit SHA256 `700b625fdb94f84820c836d0479cb34e814827e94a8ccf7d6127b75915126c58` 的`evidence/quick04_scene_last.png`把用户确认的橙色实体卡显示为绿色：颜色验收失败。满帧、计数0错、启发式“无紫/绿疑似”或旧数字RGB回环都不能推翻这条物理证据。`colour_baseline04`和`colour_chart04_full`各120帧长度正常，仅是后续实拍数据；尚未有各色patch量化结论，不能先写chart正确。
- 官方[Linux主线IMX415驱动](https://github.com/torvalds/linux/blob/master/drivers/media/i2c/imx415.c)默认RAW10使用`MEDIA_BUS_FMT_SGBRG10_1X10`，[Rockchip官方5.10驱动](https://github.com/rockchip-linux/kernel/blob/develop-5.10/drivers/media/i2c/imx415.c)也有GBRG及1944×1097 binning模式。因此GBRG是**有官方依据的强候选**；两份驱动的全部寄存器/bitdepth/clock并非与本地表逐项一致，不能只凭名称认证实际Bayer。当前本地3030=0无翻转，x4/y偶数裁切保持输入相位；改原点/flip/binning须重新确定相位。误把GBRG当RGGB可把R/B采样当G，不能用AWB增益或简单RGB字节互换掩盖。
- runtime编码0=RGGB、1=BGGR、2=GRBG、3=GBRG。06候选D8只写/读shadow，reset3；DC只读最近**裁切接受SOF**锁定的mode。cam在`crop_valid && crop_ready && crop_user`锁帧，再将mode与被BLC背压的帧保持一致；demosaic、bilinear在各自接受SOF锁定，首beat必须用本帧请求值，不能因NBA使用前帧mode。不能直接把live D8穿过前置流水，或只看当前D8/DC给仍排队的RK buffer标帧号；DC不含每个buffer的epoch，稳定比较需排空旧帧并等待增益稳定。四模式golden须显式连接runtime端口，不能靠悬空/XZ的参数fallback证明新端口正确。
- `tools/bayer_runtime6/README.md`记录32帧全像素golden：四模式依次切换、帧中shadow变化忽略、真实BLC/矩阵/RAM、首末边界/标记/随机stall及720p/1080p，0error/0warning。该数字测试不证明传感器真实颜色，也不覆盖整机PHY/PCIe。06集成清单`evidence/colour06_integration.json`，top SHA256 `066f9ab0fd0cb8e530b4ccd94a0dbaec86e691b596966530411fab010c88ea5e`；后续07变更须新清单，不能拿06hash标新源。
- 使用`tools/hdmi_colour_pattern.py`及`reports/hdmi_pattern_tool.md`生成固定RGB九宫格：R/G/B、白/灰/黑、橙/青/紫。当前RK无`/dev/fb*`，用Xorg :0现有HDMI-1 1920×1080无边框Tk窗口，不停止lightdm/改DRM模式；DSI1与HDMI窗口部分重叠，记录该事实。等待ready.json匹配命令ID/generation，再核对稳定成功的真实XWD。参考PNG的CRC/ROI数字自检与XWD只能证明数字图案/窗口，**不能证明HDMI线、面板色度或相机颜色**。
- 让相机真实拍到图案，记录具体场景、bit、驱动、D8/DC及增益稳定期；仅比较各patch中央30–70%区域，排除文字/边框/高光/饱和/摩尔纹。以R/G/B主导关系、橙R>G>B及灰中性趋势判通道，不要求经过曝光/AWB/gamma/显示光谱的相机8bit值与源PNG逐字节相同。按四个Bayer候选保存完整原图，不能仅选“看起来最好”的一张或删除失败帧。
- **先证明实际输入尺寸足够裁切。** driver07+04bit首次真实1080p试验0/8帧：持续收到6197776后跟16字节包，而非6220800。1097行输入下，旧首行20至1099只实际选中1077行；声明height1080导致矩阵不执行末行DRAIN，只输出1076行×5760=6197760字节且没有EOF。现场额外16字节的completer/flush来源未由下面的边界TB证明。792次reject、DMA errors0不能归为仅软件模式切换，也不能容忍99%长度。历史1080p“50帧零差异”是生成RGB双向回环，从未证明1080p相机裁切。
- 07裁切数字证据：[tools/crop_height07/README.md](../../../projects/pcie_imx415_fix_20261003/tools/crop_height07/README.md)及physical_crop.log。实际ModelSim完整1944×1097/3888×2192 CSI RAW10包（WC2430/4860，ECC/CRC/低2bit）经过真实parser/unpack/crop/零偏移BLC/同步RAM/matrix/bilinear/packer，exit0、0error/0warning，逐像素及packed字节全部黄金一致。旧1080精确复现1077输入行→1076输出行/6197760bytes/EOF0；新1080 y16..1095为1080行/6220800bytes/EOF1；新4K y16..2175为2160行/24883200bytes/EOF1；720p→1080p完整边界无reset也通过。均首列4/偶数首行，保持GBRG帧锁。此测试假设物理输入尺寸，线上每帧RAW包/WC仍须实测；未例化PHY/CDC/AWB/PCIe/completer，不证明任意帧内换模式、新TD或新位流颜色/双向实机通过。4K只有数字边界验收，不代表带宽/CMA或实拍认证。
- **06独立副本的Bayer原点与主PCIe不同。** 其ui06_csi_frontend默认skip1行，即首原始行y1，首列x4：sensorGBRG在奇数行、偶数列原点变为RGGB，因此保持06自身ISP默认RGGB；不能把主PCIe偶数首行的GBRG默认盲搬过去。重新修改skip/flip/binning时按实际首像素奇偶重算，并用真实原色图确认。
- 宽高目前仍有live端口进入部分后处理/打包；仅矩阵/裁切锁尺寸不意味着任意帧中修改已安全。复用前置条件是**STREAMOFF→关闭pipeline并flush→REQBUFS(0)→修改/核对模式与尺寸→重新分配→STREAMON**，不能绕开驱动busy守卫直接改BAR并声称原子换模式。需要任意帧内更新时另设计整帧epoch handshake。

## RK 驱动与状态切换

- 动态发现 PCI ID、BDF、BAR、字符节点和 V4L2 card。本次节点大小写为 `/dev/ANLOGIC-PCI0_{h2c_0,c2h_0,user,control}`，V4L2 节点曾为 `/dev/video73`；不得将这些编号作为普遍常量。
- 驱动必须用实际 `xfer_len == expected_frame_bytes` 判断完整帧，不能接受 99% 后把未写入尾部当作有效像素。短包应丢弃并计数；记录启动短包与运行中短包，不能隐藏。
- EOP 模式须与帧末 TLAST 对应，配置失败应让 STREAMON 失败。此字符 DMA 驱动通过 C2H `open(..., O_TRUNC)` 选择 EOP flush；以实际驱动源码为准。
- 候选setup **BAR初始化在V4L2 insmod之前**；旧先加载再CAM_MODE0，会把硬件mode2缓存为720后再变1080。从mode2执行setup负测，G_FMT/CAM_MODE/WIDTH/HEIGHT必须一致。
- `dma_map_sg` 仅返回0为失败；合法合并可令mapped nents小于orig_nents。候选描述符用sgt->nents，unmap用orig_nents，不能覆盖原计数或成功映射直接泄漏返回。平台是否实际发生SG合并仍须实测。[Linux DMA API](https://docs.kernel.org/core-api/dma-api.html)
- S_FMT 在缓冲已分配时返回 EBUSY；先 STREAMOFF、释放 REQBUFS、再换模式。运行时跨域参数必须稳定或握手，不能把各位 2FF 当作任意多位原子更新。
- 候选STREAMON检查硬件mode/宽高/padded bytes与REQBUFS格式完全一致；不在已分配后改DMA长度。外部BAR改模式必须-EINVAL、返还QUEUED且不启动DMA；REQBUFS(0)后再切换。[videobuf2 文档](https://docs.kernel.org/driver-api/media/v4l2-videobuf2.html)
- raw字符streaming与V4L2共用**每engine生命周期lease**：engine->lock短暂claim/release，同方向双客户端-EBUSY；H2C/C2H独立可并发。V4L2占用覆盖start→worker→stop，worker结束才释放，启动失败返还QUEUED/清理；不能只锁一笔DMA或只用V4L2 ioctl锁，也不在自旋锁内等待DMA。
- 候选连续3次意外DMA负错误关闭pipeline/vb2_queue_error，STREAMOFF正常中断不计运行失败；posted stop必须实际读状态flush，旧“dummy read”注释不是证据。先clean/编SGDMA，再以新Module.symvers编V4L2并一起更新，核对kernel headers、CC/LD/MODPOST和模块hash，防未来对象时间戳跳过构建。
- V4L2启动首个完整帧前等待1000ms，之后100ms；短包不触发稳态。同步DMA保存原生wait返回：0为timeout、负数保留signal errno，完成状态优先；不能统一改成ERESTARTSYS或重试signal直到超时。driver05实测正常STREAMOFF用SIGKILL中断等待，十秒后旧poll仍报timeout，必须修取消而非删日志。
- 驱动06锁内读取head并只复制threshold+64bit generation，空队列的`list_entry`不是NULL判断。stop/abort/start/new-head使epoch失效；每次WB读/清以及service前都锁内重验，取消静默ECANCELED，真实当前请求超时仍报错。worker在锁内work-list选择/轮转并租用engine，detach后等在途lease归零及final lock barrier，再free WB/engine；IRQ deferred work也join。spinlock内不睡眠，线程创建部分失败必须先join已活线程再free storage。
- **软件epoch不是硬件DMA排空。** abort/error设置quiescing拒绝新queue/start；两同步异常出口在spinlock外保留desc_lock、descriptor、SG和外部buffer，检查实际RUN0/BUSY0后清旧WB再destroy/unmap；卸载同样先join worker/IRQ work再确认idle。超过1秒仍busy明确报告保留映射并继续等待，不因signal或deadline返回让vb2 free。永久busy是未恢复故障，不能计PASS。core加密且现有官方资料未承诺BUSY0含所有最后postedWB，CPU barrier/fixed sleep不能补该规格；热拔/活跃client强制unbind、旧async/cyclic/debug API不在本同步修复认证内。[安路SGDMA概述](https://www.anlogic.com/news/company-news/83.html)
- 驱动06模型20 poll/10 lifetime交错、66停止状态、24源码守卫及独立锁序审查通过；RK实际06模块编译、加载版确认及`driver_negative06_loaded.jsonl`8/8已通过，仍须20轮start/stop、停止后>10秒无残留日志、raw SIGTERM恢复、CMA回收、正常close后卸载重载及双向图像。`reports/poll_cancel_review.md`、`driver06_independent_review.md`记录范围和hash。
- **编译/磁盘文件不是已加载版本证据。** 本次06首次setup权限不足，实际仍加载旧05；它的8/8测试已改名为`_NOT_LOADED_old05`，不得计入06通过。setup用能传播失败的shell（如`bash setup.sh && ...`），检查insmod返回、实际/sys/module与唯一新增符号；本次真正06加载后已取得`/proc/kallsyms`的`engine_service_poll_generation`及`driver_negative06_loaded.jsonl`8/8日志（本地见`evidence/rk_serial.log`）；这只证明该负测范围，不能替代持续图像/循环/双向验收。记录模块源manifest与新SGDMA/V4L2 ko哈希；本次06编译文件分别为`b79357c7a12dd9fc7eb7749f702c36567037bab8291f0bd63ecfa6c21cd1f9c4`和`b7d6d24f51419ef9e748c002445ff1e80a7f894afe248d670fb44072e700b588`。该符号证明06功能存在，不能区分继承该功能的07；07还须核对它自己的模块哈希和部署manifest。任何setup失败都应停止依赖验收，不能用后续成功输出覆盖前面的权限/加载错误。
- probe07候选已修“ID不匹配/没有下一通道”与真实ENOMEM/初始化失败混淆：前者专用ENODEV正常结束该方向；后者保留负errno、部分init先回滚，成功C2H反序再H2C反序清理并将max归0；无任何engine返回ENODEV。MAGIC_ENGINE仅完整init后发布，失败回滚清IRQ mask，复用06 STOP/worker lease join/deferred-work cancel/idle guard，之后才能free已编程DMA目标；不能缩channel_max后return0让partial engine逃出remove范围。
- `reports/driver_probe_error07.md`、`evidence/driver_probe_error07_manifest.json`记录07仅修改lib.c（SHA256 `38eb739398f7645641f6604f0210b170637b5275c1f4e7a5b5903594e5ea8029`），header/thread仍为06。主机GCC严格编译实际五生产函数，416cases/384故障注入及06 poll model通过，核对资源/IRQ/计数/错误码/回收顺序；这是内核/MMIO/mock结果，假设STOP成功，**不是板级故障注入通过**。随后07已实际RK编译/加载（BUILD07_RC=0、SETUP07_RC=0、新增取消符号存在），SGDMA ko SHA256 `b2caa435b33822410872189cf010881628f34ae2cb5d0fbab12984556457baef`，V4L2仍`b7d6d24f51419ef9e748c002445ff1e80a7f894afe248d670fb44072e700b588`；serial回收原文是加载证据，不将06的ko误标07。07负测8/8，但20cycle计划在cycle1真实1080p因上文裁切不足失败，只有cycle0的720p八帧通过；本次停止最终RUN0/BUSY0、CMAFree61516KiB恢复，未证明后续循环/两档完整恢复。正常一次probe成功也不证明OOM回滚。仍须修裁切后的长测、raw中断/回环、停止>10秒和close后卸载重载；活跃client hot unbind不支持。
- 全图回环工具先open两方向再改BAR，V4L2已加载时拒绝，源/返回不能同inode。atomic stop/failed、SIGINT/SIGTERM统一清理A4 mux/0x20命令/CTRL；SIGKILL无法清理，须显式恢复。候选CTRL软复位同时清独立loop FIFO，不仅恢复mux，也不连AXIL响应一起复位；进入/退出软复位，中途终止后重验下一次首帧hash。
- 4K RGB24 的 PCIe Gen2 x1 负载超预算，应拒绝或采用明确的压缩/降帧方案。例程命名的 60 fps 不等于实测帧率，使用单调时钟的连续帧时间戳计算。
- 吞吐测禁用/限频同步raw保存，避免eMMC写阻塞DQBUF/QBUF人为耗尽四缓冲。bytesused超buffer length先拒绝再统计/写文件；模式表/g_parm的60fps不作为实测性能。
- 重下载 FPGA 前停应用、卸 V4L2 和 SGDMA、解绑 RK PCIe 控制器；下载后重新枚举和加载，避免旧 DMA 引用失效硬件。底板整机掉电会丢 SRAM 位流；仅 RK 软件重启不等于 FPGA 已重新下载。
- 此板 PERST GPIO 与旧 sysfs GPIO 占用曾冲突；先核对拥有者，再释放试验脚本的占用并重新绑定。不要随意拉高未知 GPIO。

## 时序与双向验收

- MIPI参考实际100MHz，ui PLL C0=150MHz presence、C2=24MHz。CAM_I2C_CLK_DIV=239的半周期120拍，SCL实际 **24MHz/240=100kHz**，SDC不照旧200k注释。HS/4字节钟频率为lane bit rate/8，与presence参考不同；27MHz候选对应445.5/111.375MHz，传感器实际MCLK、线路/线上速率须新bit核实。
- PCIe运行Gen2 core/user为125MHz，SDC8ns；PLL **FIN62.5是初始Gen1训练态**，clock_ctrl经DRP转125，不为清静态warning改FIN或预设。实际反馈1:1、运行user25%占空比；初始参数/Gen2约束频率差异的告警须记录动态切换证据。若需训练态STA，另做16ns Gen1场景；两状态互斥，不用跨态false path掩盖同域违例。
- SDC用真实PCIe IP层级、显式master/generated及I2C生成钟；检查 `get_clocks` 非空与evidence/clock_collections.txt。TD6.2的 `-include_generated_clocks` 曾为空，命令存在不代表有效。独立分组不认证CDC；同域setup/hold都须通过，逐条评估未约束和高等级告警。
- TD ASYNC_REG需同时`set_param rtl directive:async_reg on`和`set_param place async_reg on`。实际tiny TD六轮证明第二次insert_debugger/OOC使查询为0，**原属性仍保留在被关闭的全局RTL directive后**：place-only不能恢复，仅重新打开rtl directive恢复原3个；不需set_property。优先`tools/cdc_attribute_restore_exact.tcl`的`cdc_exact_reenable_after_debugger`在OOC后重开两参数并与准确gate名单逐项核对，拒绝缺失/多余/歧义；TD过滤`NAME == bare_name`有效，带引号值实际查0，不照搬Vivado current_design API。RTL原ASYNC_REG受DONT_TOUCH保护，不能晚补属性假装恢复已优化掉的链。
- main5 gate196个AL_MAP_SEQ、post-place83个PH1_PHY_LSLICE是不同映射表示，不能要求数量/名称逐个等同；沿原同步链端点核对物理寄存pin/属性/布局。证据`reports/td_async_ooc_attribute_review.md`及`evidence/td_async_ooc_review_manifest.json`，仅属性可见不证明CDC安全。main5随后`report_mtbf -cdc_sink_pin` native crash，与属性恢复是两件事，Tcl catch不能修复进程崩溃；先保存**时序合格**的route checkpoint/bit，再在隔离TD进程调查MTBF，现5负时序不能因该建议而提前bit签核。build04、03/04副本`CDC_NOT_REPORTED`和本次未获有效MTBF仍明列。
- **相机→FPGA→RK**：720p、1080p 连续采集，记录实际帧长/序号/帧率、短包/溢出、头尾及异常原始图像；检查 RGB、上下行拼接、启动、反复开关与分辨率切换。
- **RK→FPGA→RK**：完整已知 RGB 图像含位置和通道编码，经 H2C 进入 FPGA 实际数据通路，再经 C2H 返回；接收先准备，发送/接收并发避免小 FIFO 死锁。逐字节比较并保存返回图，核对源与返回 SHA256；再用真实相机帧回传，改变分块大小、重复多帧。
- 新组合另验校准/失钟恢复、CSI计数、随机读端停顿和回环终止/软复位后首帧；旧20/50帧零差异不能替代。负测同方向双open、raw C2H与V4L2互抢-EBUSY，REQBUFS后BAR改模式STREAMON -EINVAL，DMA失败POLLERR/EIO后close/恢复开流，确认buffers/lease释放。
- 区分“图像经 FPGA 回传”与“FPGA 向屏幕显示”。FIFO 回传能证明双向传输，不证明 FPGA 显示端色彩或画面输出；涉及显示时另验对应 DSI/HDMI 输出。
- BAR RAM 写读只是辅助检查。厂商 `axil_anal.v` 对地址低字节 0x28 有 IRQ 状态别名，RAM 测试须排除此地址，不能把预期特殊寄存器读值误报为 PCIe 数据错误。
- 检查 PCIe endpoint/root-port AER、速度/宽度、连续传输及重新枚举。交付列出测试位流哈希、boot 哈希、驱动版本、图像比对结果、测试范围和未验证项；不写“所有问题不存在”。


## 2026-10-10 当前35/SGDMA36：8/13及新增根因

当前完整证据见`projects/pcie_imx415_elastic_loop35_20261009/evidence/issues1_to8_acceptance36.json`和原任务`reports/current_status_20261010.md`。FPGA35使用160bit payload/KEEP/USER+TLAST的真实AXIS弹性环路FIFO，256词；40k拍元数据、满缓存与指针绕回数字通过，原34错位失败保留。SGDMA35在两个同步成功路径也等待真实RUN/BUSY空闲再释放描述符/SG映射，不能把STOP posted-read当成BUSY清零。

该正确等待暴露了另一缺陷：信用模式环容量1023描述符，1080全帧需6描述符；旧transfer_init按环尾剩余槽截断，导致一次AXI-ST packet在环尾分成两段并在中间STOP，35/SGDMA35长测交付10000但内核拒收47。独立SGDMA36先在真实硬件及软件空闲时选择足够连续的环首，整个拟合请求一条链，超过容量未提交请求返回EMSGSIZE，忙碌不能复用环头。保留成功释放等待，不用减小等待/丢弃短包/放松检测掩盖缺陷。当前1080观察58次真实绕回，10000帧rejected0/error0；720亦10000/0/0。生产selector头文件由原生严格GCC穷举及10000请求测试直接使用，未写替代模型。

当前九色3780采集、13画面10000、同屏九ROI1000/180000行和两档全图30k采集独立复核；167双向整帧969753600B及真实SIGTERM/12s连续kmsg通过。16B实际故障注入仅在独占负测会话，通过私有环路给视频DMA送出一个TLAST；内核拒收1、用户交付0，再STOP/重启恢复。忙碌格式EBUSY、未STREAMOFF活跃close、卸载重载/32整帧恢复及连续232条kmsg通过。负测中的人为拒收不能并入普通相机零拒收记录，也不认证未支持AIO/cyclic/hot unbind。

大文件归档在RK native gzip/tar通过固定主机键SSH流传输，避免板端低磁盘再建大tgz；两端压缩流SHA/尺寸及每个安全提取文件SHA都正确才移走精确列出的native冗余RGB/统计，完整本机两份和板端元数据/内核/CSI/XWD保留。历史dmesg前缀可能滚动：取消静默用read-only/dev/kmsg连续序号，EPIPE/gap失败；普通颜色本轮18条累计STOP和精确1024行pre尾部重合证明测试区间未丢，原严格历史prefix失败原样留存，不能把失去测试区间也当通过。

当前35 setup+.194/hold+.020、四lane PAD正余量、244属性并不替代MTBF。新同build只读report_mtbf最小入口仍在原生TD报0xC0000005，原DB/bit/TS哈希不变；日志/dump与未验证边界保留。剩余USB0实物、六例程、最终交付及BAR AXI-Lite继续，不宣布全13完成。

## 2026-10-10 当前37/SGDMA36：9/13及BAR契约

当前组合为FPGA37/0x56442501、原SGDMA36与V4L2_37，正式记录`projects/pcie_imx415_bar_contract37_20261010/evidence/issues1_to8_and13_acceptance37.json`；已验收第1–8及13项，剩余9–12。35原验收和所有失败不覆盖。37完整317依赖按`build37_sources_v2.json`冻结，仅6文件变化，311不变；220个原CSI/ISP/裁切/打包/约束依赖逐SHA相同，只复用全裁切数字证明，所有物理图像重新采集。

继承AXI-Lite必须独立保存AW/W并在实际成对提交时通知应用，不能以地址/数据总线上相邻周期的值或wr_hit上升沿执行命令。所有WSTRB位只更新对应字节，命令须检查byte0；高BAR地址不能用低位混叠成视频控制。八应用bank共512字采用完整索引，IRQ/legacy命令特殊地址保留。B/R保持到ready，RDATA包含视频读mux的实际AR时快照；仅修厂商AXI-Lite、仍让顶层live ARADDR或计数器追踪响应，会留下背压错误。读通道不应被BVALID背压全程阻塞。

37实际明文模块与逐字生产写/读slice自检覆盖512字/16WSTRB/AW-W错峰/B-R背压/IRQ/高位地址/reset及112响应14224停顿周期，旧35实际源码RDATA停顿变化复现并保留。板上用原生对齐32bit和实际CPU字节MMIO验证gain恰好一次、upper byte无命令、15个高BAR页不混叠及1000组读取。CPU即时读取不等于物理强制RREADY；后者和零WSTRB只属于RTL自检范围，不编加密PCIe/PHY替代模型。

完整TD37 setup+.148/hold+.019/TNS0/覆盖99.97%，244属性、四lane PAD正余量，SRAM版本与bit SHA读回。新720/1080各10000帧、九色3780、13画面10000、同屏九ROI1000、暂停400、启停20轮160、167双向整帧及真实SIGTERM/12s、8负测和16B故障/忙碌格式/活跃关闭/模块重载32帧恢复全部新采集独立复核，8组完整归档两端SHA和每文件SHA正确。颜色日志本轮用持续读取/dev/kmsg序号，400条原始记录及18条STOP逐条验证，无历史prefix滚动豁免。

当前bit SHA391fe012ea487c18e450bf3ba4f6c23cbb7752dbce2d3747be39b521236c3b0a，SGDMA SHA0eae16450705a87f58e055875a8878b3d8a0a01c9adae9535dc3d9f2147a8ef2，V4L2 SHA1e8cfa968ecd51acd3df7c1fec4a0c6e8b8ae409d6d216edcca9f224e903cebb。新同build MTBF仍崩溃0xC0000005，输入前后SHA相同，不是PASS。USB0当前okay/otg、Type-C device/sink、无外接枚举，尚无实物共存证明。06完整新TD生成诊断bit但setup−4.845ns，来自DDR MCU GPIO→FDMA复位，原IP mcu_clk约束空匹配与加载顺序继续检查；不下载失败bit，不用屏蔽整组相关PLL时序来补签核。
