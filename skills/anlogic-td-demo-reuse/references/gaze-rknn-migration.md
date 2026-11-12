## Freeciv原生游戏与既有模型接入边界

用户已退役旧PvZ/扫雷，当前游戏为`freeciv-rk3576-gaze-demo`原生单地图军事版。真实RK3576已完成ARM64构建、键鼠与UDP整局战斗、生产增援/占领/服务器胜利；当前验收和维护步骤读取该仓库`BOARD_TEST_REPORT.md`与`PORT_TASKS.json`。游戏使用唤起、确认、取消、下一部队、结束回合五动作、动态目标中心吸附和确认后休眠，不沿用旧游戏固定网格。

复用主程序连续视线输出时，使用实际X11地图矩形及坐标原点，不把HDMI高度或包含DSI的根窗口高度当地图范围。接口可在原回调中低频查询几何，不另起摄像头或推理；持续动作须按原识别结果的保持/释放边界去重。可选包装入口在原模型导入之前锁定原`gaze.lock`，原主程序持锁时必须拒绝重复实例。原手势入口和定义未取得时保留为缺项，不自定义五种新手势。

独立/并行静置、选点、战斗的CPU/RSS已测。所有主程序对照窗口均为无脸PREVIEW、NPU调用0，不能把处理更新率或CPU人脸检测耗时写成NPU FPS/延迟。UDP测试坐标、完整脚本战斗和inert锁测试也不替代真人个人标定、原手势联动或实际控制成功率。

## 历史v182可复用边界

串口分层：HCK控制/首写ACK通过不代表root27、BYTE、PHY训练或RAW通过。缺HCP记录是缺测，停钟后的旧窗口/旧held snapshot不作为新进展；需最近窗口序号与源handshake持续推进。17项本地诊断和存量RAW0解码不代替新板测。

同一Python进程启动和F10时必须保留原Popen，活态登记实际argv/PID/startticks/PPID/PGID/SID；只有本父进程已验证的退出子launcher才可精确非阻塞回收，再跑原完整session/FD守护。JSON不能重建回收权限，不能泛化忽略Z；实际inert通过也不替代生产路径验收。

有限UART查询只在发请求前用两条连续CRC-valid legacy对齐；窗口内不重同步或跳过旧回复。legacy半包可跨请求，发送前开始的clock包不能成为因果回复。记录有界raw及逐read/write偏移、计数、QPC和异常；sample必须绑定回复末字节所在read，不能只保存逻辑sample时间。软件transport不代替真实串口/FPGA时钟/帧延迟验收。

现机prepared headers/UTS/API exports、模块ELF/undefined差异和归档SHA闭合只签独立编译，不能签可加载性或真实增益行为。用户认可当前镜头后以动态CURRENT和最新反馈恢复，不能照搬历史app24或旧画质结论。

Windows文档做字节级换行修正时read_bytes/write_bytes成对使用并留前后快照；写新UTF-8正文时显式编码/newline，避免CRCRLF倍增。

# v179 补充：独立预览与异常提交的可复用经验

同一个native camera owner可同时提供原1920×1080 processed RGB预览和640×360模型输入；保持模型MCF、rect、原RKNN/NPU及控制文件语义。不要为预览再次打开摄像头。

本例使用sealed memfd（禁止grow/shrink）、64字节元数据和有界单槽RGB。C生产者用POSIX F_SETLK，Python用lockf，双方锁同一byte0/len1并非阻塞获取；拿不到锁就跳过预览，不能拖住模型采集。继承的flock依附同一open-file-description，父子可能共享锁归属，不能拿它代替这里的跨进程互斥。Python再以threadlock覆盖lock/read/unlock/close，避免线程间并发与关闭竞态。

Python mmap可能复制文件描述符，检查owner时记录全部指向该memfd的FD，不能硬断言只有一个。reader在锁内复制私有像素并验证header；停止、线程退出及close遵循同一threadlock，原生子进程退出后才关闭map/FD，不能留下逃逸的共享numpy视图。

writer持record锁仍不足以防异常死亡：进程死后内核自动释放锁。app26在重写payload前保留旧valid header，可能把半写像素当成未消费的旧帧；该试验已回退25，不能用正常退出通过忽略此反例。27/28先以对齐atomic32清valid_bytes=0并执行全序fence，再写payload和valid0元数据，最后release atomic提交完整长度。实际SIGSEGV在生产publish复制中发生的ARM反例证明锁已释放、valid仍0且reader拒收；这里只覆盖该异常提交语义。

预览读取失败或源/发布时间超过500ms时，显式stale并回退模型预览；1080预览不套用旧640模型检测框。10/15/20发布上限是节流配置，不是实测HDMI或NPU FPS。

显示耗时要在实际尺寸测量。本例raw1080先精确INTER_AREA 2:1缩至960×540，再建pygame surface，离线三真实RGB路径约4ms，原先先建全分辨率surface再缩放约31ms；GUI像素另与OpenCV逐字节核对。非整数972×547的AREA仍慢，不能把4ms推广到其他尺寸或称为真人FPS改善。模型640输入保持等3×3均值。

root已查看当前app28实际HDMI截图与同一native共享槽直接取得的processed RGB1080：暗部彩噪在进入HDMI前的处理RGB中已可见。这不是sensor RAW10，也不是同帧光学对照；肤色、阴影和整项画质仍未验收。低码RAW/Gamma数学路径只证明可充分产生残余偏绿，不能认作全部实机彩点的唯一根因。

当前仍是SRAM51/stage0/gate0/app28（61305/61347），Flash37及原NPU保持。重启窗口17.80次模型更新/秒、共享槽16.26次发布/秒，NPU调用和valid行均0；不能宣称20fps或性能全部改善，25约18.7次更新/秒仍略高。

