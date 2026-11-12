# v191：真实 n0 回放与新被动诊断副本

当前32条PAD→首级检查为正，稳定51实采去重4包、12次接收RTL回放/拒绝通过；新 trace2 完整副本保留接收/卷积/DSI，新增坏头前后n0冻结与版本化UART回传，修正count先锁存再判断。详见 [CSI 实采回放与被动跟踪](hci06-csi-real-replay-trace.md)。自己的最新gate/完整native/实板状态读取根清单；不据数字功能签硬件通过。

# v190：完整实板诊断和 CURRENT51 恢复

本版已经实际 SRAM 测试，内部时钟正常但 592 次采样测试/16 轮扫描均未通过，CSI ECC/CRC 故障仍阻止卷积帧界应用。原相机、模型和 HDMI 已恢复；实际失败、修复及父进程维护规则见 [bundle5 当前实板接收与恢复经验](hci06-bundle5-real-receive-20261020.md)。当前版本与运行代次以根 CURRENT_CAMERA.json 为准。以下旧版本描述均保留为历史。

# v189：打包后按逐寄存器网络核验 ASYNC_REG

不能把打包后的物理单元布尔标志当作逐FF属性清单。当前bundle5的453个门级ASYNC FF，实际均唯一映射到453个物理FF及453个原生`get_nets`读回为真的网络；245个相关物理单元只有205个带标志，另外40个单元内的53个第三级FF属性仍完整保存在网络上。此前仅按cell读回推断“53个属性丢失”已纠正，不应给混装普通FF的整颗单元盲目补属性。精确名字→物理Q等价类→唯一FF侧的核对拒绝缺项、重复、同数量外来net/错误Q根、歧义名字、假布尔值和伪计数，不能仅凭453这个数量签核。

实际最小对照`projects/td_async_pack_cases_20261020`中，三级、三级+DONT_TOUCH、四级、两级+普通寄存器共12个ASYNC声明，布局后只有4个单元标志，但12个网络属性完整，原生报告仍识别3/3/4/2级链。显式DONT_TOUCH未改变该呈现方式。报告的巨大settling数值仍无效，完整工程MTBF命令退出0xC0000005，失败/转储保留；正确链级数或网络属性不等于有效MTBF。

本版全部453个目标FF已按200条私有D/Q链枚举，并在place/route分别核对唯一FF归属、目标时钟/极性、CE、真实复位模式/值/连接和D入口：438异步复位、12无活动复位、3同步复位。检查器不能强制所有同步器使用异步复位；显示配置链实际使用同步复位，必须按原门级模式严格比较SSR与ASR。451个D按精确网络匹配；另外两个只接受既有I²C观测的PAD TS角色绑定和同D/clock/控制/初始化的并行SCL寄存器证明，不把改名当新增流水级，也不豁免其他不匹配D。9项控制反例检查通过。全部target阶段检查仍不签源D/CE布尔函数、源时钟/电气波形、外部IO/PHY、MTBF或板端RAW/卷积。证据：`projects/hci06_csi_bundle5_review_20261020/evidence/current_async_net_review_v2/result.json`及`evidence/all200_cross_review_v1/result.json`。

# 原生约束对数与不同终点数要分别验收

历史v187检查状态（“属性缺失”解释已由本页首段v189复核纠正）：当时重新推导95条既有链及64条观察器链；place/route各159条、549个实际gate/physical FF的Q/D/clock映射通过所列范围，70个FIFO decoder只签Q/clock/reset归属，未签完整D函数。245个物理单元逐项原生读回后，原453个gate ASYNC声明全部唯一映射，但205个物理单元有标记、40个无值，涉及53个第三级FF。该cell读回事实保留；其单独不足以判断逐FF网络属性丢失。全CDC/MTBF或执行就绪仍有独立验收范围。

自己的DB副本仅import不足以恢复全部运行时约束；原样重放本轮root SDC、精确reset/PLL合同后，标量才与原生+0.145/+0.020ns一致。普通报告同一physical endpoint/check可因不同源/时钟组出现多条记录，不能只按endpoint/check拒绝或去重。保留每条distinct begin/end/check/corner/group/budget路径，核对各组完整统计及目标/check集合。本版新增观察器256条、I²C19条timed记录均非负；首级SDA由datapath_only产生的hold cut仅按该精确已知约束保存为未定时元数据，不冒称hold STA通过。证据：同review项目`evidence/pathwise_raw_review_v2/result.json`、`evidence/pathwise_parser_counterexamples_v2/result.json`和`evidence/all_async_physical_route_v1/result.json`。原import-only与旧计数守卫失败保留，原工程/DB/bit保持。

bundle5完整176注册+12依赖的原生79464已终态，189输入保持，最终setup+0.145ns/hold+0.020ns、两TNS0，位流SHA `089f68a2b81753b884ed23d901aac2a6ee77fda1c2b3ae968a96ddef21ee2746`。独立原始报告解析确认最终标量、place/route所列reset/Gray/startup边界；自己的Slow/Fast PLL首段SDF最大1.294/0.807ns且私有二级普通setup/hold39.245/0.279ns。完整per-FF CDC、外部IO/PHY和19条跨阶段critical-warning仍分开归属，103个无input/output-delay报告项未签核；CDC MTBF延后，尚无本版实板RAW/卷积图像验收。最终报告两份只允许忽略各自唯一Generated时间行，其余全部字节须一致，不忽略路径或统计差异。证据：`projects/hci06_csi_bundle5_review_20261020/evidence/final_exports_v1/result.json`。

本版PAD前LUT实际接在`clock27→自动SCLK→LUT`分支上，旧审查直接比较LUT输入与clock27别名而失败，原失败保留。新审查只沿实际唯一SCLK驱动追溯至clock27，核对公开文档默认BYPASS/DELAY、无动态CE，32地址AND-enable配置全等，继续追至实际相机PLL输出1；不合并或重标记net。实际正例及其他PLL时钟、错enable、LUT单bit错、丢/多驱动、循环、动态CE、非零延迟、禁用bypass共9个反例通过。place/route实际6个观测FF映射/私有Q与并行SCL配置分别归属，外部电气/时序和保护模型行为未签核。5颗RAM的10项告警实查为B侧控制且WEBMUX0，只是B写禁用静态事实，不等于RAM复位安全或告警全部解决。证据：同review项目`evidence/export_attribution_v2`、`evidence/forwarded_clock_branch_guard_v2`。

