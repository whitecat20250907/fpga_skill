# v182 当前已认可配置与实际native状态

保持用户已认可的CURRENT app28/SRAM51/stage0/gate0/gain32/Bayer3，模型62436/采集62482及startticks未变；原模型/RK3576 NPU、105源像素与GUI、驱动及Flash37保持。root构建后仅只读观察同boot、video73仍stream、reject0；最近10秒172个unique source记录，NPU0/valid0，当前模型启动后1154条kernel新增行严格fault候选0。这不是真人NPU FPS或个人标定/游戏验收，不重做增益/RAW画质试验。29比较后拒留，已实际恢复28。

T08 full196/191的原构建、29996续跑及1200 postroute polish失败证据保留；249个实际ASYNC_REG声明已恢复，但1200终态仍setup WNS/TNS−0.016/−0.016ns、hold+0.020ns/TNS0。唯一own-site54740实际终态rc1：目标x1y56无available slot、MoveCells moved0，真实位置仍2/58/4，guard拒绝no-op并在incremental route前停止；只有before时序−0.016/+0.020，无本次final STA/bit。实际abnormal_before仅列O_rk_hs_clk_p_syn_2.Q_bpad_D，唯一−16ps路径也落在同一物理实例的doq[0]；目标x1y56的8个offset0..7全被debug_hub LSLICE占满。不能称已修好，不自动试第二站点；后续拟独立关闭ignore_aync_timing再严查优化，尚无该候选实际结果；整体物理/实机nonce仍待。

F15新的hci06_csi_bundle2_20261019完整176+11、171 staged已由root实际启动唯一TD31196；截至2026-10-19T15:27:30.499488+00:00，owner/创建时间/命令行和全部source/runtime hash均实读闭合，RUNNING，最近stage见本版actual_observation。功能HDL与严格父版逐字节相同，针对旧图933首D/64漏目标补齐完整held约束，本次仍按动态实图集合守护。PLL.lock无launch arc的首级只允许真实单bit exact cut，自己Slow/Fast SDF首段物理延迟<38ns、私有二级普通STA及全部覆盖门必须在位流前通过；当前未有本次final STA/bit/板测/光学验收。observe2及mapped旧失败、0路径和64漏bundle证据原样保留，不把准备/运行升级通过。新的分层诊断17项只在本地通过：存量F14 UART111包中20条HCK6为限定控制PASS，但RAWgood仍0、ECC增25、HCP1为0，缺root27/BYTE时钟证据；停止后的旧窗口/旧snapshot不能当新进展。没有新增板测或硬件验收。

Gain候选已在现机prepared9 headers下实际独立ARM编译，归档/135576字节AArch64 ko/62个undefined及新增5个标准API、移除v4l2_ctrl_new_std、9hash均独审闭合；只编译未加载，未做真实ioctl或增益/RAW试验，未取得May11完整内核源。新的公共测试runtime用原Popen和PID/startticks/parent/session登记，仅回收本Python已验证的退出子launcher，再跑原完整session/FD守护；实际Linux7项inert集成通过，其他Z/live/unknown仍拦，未生产接入。clock collector v1四个真实反例已修，v2新增有界逐read/write raw偏移/QPC及reply末字节read归属，normal/-O各26个纯transport用例通过；未打开真实串口，不等于FPGA时钟标定或nonce板测。

以下为有版本标签的历史记录。

# v181 当前已恢复配置与实际终态

用户已认可当前摄像头/HDMI，继续后续任务。app29真实A/B已完成：CPU下降，但模型更新由35.30降至27.50次/秒，input-age p95由42.27升至51.84ms；两窗口NPU0/valid0且场景有变化，不作为真人推理率结论。root拒留29，实际恢复并出版app28；当前模型62436/采集62482，SRAM51/stage0/gate0/gain32、原RK3576 NPU及Flash37保持。增益/RAW实际试验取消。