证据及本次补充快照：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v179/skill_experience_update_v1/publication.json`。原v179发布、全部83+12+47及status保留。

# v179 当前app28与异常提交边界

当前CURRENT已实际发布app28，SRAM51/stage0/gate0及原RK3576 NPU保持，模型61305、采集61347。app26试验未留用：全1080表面再缩放有CPU开销，且发现writer死亡后旧valid头可能覆盖半写像素，已干净回退app25（60370/60412）。独立app27只修原子valid0→像素/元数据→release提交；app28在此基础仅改显示表面/960×540 widget，105源104继承同27。真实ARM三RGB/原模型oracle、跨进程锁、SIGSEGV后invalid拒收及GUI像素证明通过；同一原生采集提供独立processed RGB1080预览，模型仍是等3×3均值640×360。app28实际F10正常退出和重启通过，root已查看HDMI并留用，但无正脸窗口不能验收肤色、阴影、控制或整项画质。

app28 start窗口18.05次模型更新/秒、原生预览slot 16.08次发布/秒；重启后分别17.80和16.26。两窗口NPU调用和有效行均0，不能称20fps实际HDMI、真人推理FPS或NPU提速；26约16.7处理更新回升，但仍略低于25约18.7，不能说性能全部改善。离线同RGB UI由先建大表面再缩放约31ms改为整数2:1 INTER_AREA到960后建表面约4ms，属于CPU显示路径耗时，NEON无明显收益且未部署。

保持CURRENT选中的51/stage0/gate0/app28及绑定原NPU，明确app25 fallback；Flash37不变，USB/RK CSI/AIQ仍隔离。继续剩余真实阴影/肤色与有效NPU处理率、个人13点标定/20点留出、眨眼/游戏；逐帧颜色归因需同源同帧RAW及实际AWB/曝光和暗场/中性色标，不能按椅子低尾猜阈值。保留T08失败原件并推导实际约束端点，不猜负slack或删约束。完成同一F15 observe2 native64204及自己的完整静态/物理审查，不重复启动或提前签核。全部83+12+47状态保留，RK精确源码/安全停流与真实双摄仍待。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v179/actual_app28_T08_observation.json`。全部83+12+47及status保持，未扩大画质/光学/整机验收。

# 历史v178：当前应用与限定证据

当前实际为SRAM51/stage0/gate0与app25原RK3576 NPU（模型58961、采集59003）。app25把1920×1080 RGB3按等通道3×3均值缩至640×360，原权重和NPU输入语义保持；实际F10退出及默认重启通过。局部颗粒减轻，但用户仍反馈HDMI画面不好，画质/真人肤色/操控未验收。20秒窗口18.75次更新/秒、NPU调用0及有效行0，只是无人脸预览，不能宣称推理FPS改善。三张实际帧的标量area3与OpenCV全字节一致，较中心抽样增加约2.6ms；NEON v1的编译告警失败保留，独立v2 ARM六图案及三真实帧/2300除法输入均通过，但中位加速0.96×/1.03×/1.09×无明显收益，未部署。Flash37保持，USB和RK CSI/AIQ继续隔离。

独立只读显示检查为HDMI RGB888 full/1920×1080p60，实际1920到1920无scanout缩放，CSC y2r/r2y均0，xrandr Gamma1/brightness1；这些配置不代替光学画质验收。另20秒无人脸窗口374行/18.7updates/s、NPU调用0：CPU人脸检测中位44.65ms/p95 56.35ms、输入年龄中位30.94ms、样本年龄104.06ms，是该窗口主要CPU开销，不能叫NPU低FPS。大核2.112GHz/约64℃，快照未见降频；根盘1.87GB及userdata3.61GB可用，不是当前空间阻塞。

