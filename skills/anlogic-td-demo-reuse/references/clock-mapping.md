# v179 当前app28与异常提交边界

T08 fresh196+5 own38456已于2026-10-19T13:13:52.549566+00:00终态rc1，耗时2366.657秒，196源及runtime/runner未改。综合/布局后derive_place_reset_graph处，旧debug_hub rst到slave_rst_sync的2ns快照约束被守护拒绝。实际异常报告total2/active2/ignored0、该约束SWNS+1.577ns/TNS0，与旧guard expected1不符；端点推导归属尚待审查，不能写成负slack时序失败或时序通过。没有自己的最终route/正STA/bit或实板nonce验收，不再记RUNNING。

未取得本版最终正STA/bit与实际32nonce查询前，不能校准生产51的FPGA源微秒；旧数字source64不能签物理误差。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v179/actual_app28_T08_observation.json`。全部83+12+47及status保持，未扩大画质/光学/整机验收。

# 历史v178：当前应用与限定证据

T08已从完整G14独立复制并冻结196注册输入及5个runtime；189父输入字节不变、6项预期修改、新增anchor。真实115200查询/24项legacy RX/邮箱source64及reset epoch数字证明通过，无查询TX连续210000周期逐拍等价。own full native38456正在执行，owner/入口/创建时间及当前日志已只读绑定；尚无自己的最终STA/bit/实板32次查询验收。

周期UART旧包不提供查询接口的描述属于历史G14/生产51；新T08接口只能在自己的native/实际下载和32次因果查询通过后签核。数字source64注入只检字段宽度，不是物理时钟校准。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v178/actual_app25_T08_observation.json`。该版本保留83主项、12正式项及47 RK子检查和全部status，不增加验收。

# 相机与接收时钟的测量边界

## 先识别计时起点

HCI03的真实`hci02_timebase.v`使用25MHz源域、每25拍递增的64bit微秒计数，经Gray寄存器和跨域寄存器传递到视频域。`hci02_frame_tags.v`在接受RAW SOF时保存源FID/时间，再匹配后续ISP帧；这个时间不是曝光开始。当前完整工程的周期UART状态不提供可由主机nonce查询的当前FPGA计数，因此不能直接将HCR/HCE源微秒减去RK单调纳秒。

已独立复核的P3功能仿真从post-ISP RGB接口SOF到完整ROI/特征CSI行CRC，包含最大ROI与强制背压，不包含上游RAW/ISP/DDR和实体RK。RGB旁路26.668ns不替代三算法支路时延。不能借此补足实机逐源帧延迟或同步曝光。

## 实际PC与RK校准

入口在`projects/pcie_imx415_bar_contract37_20261010/tools/`：

- `measure_PC_RK_QPC_bounds.py --attempt <新编号>`：单条固定公钥SSH连接，启动自己的无特权临时Python进程。32个独立nonce，PC在发出请求前和读回回复后计时；RK在处理请求时读取CLOCK_MONOTONIC。保存全部原始行、时间、boot ID及前后PCIe只读状态，不启动相机或改硬件。
- `clock_interval_bounds.py`：以正斜率仿射时钟为显式假设，所有请求/回复边界共同约束斜率和偏移，用Fraction精确运算。没有假定网络RTT对称，没有省略较慢样本，默认拒绝测量范围之外的外推。
- `review_PC_RK_clock_bounds.py --capture-attempt <编号> --attempt <新编号>`：不导入采样或边界实现，用半平面交点独立重算所有极值，并核对原始nonce、哈希、时间、boot和PCIe。

2026-10-11实测`PC_RK_clock_bounds_v2`：PC QPC分辨率100ns，RK报告1ns；32次RTT最小5.294ms、中位10.3854ms、最大25.7579ms。全样本条件下的最大映射区间宽度6.720205ms；8个可行顶点的独立复核通过。采样前后PCIe均为Gen2 ×1，自己的远程进程EOF退出且状态码0。宽度是上界减下界，不能写成“±6.72ms”，也不能当作真实网络单程延迟。

保留第一轮`PC_RK_clock_bounds_v1`及原始入口：本机Python的`monotonic_ns()`实际实现为GetTickCount64，分辨率15.625ms，导致最大区间33.850820ms。选择高精度计时必须先读`time.get_clock_info()`，不能仅凭函数名中的ns认为它具备纳秒分辨率。第二轮独立入口使用`perf_counter_ns()`，保留RK端的`monotonic_ns()`；不覆盖第一轮代码或结果。