T08 full196原38456和入口81364失败保留；own place同源续跑29996已终态rc1，setup WNS/TNS −0.016/−0.016ns、hold WNS +0.020ns/TNS0；唯一负路径为RKTX clock lane833ps相关，未生成bit。未改时钟/SDC或假豁免，后续仅可用自身DB合法物理修整，并补四级capture释放链的实际属性和普通setup/hold独审；完整物理/IO与实机nonce仍待。 本次57188只读导出已完成；四FF实际独审BLOCKED，[2]/[3]物理cell确实缺ASYNC_REG，另last-valid报告自动展开epoch使能端点的parser适配待补，不因STA正值豁免属性。

F15 full176+9的64204及mapped v1失败保留；完整171 staged闭合的mapped诊断v2实际60384已终态rc0，状态EXPORTED_OWN_F15_MAPPED_DIAGNOSTIC_NOT_COVERAGE_NATIVE_OR_OPTICAL_PASS。该诊断仅导出own mapped图/约束/目标报告，不代表覆盖守护、完整native/正STA/bit或光学通过；按实图推导held→snapshot/previous_cycles/clock_delta与PLL.lock首/次级端点，禁止硬编码869/901。 真实图为944逻辑held/901实际源FF/933首D（snapshot869、previous_cycles32、clock_delta32）；原38ns SMD仅覆盖snapshot，另64个previous/delta实际按byte→sys相位时序检查，WNS−3.155ns/STNS−109.658ns；需新非冻结SDC覆盖真实完整held消费者并动态核对，不能把901守护常数改成869。PLL.lock首D直连及私有二级可证，首级原生仍0路径、二级普通setup+39.255ns；异步宏输出的合法首级CDC/物理延迟验证待官方工具语义，禁止伪造launch clock或0改1。

机器清单：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v181/ledger.json`；全部83+12+47及status保持。以下为有明确版本标签的历史记录。

# v180 当前用户确认与后续任务

2026-10-19用户明确确认“现在我感觉摄像头没问题了，你继续之后任务吧”。保留CURRENT选择的SRAM51/stage0/gate0/gain32/app28和HDMI配置，取消尚未执行的增益/RAW采集计划；备用工具的host测试不代表上板试验。当前视觉认可不替代个人眼控标定、有效真人推理率、游戏实玩或仍隔离的RK直连CSI验收。机器清单：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v180_revision02/ledger.json`，全部83+12+47保留。

app29保留app28图像/GUI/NPU，通过实际ARM编译及假V4L2系统调用边界的生产main集成测试，尚未部署。对60Hz输入使用有界锚定deadline选择30Hz模型交付，继续及时归还每个DQBUF；稍迟推进一个period，落后整period才重锚定，不追赶旧帧。仅用`now-last>=period`会在60Hz抖动下少发；实际便携反例235/600，而锚定策略300/600。实际收益须比较CPU、时延与有效处理率，不能用合成trace或无脸窗口当真人NPU提速。

T08 v3当前为同196源自身place checkpoint续跑，原full38456和v2入口失败保留，不能称重新完整综合通过。F15 full64204已终态守护失败；完整mapped诊断v2_ready尚待串行执行。处理checkpoint/路径与实际约束图的经验见[native续跑](native-checkpoint-continuation.md)。以下v179段落为历史快照，运行PID/状态以最新机器清单及实际进程为准。

# v179 历史补充：共享预览、显示耗时与当时画质边界

同一native camera owner分离1080预览与640模型输入，保持原MCF/模型语义；sealed memfd有界单槽以C POSIX F_SETLK/Python lockf非阻塞互斥，并用Python threadlock覆盖读写与close。继承flock不提供所需父子进程互斥；mmap可能dup FD，应记录全列表并在退出及锁保护后关闭。writer death会释放record锁，必须先atomic valid0、再copy、最后release提交；app26旧valid头对应半写像素的反例已实际回退，27/28的真实publish SIGSEGV拒收证明不可省略。完整生命周期见[gaze预览经验](gaze-rknn-migration.md)。

raw1080先精确AREA 2:1到960×540后创建pygame surface，实际离线CPU路径约4ms，对照先建全表面再缩放约31ms；非整数972 AREA仍慢，其他尺寸不能泛化4ms。此为显示CPU耗时，不能推导真人FPS。当前28重启17.80次更新/秒、slot16.26次发布/秒且NPU0/valid0；略低于25约18.7，尚无肤色或整项画质验收。

