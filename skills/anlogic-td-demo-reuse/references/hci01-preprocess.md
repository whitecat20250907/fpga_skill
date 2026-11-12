# HCI01实测完整预处理例程

2026-10-16 HCI09形状检查时序经验：自己门级实际路径显示，
`hci09_preprocess_identity`以32位`input_index % (WIDTH/4)`检查行末，
在1920宽下形成15级组合链；选中C版m_abort只有+0.069ns余量，另一等价表示D已跌至-0.056ns。
先读真实path，不用局部功能等价代签时序。独立候选
`projects/hci09_row_counter_20261016`及enabled副本用`$clog2(Q)`位行内计数替代该取模，
仅在`take&&accept_image`推进，与旧index保持同样的SOF、abort、reset和输出EOF覆盖优先级；
Q=1单独归零，保留32位总帧EOF检查，不增加接口流水延迟。
实际旧/新完整预处理511位端口逐周期比较累计1270257周期，9种尺寸含完整1080p RGB帧，
并验证行尾/EOF错误、身份变化、提前SOF、显式abort、背压中复位和多算法配置；
同时断言新行列值等于旧实际index取模。1..1024每一种Q的全部524800列转移另行枚举。
这是两态输入下的可达仿真和数学转移复核，非全设计形式证明；完整核心及自己的综合全局结果仍须单独验收。
证据在选中C的`evidence/row_counter_v1`、`row_counter_review_v1`和`critical_cones_review_v1`。

工程在 `projects/hci01_preprocess_20261010`，完整相机CSI/RAW/ISP/DDR/DSI/PLL/ROM/.al/ADC/SDC来自当前06 frameguard，新的真实ISP输出串接4像素/拍gray→Gauss→上一完整帧histogram→post→原DBUF。详见 [工程README](../../../projects/hci01_preprocess_20261010/README.md)。不要覆盖06或正式37，也不要继承parent的通过标记代替新工程验收。

当前可复用：gray `(77R+150G+29B+128)>>8`，3×3Gaussian边界复制/加8除16，64档生产直方图（256档参数实际单位测试），精确RGB128bit旁路，Sobel、暗mask、3×3腐蚀/膨胀；每级保持ready/valid元数据，行末与末行自行排空，SOF接受一次配置。首帧/常量前帧直方图identity；CDF使用完整计数和串行32周期除法。直方图创建/清空的实际背压要接到ISP ready，不能只将输出改线。

真实缺陷经验：短RGB旁路可能在旧CDF尚未建立完时结束，简单拉低LUT valid会被旧builder再次置高。持续`lut_poisoned`直到新完整处理帧后再解除。原v1失败/旧RTL SHA保留；v2/v3逐像素与后续实板通过的是修复版本。复用时测试连续SOF、RGB→处理切回、小几何、常量图、双向长停顿；不能只测单帧无停顿。

115200 UART RX V11（LVCMOS18/U42）、TX U11。`HCIC`16B采用标准CRC32、版本/保留/模式/新鲜序号校验，20ms已找到头的半包超时；25→75MHz配置用held-bus握手，然后在真实ISP SOF提交。默认三算法模式0/threshold128；mode1 RGB、6仅luma、8 Sobel、16/24/32暗mask/腐蚀/膨胀。低14bit配置`threshold<<6|mode`。DSIF word11源帧已接受seq；word12低14bit该帧cfg、bit14 LUT有效；word13预处理sticky错误，word14命令reject。不要把这些源端字段说成DDR/DSI正在扫描的帧标签。

当前证据：主37 `evidence/hci01_pixel_unit_v2/v3`累计4523576像素精确oracle；`hci01_reset_phase_v1`三个实际过滤/CDF内部复位阶段后再9360像素比对；真实vendor RX/TX、atomic CDC，以及实际CSI前端→完整ISP→新预处理→实际DBUF联合自检。加密PHY/DDR只由native/实板覆盖，单位使用FDMA事务对侧，不用stub证明整工程。