TD的SMD例外汇总可能计源Q→首D对，而`report_timing_path -path_num 1`只保留每个终点的最差路径。实际bundle2图有901个held源FF、933个不同首D、1429个源—终点对；减法carry锥让同一终点依赖多个源。这些是该次图的观测值，不是下版守卫常量。不能只把933改成1429，或用933条最差路径推断其余连接均已覆盖。

在自己的mapped图中推导完整源—终点关系，独立核对终点集合和对集合。需要证明全部连接时，可逐实际源Q查询其所有首D，每个终点保留最差一条路径；严格核对原生真实起点、全部目标、类型/预算/slack、报告完整统计，再合并精确对集合。例外汇总的active总数与派生对数匹配，shadow/ignored仍须拒绝。全局终点齐全而漏掉一个源到共享终点的连接也必须失败。

完整候选见`projects/hci06_csi_bundle5_20261020`，验证入口为`tools/complete_held_contract_v2.py`；14项纯反例及901源查询参数闭合只证明检查机制，实际原生、SDF、最终STA/bit与上板结果分别读取本版`evidence/full_build_v1`和根任务表。父版原失败保留；不改功能RTL/原SDC预算，不因检查器修复签核RAW或卷积图像。逐源原生查询不加-to，让工具发现该源全部终点，再与实际图独立比较；不要用图目标过滤掩盖图遗漏的真实连接。

本机TD的report_timing_path把`-file [file join ...]`计算路径写到了默认文件；只加`eval [list ...]`在bundle4完整运行及同形式复现实验仍失败。该实验中普通字符串变量、字面嵌套路径均正确：无-to的单源1对/扇出33对与目标过滤控制33对匹配，原所有源/报告/DB保持。因此本例新候选使用字面相对报告路径并检查cwd，且严格拒绝缺文件。不要泛化成“所有变量均失效”，或仅凭日志中空from/to断言真实过滤丢失。所选查询只确认API写法，完整构建仍须本版全部逐源报告。

# 历史v179：app28与异常提交边界

F11原F14的RUN/table200/ACK与正STA只保留限定范围，RAW0/通用卷积仍未验收。当前hci06_csi_observe2_20261019完整176+9、171staged，HDL同revision1；仅Gray27→root firstD预算38.000改35.037ns（低于源37.037ns）并更新精确guard，preflight17538…通过。root已实际启动own native64204，owner/创建时间/入口和176+9源已只读绑定；place/route debug-reset coverage将从本次实际网表推导，不沿用T08 expected1。尚无本次gate/place/route终态STA/位流或实物通过，不能把v1预算或旧native证据签给observe2。

保持CURRENT选中的51/stage0/gate0/app28及绑定原NPU，明确app25 fallback；Flash37不变，USB/RK CSI/AIQ仍隔离。继续剩余真实阴影/肤色与有效NPU处理率、个人13点标定/20点留出、眨眼/游戏；逐帧颜色归因需同源同帧RAW及实际AWB/曝光和暗场/中性色标，不能按椅子低尾猜阈值。保留T08失败原件并推导实际约束端点，不猜负slack或删约束。完成同一F15 observe2 native64204及自己的完整静态/物理审查，不重复启动或提前签核。全部83+12+47状态保留，RK精确源码/安全停流与真实双摄仍待。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v179/actual_app28_T08_observation.json`。全部83+12+47及status保持，未扩大画质/光学/整机验收。

# 历史v178：当前应用与限定证据

F14原完整174+9正STA/bit和23项wire路径仅保留原限定范围；实板RUN/table200/ACK后仍PHY窗口0、RAW0，通用卷积图像未验收。新增对稳定51的源/实际网表对照：201项模式表仅4项GAIN不同，lane/rate/INCK一致，双方64位采样Q/D/clock及LCLK/PAD/PLL参数一致；F13少量good包伴大量CRC坏，F14主要停在包头前，尚无已证实功能修复或光学根因结论。历史F14试验恢复47/app24不作为当前恢复目标；当前按CURRENT选中51/app25。

下一独立观察候选仅本地准备；不沿用旧位流、旧held计数或父STA签新接口。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v178/actual_app25_T08_observation.json`。该版本保留83主项、12正式项及47 RK子检查和全部status，不增加验收。

# v172 F14已终态及实板训练失败

F14完整174+9已原生终态：5584.813秒，最终setup +0.158ns/hold +0.020ns、TNS0及自己的bit；内部LUT驱动配置及全部23项实际wire时序检查通过限定范围。真实上板传感器RUN/table200和ACK通过，但PHY窗口0/无deskew/RAW0，首项卷积命令未在帧界应用，后3项未执行，实际图像与通用卷积仍未验收。已用同一BW恢复47及原app24，无Flash新写。字节齿轮/对齐、9个相机ADC属性和27MHz PLL与稳定47核对，不能凭这些推定实际时钟波形已正确。

# v161 F9派生正STA与实板无START诊断

F11新F9原完整174+7在1456.328秒以rc1终止：守护误限功能producer只能直连D；之后自己的布局副本路由也被固定LUT脚顺序守护拒绝，两次原始失败均保留，未当作完整重建通过。新增严格LUT6六输入双射/64组合等价及12反例通过；自己的派生route终态生成9fb4c51e…位流，最终setup+0.140ns/hold+0.020ns、TNS0、no_clock/invalid0；place+0.551ns，33私有resetFF/19ASR/19D、38组1308路径活跃，完整修正全源重建仍待。自己的95条所选CDC链357FF/70decoder归属、监视器4同步FF/私有首Q及实际wire首D1/后D6/SR4原生路径均已核；SCL监视使用与PAD驱动同D/同clock/同控制初值的并行寄存器，place/route12反例通过，不是外部SCL回读。全阶段5类39条重复计数告警保留且未豁免。实际派生SRAM测试7681字节110完整CRC/seq连续包、尾部1字节有效未完整包前缀；14个v3快照均startup0x057f、table0/state11、ACK-error history1，但wire无START/STOP/完成字节，RAW/ISP0，硬件未验收且不能推断传感器电气NACK。已真实恢复精确47、app20 STREAMON后gate2完整2073600像素hist、5GT/s×1、原NPU会话PID31503/31545；同boot前42480/后42588条内核日志严格故障候选0，Flash37未动。随后同RTL全部250分频相位均能捕获首写与NACK1，未复现实板无START；实际gold47与F9 SDA十项显式PAD参数一致，仅限静态归属。GitHub/资料再查仍无已核匹配的厂商Linux6.1.99源码，官方SDK入口已记录；真人暂缓，RK CSI/AIQ隔离。