root已查看当前app28实际HDMI截图与同一native共享槽直接取得的processed RGB1080：暗部彩噪在进入HDMI前的处理RGB中已可见。这不是sensor RAW10，也不是同帧光学对照；肤色、阴影和整项画质仍未验收。低码RAW/Gamma数学路径只证明可充分产生残余偏绿，不能认作全部实机彩点的唯一根因。

当前CURRENT28/SRAM51及61305/61347保持。F15 observe2 native64204在本次发布观察点为SYN运行、最终签核待；T08原38456保留布局后guard count不符的rc1及实际正值约束报告，下一步准备与原失败分开记录。全部83+12+47状态保持。

补充证据快照：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v179/skill_experience_update_v1/publication.json`。原v179出版记录及历史内容不覆盖。

# v179 当前app28与异常提交边界

当前CURRENT已实际发布app28，SRAM51/stage0/gate0及原RK3576 NPU保持，模型61305、采集61347。app26试验未留用：全1080表面再缩放有CPU开销，且发现writer死亡后旧valid头可能覆盖半写像素，已干净回退app25（60370/60412）。独立app27只修原子valid0→像素/元数据→release提交；app28在此基础仅改显示表面/960×540 widget，105源104继承同27。真实ARM三RGB/原模型oracle、跨进程锁、SIGSEGV后invalid拒收及GUI像素证明通过；同一原生采集提供独立processed RGB1080预览，模型仍是等3×3均值640×360。app28实际F10正常退出和重启通过，root已查看HDMI并留用，但无正脸窗口不能验收肤色、阴影、控制或整项画质。

app28 start窗口18.05次模型更新/秒、原生预览slot 16.08次发布/秒；重启后分别17.80和16.26。两窗口NPU调用和有效行均0，不能称20fps实际HDMI、真人推理FPS或NPU提速；26约16.7处理更新回升，但仍略低于25约18.7，不能说性能全部改善。离线同RGB UI由先建大表面再缩放约31ms改为整数2:1 INTER_AREA到960后建表面约4ms，属于CPU显示路径耗时，NEON无明显收益且未部署。

T08 fresh196+5 own38456已于2026-10-19T13:13:52.549566+00:00终态rc1，耗时2366.657秒，196源及runtime/runner未改。综合/布局后derive_place_reset_graph处，旧debug_hub rst到slave_rst_sync的2ns快照约束被守护拒绝。实际异常报告total2/active2/ignored0、该约束SWNS+1.577ns/TNS0，与旧guard expected1不符；端点推导归属尚待审查，不能写成负slack时序失败或时序通过。没有自己的最终route/正STA/bit或实板nonce验收，不再记RUNNING。

保持CURRENT选中的51/stage0/gate0/app28及绑定原NPU，明确app25 fallback；Flash37不变，USB/RK CSI/AIQ仍隔离。继续剩余真实阴影/肤色与有效NPU处理率、个人13点标定/20点留出、眨眼/游戏；逐帧颜色归因需同源同帧RAW及实际AWB/曝光和暗场/中性色标，不能按椅子低尾猜阈值。保留T08失败原件并推导实际约束端点，不猜负slack或删约束。完成同一F15 observe2 native64204及自己的完整静态/物理审查，不重复启动或提前签核。全部83+12+47状态保留，RK精确源码/安全停流与真实双摄仍待。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v179/actual_app28_T08_observation.json`。全部83+12+47及status保持，未扩大画质/光学/整机验收。

# 历史v178：当前应用与限定证据

当前实际为SRAM51/stage0/gate0与app25原RK3576 NPU（模型58961、采集59003）。app25把1920×1080 RGB3按等通道3×3均值缩至640×360，原权重和NPU输入语义保持；实际F10退出及默认重启通过。局部颗粒减轻，但用户仍反馈HDMI画面不好，画质/真人肤色/操控未验收。20秒窗口18.75次更新/秒、NPU调用0及有效行0，只是无人脸预览，不能宣称推理FPS改善。三张实际帧的标量area3与OpenCV全字节一致，较中心抽样增加约2.6ms；NEON v1的编译告警失败保留，独立v2 ARM六图案及三真实帧/2300除法输入均通过，但中位加速0.96×/1.03×/1.09×无明显收益，未部署。Flash37保持，USB和RK CSI/AIQ继续隔离。