本轮native v1最终setup +0.259ns、hold +0.020ns、负TNS均0、覆盖99.49%；LUT6 30003/64320、ERAM61/272、DSP70/240，5条加密DSI ODDR critical warning保持透明。bit SHA `13e73d677d378109a80a1aedccbf9800e40db66c179f0dceade72b244adc8ab2`。不能从该正STA推出MTBF或动态SDF。

`physical_hci01_v1/independent_physical_review.json`复核真实7条命令、9个实际XWD源色、原始DSI6/DSIF CRC/连续seq、全部稳定CSI绝对计数/预处理error/reject为0、6种模式持续源帧。RGB旁路主次色响应正确；threshold0三个mask路径实板全零，其余处理灰度通道和相等。Sobel精确值由数字oracle覆盖，实板只声明实际模式/灰度响应/帧推进。相机约55.57fps按名义50ms快照序号计算，避免用已排队UART数据除主机读取秒数。当前显示是源左上1024×600，不能声称1080缩放或光学逐像素等价。

独立守护入口先核对同源native与数字门，再SRAM测试，finally关闭本次拥有的HDMI窗口、恢复正式37，核对完整driver/boot/控件/DMA空闲及新32帧。SRAM测试授权属于本会话；普通复用helper不能默认自动烧新板。DSI光学显示、动作→光子真值和完整HCI02–04仍独立待验。

后续HCI02联合v3发现额外未覆盖边界：帧间`pending cfg[0]`改变会在未接受任何RGB帧时提前poison LUT。v3实际acceptedRGB=0/idlePendingRGB=9996，第二帧identity与CDF golden不符。仅在`(in_frame&&frame_config[0])||(take&&s_sof&&selected_config[0])`失效，v4/v5联合精确通过。修复在HCI02和独立`projects/hci01_lutguard_20261010`；旧HCI01包保持原SHA/实际已测scope，旧bit没有因此被修好。复用控制时增加“无valid帧间pending配置干扰”的自检，不只测试帧内噪声或连续SOF。

当前优先复用 [完整LUTguard修订](../../../projects/hci01_lutguard_20261010/README.md)：376376+4147200像素、内部reset、真实CSI/ISP/DBUF均通过；本版native最终setup +0.207ns/hold +0.020ns、负TNS0、覆盖99.49%，29968LUT6/61ERAM/70DSP，bit SHA `6f14678a05ec2bfcdcd7100a5a5556ecd21075679a687bd7f57fc1b24ef8ecd2`。本版独立`physical_hci01_lutguard_v1`原始9源色/7命令/6模式、绝对CSI/预处理error/reject0及正式37新32帧恢复通过；相机按名义快照间隔约55.5629fps。旧HCI01 bit作为历史已测版本保留，选当前bit使用LUTguard入口和对应native/guard，不能混用旧源与新bit。


2026-10-15 F10验收可观测性审计：当前物理候选hci01_rgb_contract_20261011仍使用dsi_frame_stats导出像素数和RGB总和。对实际同SHA模块执行8×8实RTL自检：中央4×4实块与16个离散点形状不同，但都产生64像素、16前景、RGB和4080/4080/4080；只有帧计数递增。说明UART CRC保护传输内容，并不能证明未传输的空间形状。证据主37/evidence/F10_observability_v1。F10不能通过更换非空图案后仅看总和签核；下一完整独立候选需保存同一接受帧的post输入halo和输出ROI、原点/模式/阈值/帧身份，处理partial/stale/reset/覆盖，独立逐像素参考后再自己的native/实际测试。已有数字形态学证明仍保留，现有空掩码实拍范围不扩大。