功能producer的内部LUT6 D与同步级的直连D必须分开严格检查；route可交换LUT输入脚，须比较真实六输入双射和全部64种组合，不能要求INIT字面相等，也不能放宽同步级私有Q/直连D。SCL内部并行复制寄存器必须核同D/同clock/同初始化与控制，不能把它写成外部PAD回读。聚合ACK-error history与被动wire无START同时存在时，先检查可观测性和复位/时钟，不直接判传感器NACK；250相位RTL通过和PAD配置一致也不证明实板根因。失败全源后从自己的DB派生出正STA/bit必须如实标为派生，完整修正全源仍待。每次真实JTAG后更新CURRENT_CAMERA到本轮恢复PIDs/会话/hist，保留所有失败原始报告。

# v160 F9自己的门级结构与真实负时序

F11新F9完整174+7已完成自己的gate并继续同一原生67968的place。实际门级估算setup−0.061ns/TNS−0.179ns、hold0，3条普通同域setup负值均从CSI parser/packet_len[1]到stat_crc_event/packet_error/raw_good；配置器和新监视器无负值，不能写门级或最终正STA通过，保持普通约束等待物理。严格33组1250全部活跃、SR0/D19/clockGray首6/后12端点均有正值，自己的14私有复位链33FF、2startup握手及12快照重核。新增监视器实际4同步FF/私有首Q/开漏PAD输入与SCL master输出连接已核，真实首D布线预算检查+36.295ns，3个后级普通setup最差+39.183ns；非外部电气/MTBF验收。新的60次原生查询重算2340别名/2304数据FF capture/hold，1152 held→1152已审查D闭合；FIFO72编码/70解码/6clockGray、5个注册singlebit源和UI resetless历史两沿flush均在本版gate新算，未携F8 gate identity。继承的两条报告标题错写正gate/32组已保存并以v2明确纠正，数值和原3负路径不变。实际HCK6v3联合数字71包23HCK、NACK2/4/复位完整初始化和3条measure恢复fixture保持；再核当前v3混合串口/19图像oracle反例及14恢复故障用例通过。自己的物理/最终STA/bit/实物未完成；当前生产仍v157真实恢复47/gate2/app20原NPU，Flash37不动，真人暂缓、RK CSI/AIQ隔离及匹配源码未取得。

复制审查工具后必须核对标题与实际数值：图结构/约束覆盖PASS不能改写为正时序。本版3条同域setup负值真实保留，不加false path掩盖；后续以自己的place/route最终STA判断。新增被动监视器4FF首级私有Q、PAD到首D和普通后级D已由本版原生报告验证，仍不是输入电气/同步器MTBF证明。改变顶层后，60 native查询、held闭合、FIFO Gray和registered singlebit均重新在新gate执行，不能借旧网表相同结论。

# v159 完整F9与实际外部总线应答联合链

F11新F9 wire_diagnostic_flow完整174+7已冻结并启动自己的全源原生67968；只新增被动总线监视器、顶层接线、HCK6v3及SDA首D精确布线预算，传感器I2C核/表/27MHz启动、ADC和视频算法字节保持。HCK6v3仍96字节，word19高16与word21低16组合实际首笔四字节，word21同时携逐字节ACK/首NACK/完整性；与配置状态同一root25沿冻结。实际startup→旧core/201表→外部SCL/SDA从机→被动监视→115200 UART联合仿真通过：205笔总线事务（两次故障和203次完整初始化）、71完整CRC/seq包23 HCK，每包四字节/ACK诊断/配置/启动均与源冻结沿一致；第2、第4字节NACK各5快照被正确拒绝，复位后完整RUN及11个readiness反例/5个codec场景通过。真实旧v2板测20HCK仍解码，旧v2 reserved wire字段严格拒绝，不冒用版本。新33组1250严格守护6用例通过，仅异步SDA首D38ns预算，后级普通STA保持，不代替外部电气时序。实际board measure入口用这份真实RTL数据验证NACK2/NACK4保存诊断后失败、控制/首线ready但无图像仍失败，3条失败均按UART关闭→47→app20→gate2恢复fixture；不是新板测。只读板端同boot/PID30630/30674、5GT/s×1、原模型SHA/CPU4会话及状态年龄96.39ms，整boot41104内核记录严格扫描0候选。新全源自己的gate/物理/最终STA/bit及实物待；F8真实table0错误根因仍未证明，生产CURRENT_CAMERA保持v157实际恢复47/gate2，Flash37不动、真人暂缓/RK CSI隔离。

新版本诊断必须冻结同一源时钟沿，完整四字节可跨明确版本字段编码并在接收端还原逐包对照；旧版本reserved检查保持。联合测试应由仅观察外部SCL/SDA的从机应答，不能看master内部W_ACK：本轮第2/4字节NACK分别定位、重置监视器后完整203写初始化通过。控制和首笔总线ready仍不足以放行图像测试，实际measure必须继续拒绝RAW/ISP/完整像素缺失。新顶层改变后重新做自己的全源gate/物理审查，不能沿用父版正STA、位流或整网表相同结论。SDA首级max只是布线预算，保留后级STA与外部I/O/电气待验。

# v158 首笔I2C被动诊断组件

F8与47实际路由PAD对应属性已核一致；被动首事务监视器14正常/逐字节NACK及8异常用例通过，尚未集成或上板。当前生产选择仍为v157实际恢复47/gate2/app20原NPU。

I2C应答诊断应由实际外部SCL/SDA驱动观察：保留首笔四字节、每字节ACK、首NACK、START/STOP及不完整状态；未观察到的ACK位0不能当NACK，必须结合完整字节数。首笔STOP后冻结并由复位清除，不能被后续写覆盖；SCL停止不伪造完成，SDA卡低不伪造START。监视器必须被动、不反馈控制，测试中覆盖真实未改动核心/延迟ACK/每字节NACK及异常。新诊断不能写入旧协议要求为0的reserved word，集成需新明确版本、输入CDC/IO审查和新的完整构建。实际PAD属性相同只排除对应配置差异，不能代替板端电压、时钟波形或传感器就绪证明。