独立只读显示检查为HDMI RGB888 full/1920×1080p60，实际1920到1920无scanout缩放，CSC y2r/r2y均0，xrandr Gamma1/brightness1；这些配置不代替光学画质验收。另20秒无人脸窗口374行/18.7updates/s、NPU调用0：CPU人脸检测中位44.65ms/p95 56.35ms、输入年龄中位30.94ms、样本年龄104.06ms，是该窗口主要CPU开销，不能叫NPU低FPS。大核2.112GHz/约64℃，快照未见降频；根盘1.87GB及userdata3.61GB可用，不是当前空间阻塞。

T08已从完整G14独立复制并冻结196注册输入及5个runtime；189父输入字节不变、6项预期修改、新增anchor。真实115200查询/24项legacy RX/邮箱source64及reset epoch数字证明通过，无查询TX连续210000周期逐拍等价。own full native38456正在执行，owner/入口/创建时间及当前日志已只读绑定；尚无自己的最终STA/bit/实板32次查询验收。

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

# 历史v173：诊断50终态前记录

F14完整174+9已原生终态：5584.813秒，最终setup +0.158ns/hold +0.020ns、TNS0及自己的bit；内部LUT驱动配置及全部23项实际wire时序检查通过限定范围。真实上板传感器RUN/table200和ACK通过，但PHY窗口0/无deskew/RAW0，首项卷积命令未在帧界应用，后3项未执行，实际图像与通用卷积仍未验收。已用同一BW恢复47及原app24，无Flash新写。字节齿轮/对齐、9个相机ADC属性和27MHz PLL与稳定47核对，不能凭这些推定实际时钟波形已正确。 实际真人测试已取得：完整105帧1080p原RGB、三张RGB/PNG逐像素一致，绿点在模型缩放前存在。47运行时门限2严重吞掉面部阴影，2→1→0预览反例已归档，门限2不再作为人脸修复。当前保留诊断门限0，原app24/NHWC/CPU4/并行/原RK3576 NPU及六项关键哈希恢复，唯一PID53502/53544。恢复后8秒窗口115/115样本有效并实际调用NPU，源时间跨度内约15.51次/秒，样本年龄中位145.18ms/P95 192.27ms；非曝光FPS、个人精度或操控验收。后续窗18/151调用说明可见性变化，不能算持续真人FPS。原始CSV布尔True/False曾被观察器误按1统计，已独立纠正。 原始绿点及门限2阴影退化已确认未修复。实际所选47 Gamma RTL4356像素含暗色立方/全灰阶/脉冲/背压通过，0→1线性通道变成0→35DN；前级10bit去马赛克在CCM/AWB前量化成RGB8，CNR保留整数Y，无法恢复截断细节或已放大的亮度噪声。这是已证实放大机制，传感器RAW黑电平/相位及首发环节未定位。完整319输入诊断49/50无颜色算术改动，八阶段RAW10/ISP导出32768像素、四lane全部1024RAW码、CSR及7个反例通过；ARM helper24项仅文件映射通过，49最终时序失败，50修正探针ready回传后由同一14708完整重建；最终时序/bit/实物导出仍待。48初次AL条目错误的终态失败保留，49仅修完整File元素，HDL逐字节相同。


诊断49完整native1307.422秒已终态，setup−0.887ns/TNS−55.082ns、hold+0.020ns，另有CSI时钟lane−0.025ns，未上板。实际最差路径含下游FIFO满→新探针ready选择→CNR组合链。新完整319输入诊断50仅把探针换为两个槽、以寄存占用量产生ready，切断这条组合回传；所有RAW/颜色算术、stageCSR、PHY/IP/ADC/SDC保持。自己的32768像素/全部RAW码/背压/标记/实际CSR及7破坏反例通过，完整native由同一14708执行；须重新核全部时序，不能忽略CSI时钟lane或下载失败bit。

# v161 当前统一入口

根TASKS.md及goal_task_ledger_v161/ledger.json保留83/12/47任务。原F9完整全源守护失败，派生正STA/bit已测试，但实板table0错误/监视器无START/RAW0；完整修正重建与硬件未验收。CURRENT_CAMERA已更新本轮实际47/gate2/app20原NPU恢复PID31503/31545，Flash37不动。

