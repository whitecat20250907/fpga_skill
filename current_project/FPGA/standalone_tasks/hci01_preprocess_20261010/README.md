# HCI01完整相机预处理与帧界控制例程

独立完整TD工程：`fpga_prj.al`、`build.tcl`，PH1A90SEG324 −2。继承当前06 frameguard全部CSI PHY/RAW/ISP/DDR/DSI/PLL/ROM/ADC/SDC，生产ISP输出实际串接新的预处理后写入原异步DBUF；没有替换加密PHY或DDR模型。新UART RX在已核对U42连接的V11/LVCMOS18，TX仍U11。原六例程和正式37不改。

## 实际功能

四像素/拍：RGBX亮度 `(77R+150G+29B+128)>>8` → 3×3高斯 `[1 2 1]^T[1 2 1]`、加8后除16 → 64档上一完整处理帧直方图均衡 → 可选Sobel、暗像素二值化、3×3腐蚀/膨胀。输出为RGBX三通道等值灰度。窗口边界复制，三轮转行存储；行末和末行在自己的ready/valid状态机排空，不依赖上游插入空拍。各级输出在停顿期间保持data/SOF/EOL/EOF/config不变。

提供真正RGB旁路，逐位保留原128bit RGBX数据、SOF/EOL与配置，不以R通道充当RGB旁路。高斯和直方图可分别旁路。配置在源ISP实际SOF握手时接受，并随各级元数据传递；帧内更新不会撕裂。下一源SOF须等前帧输出EOF握手。直方图首帧和常量前帧使用精确identity；RGB旁路返回后也先identity，只有新完整处理帧建立的LUT能重新启用。CDF不对计数做右移截断；逐bin32周期无符号除法，建立/清空期间向上游背压。

Sobel输出 `min(255,(abs(Gx)+abs(Gy))>>2)`，暗mask使用`Y<threshold`；腐蚀/膨胀先做同一暗mask再3×3全1/任意1。参数化WIDTH必须4的倍数、HEIGHT至少1；本生产工程固定1920×1080/BINS64，256档和4K行宽仅在当前数字测试范围。不称sensor物理帧率增加，不声称当前4K上板模式。

## 控制与遥测

主机115200 8N1发送16B `HCIC`命令，前12B的CRC32使用标准zlib/反射0xedb88320。字节：0..3 ASCII HCIC，4版本1，5 mode，6 threshold，7保留0，8..11 little-endian sequence，12..15 little-endian CRC32。mode bit0为全RGB旁路、bit1高斯旁路、bit2直方图旁路、bit5:3为后级0无/1Sobel/2暗mask/3腐蚀/4膨胀；bit7:6必须0。默认mode0、threshold128。

第一次有效sequence允许任意值，其后模2^32增量必须1..0x7fffffff；重复、陈旧、半窗口、CRC/版本/保留字节/模式错误只累计reject，不改变配置。已找到header的半包超过20ms超时丢弃，可重新搜索magic。原vendor UART RX+专用2FF保留，25MHz的完整配置/seq/reject计数用held-bus握手到75MHz，再在ISP SOF使用。

原64B DSI6/DSIF、CRC和共享seq保留。DSIF word11是已接受到源帧的command sequence；word12低14bit为该帧配置、bit14为当前LUT有效；word13为预处理sticky错误；word14为跨域快照的command拒绝计数。低14bit配置=`(threshold<<6)|mode`。注意bit14与word11不是屏幕此刻扫描帧的配置标签；观察模式要给整帧/DDR/显示排空时间。原flags31、614400显示像素、CSI和各级流量语义继续保留。

下发模式只修改易失预处理状态，不写RTC/EEPROM/Flash或传感器寄存器。若以后在RK提供控制UI，沿用CRC/版本/新鲜度与帧界提交，不直接跨时钟采样config总线。

## 当前验证与待验范围

主37 `evidence/hci01_pixel_unit_v2`：6组几何、26帧/组，共376376像素，包含1像素行组/1行、64/256档、1920/3840行宽、常量帧及RGB旁路返回、所有后级模式、帧内配置干扰、双向随机/持续停顿和持有RGB输出时复位，通过独立NumPy逐像素oracle。`hci01_pixel_unit_v3`再验证两帧1920×1080，共4147200像素和1036800拍，178262个下游停顿周期，全部像素/标记/config精确一致。累计4523576像素。该数字范围未证明整图恶意缺SOF/短行的恢复；检测旗标不能代替帧丢弃/恢复协议。

首轮 `hci01_pixel_unit_v1`实际失败：短RGB旁路帧结束时旧CDF仍在建立，随后会重新激活过期LUT。增加持续poison直到新完整处理帧后修复；v1原始log/oracle保持，旧RTL按已记录pre-execution SHA逐字节恢复存档，明确为事后精确恢复。v2源副本也是测试后按原SHA保存；v3在执行前保存，均不篡改原失败结果。

`hci01_control_uart_unit_v1`真实vendor默认217clock UART位流，异步3ns相位、CRC/版本/模式/序号回绕、重复/旧/半窗口、半包20ms超时、RX起始位中复位、25→75MHz原子快照，共16检查通过。`hci01_status_uart_unit_v1`真实vendor TX八个64B包、四扩展word动态字段原子性和CRC/seq通过。

