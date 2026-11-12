# CSI训练、像素准入与被动观测

在开放PHY、CRC反馈训练、无图或训练期间FIFO溢出时读取。当前完整候选为第14版 `projects/hci06_capture_clock_reset_20261019`，父F13实板失败保留；布局通过但内部LUT-fed wire与最终/实机仍待，验收状态以根 `CURRENT_CAMERA.json`、`TASKS.md` 和对应实际证据为准。

- **传感器初始化和图像有效分开验收。** F12的100ms启动等待使实际首笔I²C四字节全部ACK、配置器进入RUN，但图像链RAW包不增长，CRC/ECC与溢出仍增长。不得凭配置done或I²C ACK签核CSI、ISP或卷积，也不能据此证明器件全局启动的电气根因。
- **训练反馈保持运行，像素输出等待训练完成和新FS。** 卷积候选原先在训练期间启用解包和FIFO；现用47在训练完成后等新帧才允许输出。F13新增同一byte时钟的就绪流水和capture_armed，禁止以像素准入条件关闭parser，否则训练依赖的CRC-good反馈会被切断。训练中途就绪不能接收半帧。
- **用实际源和物理配置缩小差异。** 本轮五个采样/延时/对齐模块经模块名归一后字节一致，四lane实际PAD显式参数相同。201项实际寄存器LUT经仿真比较，仅0x3090/3092/3094/3096增益值不同。相同源码或参数不能替代波形、时序与电气验收。
- **先追参考时钟用途。** 此版75MHz的I_ref_clock只驱动Gray时钟存在检测；7500000周期和现用150MHz的15000000周期均是100ms。该信号不接采样延时校准参考，不应仅凭频率不同改PLL。
- **新增训练观测跨域要整包。** F13将16位PHY状态附加到既有CSI held快照，宽度192→208，DSI6/DSIF flags[31:16]依次为auto_done、deskew_lock、best_len[5:0]、tap[4:0]、delay_load、all_lane_valid、any_SOT；原低16位语义保持。普通字段不逐位同步。原生精确约束保留时钟与预算，仅将已证明的held端点数增加16；新native须实际验证33组1266路径及自己的物理结果。
- **主机验收跟随协议。** 低16位有效标志仍须严格为31；此候选实机验收另外要求auto_done和非空窗口。高16位诊断不是图像错误豁免，CRC/ECC/WC/溢出和持续帧进度仍需独立通过。

实际基线只读观测：47自动训练完成，有效窗口24，手动override=0；12个稳定快照RAW增加144818，CRC/ECC/WC/timeout/overflow均0。旧采集器将0x11c误命名为first_bad_header，该原始字段保留并在复核中纠正：0x11c是sticky镜像，完整首个错误header为0xf8。不要沿用错误标签解释根因。

F13数字证据：旧版训练期间泄漏48像素，新版拒绝；训练中途就绪、后续新帧、训练失效、CRC/ECC反馈及两帧96精确RAW像素通过；完整CSI→ISP→signed卷积→真实DBUF数字联合通过；208位快照的6个实际115200串口包CRC/序号/字段一致，19项原图像oracle加6项训练标志测试通过。测试不包括受保护PHY行为、实际采样眼图、新native或新上板结果。

证据入口：父工程 `evidence/board_trial_v1/independent_review.json`、`evidence/PHY_difference_v3/result.json`；新工程 `evidence/preflight_v2/independent_review.json`。测试驱动的旧失败与原始日志均保留；旧版单周期裸协议包间隔不符合当前四周期DRAIN接口，修订fixture使用8周期间隔，并未为测试修改parser。


## v167实际上板

F13完整174+9冻结源已完成5584.296秒自己的TD构建，最终setup+0.184ns、hold+0.020ns、TNS0，位流SHA0f5eb1a5…；自己的gate/place/route、95选定物理链与wire隔离副本查询已复核。实际I2C drive输入经四个LUT输入对应三组寄存器来源，旧endpoint/check唯一假设失败保留；新检查保持10个端点/类型覆盖并核验全部12条来源路径、6条reset检查，8反例通过。原RTL/约束/DB/bit未因复核修改。

实际SRAM上板已执行，图像/训练专项仍失败：PHY calibration incomplete or empty sampling window。末个profile RAW包[3, 6]，CSI错误首末[365342, 1880, 0, 0, 2]→[534257, 2786, 0, 0, 3]，PHY首末[{'auto_done': False, 'deskew_lock': True, 'window': 0, 'tap': 23, 'raw_flags': 1085931551}, {'auto_done': False, 'deskew_lock': False, 'window': 0, 'tap': 8, 'raw_flags': 4194335}]。常量帧和遥测不替代任意卷积逐像素验收。

同一受控事务已真实JTAG恢复47/gate2完整2073600像素直方图、app22原RK3576 NPU，新PID43909/43951，PCIe5GT/s×1、USB1关闭、CSI/AIQ隔离、同boot内核检查保持；Flash37未写。

实际记录：`projects/hci06_calibrated_capture_20261018/evidence/board_trial_v1/independent_review.json`。下一步依据真实训练窗口与错误分布定位，不凭像素准入数字通过宣称PHY问题解决。


## v168复位候选

新完整副本F14（hci06_capture_clock_reset_20261019）只改一处HDL：接收LCLK reset除PLL lock外还跟随capture/config就绪；其余174注册/9运行助手均冻结，ADC/SDC、频率/分频参数、传感器表、训练算法、100ms启动等待和新FS像素准入保持。实际新旧wrapper/open PHY/clockgen/clockdet的16组启动/停钟/重新使能及反馈连线测试通过，旧接线16次未随capture复位；LCLK计数/延时/IDDR用明确替身，不是受保护原语相位、眼图或实机证明。前两版fixture为小数延时/匿名generate路径编译失败；后续fixture初始就保持复位但无明确断言边沿，source计数为X，修订为停钟时实际施加复位脉冲后通过；未为测试更改生产RTL。169 staged元数据与33组1266精确守护通过；自己的完整TD原生73700实际存活，自己的门级/物理/最终STA/bit/上板仍待。父F13自己的最终+0.184/+0.020ns及位流成立，但实板训练窗口0、RAW3→6且CRC/ECC增长；仍失败。生产沿用其实际恢复的47/gate2/app22原NPU，Flash37保持。

手册UG910_1.6第19节确认LCLK rst高有效和DIV/LCLK输出选择；不提供本板实际相位/复位波形证明。后续以自己的实际训练窗口、CRC与完整帧验收。