# v160 当前统一入口

根TASKS.md及goal_task_ledger_v160/ledger.json保留83/12/47全部任务。F9自己的gate有3条setup负值，结构/33组1250与新监视器路径已核，同一全源67968继续place；自己的最终/bit/板测待。CURRENT_CAMERA保持v157恢复47/gate2/原NPU。

# v159 当前统一入口

根TASKS.md及goal_task_ledger_v159/ledger.json保留83/12/47完整范围。F9完整174+7数字链通过、自己的全源原生67968运行，gate/物理/最终STA/bit/实物待；CURRENT_CAMERA为v157实际恢复47/gate2/app20原NPU。

# v158 当前统一入口

根TASKS.md及goal_task_ledger_v158/ledger.json保留83/12/47任务。F8与47实际路由PAD对应属性已核一致；被动首事务监视器14正常/逐字节NACK及8异常用例通过，尚未集成或上板。当前生产选择仍为v157实际恢复47/gate2/app20原NPU。

# v157 当前统一入口

根TASKS.md及goal_task_ledger_v157/ledger.json保留83/12/47全部任务。F8自己正最终STA/bit已核，真实table0事务错误、RAW0未验收；CURRENT_CAMERA已更新本轮真实恢复47/gate2/PID30630/30674。G14未来厂商仿真包已准备但52carry位未证明。

# v156 当前统一入口

根TASKS.md及goal_task_ledger_v156/ledger.json保留83/12/47全部任务。F8自己的gate+0.207ns/32组1249已核，完整原生89588仍运行；最终/bit/物理/实物待。CURRENT_CAMERA仍为v153恢复选择。

# v155 当前统一入口

权威清单为根TASKS.md及goal_task_ledger_v155/ledger.json。F8完整173+6当前实际原生89588；F7自己的gate/结构已核，最终/bit/实物未验。CURRENT_CAMERA仍为v153实际恢复47/gate2/原NPU。

# v154 当前统一入口

根TASKS.md及goal_task_ledger_v154/ledger.json记录全部83/12/47任务。F7自己的173全源诊断gate84108运行中，新时钟/复位尚未验收；生产CURRENT_CAMERA保持v153实际恢复选择。

# v153 当前统一入口

权威清单为根TASKS.md及goal_task_ledger_v153/ledger.json。F6自己的最终正STA和新bit已核，真实RAW0/错误0未通过；本轮实际恢复47/gate2/app20原NPU。下文历史保留。

# v152 当前统一入口

权威清单为根TASKS.md及goal_task_ledger_v152/ledger.json。sensor_flow本轮自己的全源gate/边界已过，实际place仍在同一PID62072；最终/bit/实物未验。生产沿用v150恢复47/gate2/原NPU。下文为历史。

# v151 当前统一入口

权威清单为根TASKS.md及goal_task_ledger_v151/ledger.json。F11当前完整sensor_flow171+6原生进程与阶段见本版native_observation；sensor_transaction自身gate/组件已核，最终/实机未通过。生产相机沿用v150恢复47/gate2/原NPU。下文均为历史版本。

# v150 当前统一入口

权威清单为根TASKS.md及goal_task_ledger_v150/ledger.json。F11真实RAW0板测未通过，已恢复47/运行时2/app20原NPU；新sensor_transaction事务/本地复位组件通过，自身原生待。下文较早v7/v9状态不是当前选择。

# 当前完整工程、13项经验与复验

路径均相对本仓库根目录。工作区位置以实际查找为准，不沿用旧电脑E盘路径。当前入口是 `projects/pcie_imx415_bar_contract37_20261010/deliverables/current_delivery_index_v1/{README.md,index.json}`。索引选择当前工程、实际bit成员及SHA；归档中的旧候选不自动成为当前版本。原 `examples` 六份成功基线保持不变。