# v157 F8最终正STA与第一笔I2C实板错误

F11完整F8 startup_flow173+6全源已终态0，2294.062秒；最终setup+0.189ns/hold+0.020ns、TNS0，no_clock/invalid_constraint0，生成自身fca22a15…bit。自己的place+0.558ns，place/route均核33复位FF/19私有ASR与startup两握手各级D/SR；实际debugger2FF/1ASR，37组1306活跃max。自己的95条所选CDC链357FF及70decoder Q/clock归属已核，仍非完整物理逻辑/IO/波形/MTBF验收。告警place17条4代码/route19条5代码未豁免；route实际SCLK分支到MCLK门控PAD已追溯，未推断电气波形。真实短时SRAM测试连续7744字节111个CRC/seq连续包：13个v2配置快照均startup0x057f、state11 ERROR、table0、done0、sticky错误及transaction ACK-error history1；RAW/ISP拍及帧0，错误计数0，未通过。只能证明第一笔事务错误，尚未证明电气NACK根因。已在同一owned BitWriter31256恢复精确47，PCIe重绑/app20 STREAMON后gate2，完整2073600像素hist active/tag2；5GT/s×1、原NPU模型SHA/CPU4与新PID30630/30674恢复，同boot前40190/后40298条内核日志严格扫描0候选，Flash37保持。独立外部SCL/SDA应答的真实I2C核8用例通过24MHz/239与25MHz/249、0/500/3450ns延迟及NACK；核与生产47字节相同，未复现板上根因。F11仍RUNNING；真人暂缓、RK CSI/AIQ隔离。

真实错误必须记录同版本的配置state/index和transaction ACK-error history；RAW0且所有包错误0不等于健康，数字startup RUN也不证明MCLK电气波形。ACK测试器只观察外部SCL/SDA，不能由master内部W_ACK驱动应答来代替总线时序。24/25MHz数字8用例通过不代表板端ACK根因已解决；本例核心与生产47字节相同。实际每次JTAG后更新CURRENT_CAMERA中的新PID/会话和完整hist证明，不能沿用上轮恢复状态。

# v156 F8自己的正门级与实际I2C/UART数字诊断链

F11当前完整startup_flow173+6自己的gate已通过：setup+0.207ns/TNS0、hold0，普通负检查0、配置器负端点0；32组1249全部活跃无shadow/ignored，33私有SR切断、19后级D与clockGray首6/后12准确原生覆盖。自己的14复位链33FF/2startup握手/12快照已重核。只排除验证过的vendor banner/时间行后，当前全部gate body及CDC属性与自身F7已实核gate逐字节相同，SHA753c4d8c…；可携2340别名/2304FF capture/hold、1152 held→1152D、FIFO72/70/6、5单bit及UI flush限定结构结论，不携旧STA/物理。当前完整原生89588实际仍在place。新增控制诊断已用实际startup→I2C core/table（CLK_DIV249，真实100k名义时钟）→115200 UART联合仿真：49连续CRC/seq包16 HCK、4个真实NACK快照、复位后完整配置及ready字段与源冻结边沿逐包相同，7反例拒绝；这是数字组件，不是板端ACK或CSI数据证明。实际板测measure入口先读v2配置/启动状态；用该真实串口数据验证NACK错误保存后恢复、以及控制ready但图像无效仍拒绝并恢复，14恢复故障注入和19图像oracle反例通过。自己的最终STA/物理/bit/板测仍待。板端只读确认同boot47/app20原模型PID29854/29896、5GT/s×1和CPU4，状态年龄148.28ms；整boot39441记录严格扫描0候选，不作为真人FPS或新NPU推理证明。生产选择保持v153，Flash37未动，真人暂缓、RK CSI/AIQ隔离。

诊断应沿实际startup→真实速率I2C→UART整条数字路径验证，逐包对照源冻结边沿；core ACK错误可先于transaction-end sticky latch，fixture不能在第一个error边沿假设两者已同时提交。板测先保存明确版本的配置state/index/错误，再跑图像oracle；控制ready也必须拒绝缺RAW/ISP/完整像素的场景。两个失败分支均用实际controller measure和实际恢复orchestrator验证UART关闭→47→app20→gate2顺序；此数字恢复fixture不替代真实JTAG恢复。

# v155 F7自己的门级与F8完整启动流程

F11的sensor_startup173源诊断gate已终态0/612.578秒；实推14条私有复位链33FF、两条startup request/ACK同步和12快照握手。当前未加新边界gate为setup−2.460ns/STNS−28.904ns、hold0，21负检查实分1条ACK首级setup−0.033ns及20条已核私有SR recovery；no_clock0但旧C1命名invalid1，不计正STA。自己的60次原生查询2340别名/2304数据FF capture/hold、1152 held→1152目的D闭合、5 registered单bit、UI resetless两边沿flush、72 FIFO encoder/70 decoder/6clockGray已重新计算。仅PLL新输出的混合concat[1:0]使首版分析选择器失败，改为展开真实位序；RTL未改。新完整startup_flow173+6保持全部RTL/IP/ROM/ADC与本轮gate/组件相同，只修自己的入口/元数据及根SDC：移除无效主PLL C1命名，命名实际camera27，并给两条已核同步首D加精确35.037/38ns边界。33 SR/19后级D、32组1249守护和缺失/重复/无效反例通过；新物理helper逐阶段验证实际startup FF/时钟极性/复位/直连数据与未切后级D/SR，当前自己的完整原生PID89588实际存活。最终STA/bit/新物理与上板仍待，不携旧F6正STA；F6真实RAW0/错误0失败及v153实际47/gate2/app20原NPU恢复保持，Flash37未改。真人暂缓、RK CSI/AIQ隔离，匹配SDK未取得。

PLL输出可将相邻有效位合并为concat内的[1:0]，按逗号数量索引会误选open线；必须展开真实位宽再选output1，并保留常量占位。原生STA负项应按端点分类：本轮1条来自已核双触发ACK首级，不是普通同域数据；精确首D max边界不切后级D/SR。新边界须先加入expected字典再解析实际report，missing/duplicate/inactive反例须拒绝。完整构建中直接保留本轮60原生alias查询，避免为同一门级重复编译。