F10同帧像素观测组件候选：[hci10_morphology_trace_20261015](../../../projects/hci10_morphology_trace_20261015/README.md)。默认64×64输出ROI和72×66输入halo，同一接受帧/配置，完成后占有RAM到释放；复位/取消/错误/越界拒绝旧数据，观测不产生图像背压。12项异常与所有权自检、三个1080p实际post帧的生产RAM边界及捕获区域14256输入/12288输出像素独立参考均通过。输入源函数与输出位行oracle独立核对；整帧只验结构/计数。当前尚未接完整top/UART，也没有本候选native或实拍，不能继承父bit通过。串口接入必须跨域请求/回复握手、包CRC/请求号/帧号/配置与范围校验，并覆盖取消/复位/断联和重复/丢失分块。


F10串口/顶层集成当前入口：[hci10_morphology_uart_sdc_20261015](../../../projects/hci10_morphology_uart_sdc_20261015/README.md)，完整160输入；功能/工具及数字证据在相邻hci10_morphology_uart_20261015。独占解码HCIC16/HCIT24，三FF toggle请求回复、同位保持payload、HCTR64响应、CRC/请求ID/帧号/配置/范围保护，实际vendor RX/TX串行波形与主机逐像素复核通过。CSI完整ISP下夹具原ROI腐蚀全空，即使全像素参考吻合也不得计非空专项；保留失败后只移ROI，新ROI腐蚀13/32、膨胀30/32，完整1536 post像素和halo/ROI读回精确，384 RGB字/48 FDMA用户事务顺序正确。encrypted PHY/真实DDR/实拍仍待。SDC解析器拒绝多行if，完整副本改单行、26.666/80ns约束值不变后gate完成；实际请求映射部分带本域控制B与非A门，按网表局部控制cone审计，115请求+409回复共524有效路径。gate setup -2.557ns来自DBUF→post ready反馈；后续独立副本处理该路径并重验，未取得自己的正STA/bit前不得上板签核。


F10显示ready反馈修订：[完整162输入工程](../../../projects/hci10_morphology_ready_cut_20261015/README.md)。将RGBX与SOF/行尾/帧尾/配置作为145位整体进入两槽缓存，ready仅依赖本地count，缓存与真实post共用S_video_rstn；被动trace仍观察post实际接受事件。验证必须使用合法保持valid/data的源，覆盖满缓存复位、连续吞吐、每个标记和配置身份。当前4783传输及20次复位、实际UART、含两端真实RGB转换的完整CSI/ISP/DBUF数字链通过；非空ROI和1536像素参考精确。数字通过不能代替本候选mapped reset与端点时序；原生审计队列独立记录，旧版-2.557ns不能当作新版结果，缺少filtered timing报告也不能宣称零路径。


F10空间滤波器时序修订：[完整emit_select工程](../../../projects/hci10_morphology_emit_select_20261015/README.md)。不要让下游advance/ready参与异步行RAM地址选择；在真实操作域证明flush_pending与flush_now等价后，可使用寄存状态作emit列/行/bank/水平像素选择，原写入及输出使能不变。必须同时验证无操作周期地址变化没有写入或输出副作用。当前与冻结父版12组60万周期的完整接口及实际RAM操作一致，并通过实际UART与含RGB转换的CSI/ISP/DBUF非空独立参考。时序需读取本副本native终态，不能以数字等价或父版裕量代替。


F10 emit_select本版综合最终setup+0.265ns/TNS0，post全部32D/32CE最差+0.584ns，524位握手及复位审查通过；这是自己的gate结论，routed/物理仍待。完整build已在full_native_queue_v1按前序终态与真实进程空闲串行排队。实拍复核使用tools/review_capture.py，从CRC有效原始串口重建全部owned块，核对身份/顺序/释放，与72×66 halo独立计算64×64 mask/erode/dilate逐像素比较并要求前景/背景并存；无关遥测首尾残片可报告保留，不能放宽捕获块完整性。复核器v2用生产尺寸RTL像素包装测试记录，三个模式和九个错误拒绝通过，不能将测试记录标作物理UART。