2026-10-11用户要求明确完整goal清单，并将所有RK CSI颜色/小问题列出逐项检查。当前权威任务表为仓库根 `TASKS.md`，机器清单 `projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v7/ledger.json`。83条固定ID包含原13、FPGA预处理/固定及可配置卷积、ROI/codec/时钟、控制/按键/激光/光电、RK CSI1九项单路排错、双路同步、交付、整机后续路线与赛题验收视图。先按实际状态和依赖选择ID，完成一项后写本轮证据和scope；未来更新保留ID，不把赛题视图与功能工作量重复累计。depends_on是最终验收前置，等待实物时可以先做独立数字实现，但不能提前签核实机。

当前重点T04自己的native仍运行，T05/T06/T07压缩实机/同输入NPU/长测待own positive；K01重新probe仍芯片ID000000，但进一步测得J9实际M1匹配DT、24次SCL高/SDA低和相邻地址伪ACK，详见[双CSI经验](dual-csi-sync.md)。K02–K09逐项核对真实graph、帧长/stride/plane、Bayer/镜像、RGB顺序、YUV矩阵范围、九色、曝光和单路长测；随后才S01–S05实际两路预处理/配对/相位/长测/几何反馈。新代码顺序T08当前FPGA时钟查询、F11通用3×3卷积、I03按钮长按连发、I05激光三重互锁、F16传感器开窗。F11已有任意核完整162输入和8组当前数字证明，自己的native/bit/实机待验；长按连发和激光三重条件仍未实现，不能因基础模块native通过补签它们。

T08已完成独立`hci03_clock_anchor_20261011`完整188输入工程、4组新增数字证明（真实115200查询、原24项HCIC/HCIR、source mailbox/reset、主机54项拒绝）以及14组图像/codec同SHA组件绑定。任务状态为部分通过：live主机collector/守护入口已准备并软件验证，自己的native/bit和实机时钟标定待验；T05实际media拓扑检查已修正并接续新等待队列，下一独立代码项为F11。原E3/P3各187冻结输入未动。

F11独立`hci06_generic_conv_20261012`的九signed16系数、缩放/舍入/饱和、HCKC40、HCK6及帧界/backpressure已实现；12组当前证明包括核心3幅fullHD6220800像素、48忙态reset/144重启帧、4幅fullHD集成wrapper8294400像素、真实CSI/ISP/DBUF及115200→productionCDC→SOF联合。修复了请求RGB但核强制灰度时hist LUT错误失效，保留失败/复验。own native/实机待验；旧source-bound队列已转为WAIT_EXPLICIT_REBASE_AND_REARM_CURRENT_CDC_AND_RESTORE_BASELINE，2026-10-17无对应等待进程。先在独立副本复核当前CDC和恢复基线，不能盲启旧入口；当前TD由HCI03 G14全源构建使用。后续physical以实际生产PCIe47/运行时门限2及保留Flash37为准；操作与范围见[通用卷积](hci06-generic-conv.md)。这不会增加原13或赛题实机通过数。

## 当前六例选择

| 例 | 独立完整项目 | 实际已证明范围 |
|---|---|---|
| 01 | `projects/demo01_uart_cdc_20261010` | 实际UART输入2FF拓扑，6边界字节与131072B/115200bps逐字节一致 |
| 02 | `projects/demo02_service_cdc_20261010` | 默认未ARM不写；两轮256地址成功256/错误0，原数据双读恢复一致，RTC只读 |
| 03 | `projects/demo03_readonly_20261010` | 默认不设时，40包/39秒连续走时，NACK/BCD错误处理；未推断日期或电池保持 |
| 04 | `projects/demo04_full_capacity_20261010` | 106轮256MiB全容量和595连续CRC包；检查器及真实AXI桥联合数字测试 |
| 05 | `projects/demo05_dsi_crc_20261010` | CRC/原子UART/完整TD；90秒899包、5261帧与RGB纯色源；光学屏幕待观察 |
| 06 | `projects/demo06_dsi_frameguard_20261010` | 真实CSI→完整ISP→异步DBUF连续/启动半帧数字测试、完整TD、实际九色/CSI/ISP/DDR读出；光学屏幕待观察 |

全部项目保留原IP生成源与加密源、PLL、ROM、ADC/SDC、顶层和TD文件集；不是孤立模块。具体setup/hold、输入manifest、bit/prDB及物理证据取索引，避免手选同名旧bit。05/06仍有5条保护DSI ODDR警告。原六例的历史成功不能代替新bit光学验收。