保持CURRENT选中的51/stage0/gate0/app25及原NPU；画质仍不接受。下一步在独立app26候选验证同一native采集的1080p预览与640×360模型输入分离，当前仅本地准备、未部署；不把NEON等像素通过当性能收益。完成同一T08 native后依次核自己的最终STA/CDC/新4FF/物理IO/位流与实板32次nonce查询；F10旧队列已取消，需重新明确自己的构建前置，不再写排队等待。F11继续限定CSI层级诊断，RK匹配源码/安全停流与真实双摄、真人标定/眨眼/游戏及全部83+12+47范围继续保留。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v178/actual_app25_T08_observation.json`。该版本保留83主项、12正式项及47 RK子检查和全部status，不增加验收。

# 历史v177：实际HDMI已切换高精度51

51高精度ISP已实际更新SRAM并留用于HDMI，原app24/RK3576 NPU已恢复（模型57543、采集57585）。修复链路在去马赛克/CCM/AWB中保留10bit，Gamma后转8bit；320源数字门、原完整native加独立物理优化、最终setup +0.009ns/hold +0.020ns且TNS0、四CSI和50ERAM均通过。root亲自查看三帧1920×1080 RGB3及真实HDMI；当前椅子/窗帘场景绿块明显减少。相同HDMI预览区域通用绿优势像素19.87%→1.15%，三帧原分辨率1.56%–1.63%；前后采集时间不同，当前无正脸，不能据此验收真人肤色/操控。Flash37保持；USB1与RK CSI/AIQ仍隔离。

以CURRENT_CAMERA.json选中的51/stage0/gate0/原app24为后续恢复目标，47仅作明确fallback；不要调用旧硬编码47/gate2恢复器。继续真人肤色/阴影/双眼、原NPU真实处理帧率及延迟、13点个人标定/20点留出/眨眼与游戏操控；另核640×360抽样预览的细节损失。全部83主项+12正式项+47RK子检查保留，内核源码/真实双CSI等依赖和未验收范围继续推进。

证据：`projects/pcie_imx415_linear_precision51_20261019/evidence/actual51_pixel_review_v1/result.json`、`projects/gaze_model_migration_v1_20261014/evidence/current_precision51_actual_v1/current_camera_selection.json`。HDMI与DSI同时启用时，应保存完整XWD并按实际HDMI viewport无损裁取，不能要求根窗口等于1080高。app24软件RGB/BGR往返抵消，未发现预览独有颜色滤镜；中心抽样640×360再放大的细节损失仍需另验。

# 历史v176：完整native结束与物理修复

51高精度ISP的完整320源native39120已结束：setup=-0.108ns、hold=+0.020ns、STNS=-0.108ns；不满足下载条件。唯一失败为CSI第2路接收器复位恢复路径，原源/IP/约束与50一致，最终同步寄存器位置/布线改变导致。root正以原51 routed DB的独立副本执行post-route物理优化，原失败证据保留；这属于完整源构建后的物理优化，不冒充重新完整构建。HDMI仍为47/gate0/app24。

完成当前同一物理优化进程，严格核正setup/hold及零TNS、四CSI路径、50ERAM、320源/约束/CDC与新DB/bit身份后更新SRAM51；采实际RGB、恢复原app24/NPU并核HDMI，再决定留用51或先停模型/解绑DMA后同一BW恢复47。Flash37保持；继续真人颜色、处理帧率/延迟、标定/操控及83+12+47全范围。

# 历史v175：完整native运行快照

51高精度硬件候选已完成并冻结320输入及450引用：实际RAW8整帧16384像素完整ISP/真实AWB增益更新/背压、连续多帧AWB及4K33bit累加、全码tone/sat与完整CSR读路由反例通过。root已实际启动自己的native39120，最终setup/hold、四CSI、缓存及bit未通过前不下载。HDMI仍为47/gate0/app24，离线重建改善不是新ISP实机验收。

继续同一39120完整native，不重启构建；核自己的最终setup/hold/TNS、四CSI物理路径/50ERAM和320源/bit身份。通过后用同一BW受控上板51，采真实RGB并在51恢复原app24/NPU和HDMI预览；root按实际图像决定留用51或先停模型/解绑DMA后恢复47，Flash37保持。再逐项完成真人肤色/双眼、处理帧率/延迟、个人标定/操控及全部83+12+47剩余范围。

# 历史v174：实际RAW与HDMI修复候选

诊断50自己的319输入native14708已终态1277.328秒、returncode0，setup+0.040ns/hold+0.020ns、TNS0，四CSI物理lane与50ERAM证据通过，bit85188a64；这些是静态和数字证明。actual_v1被系统盘预检拦截，actual_v2在主机JSON结果解析失败，失败证据及versioned parser修正保留；actual_v3在首次原生采集前被ISP8 capability helper拒绝，真实RAW帧为0。冻结50的读选择范围仍到0x188，新case0x18c/0x190/0x194未纳入路由，实际导出失败，不能拿静态PASS签核RAW或根因修复。随后actual_v4采用精确50 bit、真实CTRL停止及全帧标记的限定RAW-only方法，已取得扣黑前/后各2张1080p共8294400像素；每stage31接收/81采集/50软件丢弃、原生结束及清理0，未签processed阶段或stage读回。同一BW85744已恢复47/gate0/app24，当前PID仅取显式CURRENT。实际RAW同帧反事实支持过早RGB8量化、共同CCM/Gamma放大绿色的路径：四帧统一RGB8绿超差指标由31.43%–32.62%降至保留10bit方案8.40%–9.07%，并恢复暗部连续信号；这是GBRG/共同unity AWB假设、CNR前软件重放，场景无正脸，不是新ISP实机验收。51独立源码正在实现，尚未启动native。系统盘已转存4目录576文件到userdata并保留原路径链接，删除11个与本地同SHA的重复包；journal、当前app/session/模块和原图目录保留。原始绿点、真人颜色/细节/噪声根因、F11/T04其余验收、RK CSI匹配源码/双摄、个人标定及游戏全部仍按固定83+12+47口径保留。

当前47/gate0/app24、PID56475/56519，以根CURRENT_CAMERA为准。51尚未生成自己的新bit，离线重建改善不能称HDMI已更新。

下一步：完成独立51的10bit去马赛克、CCM、AWB统计/精确除法及帧界锁存、原Gamma表低2bit插值与饱和度0恒等；以实际RAW和独立RTL参考进行像素、背压及多帧验证，冻结完整输入后执行自己的native和setup/hold/四CSI/缓存检查。全部通过才受控上板比较HDMI暗部、绿点和真人肤色/双眼细节，随后验证原RK3576 NPU处理与操控。现用47/gate0/app24与Flash37保留为恢复基线；完整83主项、12正式项、47RK细项其余未完成范围继续逐项完成。

# 历史v172：真人原RGB反例与app24

实际真人测试已取得：完整105帧1080p原RGB、三张RGB/PNG逐像素一致，绿点在模型缩放前存在。47运行时门限2严重吞掉面部阴影，2→1→0预览反例已归档，门限2不再作为人脸修复。当前保留诊断门限0，原app24/NHWC/CPU4/并行/原RK3576 NPU及六项关键哈希恢复，唯一PID53502/53544。恢复后8秒窗口115/115样本有效并实际调用NPU，源时间跨度内约15.51次/秒，样本年龄中位145.18ms/P95 192.27ms；非曝光FPS、个人精度或操控验收。后续窗18/151调用说明可见性变化，不能算持续真人FPS。原始CSV布尔True/False曾被观察器误按1统计，已独立纠正。 原始绿点及门限2阴影退化已确认未修复。实际所选47 Gamma RTL4356像素含暗色立方/全灰阶/脉冲/背压通过，0→1线性通道变成0→35DN；前级10bit去马赛克在CCM/AWB前量化成RGB8，CNR保留整数Y，无法恢复截断细节或已放大的亮度噪声。这是已证实放大机制，传感器RAW黑电平/相位及首发环节未定位。完整319输入诊断49/50无颜色算术改动，八阶段RAW10/ISP导出32768像素、四lane全部1024RAW码、CSR及7个反例通过；ARM helper24项仅文件映射通过，49最终时序失败，50修正探针ready回传后由同一14708完整重建；最终时序/bit/实物导出仍待。48初次AL条目错误的终态失败保留，49仅修完整File元素，HDL逐字节相同。


诊断49完整native1307.422秒已终态，setup−0.887ns/TNS−55.082ns、hold+0.020ns，另有CSI时钟lane−0.025ns，未上板。实际最差路径含下游FIFO满→新探针ready选择→CNR组合链。新完整319输入诊断50仅把探针换为两个槽、以寄存占用量产生ready，切断这条组合回传；所有RAW/颜色算术、stageCSR、PHY/IP/ADC/SDC保持。自己的32768像素/全部RAW码/背压/标记/实际CSR及7破坏反例通过，完整native由同一14708执行；须重新核全部时序，不能忽略CSI时钟lane或下载失败bit。

# 当前运行：app22原NPU、并行与停止修复（v166）

当前默认已实际切到app22，CPU4/原MGazeNet RK3576 NPU，模型SHA9eee…保持。app21照片容量实测13.703→22.237次/秒为既有照片范围；默认F10暴露MCF1半包后已拒绝并恢复20。实际旧native导入__sysv_signal、源线程唤醒与owner释放重复停止；RK辅助对照旧版第二次SIGTERM退出−15，新sigaction正常0。app22持久处理/幂等停止10用例、完整103文件及ARM程序、照片158个有效NPU样本/PCIe154无人脸样本真实F10、默认启动→F10→再次启动均通过。当前PID43174/43216、47/gate2完整直方图、原NPU与同boot内核/OOM无故障已核，app20回退保留。仍有彩点，真人肤色/实际FPS/跟手/20点精度及游戏实玩待验；不把照片或无人脸拼成真人通过。

见[原生采集停止](native-capture-stop.md)。下文较早版本为历史，现用按根CURRENT_CAMERA。

# 当前运行与app21性能候选（v164）

当前生产保持47/门限2/app20原RK3576 NPU CPU4，真实恢复模型39783/采集39826、完整2073600像素hist与5GT/s×1及严格整boot内核复核。App21只改线程调度和停止唤醒，原权重/预处理/标定/UI/串行Pipeline保持；8主机用例、实际NPU固定照片ABBA100样本13.703→22.237次/秒(+62.27%)通过限定吞吐/P95门槛，中位年龄+3.164ms及特征变化保留。真实PCIe候选50样本正常清理，但face0/NPU0；尚未选作默认或验收真人FPS/肤色/精度/控制/游戏。历史47静态绿点指标改善25.09%保留，残余彩点未解决。F12新100ms源自己的gate/place已核而最终/bit/实物待。真人由用户暂缓，RK CSI/AIQ继续隔离。

调度、停止、实际数据和证据边界见[重叠推理与资源归属](pipeline-overlap.md)。下文较早运行版本为历史，当前选择以根CURRENT_CAMERA为准。

# GazeFollower / mouse3 的 RK3576 NPU 迁移

用户明确第一版必须使用RK3576 NPU。工程为 `projects/gaze_model_migration_v1_20261014`，正式M01–M12见TASKS和其最新机器清单。原mouse3/start.cmd仅切目录/设编码后启动Windows虚拟环境中的run_gaze.py；保留后台采集、MediaPipe定位、MGazeNet258维、Ridge+isotonic个人标定、OneEuro和区域/连续模式。Windows虚拟环境及旧个人标定不直接搬到RK。

## 原模型与输入

原型固定c61ffe20cd8c16b35291e5ac198d1b76c7702290；base.mnn SHA256为2f96b95275fe6d7b79e98df3237ebb96e15ef5522c96968f08167da7e1954a96。49组原卷积权重（含稀疏展开）保留，静态形状子图求值得到264节点ONNX。原文件本来就是IR9，不能把IR兼容检查说成格式转换。原MNN与ONNX严格16组有1组未过阈值；首层独立float64分析支持引擎算术差异，但不代签全网精度。

图像为RGB float32 /255；face224×224、左右眼112×112，右眼在resize后水平flip。rect12依次脸/左眼/右眼的[w,h,x,y]，除以全图[w,h]。MNN应用输入顺序face/left/right/rect，当前ONNX/RKNN顺序left/face/rect/right，三图NCHW、rect[1,12]。不要重复做RGB/BGR或归一化。MediaPipe原入口接BGR并在内部转RGB。runtime/RKNNGazeEstimator.py提供显式RK3576/RKNPU检查和无CPU回退的后端；完整应用接入尚待。

RK_preprocessing_v1在板上使用实际原detect/clip_patch函数、记录tensor接收器，12组RGB/随机/边缘裁切的四输入逐位一致。该测试只验证预处理，记录器不是MNN执行或NPU证明。

## 环境与复验

板端Python3.11/aarch64，SDK与原有librknnrt均2.3.0。转换环境放 `/userdata/gaze_model_migration_v1_20261014/venv`；系统root曾仅63MB可用，依赖分块校验后放userdata，禁止向root堆模型环境。文件传输/独立作业入口为tools/start_userdata_job_v1.py，源和资产逐SHA记录。

ARM64 SDK2.3.0需要onnxoptimizer0.3.8；该版本无ARM wheel，须源码构建。需要pytest-runner和Python开发头文件；头文件从与系统同版的libpython3.11-dev包提取到userdata sysroot，CMAKE_ARGS指定Python_INCLUDE_DIR/Python_LIBRARY/pybind11_DIR，包含路径覆盖multiarch pyconfig.h。单作业编译适合该2GB板，不能因日志长时间无新增而重复启动。

setuptools84删除pkg_resources，SDK能import但构造RKNN失败；固定75.8.2后实际编译通过。转换SDK固定protobuf3.20.3，而MediaPipe0.10.18需要protobuf4，必须分开app_venv；只通过pip check/import不等于实际RKNN构造、模型编译或MediaPipe运行通过。

## 已有实际NPU证据及边界

RKNN_compile_v2将原ONNX编译为RK3576 FP16，不加第二次归一化，不替换小模型。模型5,472,730字节，SHA256为9eeeaedd671d6cab7c7a637175e8c540b8649d315d2cd25d085a35a4c0801ad2。RKNN_NPU_v1使用RKNNLite2 on-device init_runtime（target=None）、实际RKNPU驱动和板上/usr/lib/librknnrt.so。16组合成输入均输出258维有限值，NPU_execution_review_v1从回传NPZ重算误差，核对模型/输入/输出和运行库SHA。

该次30次稳态推理中位31.809ms、P95 33.418ms；不包含摄像头、MediaPipe、标定、GUI。相对原MNN最大特征绝对差0.008607864、最大相对L2 0.001029818；不能把特征差换算成屏幕像素误差。离线NPU执行已经成立，真实人脸ROI、现场新标定/20点验证、完整PCIe实时入口和模型玩游戏仍未验收。FPGA侧相机保持正式37已验证入口，USB不启动。

游戏候选pypvz固定c88a018209ca48457e24db124f6532aea350f60d，1919文件按Git blob核对，13个Python文件通过3.11语法解析；其元数据声明>=3.12仍保留，实际运行尚待。没有独立LICENSE，不把公开仓库直接说成资源许可已核对。注视模型输出指向，不能宣称它自带植物大战僵尸的自主决策能力。

## 2026-10-14 应用与 HDMI 实拍推进

独立 app_venv 已实际安装并通过依赖、导入检查。app_v5 是当前应用候选，后台 CameraWorker 保留 mouse3 的采集/推理结构及原标定/滤波实现；Windows GUI 仍未移植，start.sh 目前明确运行离线检查入口。RK_app_check_v5 两张仓库人脸图片均通过实际 MediaPipe→原预处理→RK3576 NPU。real_image_numeric_v1 用同一套真实 ROI 输入比对原 MNN、ONNX 和回传 NPU 输出，两张图 MNN/ONNX 均满足原阈值，NPU 最大特征绝对差分别约 0.003064、0.003879；不代替原合成 16 组的未过门槛或个人屏幕精度。

重启可改变 videoN 编号。本次 /dev/video22 已变为 rkcif，实际 PCIe 节点是 /dev/video73。只从 sysfs 的精确名称 Milianke PCIe Capture 找唯一节点，再核对 device/driver 为 Anlogic-pcie 和 QUERYCAP 的 milianke-v4l2；不遍历打开摄像头，不启用 USB，不固定 video22。

1080p RGB3 每帧 6,220,800 字节。原八缓冲申请遇到 reqbufs ENOMEM；降为四缓冲仍在先加载 NPU 时失败。实际有效顺序是打开 PCIe 并等到第一帧（确认连续 DMA 缓冲分配成功），之后才构造 MediaPipe/NPU。仅先启动异步采集线程不足以保证顺序。app_v5 已把第一帧屏障加入真正的 CameraWorker。SIGTERM 时完成当前 stdout 帧记录再退出，检查 STREAMOFF/REQBUFS 清理，不能把强杀或 errno 非零记为通过。

live_PCIE_app_v4 实际完整采集 30 帧但没有人脸，NPU 执行帧数为零。随后 HDMI_optical_v1 将原仓库脸部照片显示在 HDMI，由 FPGA 摄像头实拍经 PCIe 送回；60/60 帧有效并执行 NPU。worker_optical_v1 再通过真正的 CameraWorker 获得 60/60 有效的 258 维输出，时间戳严格递增，原生采集共 149 帧后正常 signal_stop。app_optical_review_v1 独立核对源码 SHA、回传数组、时间戳和清理记录；该次 worker 的 MediaPipe+NPU 中位 108.51ms、P95 138.35ms，不是端到端延迟。相机时间戳是驱动采集时间，不能冒充曝光同步。

这两次光路测试是屏幕照片，尚未进行真人校准、20点误差验收或游戏操作；RK 直连 CSI 仍未读到有效 ID。HDMI 窗口在测试结束后关闭。硬件测试期间使用只有 Tcl 等待的 BitWriter 进程排斥已排队的下载任务，不执行 JTAG 或烧录；Windows Tcl 脚本参数用正斜杠路径。完整证据保留每次失败，后续成功目录不覆盖失败目录。

## Linux 校准界面与游戏部署

当前应用为 app_v9。Linux UI 用 xrandr 的 HDMI-1 活动几何建立屏幕坐标，不能把同时连接的 DSI 高度当成 HDMI 高度；用 NOFRAME 窗口保留显示模式。中文字体从 fc-match :lang=zh 取得，本板为文泉驿。预览按真实16:9缩放。Windows 生成的 .sh 必须明确写 LF；v6 的 CRLF 导致 set/cd/DISPLAY 出错，失败保留，v7 修复。v8 修复原界面提示文字重叠，已查看实机截图。

desktop_input.py 使用 X11/XTest 提供坐标移动、按键边沿和左右键原语。当前 UI 只接入可开关的左键停留确认，默认关闭：F8 鼠标、F6 停留点击、F7 区域/连续、H 隐藏、F9 返回、F10 退出。停留策略要求新鲜样本，稳定1秒仅点击一次；离开半径、断流、无效输入重置。自有窗口实际验证了鼠标按下/释放和F6边沿，不能把它称为真人视线点击验收。

实际最小化/F9测试发现 XMapRaised 后立即 XSetInputFocus 会因窗口管理器异步恢复而触发 BadMatch，Xlib直接退出进程。app_v9 移除抢设焦点，只请求映射/抬升；UI_hotkeys_v2 实际通过最小化、全局F9恢复、F10退出及采集清理。失败v1的进程已确认消失后，观察器保留原RUNNING记录、记录X错误终态并释放测试注入的F9；不能仅凭状态文件仍RUNNING就认为任务活着。

UI_games_review_v1逐AST确认原fit、finish_validation、advance和七个运行时校准/滤波/评测函数未改变，Ridge+isotonic文件逐SHA相同。calibration_flow_v1用390个明确合成特征完成原UI拟合、240个合成留出样本形成20点报告，测试产物隔离到synthetic_sessions；这只是软件流程证明，不是NPU特征或个人精度。真人仍需转动镜头面对使用者并现场新标定。

游戏方面：原pypvz c88a0182的1919源/资源文件已原样部署；脚本从菜单选10张卡后进入真实play阶段。另固定带MIT LICENSE的marleysudbury/minesweeper-pygame e1b946f696c6fab8bda8a72a58fd97666b08a196，原样部署并通过9×9首次翻格。均使用真实X11窗口，游戏动作来自明确的测试输入，尚不是模型玩游戏。测试用dummy音频，不接受真实音频效果；用户PvZ启动脚本指定SDL software renderer。

板端三个入口位于 /userdata/gaze_model_migration_v1_20261014/bin/：gaze.sh、pypvz.sh、minesweeper.sh。gaze.sh运行完整Linux界面并带flock；会话写gaze_sessions，不加载历史个人标定。运行说明见工程RK_RUN_GUIDE.md。M08真人20点与M11/M12真实操作、误触、成功率和长稳仍需现场证据，整个首版不能因上述软件测试而宣称验收完成。

## 游戏快速点击的实际事件链

原pypvz处理MOUSEBUTTONDOWN时调用mouse.get_pressed()/get_pos()。若XTest按下和释放已经同时入队，实际当前状态为松开，游戏收到事件却丢掉点击。pypvz_XTest_original_v1在RK实机复现完整down/up但游戏标志全false；不能用直接赋值Control.mouse_click的测试证明真实桌面输入可用。

独立完整候选games/pypvz_input_v1保留1919文件，仅source/tool.py改为从event.button/event.pos解释左右键，忽略滚轮和中键。pypvz_XTest_fixed_v2使用未改动的app_v9 X11Input，经真实XTest→SDL→游戏event_loop完成17次点击/34个按下释放事件：菜单、10卡、开始、右键取消、种植和拾取自然生成阳光；种植花费50、拾取增加25。没有修改游戏状态或调用直接点击注入。pypvz_input_review_v1独立核对全部文件、事件坐标/顺序、游戏状态和启动入口；板端bin/pypvz.sh已切到pypvz_input_deploy_v1/game，原版保留。这仍是脚本坐标输入，不能签核真人视线、模型策略或游戏成功率。


RK3576原MNN数值诊断补充：ARM_MNN_reference_v1 在/userdata独立--target目录安装固定SHA的MNN3.6.1 ARM64 wheel，不修改应用环境或启动摄像头。原模型/原16组输入、atol=5e-5及rtol=3e-4不变，实际ARM MNN low对ONNX通过0/16，high通过16/16；最大特征差分别0.0216817856和0.0002231598。ARM_MNN_reference_review_v1 从回传数组重算并绑定输入/权重/ONNX SHA。历史NPU对ARM high最大特征差0.0086050034，本轮没有重跑NPU。原Windows15/16失败与原low目标失败均保留；high是数值诊断参考，不得替换原基线来宣称验收通过。个人标定、20点屏幕误差和模型实玩仍待。


Windows数值门槛定位补充（Windows_winograd_v1及Windows_winograd_review_v1）：MNN3.6.1 CPU low、2线程和同一原模型/16组冻结输入不变。默认及显式Winograd内存等级3均逐位复现旧结果15/16；加载模块前调用runtime.set_hint(3,0)、等级1或2，均在原atol=5e-5/rtol=3e-4下16/16。等级0最差容差比0.03910，默认为1.20052。参数编号与含义核对[官方3.6.1头文件](https://github.com/alibaba/MNN/blob/3.6.1/include/MNN/Interpreter.hpp)，副本及SHA已归档。

同一原5x5卷积、共享输入/权重的独立float64对照：random_2最大误差等级3为0.00109714、等级0为0.00000251629；checker分别0.00576266/0.00000697438，gradient为0.0000163443/0.00000183449。该干预支持Windows后端卷积算术差异的解释；不改权重、ONNX、原默认失败记录、生产app或NPU模型，不把诊断参考代签原基线、个人屏幕精度或游戏实玩。原ARM low/high及实际NPU证据仍独立保留。


2026-10-15 可复现CPU参考配置：portable_MNN_review_v1使用同一MNN3.6.1、precision=high、backend=0、numThread=2和加载模块前runtime.set_hint(3,0)，Windows x64与RK3576 ARM64运行同字节原模型及16组冻结输入。全部258维Windows↔ARM、各自↔ONNX均16/16满足原atol=5e-5/rtol=3e-4；独立审计核对实际返回NPZ字节、模型/输入/运行脚本SHA和每元素误差。原默认low失败保留；这是明确配置的CPU参考，不改原权重、不覆盖旧基线、不改生产NPU应用，不用FP16特征误差代替个人屏幕精度。工具evaluate_portable_MNN_reference_v1.py及review_portable_MNN_reference_v1.py提供精确重现逻辑，证据目录独占创建以防覆盖旧结果。


2026-10-15 NPU离线收束（M06_M07_offline_audit_v1）：按原NPU_required_v1定义逐项核对同权重/同图片ROI/258维与原始坐标、误差分布、实际后端和均值/P90耗时，M06与M07离线范围完成。统一CPU high/Winograd0参考16组合成和2张人脸照片的FP32转换均通过；真实NPU原16组及优化等级0/1/2新增48组执行已归档，三等级与生产等级3逐位一致，生产模型未更换。NPU对统一CPU最大绝对差0.00857735，最大相对L2差0.00103020；两照片最大绝对差分别0.00298309/0.00382614。原30次steady计时均值30.9739ms、P90 33.2059ms；含定位/图像处理的系统帧率需另测。全部4128个返回值可精确表示为binary16；按Python标量IEEE half转换及相邻可表示数独立核查，有47个位置即使最优FP16舍入也超出原FP32转换阈值。该下界只解释可表示性，未解释的累积残差仍单列；不能据此接受全部FP16误差，也不把特征差直接换算为屏幕误差。原默认low失败及FP16不满足FP32阈值的结果均保留，未修改阈值。完整首版继续要求M05实际颜色/噪声、M08新个人标定与20点留出、M11模型游戏及M12最终验收。


2026-10-15 实际九色复核：colour_chart_review_v2将HDMI九色图通过真实相机、FPGA与PCIe抓取32帧。用四ArUco角标及独立DLT核对ROI，首尾完整图像字节与原始采样一致，逐帧序号/单调时间/有效载荷均核对。六彩主通道裕量>150DN，白灰黑顺序正确；真实prepare_inputs的RGB、resize、归一化、NCHW、右眼翻转逐位复核。用真实色块ROI验证输入契约，不是人脸或NPU精度实验。灰块时域RMS噪声3.681/2.851/3.292DN，部分暗通道约15.7DN；包含屏幕刷新、曝光与ISP，不能称纯传感器读出噪声或直接判缺陷。稀疏24×24采样不能冒充连续像素做3×3滤波验收。v1因角标被实际画面裁切而失败，保留；v2只移动HDMI图位置后成功。两轮均先取得BitWriter排他租约，实际摄像头关闭、PCIe绑定及同boot复核后释放；USB关闭、黄金37未改。M05仍PARTIAL，未接受噪声质量、DeltaE或个人精度。


2026-10-15 连续像素/卷积核实测：colour_chart_v3在真实HDMI→PCIe图像取九块40×40相邻像素，各32帧，逐点检查网格连续、独立单应反投影位于色块内部、首尾PNG字节、模型三路输入与清理。九色再通过，灰块RMS为3.724/2.801/3.264DN。此前稀疏样本的均匀帧间偏移只占总时域方差约0.1–0.4%，其余是空间不均匀时域残差；统计分解不归因具体器件。对新增连续裁块内38×38中心做逐通道3×3高斯(1,2,1外积/16)、均值(/9)、中值；每种1247616个RGB输出与独立OpenCV逐位一致。灰块原中心sigma=3.718/2.803/3.257，高斯=2.476/1.609/2.157，均值=2.237/1.445/1.943，中值=2.582/1.537/2.182DN。生产输入未改；均匀色块的降噪不证明眼部边缘保真、实际NPU精度或运行时通过，不能只按sigma最低选核，也不把RGB软件试验冒充现有FPGA灰度核实物验收。
# 2026-10-15运行时延迟实测补充

当前运行版本为`projects/gaze_model_migration_v1_20261014/app_v14`，RK默认`/userdata/gaze_model_migration_v1_20261014/bin/gaze.sh`已指向v14连续模式。原FP16 NPU模型SHA仍为`9eeeaedd671d6cab7c7a637175e8c540b8649d315d2cd25d085a35a4c0801ad2`。本轮没有把CPU模型作为首版替代。

先记录真实分段耗时，不能把处理FPS称作摄像头FPS。重启前TRACK约6.83处理FPS，样本年龄中位503ms/p95 646ms；这会触发500ms控制截止。默认12帧区域投票和3帧迟滞会另加响应等待。每批结果保留完整校准/滤波/日志，但仅对最新样本派发光标；区域置信度不足时拒绝旧格子控制并清停留点击。连续模式独立于个人标定参数，F7可切回区域模式。

RGB3原始MCF1仍按1920x1080完整plane/stride/时间戳校验。先按模型640x360缩放RGB，再转换BGR，减少全分辨率通道拷贝；在RK实际OpenCV上8种目标尺寸/stride共5183438像素与旧先BGR再缩放逐位一致，主机也通过。这是像素路径等价，不是对真实肤色/绿点的验收。

MediaPipe VIDEO需要毫秒时间戳。输入仍来自原始CLOCK_MONOTONIC纳秒，整除1e6后严格递增，拒绝量化重复/倒退；不人工推进时间掩盖坏时戳。保留IMAGE模式供对照，VIDEO初始化必须成功使用Tasks API。[官方API说明](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python)支持VIDEO跟踪与`detect_for_video`。本轮VIDEO单独仅带来有限收益，不能认为模式切换足够解决帧率。

CPU分析另发现每帧478关键点调用1434次标量np.round；改成float64批量乘法、np.rint及Python浮点字段，保持原双精度乘法和ties-to-even舍入。100组共143400坐标含半像素/画外边界与旧实际表达式完全相同，int16 face mesh也相同。同板重复人脸图像、原NPU模型，v13 VIDEO总耗时中位99.784ms，v14 VIDEO为81.012ms；这不是实际摄像头/真人/游戏FPS。v14无人脸预览1574条样本年龄中位144.655ms/p95 192.416ms，没有实际NPU调用；另有20次有效重复图像的真实NPU调用验证。真实人脸颜色、精度、响应和游戏仍待，不能拿无脸预览或静态图耗时补签。证据：模型项目`evidence/latency_v14_deploy_20261015_205812/review.json`。

2026-10-15绿点诊断补充：`evidence/colour_phase_v1/result.json`使用旧真实32帧、9块连续40×40的460800像素，按完整图像坐标统计2×2/4×4相位和四像素x余数。不同色块/通道的2×2均值峰峰差最高约5.057DN，四像素x余数最高约3.871DN。黑色块相对局部逐通道3×3中值的正绿残差，在8DN诊断条件下约3.95%，16DN条件下约0.017%；这些不是坏点率或验收阈值。相位偏差、场景斜率、屏幕结构、去马赛克与时域噪声都可能参与，不能凭单份统计指定Bayer、ISP或PCIe根因，也不能把RGB顺序已通过当作肤色/暗部质量通过。生产滤波未改变。当前RK失联，必须恢复后取同条件实际肤色/眼部纹理、曝光/增益和新原始帧再比较，不能把旧色卡当作当前人脸修复验收。

2026-10-15控制恢复补充：`app_v15`目前仅本机准备，尚未部署RK。实际旧`App.process`在无效帧时重置滤波和停留点击，但不清除RegionDecider投票；旧格A的12票在恢复到新格B后仍占多数，会继续指向A。v15只在该分支增加`region.reset()`和`region_cell=None`，原模型/标定/像素路径保持。`evidence/reacquire_v15_check/result.json`运行真实新旧App.process/apply_pointer及真实RegionDecider/DwellClick，旧缺陷可复现，新版需三个新样本确认B；同输入连续模式控制/CSV逐值一致，批内最后无效时不会派发旧有效点。该检查用合成校准坐标、恒等滤波和假时钟，没有人脸/NPU/实际鼠标，不能计真人稳定性或游戏通过。RK默认最后已确认版本仍是v14连续模式。

`evidence/control_eligibility_v1/result.json`进一步核对旧v10 CSV的602条TRACK记录：601条有效，鼠标开关均开启，其中312条有效/有限坐标在日志时刻不满足500ms新鲜度条件，仅289条同时满足所列条件。该代理记录间隔最长约2.950秒，288个间隔中111个超过250ms。CSV年龄在处理后写入，未记录区域置信度、实际X11派发或真实光标轨迹，所以这些数量不是实际光标更新率；也没有TRACK独立真值来推断精度。原截止阈值未改，待新版真实人脸测试复核延迟与控制。



## v125 当前已部署与复验边界

2026-10-16当前选择：SRAM40（bit SHA bcd9c7e16ba7f4d597b1940ab05d5fecaeb55120689cbf5eb29d991557e2e382）+默认app_v18+原RK3576 NPU。Flash仍正式37。BAR0x56442501是共享ABI，当前SRAM身份须绑定成功JTAG日志和bit SHA，不能由BAR独断。

原始绿点已实拍改善但未全验收：统一RAW底值54的39版虽降绿点，却把木板蓝色均值56→14并损暗细节，已拒绝并回退；40版保留BLC50和原色矩阵，只门控线性RGB全部为0/1的最低量化值。自己的317输入完整构建setup +0.240ns/hold +0.021ns、四CSI物理路径通过。实际正常增益32/Bayer3，37与40各422/416帧完整；两块暗区绿超差比例12.69%→1.20%、13.79%→0.010%，墙面/白柱/木板没有该阈值定义下的大偏移，已保留SRAM40。该比例是绿超差代理量；残余绿点、低照纹理、人脸/眼部与九色仍待，不计M05完成。Flash37未改。

默认app_v18已实际部署并以当前模型打开的CSV文件描述符绑定会话；原RK3576 NPU权重和预处理语义未变。复制DMA后先QBUF再发布两份有界输出，整数3:1在私有副本生成640×360，RK5529600个RGB值等于原OpenCV。实际C与Python共21模拟用例通过；三次真实PCIe各141帧，接收中位9.07→2.40ms。真实无脸应用窗口输入年龄中位39.26→20.21ms，样本年龄143.86→118.02ms；不是真人FPS或控制精度验收。v1按目录mtime误选旧会话的失败记录保留，v2以实际日志恢复正确会话，v3用活进程CSV FD确认默认18新鲜运行。

G7自己的完整187输入综合和全部关键绑定复核已完成：456属性、24组6360路径，snapshot/Gray后级、parser和38用户复位检查为正；全局仍9setup/47recovery，WNS/TNS -2.340/-63.000ns。完成历史链本身无运行复位，已证明UI两周期主复位保持期间历史清零，并核对消费者原生复位D余因子，不能虚称这些FF带异步复位。完整G8副本RTL/IP/ADC逐字节等于G7，只给五条注册源到私有首D增加2ns精确预算，29组6365路径的检查器与28负例通过，自己的完整综合实际执行中；不选上板，不加宽域false path，最终PHY/reset/MTBF仍待。

RK CSI/AIQ继续停止；已确认ISP停流超时→IOMMU页错误→内核Oops，具体函数根因/修复未签核。async18在PCIe路径的复制/QBUF改进及21模拟用例不能代签RK ISP停启修复；不重跑已触发故障的6.25秒阻塞读端试验。

证据入口：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v125/progress.json`。此前本页的黄金37/app16和“缩放未集成”描述均属于v124历史。


