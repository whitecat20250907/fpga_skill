# 当前双路 CSI 相机范围与排错经验

## 当前软件修正与未完成边界（2026-10-17）

最新实机选择以根CURRENT_CAMERA.json为准：47 SRAM及运行时线性门限2，app20 CPU4/原RK3576 NPU，Flash37保留；不能重放本文历史恢复37的脚本。真人由用户暂缓，RK原生CSI/AIQ仍隔离。

新增独立`rk/retained_cleanup_v9b`修复STREAMOFF失败仍释放映射和停止信号下EINTR不重试的问题。失败后保留映射/fd/子进程，使用sigaction维持重复停止信号处理，现有manager继续保留AIQ。RK ARM64编译、12项完整C memfd故障注入及10项假进程生命周期案例通过，未包装真实程序仅编译未执行，未部署。完整边界、旧版反例、保留PID与证据见[内核/停流定位](rk3576-kernel-stop-triage.md#用户态停流错误路径v9b独立未部署)。它不能解决驱动内部timeout却返回0或内核挂死的问题，不增加实际双摄验收数。

## 历史内核故障与恢复边界（2026-10-16，v14）

用户现场重启后固定SSH身份在192.168.8.197恢复。按故障前明确boot_id
`c34dabd0-2295-4ee6-ab45-461ebae7b70b`查询journal，而不是只用`-b -1`：
历史journal索引曾显示陈旧boot列表，明确ID的JSON元数据才确认了本次记录。
实际顺序为ISP capture停流超时 → ISP子设备停流超时 → `27c07f00.iommu`连续页错误 → 内核Oops。
pstore为空不等于没有内核故障。缺最终函数回溯，不能将IOMMU无效页直接认证成某个特定use-after-free。
完整原始证据与独立复核：HCI05 `evidence/crash_reconnect_20261016_062633/review.json`。

旧背压试验完成并误报相机超时，第二轮AIQ ready但无结束记录；旧/新对照不通过。
本机当前kernel下不要再运行`verify_backpressure_watchdog_board_v1.py`或故意阻塞6.25秒的读端试验。
先去掉stdout阻塞对V4L2归还buffer的影响，检查ISP/AIQ停启与buffer生命周期并观测真实停流完成；
仅修用户态watchdog计时不能证明驱动停流已安全。当前RK CSI与AIQ保持停流，双摄验收保留失败。

新boot为`80995559-80cb-448c-a1bb-f4c35b1b5915`；首次PCIe建链失败，检查空总线且无驱动占用后，
只重新绑定既有root并加载正式驱动即恢复5GT/s×1、版本0x56442501，80张完整1080p RGB连续帧通过。
随后恢复app_v14原权重RK3576 NPU预览；没有新JTAG/Flash写入，也没有证明FPGA独立断电自加载。
USB1仍disabled。根分区曾仅剩63MB，三份关闭的本任务证据640文件逐SHA迁至userdata，原路径以符号链接保留，
可用空间恢复约1.31GB；不删故障journal来释放空间。当前未暴露`/dev/watchdog`，不能宣称硬件看门狗已配置。
用户态自动重启与内核/硬件看门狗分别设计，不能用应用守护保证内核挂死后还能SSH。

## 双路停流与待验修正（2026-10-15晚）

在未主动停止v14 PCIe模型的情况下，RK CSI单独capture/decode/preprocess再次取得178帧、连续序号，中位22.785ms。双路v4此前RK22帧后失败，不能简单归因于接口不能共存。发现native的五秒watchdog把stdout管道阻塞也计入相机无数据；修正版从QBUF返回后计实际poll/DQBUF等待，并用ETIMEDOUT报告实际等待超时。旧/新各故意暂停读端6.25秒的实机对照发出后，RK ping/SSH再次不可达，结果未取回，不能据此签修复成功，也不能据SSH超时断言远程进程已终止。COM3的CH9102身份仍能枚举，但端口独占打开被拒绝，本轮没有发送串口字节。

v5将PNG保存移出配对线程，保存容量1，PNG压缩等级0、保持无损；像素交付后只读。保存队列满、写失败、漏掉计划快照、收尾线程未退出，都必须失败；普通帧序号缺口/错误buffer/配对队列溢出检查保留。主机16幅PNG全像素及队列满/磁盘失败/关闭检查通过。1080p配置配对容量8、事件容量4，包含活跃/待写图像的像素内存估计398131200字节，小于384MiB预算。`deliverables/dual_runtime_v5`目前只完成源包冻结，板端C编译和双路修正实测仍待连接恢复；不能把单路178帧或主机保存测试计成双路通过。

恢复连接后先查boot_id、旧/新capture和AIQ PID、fuser，再读取`backpressure_watchdog_20261015_211406`结果；不直接重跑覆盖未知状态。记录见`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v105/progress.json`。实际Flash冷启动也仍待核对，不能在未读取版本前重新下载SRAM而破坏冷启动证据。

## 正式37的Flash固化（2026-10-15）

用户确认整板断电后，正式37 SRAM配置需重新恢复。用户随后明确要求Flash固化：实际AL-LINK识别PH1A90，`get_flash_manufacturer -cable 0 -spd 5`读出C8/65/18；核心板原理图第6页的U10为GD25WQ128ESIGR、128Mbit，默认M[2:0]=001 Master SPI。所选位流为已验收正式37，SHA `391fe012ea487c18e450bf3ba4f6c23cbb7752dbce2d3747be39b521236c3b0a`。

有明确Flash授权后，先结束模型自己的采集并确认DMA空闲，卸载两PCIe驱动、解除空闲RC绑定，再由BitWizard执行 `download -bit <正式37.bit> -mode program_spi -v -spd 7 -cable 0 -flashsize 128`。`-v`启用写入回读校验；本机实际耗时768.844秒，工具输出`SPI flash Page program and verify`并正常完成。不能把工具长时间没有百分比输出当作进程已终止，也不能在擦写期间启动第二个编程任务。前置整片只读备份因内存超过3GB且耗时较长被主动取消，未取得完整旧Flash备份，记录保留；备份取消发生在任何擦写之前。

烧写后重新运行既有PCIe setup，实际版本0x56442501、78帧连续完整1920x1080 RGB3、5.0GT/s及原v10模型新鲜样本均已核对。PH1A90实际拒绝`download -mode refresh`（Unsupported model），不能据通用工具帮助推断此器件支持；本轮没有实际断电，Flash独立重载/冷启动仍待复验。原始采集程序曾用RELOADED标签表述过度，独立报告明确纠正，后续入口已改成仅说明Flash烧写后的版本和采集验证。证据与复核：`projects/gaze_model_migration_v1_20261014/evidence/flash37_20261015/result.json`；实际入口为该项目`tools/program_flash37.tcl`、`finish_flash37.sh`与`review_flash37.py`。这次固化不增加双摄对齐、颜色或模型精度的验收数。

2026-10-11用户将三路任务改为两路：FPGA IMX415走PCIe，另一颗IMX415接RK CSI1、无单独供电。USB摄像头启动和对齐退出当前任务；历史三路的软件包和[经验](three-camera-sync.md)保留，不能据此继续启动USB。

当前完整工程：`projects/hci05_dual_csi_sync_20261011`。入口 `rk/run_two_camera.py`、独立复核 `rk/review_two_capture.py`。9项两路算法自检及RK实际C编译通过；16幅合成RGB共9654304像素的三算法全像素参考比对通过。原生1080p三算法中位13.056261ms，不包含双路并发/颜色解码/传输与哈希，不能称实际双路帧率。

用户现要求包括RK原生CSI的所有颜色和小问题。完整列表见根 `TASKS.md` 的K01–K09与S01–S05：先芯片ID/graph，再完整buffer、Bayer/方向、RGB通道、YUV矩阵范围、实际HDMI九色/灰阶、曝光/AWB和单路长测，然后两真实源的算法/时戳偏移/并发长测/几何反馈。通用解码器合成输入通过不能代签此实际sensor的fourcc、ISP或RGB。

K01–K09细分检查也写入根TASKS及机器清单：连接器/电源/pinctrl/reset/真实MCLK、节点身份、lane/pad、stride/bytesused/data_offset、CFA及裁切奇偶、RGB/BGR/RGB565、UV顺序/601/709/范围、九色/灰阶/棋盘、AE/AWB/曝光增益/防频闪、黑白端/坏点、丢帧/半帧/停启/资源释放。每个细项独立留原始失败、修改和同条件复验；未存在的格式/controls在真实枚举后注明不适用，不能凭假设勾通过。相机拍屏包含光学/ISP变化，HDMI像素不能与相机像素要求零误差；颜色主通道/灰阶顺序按事先确定阈值验收，buffer解码/算法路径则与独立参考逐像素一致。

`tools/inspect_dual_camera_readonly.py`只读sysfs、media、V4L2设备、debug和正式37元组，不probe/STREAMON/改电源或GPIO。2026-10-11 23:31复核CSI1/另一DT地址均没有绑定driver，graph没有注册IMX415；PCIe仍Gen2×1，USB1 disabled。media2/video22实际源名为`m02_back_FPGA-MIPI 9-001a`，这是FPGA传输的虚拟sensor，不是RK第二颗物理IMX415。旧HCI03预备guard按`milianke`字符串检查media2会错误拒绝。T05已修新v3入口：逐entity/sink检查唯一启用的FPGA-MIPI→DPHY3→CSI2→video22；实际RK前置及9错误拓扑拒绝通过，三个等待队列已完成接续。旧冻结入口保留，不任意接受存在video22，实机压缩/同输入NPU仍待own positive native。

## 先证明两颗物理传感器

FPGA/PCIe驱动为 `milianke-v4l2`。RK CSI第二路必须在指定media graph中看到真实注册成功的IMX415，且对应实际video节点。RK的 `FPGA-MIPI` 虚拟传感器不是新增第二颗IMX415。未识别的CSI/ISP节点存在，不证明摄像头工作。

2026-10-12重新检查完整页面后纠正此前路由判断：AFH03底板原理图第13页的CSI1/J9以及硬件手册30–32页使用I2C5 **M1**，与active DT/GPIO1_PD4、PD5一致。核心板连接器表写M3，不能把它直接套到J9。历史M3/rail/clock测试失败并已回退；它们没有证明J9需要M3。J9 pin1/2接VCC_3V3，33为MCLK1，37为MIPI_CAM1_PDN_L；DT avdd指vcc_mipidcphy0和另一rail无消费者仍需核对，但不能仅据此判J9小板没有供电。

用户确认实际接入后，有限重probe5-001a仍ID000 ret0，8-001a ret-5，均未绑定。观察到内核自己选择cam_clk1m0、启用nominal37.125MHz、GPIO125 out hi ACTIVE LOW；default pinstate警告不能直接推断本次没有MCLK。这些kernel状态不等于相机小板的真实电压/波形。

本轮进一步发现：在I2C5仅对0x18–0x1b做receive-byte扫描，四个地址全ACK；仅选择0x1a五个已知寄存器再读取，全部00。按Rockchip官方gpio_regs_v2的EXT_PORT0x70和DT GPIO1基址，只读24次实际引脚逻辑电平，均SCL=1、SDA=0，GPIO版本及已知GPIO48高电平交叉检查有效。没有GPIO请求、寄存器写、强拉高或新增USB。由此可推断SDA持续低解释伪ACK/零数据，但尚未证明是排线、转接、上拉装配还是小板造成。禁止把i2cdetect出现1a或ret0当作芯片识别成功；先隔离SDA，再读有效ID与注册真实graph。不得向未知接线推挽驱动SDA或盲翻复位极性。

证据汇总在`projects/pcie_imx415_bar_contract37_20261010/evidence/CSI1_reprobe_and_hci06_progress_v1/CSI1_diagnosis.json`；各次原始输出保留在HCI05 evidence中。正式37最终只读Gen2×1复核通过；没有实际RK CSI RGB或双路对齐验收。执行重试前重新核对active DT、无人占用、当前boot/PCIe；只在与本轮状态相同的设备上使用已留存入口，不盲重放临时pinctrl脚本。

2026-10-12 08:23–08:25用户再次确认实际接入后，重新核对手册/active DT、触发既有驱动probe并限定扫描，仍ID00/无driver。新入口`projects/hci05_dual_csi_sync_20261011/tools/observe_CSI1_powered_bus_v1.py`在一次内核自己的上电probe期间只读采样GPIO和debug：10次SDA均低；同时段3个debug样本显示clock1 enabled nominal37.125MHz、cam_clk1m0、reset125高ACTIVE LOW及DT avdd控制118高。加上24次空闲SDA低，故障并非仅有probe结束后的零读数。记录为顺序读取，不能称原子波形或证明小板供电；dummy dvdd/dovdd与camera_default警告也不能单独判定根因。当前汇总是HCI05 `evidence/CSI1_current_diagnosis_v3/result.json`，正式37前后Gen2×1。下一步断电核对相机/转接完整型号和针脚，隔离未接/已接时SDA；不要继续重复伪ACK扫描代替有效ID，或盲改M3/复位极性。整板掉电会丢失SRAM位流，按现有守护流程恢复正式37后再检查PCIe。

最新复查汇总为HCI05 `evidence/CSI1_current_diagnosis_v5/result.json`（2026-10-12 12:23–12:26）：仍ID00/无driver、24空闲及6内核probe样本SDA低，PCIe前后Gen2×1保持。新增只读入口 `tools/inspect_CSI1_endpoint_chain_v1.py` 从实际sensor节点追踪remote-endpoint及其反向引用、继承status和平台driver。当前IMX415→DPHY1→CSI2→CIF四节点已启用、6个引用双向一致、3个采集平台driver已绑定；这些结果只证明active DT连接关系，不能代签实际sensor ID、lane线序、ISP/RGB或第二路帧。

核对原理图13页CSI1右下上拉网络：SCL为R240/4.7K，SDA为R244/4.7K/NC，PDN_L为R242/4.7K/NC。当前GPIO60/61 pinconf显示input bias disabled；实际R244是否装配、相机小板是否自带上拉必须另查，NC标记不能直接证明缺件或根因。持续SDA低时优先核对排线/转接针脚、供电和实际总线上拉，分开观察未接/已接状态；不要把全地址ACK当作多颗摄像头，也不要向未知接线强拉高或盲改M3/复位极性。先只读检查最新boot/占用/driver；已经绑定sensor时转入真实graph/帧/RGB检查，不再对它重复裸I2C扫描。

2026-10-12 13:49–13:52按照用户再次确认实物接入的要求，完成一次新的手册/active DT检查、现有驱动上电probe和限定扫描，汇总见HCI05 `evidence/CSI1_current_diagnosis_v6/result.json`。仍reset probe ID00/无driver；7次probe及24次空闲采样SDA均低，2个debug样本见clock1 enabled nominal37.125MHz/cam_clk1m0。六个端点引用互相对应，前后正式37 PCIe Gen2×1同boot保持，USB未启动。此状态没有增加实机验收数；下一步需实际比较未接/已接SDA和排线/供电/上拉，不能继续重复全零扫描当作进展。

补充探测值范围：Sony寄存器表中0x311A是INCKSEL4；当前Rockchip00.01.08驱动以reset值0xE0作probe判断，并在某些模式初始化表中将该寄存器写成0xE7。因此E0用于相应复位上电probe，不能把运行中非E0读数一律解释为错误芯片。必须分别记录reset/power/clock状态、已配置模式和真实graph；本次probe00及持续SDA低仍是实际失败。

## 排线修正后的实机恢复（2026-10-15）

用户更换此前错误排线后，CSI0 的 IMX415 `8-001a` 正常识别 reset ID `0xE0` 并绑定驱动。旧 CSI1 `5-001a` 未绑定不代表当前相机失败。真实链路是 media0 的 sensor→DPHY0→CSI2→CIF，再经 media3 的 CIF→ISP→mainpath `/dev/video33`。已取得4个 RAW10 CIF缓冲及61个连续序号、完整12441600字节的3840×2160 NV12 ISP缓冲，约30fps。证据：HCI05 `evidence/corrected_cable_20261015_184304/aiq_review.json`。此前SDA低、全地址ACK、ID00诊断保留为历史，不再作为当前状态；绑定成功后不要重复裸I2C扫描。

用户确认已取镜头盖且朝向明亮场景，首张ISP图像仍很暗。实际 `rkaiq_3A.service` 未运行；仅为 `m00_b_imx415 8-001a` 调用已安装RK API的 init→prepare(3840,2160,NORMAL)→start，并等待READY后采集，Y均值从13.401升至116.099。局部探针为HCI05 `rk/csi0_aiq_probe.c`，只运行有限45秒，退出时stop/deinit；它不是生产常驻服务。必须在实际采集生命周期内维持3A，并管理自己创建的进程；不要启动会枚举所有media的全局服务来替代有明确作用范围的初始化。

当前IQ文件为 `imx415_CMK-OT2022-PX1_IR0147-50IRC-8M-F20.json`，尚未证明匹配CAM005镜头。自然场景恢复可见只证明图像与3A链路，不能代签Bayer/RGB、矩阵范围、色卡、双路曝光同步或长稳。仍须检查启动CSI ERR2、859us短vblank警告，以及AIQ虽正常stop/deinit却报告pool items still in use的问题。测试结束自己的AIQ进程已停止，没有启用开机服务；PCIe保持Gen2×1，USB1保持disabled。

2026-10-15补充60秒连续采集：定向AIQ运行期间1800个4K NV12缓冲序号0–1799完整，时间戳跨度59.967245秒，平均29.99971fps，间隔32.455–34.212ms。新增内核日志仍有启动ERR2一次及859us短vblank警告两次；AIQ退出码0但资源池警告仍在。证据HCI05 `evidence/csi_60s_20261015_190736/review.json`。只能标记这一分钟缓冲连续性通过，不能扩大为无错误长稳、颜色或双路同步通过。当前PCIe由注视模型运行实例占用，独立CSI测试没有终止它。

短vblank的两次受控实验（2026-10-15）：单独设V4L2 vertical_blanking=80后，180帧完整，但AIQ把它改回58；本次启动没有短vblank日志不代表持续修复。通过板上已安装头文件确认 `rk_aiq_uapi2_setFrameRate` 的 `frameRateInfo_t.fps` 是无符号整数，独立探针设OP_MANUAL/29fps并在开流前设vblank80，180帧平均29.0064fps，结束时vblank136，未出现短vblank警告。两次仍有启动ERR2；均正常停止自己的AIQ并恢复vblank58，没有改变正式配置。证据分别为HCI05 `evidence/csi_vblank80_20261015_191026/review.json` 与 `evidence/csi_fps29_20261015_191154/review.json`。29fps只是验证消隐与AIQ帧周期协同的实验，不可将降帧率默认为30fps目标已完成，也不可宣称ERR2或AIQ池告警已修复。

ERR2观察方法（2026-10-15）：Rockchip develop-6.1 `drivers/media/platform/rockchip/cif/mipi-csi2.c` 的IRQ2处理对日志限频约1秒，不能以单条日志推断单次硬件中断；该公开版本也未单独解码0xf0000所在的16–19位，不把它直接说成CRC或SOT错误。源文件和哈希保存在HCI05 `evidence/csi_err2_source_v1/`，公开分支不等于板端内核精确提交。新增300帧实机审计前后读取 `/proc/interrupts`，全部CSI host IRQ仅81增长1（7→8），其余不变，300帧连续完整；证据 `evidence/csi_irq_audit_20261015_191435/review.json`。支持本次采集没有持续错误中断风暴，仍不能宣称启动ERR2已消除或确定电气根因。

真实CSI预处理验收（2026-10-15）：RK约2GB内存，注视模型与游戏并行时，整帧浮点YUV转换加float64独立参考曾触发OOM，内核只终止本次校验PID4999；模型3872与PCIe采集3915仍在运行。正式 `rk/preprocess.py` 的YUV转换已改为64行分块，独立参考按32行处理，避免巨大浮点临时数组。两张真实3840×2160 NV12（AIQ前/后）在RK本机原生C预处理通过：16588800像素、RGB与独立全范围BT601参考最大误差0，灰度、3×3高斯、上一帧直方图LUT全部逐像素一致。证据HCI05 `evidence/real_csi_preprocess_20261015_191811/stdout.json`，失败记录保留在191701目录。Python转换约600–900ms/帧，C预处理约50ms/帧，明确不满足4K实时双摄；后续需原生/RGA转换或经验证的ISP缩放。数学正确不代表光学RGB校准、实时吞吐或双摄对齐通过。

## 配对范围

两路V4L2的MONOTONIC时间戳、timestamp source flags、driver sequence需连续且稳定。每帧只使用一次，严格abs(delta)<=tolerance，容量8，显式偏移；unknown/copied时间戳默认拒绝，arrival fallback需配置并记录。较快源未配对帧与driver gap/ERROR/容量丢帧分别统计。固定偏移没有测量时标为UNMEASURED_ZERO_OFFSETS；buffer完成时间配对不等于硬件同步曝光。

RGB canonical低字节红的处理约定、stride/plane、BT601/709 full/limited颜色范围、上一帧hist LUT及全部metadata/已保存像素独立检查继承真实实现。实际两路未枚举前不调用采集验收，不以合成双流或CPU吞吐增加实机通过数。

跨PC/RK时间轴或FPGA源SOF到RK延迟时，再读[时钟映射](clock-mapping.md)。32个实机PC↔RK nonce已采集且精确边界独立复核通过；这组校准没有FPGA当前计数锚点，不能增加双路曝光对齐通过数。本机Python monotonic原实现15.625ms分辨率，改用QPC后仍须报告实际误差区间。

## 本次PCIe恢复

启动Link Fail后，实际RK没有PCI根总线，控制器未绑定。启动镜像、模块与正式37的SHA相同；单次重新probe仍失败。恢复已验收37 FPGA SRAM并运行原配套setup后，实际恢复Gen2 ×1、1edb:abcd端点及32个连续完整1080p RGB帧，独立空闲/模块/boot/版本复核通过。下载与编译进程独立；本次持有一个真实BitWriter进程作为硬件队列租约直到RK恢复终态，原native44884同PID且CPU前进，没有取消重启它。

此结果支持FPGA配置/启动状态异常的方向，但没有证明触发原因是掉电。当前USB1 disabled且无USB摄像头启动，不能把本次故障直接归因USB。SRAM掉电会失效；继续保留PCIe/USB1互斥规则和真实当前版本检查。

恢复入口第一次本地主机选错JSON行，保留KeyError失败记录；实际下载/setup/32帧阶段均返回0，独立复核重新解析status行并读实机确认恢复。不要为修主机记录错误重复下载正常位流。

2026-10-12 20:03–20:05用户再次确认已接后，完成新一轮手册/active DT检查、一次驱动上电probe及限定扫描，当前汇总更新为HCI05 `evidence/CSI1_current_diagnosis_v7/result.json`。仍ID00/无driver、7上电和24空闲SDA低；四节点/六引用/三采集平台绑定正常，正式37 PCIe Gen2×1同boot保持。先核对小板/转接实际针脚和未接/已接SDA，不能将全地址ACK算识别或新增RGB/对齐通过；本次未改DT/boot、未手动GPIO或clock/regulator。83任务/47细项保留。

2026-10-12 21:51–21:53用户再次确认已接后，完成新一轮手册/active DT检查、一次驱动上电probe及限定扫描，当前汇总更新为HCI05 `evidence/CSI1_current_diagnosis_v8/result.json`。仍ID00/无driver、8上电和24空闲SDA低；四节点/六引用/三采集平台绑定正常，正式37 PCIe Gen2×1同boot保持。先核对小板/转接实际针脚和未接/已接SDA，不能将全地址ACK算识别或新增RGB/对齐通过；本次未改DT/boot、未手动GPIO或clock/regulator。83任务/47细项保留。

最新CSI1重查为HCI05 `evidence/CSI1_current_diagnosis_v9/result.json`（2026-10-12 23:24–23:26）：live DT四节点/六引用/三平台绑定正确，driver reset probe仍00，无sensor driver；10上电及24空闲SDA低、3个nominal clock-enabled debug样本；限定0x18–1b全ACK/已知寄存器全00。正式37前后同boot Gen2×1，USB未启动。等待相机/转接实际丝印针脚、未接/已接SDA及实际供电/上拉检查；无实物变化不反复伪ACK扫描代替隔离，RGB/对齐未通过。

## SSH失联与串口恢复的证据边界（2026-10-16）

双摄背压测试中网络失联后的远端结果未知。当前LAN扫描只见路由器，没有匹配已固定公钥的RK；
ADB也无开发板。用户授权重启后，COM3最初仍拒绝打开；实际所有者是MobaXterm的MoTTY子进程，
不是主程序本身。按Windows句柄核到 `\\Device\\Serial2` 后仅关闭该串口会话，保留主程序及其他连接；
不能凭进程名猜测持有者或强关所有终端。

已固定CH9102 VID1A86/PID55D4/序列5B32022924，1500000波特、DTR/RTS保持不激活。
回车、BREAK/h、Rockchip `fiq`/help、reboot及FIQ reset请求在主机串口驱动共接受30字节，接收始终0。
没有启动日志或新boot_id，不能说重启成功，也不能仅凭静默认定内核panic；供电、串口链路和硬锁仍待区分。
证据HCI05 `evidence/rk_console_recovery_20261016_125842/result.json`。端口测试后已释放。

Rockchip公开 `drivers/soc/rockchip/fiq_debugger/rk_fiq_debugger.c` 的调试入口识别字符fiq；
通用串口BREAK+SysRq不能代替核对本机ttyFIQ0实现。FIQ功能及运行中断状态未确认时不能保证能救活硬锁。
用户暂不能现场复位，不重复发相同无响应命令充作进展，也不重烧正常Flash37来处理RK失联。
恢复连接先固定SSH身份、记录boot_id，并运行HCI05 `rk/collect_crash_evidence_v1.sh` 收集pstore、前后boot内核日志、
内存/压力/进程/网络/已有watchdog配置。该脚本尚未上板，不开DMA/BAR、不重现压力、不改sysctl或启动看门狗。
先区分应用退出、OOM、驱动阻塞和整机挂死，再决定应用自动拉起及硬件看门狗策略；缺崩溃日志不能断言根因。


## 用户换口后的对比（2026-10-14）

当前RK相机由原CSI1移到另一口；实际异常现在出现在CSI0/I2C8M1/8-001a。不要继续把所有新诊断固定在5-001a。新boot0fb050e6-396f-4e4f-807f-75e4c571c749中，两个既有IMX415 client各一次正常内核probe后均未绑定：旧口5-001a ID00/ret-5，新口8-001a ID00/ret0。GPIO1实测24次空闲：新口54/55=SCL1/SDA0，旧口60/61=SCL1/SDA1；新口再一次内核上电probe期间10次SDA均0。与原CSI1接入时SDA低对比，异常随相机连接移动，优先隔离小板、排线/转接针脚和供电；不能据此断言具体坏件或把软件采样当成电压/时钟波形。

用户随后照片确认CAM005-MIPI-4LANE，主板空口为DSI_TX，插线位置与CSI0/R234相符；照片没有展示触点，AWM20624不能证明排线同面/异面或1对1，未找到CAM005精确原理图前不指示翻转。照片证据为HCI05 evidence/CAM005_photos_v1/result.json。

当前汇总HCI05 evidence/CSI1_current_diagnosis_v12/result.json沿用稳定任务ID，但注明物理接口已换CSI0。实际RGB、第二路帧与曝光对齐仍待。系统重启后PCIe root未建立；恢复既有formal37 SRAM与原运行环境后32连续完整1080p帧通过，native52064同进程CPU前进。最初BitWriter的失败是本机hwserver未监听；按原program_sram.ps1的5555/5556服务参数启动后恢复，不将服务连接失败当作FPGA下载失败。USB仍disabled，没有改启动分区/DT/kernel。


## v125 当前已部署与复验边界

2026-10-16当前选择：SRAM40（bit SHA bcd9c7e16ba7f4d597b1940ab05d5fecaeb55120689cbf5eb29d991557e2e382）+默认app_v18+原RK3576 NPU。Flash仍正式37。BAR0x56442501是共享ABI，当前SRAM身份须绑定成功JTAG日志和bit SHA，不能由BAR独断。

原始绿点已实拍改善但未全验收：统一RAW底值54的39版虽降绿点，却把木板蓝色均值56→14并损暗细节，已拒绝并回退；40版保留BLC50和原色矩阵，只门控线性RGB全部为0/1的最低量化值。自己的317输入完整构建setup +0.240ns/hold +0.021ns、四CSI物理路径通过。实际正常增益32/Bayer3，37与40各422/416帧完整；两块暗区绿超差比例12.69%→1.20%、13.79%→0.010%，墙面/白柱/木板没有该阈值定义下的大偏移，已保留SRAM40。该比例是绿超差代理量；残余绿点、低照纹理、人脸/眼部与九色仍待，不计M05完成。Flash37未改。

默认app_v18已实际部署并以当前模型打开的CSV文件描述符绑定会话；原RK3576 NPU权重和预处理语义未变。复制DMA后先QBUF再发布两份有界输出，整数3:1在私有副本生成640×360，RK5529600个RGB值等于原OpenCV。实际C与Python共21模拟用例通过；三次真实PCIe各141帧，接收中位9.07→2.40ms。真实无脸应用窗口输入年龄中位39.26→20.21ms，样本年龄143.86→118.02ms；不是真人FPS或控制精度验收。v1按目录mtime误选旧会话的失败记录保留，v2以实际日志恢复正确会话，v3用活进程CSV FD确认默认18新鲜运行。

G7自己的完整187输入综合和全部关键绑定复核已完成：456属性、24组6360路径，snapshot/Gray后级、parser和38用户复位检查为正；全局仍9setup/47recovery，WNS/TNS -2.340/-63.000ns。完成历史链本身无运行复位，已证明UI两周期主复位保持期间历史清零，并核对消费者原生复位D余因子，不能虚称这些FF带异步复位。完整G8副本RTL/IP/ADC逐字节等于G7，只给五条注册源到私有首D增加2ns精确预算，29组6365路径的检查器与28负例通过，自己的完整综合实际执行中；不选上板，不加宽域false path，最终PHY/reset/MTBF仍待。

RK CSI/AIQ继续停止；已确认ISP停流超时→IOMMU页错误→内核Oops，具体函数根因/修复未签核。async18在PCIe路径的复制/QBUF改进及21模拟用例不能代签RK ISP停启修复；不重跑已触发故障的6.25秒阻塞读端试验。

证据入口：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v125/progress.json`。此前本页的黄金37/app16和“缩放未集成”描述均属于v124历史。


## v126 实际续查

已修订一处用户态停流顺序：旧版采集子进程超时仍活着时也会停止AIQ。完整离线ordered_lifecycle_v8_v2使用已验证async7复制/QBUF采集；AIQ不再按固定时间自行退出，须等所有指定采集进程退出、工作线程结束及原生最终清理记录cleanup_errno0后才请求停止，超时不强杀。RK实编译原生/AIQ/预处理通过，13项真实假进程测试含实际旧管理器负对照及AIQ提前exit0不误通过。未启动真实RK CSI/AIQ、未部署，不计内核根因修复或双摄通过；官方驱动STREAMOFF内部超时可能仍返回0，风险未消失。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v126/progress.json`。当前选择详见根目录`CURRENT_CAMERA.json`；FPGA断电/重配后必须重新核对，Flash仍37。