## 原13项可复用经验

| 项 | 根因与修改/复用规则 | 验收边界与入口 |
|---|---|---|
| 1 CSI | PAD PCLK用本地LCLK、fabric用全局div输出；共同active-high复位Q直连，nibble采样与byte重组保持物理相位；解析器只从新FS输出payload | 当前37真实27MHz/891Mbps/1080p约60fps及四lane恢复/保持；不能cut相关时序。历史09静态不等于板测 |
| 2 RGB | Bayer由实际源、首行/首列裁切及镜像共同决定；中性AWB、CCM和gamma黑端点从真实RGB链核对 | 37首行16/GBRG不能盲抄到06首行1/x4/RGGB。HDMI真实XWD源、九色及同屏ROI；非全照明色度学 |
| 3 闪屏 | 保持AXIS数据与KEEP/USER/TLAST一起弹性缓存；SGDMA信用环不能在整帧包中途STOP | SGDMA36在空闲时为整请求找连续描述符，超过容量EMSGSIZE；两档各10000帧零普通拒收，原失败保留 |
| 4 短帧 | 实际1097源行到1080裁切须精确计数；最后有效拍带EOF，末行flush不能只靠补16像素 | 正常720/1080全长、4K数字golden；6220800B缺一个字节也失败，4K数字不代表PCIe x1实机吞吐 |
| 5 启停 | 格式切换先正常停止/排空，首帧重新验长及序号；活跃改格式返回EBUSY | 20轮720/1080切换，STOP后12秒、RUN/BUSY/信用/CMA；不扩展到热解绑 |
| 6 下行 | BAR、长度与单张截图不足以证明完整帧；绑定当前源、bit、boot、驱动SHA | 当前37逐行统计、序号、CSI/内核日志与两档各10000帧；选帧和全量精确统计归档 |
| 7 双向 | 原弹性FIFO必须带元数据；先打开收发，再切mux。结束等真实RUN/BUSY空闲才释放映射 | 167帧/969753600B零差异、source/echo SHA、多个DMA块长、SIGTERM/首帧与12秒kmsg恢复 |
| 8 异常 | posted STOP读回不等于BUSY已清；同步成功与取消路径均等待硬件空闲，短包拒收后可恢复 | 八负测、真实16B短包交付0、活跃close/模块重载与32帧；旧AIO/cyclic与BUSY热解绑未认证 |
| 9 互斥 | RK PCIe1/SATA1/USB OTG1为硬件复用，不能改boot实现共存；USB0须实物独立验证 | 用户明确硬件豁免验收，既有USB0未连接记录保留，不发明USB/Wi-Fi共存测试 |
| 10 时序 | 完整native源冻结、STA/PAD recovery/removal；debugger后恢复async-reg优化/布局识别，保留high hold策略 | 正式37 STA真实通过；MTBF原生崩溃/数值sentinel和动态SDF无有效结果。用户暂计并留独立prompt，不是工具技术PASS |
| 11 六例 | UART真实2FF，EEPROM备份/ARM/恢复，RTC默认保留时间，DDR全容量及完整AW/B语义，DSI实际CRC与分级帧统计，06下一SOF等待前帧排空 | 01–04实物通过，05源与06 CSI/ISP/DDR/RGB通过；光学屏幕单独观察。细节见DSI参考与各完整README |
| 12 交付 | 当前工程选择、原始失败、用户豁免和真实通过分开；源/IP/ROM/约束/当前产物/runtime/原始物理证据/复验方法逐SHA归档 | 原examples逐SHA无变化；阶段归档不回写。最新索引与独立交付审计为准，未验收项也明确交付 |
| 13 BAR | AW/W各自锁存后成对提交，WSTRB按字节作用，完整地址译码，高地址不得低位别名；RDATA在AR时锁快照、保持到RREADY | 512字/16WSTRB/错峰/背压实际RTL自检、板上CPU32bit/字节MMIO。强制RREADY和零WSTRB仅数字范围 |