## v127 实际续查

默认app_v20已实际部署，MediaPipe每实例显式XNNPACK4线程；NPU仍原权重RK3576，native18/MCF1缩放/ROI与滤波控制代码保持。当前调度0–7/OpenCV8的ABCCBA复测中，有脸帧中位78–81→54–56ms，240条记录的整数3D关键点/眼区框/开合度/有效性逐项相同；RK实际60对输入、13548240个float32值完全相等。实机无脸355/481样本：检测56.84→44.68ms，处理更新16.12→20.02次/秒，样本年龄110.77→104.68ms，但输入年龄20.64→29.19ms变差，不能称全面延迟或真人FPS验收。已核当前唯一模型/采集、新鲜FD绑定会话、原NPU权重及回退启动器。

证据入口：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v127/progress.json`；新选择见`CURRENT_CAMERA.json`，断电/重配后重验。


## v128 实际续查

用户表示正在调整摄像头，随后只读30/30/120秒三窗共4043条均无有效人脸/NPU调用，截图仍书架/天花板；不能把20–24次/秒无脸更新率称真人FPS。当前连续模式region_mode=false，12帧区域投票不是本次运行延迟原因。默认app20、唯一模型13556/采集13598、新鲜样本约74ms、原NPU和原驱动通过复核；没有当前内核故障候选，RK CSI/AIQ/USB保持此前状态。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v128/progress.json`。