正仿射模型与±报告timer resolution只提供本组数据下的数值范围。所有边界可行不证明中间时刻严格线性、震荡器精度或未来漂移。重启后boot改变、时钟源改变、测量跨度外的帧均须重新建立有效测量范围。

## 尚缺的FPGA实机链路

PC↔RK校准本身没有给FPGA计数提供锚点。要测RAW SOF到RK接收，需要另外取得同一FPGA时钟/复位代次下的因果锚点，例如带nonce回显且在请求与回复之间锁存FPGA当前计数的协议。协议需有独立完整工程、数字回归、own native/STA/位流及实机校验；不能修改正在运行的E3或已冻结P3输入，不用旧帧时间伪装当前时钟查询。

取得有效FPGA↔PC映射后，和同期PC↔RK范围组合，保留量化、CDC、时钟模型及RK时间戳source标志的误差界；每帧报告延迟区间。两个V4L2节点均使用RK CLOCK_MONOTONIC只说明同一计时基准，仍需分别测量驱动stamp所在位置及传感器曝光偏移。光电动作到显示和两颗IMX415同步曝光另需实物证据。

## T08独立时钟查询工程的数字实现

新增完整副本`projects/hci03_clock_anchor_20261011`，协议见其CLOCK_PROTOCOL.md。共用实际115200 UART，新HCTQ16B请求/HCT4 40B回复锁存nonce、现有source_time_us、capture-reset epoch、source-valid和拒绝计数；一项pending不覆盖，到期遥测优先规则保持七种旧包/seq/phase。父E3/P3各187输入未变，当前工程尚未取得自己的native/bit/实机，不沿用父位流。

四组数字验证通过：21万周期无query旧TX逐拍一致；真实115200 RX/TX9个回复与原子快照/CRC一致；原24项HCIC/HCIR所有边界；pending/global/subclock reset及epoch；主机19个实际RTL包/54异常拒绝。22个完整请求另有1个超时半包，不能误计23个完整包。失效源或epoch变化使时钟采样失效。

source域快照范围留1us量化+40ns旧计数采样裕量；RAW SOF在video域采样，还须单独计算Gray同步及事件读旧值的边界，不能套用1040ns。主机协议类不直接接硬件，未来实机采样先核对own positive native/源/位流/实际下载租约和串口身份。T08部分通过，T10与曝光同步仍未实机通过。

## T08主机采样与恢复入口

`projects/hci03_clock_anchor_20261011/tools/clock_guard.py --preflight-only --attempt <新编号>`只做本地只读检查；`--run --attempt <新编号> --samples 32`仍须本工程自己的188输入positive native/bit、全部旧队列终态、工具/证明SHA、COM4/0403:6042/AL7A9AF422B和正式37空闲元组。DTR/RTS关闭，默认不向37发查询。新的时钟工程尚无自己的native/位流，两个CLI模式现均真实拒绝，未打开串口/启动下载/联系RK。

`clock_sampler.py`从同一已拥有的串口记录serial.bin、所有read返回QPC、包偏移/CRC、nonce请求字节与发送前时间。启动最多4096B只允许一次对齐且留丢弃数，需两连续legacy包；测量中不重新搜索，gap/CRC/半包/nonce/source valid/epoch全部严格拒绝。异常路径终止自己的非daemon reader后由调用者关闭串口，原始失败字节保留。`review_clock_sample.py`不导入生产decoder/数值算法，独立从原始字节、分块最后字节时间和精确半平面顶点重算。

一个BitWriter在quiesce之前开始持有设备；候选下载、采样、正式37 SRAM恢复、原RK runtime、新32帧和相同boot/驱动/控制元组都在其存活期间完成。180秒守护超时或控制器退出后，BitWriter自行恢复并等待其Python子进程完成；不存在两次programmer之间释放硬件队列的窗口。候选/恢复bit复制后核对SHA，在每次下载前独立子进程重新核对。不得在执行期间编辑已固定guard/helper或暂存bit。

软件检验已通过实际RTL字节的正常/7异常、独立精确复核、重新绑定hash后的7种语义篡改拒绝和真实Tcl8.6的8种守护控制分支。Tcl测试公开connect/download/exec是调用记录器，生产180秒watchdog仅在测试副本缩为10ms；没有调用BitWriter/JTAG或测试真实恢复。首轮独立复核路径变量被Fraction覆盖，修复后v2通过，保留v1失败原始源。准备材料在主37 `evidence/hci03_clock_host_ready_v1`；旧数字/文档快照保留，新文档绑定单独记录，188器件输入未变。T08仍是部分通过，不能计为实机FPGA时钟或T10完成。
