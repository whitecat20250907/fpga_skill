# DSI CRC与当前帧观测

2026-10-21新增[FPGA MIPI算法仪表盘](mipi-algorithm-dashboard.md)。数字孪生预览、自己的TD位流、真实遥测和实屏共存分别验收；原05相对路径/字体初始化经验见该页。

修改DSI视频封包、调试05测试图或06相机显示时读取本页。当前选择是完整 `projects/demo05_dsi_crc_20261010` 和 `projects/demo06_dsi_frameguard_20261010`；下文CRC/flow版06失败属于保留历史。统一当前索引见主37 `deliverables/current_delivery_index_v1/index.json`。

## 封包规则与数字验证

`dsi_video_mode_packet.v` 的 `CRC_ENABLE=1` 使用反射多项式0x8408、初值0xffff、不做末尾取反。每拍四个实际payload字节按lane0到lane3更新；低16位输出CRC，高16位是四lane对齐填充。保持原header ECC字节布局、payload/valid/last流水线。`CRC_ENABLE=0` 显式保留原零CRC footer兼容模式；不能仅凭原footer为0断言原屏幕有故障。参考[DSI控制器CRC参数](https://docs.amd.com/r/en-US/2026.1/pg238-mipi-dsi-tx/User-Parameters)。

边沿线网声明应在引用它们的时序逻辑前；Icarus第一轮实际绑定失败已保留。真实两项目封包源在4/8/16/64/1024 RGB像素、零/全1/递增/随机图样下与独立bit串行oracle比较，共53568个payload字节；另与原vendor CRC方程核对3072字节。真实UART发射位流4个64B包、动态字段原子性、CRC32也通过。详见主37工程 `evidence/dsi_crc_telemetry_unit_v2`。该范围不覆盖加密PHY、光学屏幕、异常半包复位或动态SDF。

## 帧观测与协议

`dsi_frame_stats.v` 从实际vsync/de/RGB统计完整帧的像素数及R/G/B和，只计DE有效像素，帧边界锁存。05取测试图源；06必须取实际DDR读出 `S_ud_rtdata`，不能取未使用TPG。异步观测使用已验证的 `csi_stats_snapshot.v` held-bus/toggle握手：请求/应答两级、源/目的释放各三级，不能把统计总线逐位两级同步后认为原子。

系统25MHz，视频50MHz，06 CSI/ISP75MHz，UART115200 8N1、100ms一个64B只读包。COM4须实际枚举0403:6042、serial AL7A9AF422B；TX球U11/LVCMOS18，经板载U42。没有串口命令，不写EEPROM/RTC/Flash。其他主机先核对自己的设备身份。

16个little-endian u32依次为：magic (`DSI5`或`DSI6`)、版本0x44530101、连续sequence、flags、framecount、上一完整帧像素数、sumR/G/B、CSI rawpacket、CRC/ECC/WC/overflow/timeout计数、前60B的CRC32。flags bit0PLL、1屏配置完成、2DDR完成（05恒1）、3视频快照有效、4CSI快照有效。当前1024×600完整帧期望614400像素。检验首个完整包之后的CRC/连续序号，保留打开时半包和结尾半包；CSI初始错误计数不可清零冒充无错，应独立检查稳态新增量。

## 构建与实物边界

新05首次完整native暴露观测ack跨钟保持违例−2.437ns。`insert_debugger`会复位异步同步器识别开关，须在debugger后、RTL优化/布局前按当前helper重新启用，核对实际gate/place/route属性，并使用已验证的high hold策略。不能删约束或添加宽泛false path。修订后的05 setup+7.864/hold+0.020ns，06 setup+0.652/hold+0.020ns，TNS均0，覆盖分别99.67%/99.11%；两者5条厂商加密DSI ODDR复位警告继续保留。

05当前bit 5beababff5ddd31ac2896f6173acecc1569f2279ae3dfdd5909335906cbf87b5，实际90秒899个连续CRC正确包、5261帧推进；红绿蓝白完整帧统计均正确。实测后精确恢复37并新抓32帧。证据 `projects/pcie_imx415_bar_contract37_20261010/evidence/physical_dsi05_uart_v1`。这证明真实FPGA视频源/遥测推进，光学DSI显示需另有操作者观察；不可自动归为整屏验收。

06当前bit 725df5ee7baef1acf21482ea5119e83f39f7d60b5670d9891008d8ee516e6f2e；实物与RGB测试结果按当前证据目录独立读取，不从其STA或05结论推断。已知RGB源测试保留RK的实际XWD像素、相同scene身份和原始UART，测量全帧响应时明确视野/色度学限制。测试窗口只能关闭本次实际拥有且cmdline一致的进程，不能用旧PID文件停止别人的窗口。

当前06 CRC版首次实测未通过：30秒299包的CRC/序号正确，rawpacket39260→1855559，视频帧39→1785，但overflow19061975→901783289，DDR读出RGB和完全不变。失败raw和恢复37/新32帧结果保留，不能将这版宣称为相机/屏幕通过。随后源审查发现CSI计数器实际在 `S_hs_rx_clk` 产生，旧新增快照接 `S_clk_70m` 会在握手之前直接跨多位计数器，违背held-bus前提。快照必须在计数器自己的实际源时钟域锁存；不能因目的端使用握手就称任意接入总线原子。

独立完整 `projects/demo06_dsi_flow_20261010` 修正该快照源时钟，增加75MHz的RAW/ISP接受拍数、SOF数、RAW停顿数、DBUF写端标志，使用第三个同域握手快照。串口交替 `DSI6` 和 `DSIF`，共享连续seq，每个包仍64B/独立CRC；实际vendor UART位流8包的交替类型/原子字段/CRC数字测试通过。分级观测当前用于定位真实冻结，不能当作冻结问题已修复。`DSIF` word4..10为RAW接受拍数、RAW SOF数、ISP接受拍数、ISP SOF数、RAW stall周期、flags、快照status。flags bit7视频复位释放、6 DBUF near-full、5写FIFO reset、4写同步done、3写ready、2写valid、1 RAW ready、0 RAW valid；这些状态属于75MHz写域，通过显式模块输出端口传出。

上述06首次30秒实测的HDMI源一直是灰色：RGB和不变仅是冻结疑点，实际画面更新须用已知变色场景证明。已经确证的失败是overflow持续新增；不以固定输入下的固定统计替代更新测试。

随后分级版实际九色源/XWD/连续UART独立复核，确证冻结：各色的RAW接受9111拍/2帧、ISP接受8123拍/2帧及RGB和完全相同，状态0x85。此状态是写valid1/ready0/同步done0，近满和写复位均0；前端overflow增长，CSI原始packet继续推进。相应证据在主37 `evidence/physical_dsi06_flow_v1`；计数器32位在长测试中会回绕，使用模2^32差值并保留回绕事实，不能将绝对值下降解释为停止或清零。

真实CSI→完整ISP→真实DBUF的连续两帧联合测试复现下一SOF到达时前一帧最后写突发尚未排空，原DBUF清空同步状态造成丢写/挂起。只分别测frontend、ISP、DBUF或先等前帧完成再发下一帧不能覆盖这一连接行为。独立完整 `projects/demo06_dsi_frameguard_20261010` 让合法下一SOF经ready等待前帧FSM idle且FIFO empty，保留未写完数据。启动还等待实际DDR calibration和相机配置，在本域释放后解析新FS，避免接收重配置中的旧半帧。正常同用例96个RGB128拍/12个user FDMA突发/帧标记/数据通过；另从无FS的旧RAW半帧中释放捕获，确认旧像素不泄漏并恢复两个完整帧，warm v4通过。v3因新增的前FS RAW packet使总计应9而测试生成顺序仍保留8，原观察失败保留，修正最终期望后通过，生产源未为此修改。完整新native/实际PHY/DDR/屏幕尚须独立核对，不从数字通过推断上板修复。

当前frameguard版实际完整native通过：setup +0.652ns、hold +0.020ns、TNS0、覆盖99.13%，144项staged依赖匹配。当前bit SHA `808874031e91c552d8f0403e65893c73dd185900b8e82003bd9c9bf5e4e43472`。实际30秒与九色场景，RAW/ISP接受拍数及SOF持续推进，CSI全部错误计数为0，DDR读出的614400像素RGB统计随实际HDMI红绿蓝、橙青品红及白灰黑正确变化。所有source XWD像素/原始UART/CRC序号/同域流量/精确37恢复和新32帧已独立复核，证据为主37 `evidence/physical_dsi06_frameguard_v1/independent_physical_review.json`。5条加密DSI ODDR警告保留；光学屏幕仍待用户实际观察，不能从遥测替代。

接受SOF帧率按25MHz系统的50ms快照序号间隔约55.56fps；打开串口可能先排出缓冲旧包，不以主机4秒捕获时长除包含旧包的首尾计数。32bit计数器用模差，保存真实回绕。当前DDR读窗为1920×1080中的左上1024×600、步长1920；显示614400像素不是整幅1080缩放。九色统计证明粗通道响应，未证明逐像素色度学或物理端到端时延。

SRAM测试前检查正式37版本/驱动/boot/空闲、卸载并解绑；从QUIESCE_BEGIN起finally必须恢复精确37 bit/runtime，再真实抓32帧并核对只读元组。连接屏幕不能代替屏幕显示结果；数字/STA/视频源/CSI/光学屏验收分别记录。