## v129 实际续查

当前已实际选中SRAM43色度降噪+默认app20 CPU4+原RK3576 NPU，Flash37保留。43自己的318输入完整构建1484.25秒，最终setup +0.012ns/hold +0.019ns、四CSI PAD通路通过；自己的完整1080p逐像素参考通过。四行缓存实际映射40颗PH1_ERAM，各2048×10，端口同属真实125MHz用户时钟；实际mode写NORMAL，不能谎称primitive字段READBEFOREWRITE或物理像素完全等同。只读导出前后全部327个native文件字节不变。

实拍v2增益32/Bayer3，40/43各408/441完整RGB帧，六张原始RGB与PNG完全一致。白墙绿色超差像素比例8.378%→1.041%，色度标准差6.917→3.518；左暗区综合色噪1.525%→0.774%。保留43用于房间色度改善。风扇ROI绿色超差比例上升、墙暗色阈值比例上升；左暗区绿色指标v1变差而v2变好，均保留，不能宣称全部绿点/边缘/人脸肤色修好。当前没有完整正脸，个人标定/实际真人NPU性能和控制/游戏仍待。

首轮418帧采集有效，但脚本停流后读取计数0误触发了40回退，原始失败保留。驱动取消DMA先写CTRL0x02，复位camera流水线；v2改为运行中四次读数，输出帧22/82/142/202、输出拍11149440/42260160/73371840/104458080均增长且故障0；随后STREAMOFF读数0实际复现。v2已实际重新JTAG43并恢复app20，当前唯一模型15984/采集16026，新鲜样本约95.9ms、计数持续增长、当前boot无故障候选。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v129/progress.json`。


## v130 实机反例与当前恢复

实机45的1080p图案验收失败：2073600像素全部与行缓存写穿模型逐字节一致，1470264像素与预期五点滤波不同，首尾两行正确，整数Y全部保持。已定位四组行缓存写入第y行时覆盖正在读取的y−4行；43共用四组拓扑，因此只能保留历史房间改善和运行基线，不能宣称物理算法正确。45已实际回退到SHA固定的43并恢复唯一app20 CPU4/原RK3576 NPU，当前boot无内核故障候选。46完整318输入改为五组缓存，154组尺寸/模式测试在旧值、新值及X冲突模型下全部通过，旧45负例失败；CSR专项通过，自己的完整数字、综合布线及物理逐像素仍在推进。Flash37不变，RK CSI/AIQ继续停流。

最新30秒真实预览689条、NPU调用0，实际画面仍是书架/天花板；没有真人FPS、肤色/眼区、个人标定或游戏验收。RK实机为厂商6.1.99、May11构建，缺匹配ISP/CIF/IOMMU源码；已保存官方develop-6.1参考，但不能当匹配SDK或已修内核。

细节：[实机缓存冲突](chroma-memory-collision.md)。


## v131 当前46与剩余范围

已实际保留SRAM46五组行缓存修复，默认app20 CPU4/原RK3576 NPU恢复，Flash37保留。46自己的318输入完整构建1339.33秒，最终setup +0.022ns/hold +0.020ns，四CSI通路通过；154组小帧在旧值/新值/X三种冲突模型通过，旧45负例被检出，完整4147200像素参考通过。实际1080p/720p六图案797帧、1199923200像素逐帧哈希完全一致；连续1→2→3→1共191帧均完整参考匹配。真实43/46分别421/437帧，保存六张原始RGB与PNG一致，运行中mode0/无故障/计数增长通过，唯一模型20256/采集20298恢复，当前boot内核故障候选为空。

修复的是已实机确认的四组RAM冲突；实拍仍有残余彩色噪点，人物只有局部脸部入镜，真人肤色/眼区/跟手性、个人标定/游戏仍待。实拍人物移动，场景相关0.942–0.951未达0.99，不接受本轮固定ROI的因果降噪比例，全部变好/变差指标保留。当前PCIe驱动仅允许1080p/720p；首轮4K在native精确格式检查拒绝、0帧/errno22/cleanup0并已回退43恢复；实际只读TRY_FMT确认4K被映射1080p，当前STREAM格式未变，不能冒称4K像素/DMA/内核失败或已支持4K。RK CSI/AIQ继续停流，内核参考源码与外部相似报告仅是线索，仍缺当前厂商May11版匹配SDK及自己的PC/LR。

当前硬件临时验收应恢复CURRENT_CAMERA.json所指46；旧P3/F11/T08/I03/I05/F10等待器仍停用，不能自动恢复37/40。此PCIe46通过不代替G8/HCI03自己的四setup/47recovery修复或整链验收。


## v132 实际47档2与独立G10范围

已保留SRAM47及运行时线性门限2，默认app20 CPU4/原RK3576 NPU恢复，Flash37保留。47自己的318输入完整链1653.05秒，最终setup +0.053ns/hold +0.020ns，四CSI和50颗行ERAM通过；新CCM32772像素、6个算术/帧界/统计负例、5个CSR负例及ARM64工具17项文件映射测试通过。实际1080p/720p六图案794帧、1193702400像素全部完整哈希一致；连续图案切换189帧亦一致。真实同流1→2→1→3→1共747帧，15张原RGB与PNG一致，每次完成帧直方图2073600像素、帧序及档位标签核对。2档静态场景绿色偏色像素指标比相邻1档均值降25.09%，粗亮度相关最低0.99384，明亮中性均值RGB差[-0.22,-0.91,-1.35]；更强3档未过既定相关门槛，全部变好/变差ROI均保留。当前模型22780/采集22822唯一且新鲜，PCIe5.0GT/s×1，当前boot内核故障候选为空。

这是室内场景受限改进，仍有彩色噪点，不签核绿点完全消失、真人肤色/眼区/帧率、个人精度/操控或游戏；用户明确稍后测真人。线性门限2须在重新下载/用户域复位后凭真实bit/JTAG和LIN1/LING重新应用，47位流自身默认1。G10自己的完整195输入gate和新PHY/前端数字测试完成，原生核对6 setup/20 recovery仍负，仅检查了所列私有复位入口/Gray链，未布局布线/bit/上板，不能套用旧G8或PCIe47通过。RK CSI/AIQ仍隔离；本地三份教程及厂家页均指向mlk-sdk-3576-v1.1.0、mlk_afh03_rk3576_defconfig；四个GitHub仓库检索无命中，厂商SDK网盘已定位但尚未取得源码包，不能把官方July29参考树当May11本机源码。

详见[低线性噪点47](linear-tail-green-noise.md)及根CURRENT_CAMERA.json。
