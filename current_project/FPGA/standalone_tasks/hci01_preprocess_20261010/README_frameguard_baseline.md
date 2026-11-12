# 例程06完整跨帧守护修复候选

从完整 `demo06_dsi_flow_20261010` 保留所有IP/ROM/CSI PHY/DSI PHY/PLL/DDR/ADC/SDC及只读UART分级观测，在独立目录修复连续帧写入。入口 `fpga_prj.al`/`build.tcl`，PH1A90SEG324 −2。本目录已完成完整TD、实际CSI/ISP/DDR读出及九色RGB响应验收；光学DSI屏幕目视结果尚未取得。

实际自然CSI数据→RAW10解包/Gray FIFO/64×3裁切→完整ISP→真实异步DBUF联合仿真，前版在burst5时写地址提前回帧起点而失败；原先RAW→ISP→DBUF测试等待前一帧全部写完才发下一帧，未覆盖此问题。新用例不等待前一帧写完就连续发两个72×4 CSI源帧，保留payload有效间隙、逐header ECC/逐payload CRC和FDMA停顿。修复后同用例96个128bit RGB拍/12次user FDMA突发/两个SOF/行尾/数据和零CSI错误通过，详见主37 `evidence/dsi06_frontend_isp_dbuf_joint_v1`（失败）、`v2`（通过）。它不模拟加密PHY、真实DDR控制器或物理颜色。

DBUF将合法的下一帧SOF保持在AXIS输出，等待上一帧写FSM idle且FIFO empty，停止在正常下一帧到达时清空未写完的上一帧FIFO。ready将此等待传回弹性ISP和前端FIFO。CSI/ISP启动条件使用真实DDR calibration done、相机配置完成与PLL lock，分别在HS/75MHz本地域释放复位，解析器从新的FS才出payload，避免DDR尚未接收或相机仍在重配置时积压旧像素。该实现针对正常完整连续帧和启动；任意坏帧/无穷停顿的恢复能力需要独立证明，不能从本次正常帧测试推断。

warm v4联合用例已通过：传感器在捕获未就绪时发送旧帧，捕获在RAW数据中途释放且没有新FS，旧像素不进入ISP/DBUF；后续新FS下两个完整帧的96拍/12突发正确。v3最后计数期望仍为8而此用例额外发送了一包无FS RAW，应为9，观察代码生成顺序修正后v4通过，生产源不为观察期望修改。证据主37 `evidence/dsi06_frontend_isp_dbuf_joint_v3/v4`，仍不覆盖整个加密顶层或真实DDR/屏幕。

系统25MHz/ISP75MHz/视频50MHz/实际PHY HS源时钟；UART U11/LVCMOS18，经板载U42，当前COM4/0403:6042/AL7A9AF422B。无新物理引脚。完整约束在 `uisrc/04_pin`，UART交替DSI6/DSIF和完整协议见 `README_flow_parent.md`。数字UART8包512B原子字段/CRC/序号与本目录相同发送源已通过；封包CRC源也与前版53568payload字节数字测试一致。

完整native通过后，实际入口为主37 `tools/guarded_dsi06_frameguard_physical.py --demo 06 --attempt 新编号 --seconds 30`。入口核对当前输入/bit/STA、数字源同一性和正式37空闲，下载到SRAM；九个已知HDMI颜色保存actual XWD、原始UART、CSI新增错误及RAW/ISP帧推进，保持所有失败证据。finally关闭本次自己的窗口并恢复精确37/runtime、真实32帧及模块/boot/空闲。图像更新必须由变色场景或帧身份证明：第一次灰色固定源下RGB统计不变只是疑点，已确证的前版物理失败是overflow持续增加。

原六例程、前版失败和诊断候选、SDK、许可与RK boot保持原样；不自动写Flash或NVM。重新构建生成路径配置时保留 `--fix-hold-high` 和debugger后async-reg策略。实际新native/bit结果须独立核对；SDF/MTBF工具项按用户暂计授权和后续复验prompt处理。

## 本版实际结果与下载选择

完整native入口 `evidence/current_full_td_v1.json`：退出0，冻结输入及144项staged依赖核对无漂移，setup +0.652ns、hold +0.020ns、TNS均0、STA覆盖99.13%。120条警告中保留5条保护DSI ODDR SYN-6024，范围见原生报告。当前bit为 `reports/direct_build_20261010_202425_70080/fpga_prj.bit`，4850318B，SHA-256 `808874031e91c552d8f0403e65893c73dd185900b8e82003bd9c9bf5e4e43472`；同轮prDB SHA `111ea9a3d92e498a6817e80f15f0f731061e121f249e4306cf66065f63901d27`。冻结manifest SHA `ef71b5cff424e310347a4849c1b8a33eaa893b237f8a9fd2800deb6958f74ab6`。

实际证据在主37工程 `evidence/physical_dsi06_frameguard_v1`：30秒基线302个连续序号/CRC正确包，RAW与ISP SOF各7→1674，有效数据持续推进，全部CSI CRC/ECC/WC/overflow/timeout为0。9色实际RK XWD源与原始UART独立复核：红/绿/蓝主通道响应正确，橙/青/品红的次色组合正确，白>灰>黑三个通道均成立。统计范围是相机视野内的整窗平均响应，不是逐像素色度学精度认证。

`independent_physical_review.json` 状态为 `PASS_INDEPENDENT_CURRENT06_RAW_CSI_ISP_DDR_READ_RGB_RESPONSE_AND_RESTORED37_ONLY`。测试后关闭本次HDMI窗口、恢复精确正式37/SGDMA36/V4L2_37/boot及参数，新的32个1920×1080 RGB24帧均6220800B且无错误，最终无打开client且DMA空闲。

本版sensor接受帧率按25MHz系统的50ms快照序号间隔测得约55.56fps；串口打开可能先排出旧缓冲包，不能用主机配置4秒除首尾计数。该数未作外部时钟标定，不是物理端到端延迟。显示读窗为DDR中1920×1080图的左上1024×600，步长1920，屏幕614400有效像素；没有声称全1080缩放显示。

原13项的05/06光学屏幕观察仍须另记。用户确认屏幕已接入，不等于此bit的实际屏幕画面正确；本轮 `physical_panel_appearance_verified=false`。MTBF/动态SDF暂计验收依据与后续电脑复验prompt见主37统一交付索引及 `docs/10_后续电脑MTBF_SDF复验prompt_20261010.md`。