# v154 F7有序启动与明确版本配置诊断

F11新增完整sensor_startup173注册/168 staged副本，复用生产47的27MHz PLL及XCLR低→高→完整MCLK→ACK→配置释放顺序；I2C、AE和配置诊断统一到板载root25域。HCK6 v2在原保留字18/19加入真实配置state/index/done/NACK/忙及startup状态，v1兼容。实际组件已通过5次锁定/复位/停钟启动、缺27时钟不放行、真实core/table的NACK拒绝/忙超时/203笔完整事务及80ms等待；真实115200十包704字节冻结字段和499999周期旧模式等价通过，真实配置诊断与5个版本/保留字段反例通过。首版诊断fixture在error的delta-cycle采样过早失败已保留，改为下一下降沿核对，未改RTL。自己的全源诊断gate当前PID84108，实际CIM确认存活；新27MHz跨域/复位合同、门级映射和最终STA/bit/实物未验。已发现继承SDC对不再使用的主PLL C1进行rename，工具明确报空对象；本轮保留诊断，下一独立副本修掉该失效命名后才接受约束，不编辑运行中源。F6自身正STA/位流与RAW0失败仍分别成立；生产保持v153实际恢复47/gate2/app20原NPU、Flash37不变。公开GitHub精确检索未取得可核对的同版源码；厂商目录确认3576-v1.1.0包和32bg下载入口，下载内容仍未取得。真人暂缓，RK CSI/AIQ隔离。

修传感器启动时把I2C和其多位状态保持同一UART参考域，避免为诊断另加不一致采样；协议用新版本启用原保留字段，旧版本仍必须拒绝非零保留字。直接检查真实NACK/超时/RUN状态字，不能从RAW0推断配置错误。功能移走后，原PLL输出可能被优化掉，继承的rename_clock会空匹配；必须据本轮实际工具修约束，不把退出0当干净时序。

# v153 F6自己的正时序与真实RAW0板测

F11完整sensor_flow171+6自己的全源已终态0，2038.188秒；最终setup+0.275ns/hold+0.020ns、TNS0，no_clock/invalid_constraint均0，生成自身c5d61720…位流。自己的place/route均核30复位FF→17私有ASR、后级D/clockGray与动态debug严格守护，35组1305活跃max；实际93条CDC链351FF和70decoder Q/clock归属已核，仍不代替完整逻辑等价/IO/波形/MTBF。告警place17条4种代码、route19条5种代码均分类未豁免。已实际短时SRAM测试：连续7744字节111个CRC/seq连续包，profile1 DSI426→637，RAW/ISP拍及帧0；与父F4不同，本轮CRC/ECC/WC/overflow/timeout全0，video reset释放位0，HCKaccepted1/applied0/输出0，无数据且零错误不能验收。配置done/错误本轮未直接遥测，不能推断实际NACK或根因。已在同一owned BitWriter90840恢复精确47，重绑PCIe、app20 STREAMON后提交gate2，完整2073600像素hist active/tag2；5GT/s×1、原NPU模型SHA/CPU4和新PID29854/29896恢复，同boot前38468/后38577条内核日志严格扫描0候选，Flash37保持。9个摄像头ADC引脚/属性与47一致，但当前MCLK25MHz/XCLR恒高，与47的27MHz/有序复位启动不同；下一版修启动并加配置诊断。F11仍RUNNING；真人暂缓，RK CSI/AIQ隔离及匹配SDK未取得保持。

真实F6板测把父版RAW0/ECC增长变为RAW0/错误0且video reset未释放；这说明错误计数也可能被未就绪流水线压住，不能当修好。配置错误和完成必须直接可观测，不能从下游零计数反推NACK。摄像头ADC9项一致不代表MCLK/硬复位一致；独立记录25/27MHz和XCLR启动。保留自己正STA位流与失败板测两个结论，并按实际新JTAG恢复更新CURRENT_CAMERA，不沿用旧PID/会话或仅ABI。

# v152 当前：自己的全源gate边界与真实V2文档

F11当前完整sensor_flow171+6自己的全源已通过gate并进入实际place，同一PID62072实际CIM确认存活。自己的30 SR入口/17后级D/clockGray首6后12和30组1247活跃约束严格通过；本轮gate scalar−0.057/−0.167ns，hold0/TNS0，只剩3条parser普通setup估算，控制器相关负端点为0，未豁免普通路径。本轮13条复位链30FF、12握手与实际配置器clock/reset已重核；仅排除经格式验证的vendor头和工具时间行后，本轮gate全部设计body和CDC属性与自身sensor_transaction已实核gate逐字节相同，精确携带2340别名/2304数据FF、1152held→1152D闭合、FIFO72encoder/70decoder/6clockGray、5单bit及UI resetless flush的结构结论；不携带旧STA/DB/物理/bit。实际门级报告包含正路径，首版分析器全负假设失败已保留并改为筛负，原生未重启。本机同版TD附带UG910_1.6§23.3的PDF页69/印刷57已抽取并渲染目检，明确V2默认BYPASS=ENABLE/GSR=ENABLE/DELAY=0，不取V1默认值；缺省参数资料缺口已补，但CE引脚缺省/显式实例覆盖/传播相位/IO实测仍不签。自己的place/route准确物理SR/D与debug数量、最终STA/告警/bit和板测仍待；本轮未触板端，生产47/运行时2/app20原NPU沿用v150实际恢复记录，Flash37保持。F11继续RUNNING，完整goal范围未缩减。

同一当前原生中，SR30/D17与clockGray边界、30组1247原生覆盖可先单独签门级范围，3条普通setup估算仍须布局布线收敛。只在完整gate body和全部CDC属性字节相同、仅排除验证过的时间头时复用限定结构结论，不复用STA/物理。普通summary含正路径，不能把全负专用解析器直接用于它。本次UG910_1.6§23.3图表实证V2默认ENABLE/ENABLE/0，补足先前protected模型无可读默认的资料缺口；源代码V1默认DISABLE不能覆盖V2，文档参数也不能代替实际实例覆盖、CE/GSR波形及实物。

当前工程`projects/hci06_sensor_flow_20261017/fpga_prj.al`，实际stage/owner见本版native_observation；下文较早记录保留。

# v151 当前：传感器修复自身gate已核，完整原生运行