正式37组合：FPGA `0x56442501`，SGDMA36/V4L2_37。完整物理汇总 `projects/pcie_imx415_bar_contract37_20261010/evidence/issues1_to8_and13_acceptance37.json`，13专项 `evidence/issue13_acceptance37.json`。不是用35旧物理结果给37补签。最后实际运行状态以索引的最新完整恢复元组为准，不能用早先连接信息覆盖它。

## 当前构建、实测与换电脑

1. 执行 `python skills/anlogic-td-demo-reuse/scripts/td_reuse.py verify --examples examples`，六份missing/added/changed必须分别检查。不要重写baseline manifest绕过漂移。
2. 在新完整副本中重定位 `.al`，用 `td_reuse.py audit --project 新目录/fpga_prj.al --direct-config 新目录/build_direct_config.tcl --fix-hold-high` 重新生成当前配置；project参数必须是实际`.al`文件，传目录会失败。执行实际audit并查看返回。保留全部IP、CWC与ROM。此命令不修改许可或安装SDK。
3. TD命令只接受正斜杠Tcl入口作为唯一位置参数：`td_commands_prompt.exe 新目录/build_direct.tcl`。不要加 `-tcl`。`projects/demo06_full_20261010/evidence/run_candidate_native.py --project 新目录 --attempt 新编号` 为当前完整源冻结、依赖及STA核查入口，依赖同目录 `run_complete_demo_suite.py`；先读路径/版本并确认没有其他native构建，序列执行，不能直接复用旧进程号。
4. 查看本轮终态、全部源/staged/hash/实际bit和prDB、STA/TNS/覆盖/警告。数字oracle与生产模块直接连接；联合测试必须覆盖连续帧交界及warm半帧，不以分段模型替代加密生产IP。只导出SDF不等于实际注入或时序字节通过。
5. SRAM物理入口位于主37 `tools/guarded_dsi_uart_physical.py`（05）和 `tools/guarded_dsi06_frameguard_physical.py`（06），必须新attempt目录。先核对串口实际VID/PID/serial及正式37空闲、卸载/解绑，从QUIESCE_BEGIN起finally恢复精确37bit、runtime、控件与新的32帧。通用program脚本只下载，不包含该全流程守护。不要重复执行只适用于旧候选版本的guard或移除版本保护。
6. 已知色测试保留实际HDMI XWD、scene身份证据和UART原始字节；主机打开串口可能排出旧包，用快照序号的50ms源间隔和模2^32计数器差值计算接受帧率。本轮06约55.56fps，不称120/240fps。614400显示像素为左上1024×600窗口，非全1080缩放。
7. 解包选定包内bit成员核对SHA；同步取得正式37源、matched SDF材料、deployed runtime和物理分片归档。库路径/版本哈希在材料中，SDK和许可不复制。凭据由用户的本地私有交接提供，不放交付包。

MTBF/动态SDF后续电脑prompt：`docs/10_后续电脑MTBF_SDF复验prompt_20261010.md`。不关闭时序检查、clamp负值、伪造加密模型或把INT32_MAX ps数值伪签为MTBF。光学屏幕缺结果时继续独立软件/材料工作，整项11保留待验收。

## T05实际节点选择修正与等待队列版本

2026-10-12当前E3/P3的`guarded_hci03_{eram,packet}_physical_v3.py`与`person_model_physical_v3.py`核对实际FPGA-MIPI→DPHY3→CSI2→video22启用sink链。旧milianke字符串会错误拒绝正确拓扑。9异常拒绝、14生成脚本及实际RK前置检查通过；不改变自己的源/STA/bit、UART/ROI/CRC、同输入NPU及正式37恢复门槛。复核`hci03_media_path_progress_v1/result.json`，不能将这项前置PASS当作实际压缩抓取/NPU通过。

旧入口和预备材料保持；三个尚无native/物理动作的自有等待进程完成验证后换为E3 physical20028、P3 native3212、P3 physical59536。实际当前句柄和CIM在checkpoint中，队列状态路径保持兼容，仍由自己的positive native决定是否行动。TD44884/parent76168/源187和P3待用源187不变。Windows脚本策略仅在已审阅的进程里使用ExecutionPolicy Bypass；不改机器策略。缺版本metadata或路径斜杠匹配失败时没有释放全组标记，保留失败记录，核对真实新进程后才放行。