`hci01_frontend_isp_dbuf_joint_v1`：实际高字节CSI/ECC/CRC/RAW10/Gray FIFO/64×3裁切→完整ISP→新gray/Gauss/hist/post→真实异步DBUF，两个连续72×4源帧、96个128bit输出/12次FDMA user突发逐值通过。启动旧半帧中释放捕获，旧数据不泄漏，后续FS恢复；所有CSI错误和预处理错误为0。FDMA对侧为事务driver，不模拟加密DDR controller或物理PHY。独立pixel单位覆盖所有后级模式；此联合用例仅默认三种基础算法。

`hci01_reset_phase_v1`补充三个实际内部状态的复位：高斯EOL排空、Sobel末行排空、histogram CDF除法。每项先观察真实内部状态，再复位，确认旧output/错误/frame/LUT均清除，重放26帧独立oracle，共额外9360像素比对通过。这是RTL复位证据，不是板上复位或畸形帧恢复证据。

本轮完整TD native v1实际通过，记录在 `evidence/current_full_td_v1.json`，冻结156项输入、stage151文件，SHA核对无漂移。最终setup +0.259ns、hold +0.020ns、STNS/HTNS均0、STA覆盖99.49%；route资源30003/64320 LUT6、61/272 ERAM20K、70/240 DSP。实际124条warning及5条原加密DSI ODDR SYN-6024保留，不声称零警告或MTBF/SDF通过。bit：`reports/direct_build_20261010_220012_90216/fpga_prj.bit`，SHA `13e73d677d378109a80a1aedccbf9800e40db66c179f0dceade72b244adc8ab2`；对应prDB SHA `4d8088a9e7176036522cc3cd7bb354927e836a43a6aa391f633408f406070250`。

本版实际SRAM上板与独立raw复核通过：主37 `evidence/physical_hci01_v1`。真实HCIC七条命令逐CRC/seq核对，DSIF观察到该源帧接受的配置；30秒RGB旁路基准与九色实拍、all_three/luma/Sobel/threshold0 mask/erode/dilate六种模式，每轮源RAW/ISP帧推进，全部稳定CSI绝对计数、预处理错误和命令拒绝为0。九色实际XWD中心样本与原始UART均保存；RGB旁路主/次/中性色响应正确，处理模式RGB三通道和相等，threshold0三种mask路径为全零。Sobel的实物检查证明模式接受、灰度响应和持续帧，不把它说成实板逐像素golden；精确Sobel在数字oracle中覆盖。

相机基准帧率由50ms快照序号间隔计算约55.5705fps，未作外部时钟标定；不能用排队串口包除以主机采集秒数。显示读区仍为1080源左上1024×600/614400像素，不是1080缩放。实际完整恢复精确37 bit/runtime/控件/driver/boot/DMA空闲并新抓32帧，每帧6220800B且无错误；窗口已关闭。DSI光学像素与动作到光子延迟未测。

HCI02 ROI/CCL/SAD、HCI03 ROI压缩/MIPI/RK接收、HCI04按钮/光电/PWM/传感器开窗仍属于扩大目标后续工程，未被本例全部代替。HCI02已独立复制完整输入基线，尚未完成新功能或验收。

## 构建和安全恢复

在新的完整副本重定位`.al`，按skill重新生成`build_direct_config.tcl`，保留high hold策略与debugger后async-reg识别，再运行本轮冻结检查/native入口。`build.tcl`调用完整direct flow。系统25MHz，ISP/新处理75MHz，视频50MHz；完整引脚/时序在`uisrc/04_pin`，新I/O仅UART RX V11。

自检入口在主37 `tools/verify_hci01_preprocess.py --attempt <新编号>`（全HD用`--full-hd-only`）、`verify_hci01_reset_phases.py`、`verify_hci01_control_uart.py`、`verify_hci01_status_uart.py`和`verify_hci01_frontend_isp_dbuf.py`。所有已有证据目录保持不可覆盖；换电脑先改入口中的Python/Icarus路径和项目根路径，再建立新证据目录。Icarus是当前实际RTL引擎；动态SDF/MTBF按 `docs/10_后续电脑MTBF_SDF复验prompt_20261010.md`在有兼容工具电脑补验。

`rk/hci01_control.py --port COM4 --mode rgb --threshold 128 --sequence <新序号> --out <不存在目录>`可下发CRC命令并等待遥测确认，序号必须比本次上电已接受值更新。该CLI自身尚未在实板调用；本轮实际HCIC和确认由守护入口完成。上板守护入口是主37 `tools/guarded_hci01_physical.py --demo 06 --attempt <新编号> --seconds 30`，该入口绑定当前证据和精确37恢复环境，换板/换机器须先更新连接及核对restore目标。

上板前必须本轮native/STA及所有相关数字测试正余量/同源核对，通过新的守护入口先核对37空闲、卸载/解绑再SRAM下载。从QUIESCE_BEGIN起finally恢复精确37 bit/runtime、真实32帧和驱动/boot/控件/DMA空闲。普通program脚本不含完整恢复。DSI屏幕的光学显示需要独立观察，光电端到端时延需要真实探头与可观测起点。