F11修复版sensor_transaction自己的171项全源gate已终态0/567.531秒，全部输入与runtime保持。自己的原生图已核13条私有复位入口/30FF（新增25MHz三级）、12快照握手、60原生查询2340别名/2304数据FF capture/hold、1152 held→1152目的D闭合、72 FIFO Gray encoder/70 decoder与6 clockGray真值、5 registered单bit和真实UI resetless历史flush。未加父版SR cuts的根30组gate剩23负检查：3条parser setup（最差−0.057ns）和20 recovery；涉及新cfg_done的4条都是已核私有复位入口，不能把−2.418ns总scalar签成正。已建立完整sensor_flow171+6，所有RTL/IP/ROM/ADC/根SDC与本版已实核gate一致，只更新自身入口/输入哈希和当前30 SR/17 retained D；5个实际Tcl缺失/重复反例及本版原生30组/1247覆盖通过。自己的完整构建当前PID62072，实际CIM确认存活，阶段optimize_rtl；最终STA/bit/物理/告警/实机仍待。生产选择保持v150实际恢复47/运行时2/app20原NPU，Flash37保持，本轮未动板端。F4实际RAW0/ECC增长失败不改写；真人暂缓、RK CSI/AIQ隔离与匹配SDK未取得继续保留。

传感器控制器从错误完成改为事务完成时，新增本地复位链必须纳入自己的原生入口合同。当前实推13链30FF、17后级D，而非沿用27/15；仅私有异步入口SR允许精确切断，所有后级D、clockGray下游及普通数据仍计时。门级总scalar为负时按实际端点分类；本轮23负检查中3个普通setup继续正常收敛，20个recovery不可凭数字个数豁免。SCLK_V2受保护默认值不可猜，新物理helper只追显式typed连接并标注未验波形语义。

完整入口`projects/hci06_sensor_flow_20261017/fpga_prj.al`。本轮未烧板；下文v150真实板测失败/47恢复仍有效。

# v150 当前：真实F11板测未通过，47恢复与传感器事务修复

F11已实际用自己的正时序ffdf…位流做SRAM板测，单一COM4连续7744字节/111个CRC与全局seq连续包；profile1显示帧432→643，但RAW包0、RAW/ISP接受拍与帧均0、ECC2205→3372。HCKC已接收却没有SOF/应用核/输出帧，固定核实机未通过，DSI扫描不是有效相机画面。已在同一owned BitWriter按实际JTAG日志恢复精确47，之后重绑PCIe、启动app20并提交门限2；完整2073600像素histogram的active/tag均2，原模型SHA/CPU4及5Gx1恢复，同boot恢复前后整boot内核日志严格扫描无候选，Flash37保持。8个RX源对照确认采样/分频/字节对齐/自动延时核心与47相同，真实RAW0根因未定。另以真实旧RTL复现NACK仍cfg_done；独立完整hci06_sensor_transaction_20261017已移植47事务/错误锁存/80ms等待，保留固定binning表，按25MHz配置并加3级本地复位释放。当前ACK/NACK/忙超时/201表项+2唤醒事务/复位，以及精确顶层20停钟相位组件通过；167注册文件与6 helper保持。新副本尚未自己的原生/STA/bit/板测，build stage哈希与新增reset/CDC合同待重建，FLOW_NOT_READY保留。F11继续RUNNING；真人暂缓、RK CSI/AIQ隔离，匹配SDK公开检索仍未取得。

F11真实板测须同时看RAW/ISP/SOF/核与屏幕计数；DSI扫描和非零RGB总和可在RAW0时继续，不能算相机有效。命令accepted也不等于SOF应用。首轮预检先拦住部署setup哈希差异；当前RK脚本使用native32 BAR写和gain32，与较早Python MMIO/gain100本地脚本不同，恢复应绑定真实部署文件，不把旧本地覆盖上去。实际恢复顺序为精确gold47下载成功→PCIe重绑→app20 STREAMON→门限2提交及完整上一帧hist tag2核对。旧配置器忽略NACK、cfg_done早于可靠唤醒且重复启流；复用真实47控制器后仍须绑定实际控制频率、保持表语义并加本地复位。NACK组件复现不证明板上本次NACK，错误分类要保留。

当前新源：`projects/hci06_sensor_transaction_20261017/fpga_prj.al`。待自身完整原生，不使用父版正时序/bit签核。父F4板测原始证据：`projects/hci06_dynamic_debug_flow_20261017/evidence/board_trial_v2/independent_review.json`。v149文档在其ledger快照；下文为更早冻结历史。

# v148 当前：F11自己的正布局与动态调试守护已通过

F11当前完整171+6全源构建已实际通过自己的布局资格并进入route：setup+0.740ns/TNS0、hold0/TNS0；自己的27 reset FF→15私有ASR、SR0/D15/clockGray首6/后12通过。新动态调试校验实推3目标FF/2物理ASR，35组/1305路径全活跃，上一版固定1而中止的问题已由当前真实全源流程修复，原失败保留。当前自己的12握手/5 registered单bit/70有效FIFO Gray/6 clockGray共93条物理链、351 FF及70 decoder Q/clock归属通过，2不活动Gray位及decoder D完整物理真值不冒签。自己的gate在仅排除合法工具创建时间行后与原自有171 body逐字节相同，CDC属性也完全相同，2340别名/2304数据FF capture/hold及1152 held→1152D结构闭合可准确复用；不沿用旧STA/DB/物理结果。已定位17条critical warning：10条RAM读B控制、1条摄像头时钟输出、5条DSI ODDR reset、1条DDR clock cascade，均未豁免。新增实机固定灰度/切换验收pure oracle已通过真实相同RTL的DSI6/DSIF/HCK6字节和19正反例，尚未板测。当前同一native继续布线；自己的最终STA/bit/PHY/IO/告警及实机仍待，F11继续RUNNING。

当前布局实测说明应精确推导每阶段ASR数，保持全部用户边界及无shadow/ignored，而不继承模板数或接受范围。复用结构证明前，本轮只排除经格式核对的vendor banner/creation-time两行，剩余53257449字节及全部CDC属性逐字节相同；不归一化cell/port/INIT/声明，不携带旧STA或物理结论。实机常量核测试使用coef全0+bias，核对accepted/applied序号、参数、RAW/ISP/kernel/DSI进度、错误增量及全显示帧RGB总和；周期遥测不是每帧/逐像素/光学证明。混合64/96字节串口只在初始最多95字节内找CRC边界，建立后不静默重同步，末尾partial字节不计完整包。

当前入口`projects/hci06_dynamic_debug_flow_20261017/VALIDATION_CURRENT.md`。下文v147及更早记录为保留历史。

# v147 当前：F11精确边界、实际布局与动态调试复位校验

F11已在独立exact171副本实际应用30组/1247精确max边界，gate的12握手/27 reset/72-70 FIFO Gray/6 clockGray、5路registered单bit及resetless completion两UI边沿flush已实核。完整全源本轮1209.031秒在布局后守护失败，未route/bit；实际qualified place为setup+0.740ns/TNS0、hold0/TNS0，3条parser gate−0.059ns已正常布局收敛，未豁免。失败原因是模板把调试复位预期写成1；隔离复制自己place DB并重放自己runtime后，原生/实际FF与ASR映射实证3目标FF共2物理ASR，35组/1305活跃路径全覆盖、2条recovery各+1.659ns，原构建全部文件SHA保持。另已核对所选93条实际物理CDC链/351 FF及70 decoder Q/clock归属，2个不活动Gray位保留未签；不作为完整物理数据等价/MTBF/IO验收。新完整hci06_dynamic_debug_flow_20261017保持全部RTL/IP/ROM/ADC/根SDC，171+6输入，只修每个place/route从当前原生别名和物理FF推导精确ASR数量的校验，16正反例和旧真实报告通过；自己的全源构建状态见本版native_observation。最终route/STA/bit/PHY/IO/告警/实物仍分项待验，F11继续RUNNING。

调试器reset的有效路径数量依赖当前寄存器打包：3个逻辑目标可能共用2个物理ASR引脚。不能继承模板固定1，也不能放宽成接受1或2；从当前阶段get_regs实际别名解析物理Q所有者、JTAG源时钟、DFI目标时钟与直连ASR，推导唯一物理端点数，再严格核对活跃/无shadow/无ignored数量。place和route各自推导；仅改变覆盖校验，不新增时序豁免。F3原失败记录保留，不写成整轮通过。2-beat tag buffer实为MSLICE DPRAM/DRAMHARDCON，不能按FF数组证明；resetless completion必须以真实两UI边沿flush及全部消费者reset/D cofactor验证，不能伪称有reset。

当前完整入口`projects/hci06_dynamic_debug_flow_20261017/fpga_prj.al`，验证状态见同目录`VALIDATION_CURRENT.md`。下文v146/F2、v145/F1及原162是冻结历史，不代表当前候选仍只有proposal。

# v146 当前：F11 PHY/CDC完整副本与自己的网表、快照保持闭合

F11当前完整副本hci06_phy_cdc_rebase_20261017为171输入，保留已实改本地复位/两拍ready边界，加入已审G14 readable PH1A RX/clock-detector/CSI feedback与FIFO属性、显示配置3FF和registered读帧信号；算法/控制/ISP/DDR/ADC保持。组件192像素/字节序及缺失复位反例、24种lane skew/断PHY复位、clock-detector丢钟/Gray/复位反例、5200拍/5busy reset/20停钟相位及完整CSI→ISP→核→readycut→DBUF两帧96字12burst/592背压通过。旧1拍包间隙fixture超时保留，新fixture按实际新PHY完成/drain合同留12拍，包内3拍holes保持；不宣称真实采样PHY通过。自己的171 gate/60别名查询已终态，原生未加替代根时序例外，290负检查为270 setup/20 recovery；3条同域parser最差−0.059ns保留正常收敛，scalar−2.807/0是未加精确边界的诊断，不是STA通过。实际12握手/27复位/72 Gray encoder和70 decoder/6 clockGray、2340别名/2304数据FF控制和1152 held→1152目的D闭合通过；32个post数据FF CE锥仍全本视频域。18组快照bound/1164预期路径仅由自己的证明生成proposal，尚未应用。下一步逐项补核5单bit、6 FIFO Gray/clockGray与精确SR入口，集成新的完整副本并own原生，3条parser同域常规收敛，不豁免。最终STA/bit/实物未验，F11继续RUNNING。

当前入口`projects/hci06_phy_cdc_rebase_20261017/VALIDATION_CURRENT.md`。下面v145的163输入修复、v144未切断162清单和原算法工程均为保留的真实历史阶段。生产相机仍沿用v134最后实核记录，真人暂缓、RK CSI/AIQ隔离；本轮无板端、相机、模型、JTAG或Flash操作。

# v145 当前：F11各域复位与ready边界已实改并完成自己的门级复核

F11新完整副本hci06_domain_ready_rebase_20261017已实改：DBUF写/读各域3边沿释放、UI源标志寄存和两拍RGB/帧标记/config弹性缓冲；算法/UART/ADC字节保持，163输入，根SDC与原诊断相同，未新增时序例外。5200拍顺序/5次带数据复位/20相位停钟释放及真实CSI→完整ISP→signed核→readycut→实际DBUF两帧96字/12burst/604拍背压通过。自己的gate终态497.110秒，SWNS-2.340ns，剩余313负检查{'setup': 266, 'recovery': 47}、同域0；原DDR复位/写FIFO指针到preprocess负端点均为0，实际post CE控制锥全部止于本视频域FF。此为有实改和门级证据的阶段修复；剩余PHY/CDC/准确边界、own正STA/bit/实物未验，F11继续RUNNING。

当前入口为新副本`VALIDATION_CURRENT.md`。下文原162工程、旧队列与v144均为保留的历史阶段，不代表TD仍被G14占用或本轮尚未执行。生产PCIe47/运行时门限2、Flash37沿用最后v134实核记录；本轮未访问相机、模型、串口或下载器，真人测试仍暂缓，RK CSI/AIQ继续隔离。

# 通用九系数图像卷积

完整例程`projects/hci06_generic_conv_20261012`是C1独立副本，162个当前构建输入，新增5个RTL，保留相机/ISP/DDR/DSI/IP和约束。F11状态为部分通过；12组当前数字/软件证明已通过，自己的native/STA/bit和实机待验。不能借C1位流或时序结论签核它。

`hci06_conv_quad`处理每拍4个8bit灰度像素。核按从左上到右下排列九个signed16系数；shift0–23，signed16 bias在缩放之后加入，再饱和到0–255。nearest关闭采用有符号算术右移，即向负无穷取整；开启为最近取整，半值远离零。边缘复制，三组逻辑PDPW ERAM只存邻域，不复位RAM。乘积25bit、行和27bit、九项总和29bit及缩放32bit容纳极端系数。

完整系数/参数/序号仅在实际接受SOF时生效，并保持到最后复制底行和所有输出排空；不能只在输入valid或外部SOF边沿换核。global elastic enable同时冻结RAM读写、像素和tag流水线。单行/4像素宽、signed极值、非可分离随机核、背压、下一SOF等待和帧中命令噪声已纳入像素oracle。

真实RGB canonical低字节红先转灰度。generic enable覆盖请求的RGB旁路位；关闭则保持原固定高斯/Sobel/hist/morph/RGB模式。实际发现RGB请求+generic开启+hist时，旧invalidate_lut仍按请求RGB位清LUT，导致W4H1第29输出与参考不同。修复为按有效`output_bypass/rgb_bypass`失效；保留v2失败，当前active v3与disabled baseline v2同SHA通过。配置请求不等于输出模式，这是复用混合流水线时的关键约束。

真实vendor115200 UART支持原HCIC16与新增HCKC40独立CRC/序号/20ms timeout；不在固定包内部搜索magic。200bit coherent mailbox传到视频域，再由SOF实际提交。DSI6/DSIF保留，尚未收到HCKC时连续499999周期与原发送器一致；收到后增加96B HCK6 coherent applied-profile telemetry。完整字段见工程`PROTOCOL.md`，host codec只编码/解码，不直接打开COM或启动板卡。

当前证明：130核心帧132080像素；3幅1920×1080核心全像素6220800像素；disabled wrapper156帧376376像素；active wrapper186帧448756像素；旧命令16检查、新核命令18检查；10个真实串行包704字节/2个HCK6；host匹配6个真实RX向量、解码2个TX包、29个负例。供应商public PDPW functional模块按原始字节使用，不解密protected tail，不替换自造RAM或改SDK。

新增4组验证也实际通过：48忙态reset场景及144重启帧173232像素，含RAM待返回、全部乘加级活跃、补底行、持有EOF、下一SOF等待和错误清除；4幅完整1920×1080 wrapper共8294400像素，Gaussian、signed非可分离随机核、请求RGB强制灰度+hist/Sobel、禁用后真实RGB与sharpen/腐蚀；真实CSI/完整ISP/RGB交换/核/实际DBUF两帧96个128bit字和12个FDMA burst；真实host HCKC→vendor115200 RX→production7500周期/200bit CDC→accepted SOF联合两命令两帧120像素。第二命令已accepted/pending而第一帧输出保持时，applied仍为第一序号，下一帧才整体切换。

保留三个测试入口的失败：4×1不可能两个乘加级同时有效；纯模余数ready可刚好错过小帧所有输出，需确定性持有SOF以证明真实背压；Icarus过程引用整数需提前声明。没有为这些测试条件问题改RTL。实际整机encrypted PHY/DDR、75MHz STA和真实场景仍分别待验。

下一步先在独立副本重核当前CDC和恢复基线，再串行own native和实机颜色/任意核/帧界控制。旧native-only队列`evidence/hci06_clock_native_queue_v1`曾实际等待，2026-10-16已转为`WAIT_EXPLICIT_REBASE_AND_REARM_CURRENT_CDC_AND_RESTORE_BASELINE`；2026-10-17的CIM复查没有该队列owner，不能把历史等待状态写成当前排队运行，也不能直接重启旧入口。F11当前SDC仍有旧异步clock_groups，不能凭数字通过跳过逐跨域检查。新构建须先核当前TD/BitWriter和owner，保留健康运行；目前TD由HCI03 G14自己的全源构建使用。当前生产相机沿用PCIe47 SRAM/运行时门限2，Flash37保留；物理复验须以实际当前bit和恢复入口为准。源码审计/数字吞吐不能代替STA或实际帧率。当前162输入和12证据绑定为PCIe正式37工程下`evidence/hci06_completed_digital_progress_v1/result.json`。

2026-10-17新增`projects/hci06_uncut_inventory_20261017`独立诊断副本：162个注册输入，全部RTL/ADC/ROM/IP字节保持，只在自己的SDC移除旧宽异步组，不添加替代豁免。实际Tcl核对157 staged项大小/mtime/SHA；`native_gate_inventory_v1.tcl`仅到gate并导出全负路径、异常和时钟检查，尚未执行原生。`preparation_v2`还实际测试了继承完整build入口在`FLOW_NOT_READY`存在时立即拒绝，避免误走布线/bit；v1仅为早期准备记录，当前输入SHA用v2。待G14全源及其原生副本查询结束、实际无TD/BitWriter后，先做这个未切断跨域的门级清单，再按自己的实际路径逐项修复。此准备不计F11 native/STA/位流/实物通过。
# v144：自己的未加根级宽切断gate已终态，进入RTL/CDC修复

`hci06_uncut_inventory_20261017/evidence/native_gate_v1`自己的162输入门级原生已完成471.844秒、退出0，162源及runtime refs保持，gate DB/网表已导出；无P&R/bit/硬件操作。退出0表示诊断入口完成，不是正STA。实际gate估算SWNS −13.204ns/STNS −72786.961ns，原始负检查18087 setup/49 recovery；其中17771个setup属于DFI时钟→视频75MHz，另64个为同视频域setup、最差−3.092ns。它们是端点检查数，不是18136个独立bug。

实际代表源包括顶层`S_ddr_app_rst_sync_reg[1]`和`X_ui_dbuf/wdbuf_fifo/wr_addr_reg[0]`，到`u_hci_preprocess/u_post/m_data_reg[*].d`等。下一步先追踪DDR-app reset、FIFO full/ready/背压到视频弹性流水线的真实锥，再在新的完整副本落实各域释放和容量足够的registered elastic边界；保留原162输入和12组算法证据。不能将复位/控制到整片数据D端广泛false-path，也不能把同域64条路径当作异步握手豁免。根SDC移除了旧宽组，工具默认async分析政策/IP约束仍在，后续仍须核对被默认跳过项。独立诊断复核见`evidence/native_gate_review_v1/result.json`。
