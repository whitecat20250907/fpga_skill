# TD参数的实际值读回

本机TD 6.2.2.200067中，`report_param -stage timing -detail`在自己的路由DB副本上未输出参数行，原`-file`方式也未生成要求的文件。SWUG105只说明公开参数与默认/非默认输出范围，不能据此推定开关值。实际发现的`get_param`接口经独立副本验证：设置前`get_param timing ignore_aync_timing`返回Tcl code1/空值，显式set off之后返回code0/value off。检查须捕获该调用的真实返回code和值，逐字要求code0且off；命令回显或set成功均不作读回。仅对本机实测形式成立，不保证其他私有参数或TD版本接口相同。

证据：`projects/hci03_clock_query_rebase_20261019/evidence/parameter_readback_native_v2`与`evidence/get_param_readback_native_v3`。上述两项接口实验原DB和复制DB逐SHA保持，没有执行优化。后续own_async_aware_v2/45276已实际执行506.781秒，四点均code0/off、一次reroute及fix_hold完成，最终仍setup−0.016ns/hold+0.020ns、STNS−0.016ns，因此没有bit。唯一普通路径为RK DPHY clk2输出FF→clk4_90d输出PAD的doq[0]，budget0.833ns、data0.812ns（net0.637ns）、skew0.161ns；实际关闭异步忽略并未解决该路径，不重复同一优化当新方案。下一物理候选须据自己的实际位置/可用槽位和时钟/数据路径推导，不能降低uncertainty、切该路径或假定原x1y56站点可用。

# v157 匹配授权厂商计数器仿真复验包

新增G14匹配厂商模型复验包hci03_G14_counter_vendor_sim_v2.zip：实际6个计数器D锥72位，29696个源状态、62个carry实例；源绑定和公开接口语法已核，52个carry-backed D功能仍未证明。未运行受保护厂商行为仿真；包内PROMPT供有匹配授权ModelSim/Questa的电脑执行，不含模型或license，不计通过。

# P3 DBUF 帧入口源条件化与复验边界

当前完整候选为 `projects/hci03_dbuf_source_sync_high_20261016`，187项输入。
原 `hci03_packet_pipeline_20261011` 的native52064继续运行，候选不修改或重启它。
原工程saved-gate/placed DB仅复制后只读查询，不能将历史place结果称为当前route结果。

原P3逻辑DBUF的rfs/wfs各有四级UI寄存器，前两级Q确实只到下一级D，
第三级参与第四级历史与下降沿检测；八级均未标ASYNC_REG。
逻辑rfs_r1的第一D来自像素时序/复位与独立LP配置完成信号的组合锥。
物理打包后的端点可能显示为FDMA计数器名；必须读实际logical annotation，
不能据打包名字修改FDMA计数器或误判FDMA复位。

候选把稳定配置完成电平经三段像素域FF交接，仅第三段控制原video_source；
再用一个像素域FF将实际VSYNC电平送入DBUF I_R_en。
保留rfs/wfs四级与原边沿功能，仅第一到第三级增加ASYNC_REG，第四级仍是业务历史。
源条件化增加一个像素边沿的读帧级延迟，配置同步另有三段延迟，不能称周期等价。
不改IO、DDR/FDMA计数器、图像payload、封包或时序例外。

原video_source输出VSYNC是内部VSYNC反相，reset/未配置时为高。
新增寄存器的初值和reset值必须保持这个高空闲电平。
首个 `hci03_dbuf_source_sync_20261016` 原型错误使用低值，同一数字测试在
`evidence/display_source_v1/run_229.log` 抓到display-only reset制造假下降沿；
该原型失败和187项输入保留，未提升或烧写。
修订另建完整high副本，测试台仅替换这两个初值/reset值后同输入复验。
这是新原型引入并被测试抓到的问题，不是已经证明旧P3实板有该故障。

修订数字证据分开读取：

- `evidence/digital_review_v1`：实际top源片段、video_source/TPG、DBUF和生成soft FIFO，
  三组UI相位229/1317/4931ps，各26源帧事件/104读突发/416个128bit字；
  每组24个稳定32×8显示帧统计，以及display-only reset不造假事件。
  另有真实写FIFO的48个128bit字/6突发、满阈背压和逐字比较。
- `evidence/display_read_review_v2`：真实DE驱动32bit读端、128bit FDMA返回有间隔，
  同三相位每组两个8帧epoch；逐DE像素比较4096像素、256突发/1024个128bit字，
  无欠载。合计48帧/12288像素是三次独立运行之和，不是长时间相机采集。
  backend/display reset只在已核对完整帧后的blank/idle阶段施加。

这些测试使用真实生成FIFO，没有为通过而替换空模型；FDMA用户端响应是测试驱动，
不包含完整AXI B/R、实际DDR控制器/PHY、CSI/ISP、DSI电气或光学屏幕。
display-only reset是组件合同输入，不能据此断言现有板级reset_gen一定产生过该场景。
局部源片段测试也不代替完整top原生展开；own gate必须另核：

1. 三条同步链的时钟、常开使能、前两级Q只到next D、所有复杂端口消费者和真实属性。
2. 恰好新增九个ASYNC_REG且原有属性未丢；第四级不能当同步中间级随意隐藏。
3. 注册读帧Q直接到UI首级D，其D及真实SYNC SR的所有寄存器叶子均属像素域。
4. 配置首级到目的级，以及source/rfs/wfs/历史寄存器的精确D/CE/SR timing；
   对比同一阶段原P3 gate的全量负端点，不能把historical placed值拿来当gate基线。
5. 新增源寄存与ASYNC_REG只是CDC结构修订，不自动豁免首级setup、全局时序、
   MTBF或物理route。若需窄范围入口预算，先证真实producer/稳定宽度和接收链合同，
   保留后级setup/hold/recovery及其他负路径；禁止宽泛clock-group/false-path。

原P3门级DB重载后的全量保守诊断为337 setup/49 recovery，WNS/TNS -3.658/-394.322ns；
读帧首级有来自不同源钟的两条setup记录，-2.216/-1.605ns，写帧首级-0.516ns。
这不是当前route867个hold端点的解释，也不是连续构建报告的同一约束状态。

修订自己的1253.156s综合及独立 `evidence/native_timing_review_v2` 已完成：
实际属性283→292、九个新增恰好对应三段配置和两条前三段帧链，原属性未丢。
在相同DB重载诊断状态下，setup337→336、recovery49不变，无新负端点；
TNS -394.322→-391.027ns，WNS仍-3.658ns。
去掉了LP配置钟到rfs首级的-1.605ns记录；像素源到rfs由-2.216改善为-0.516ns，
wfs首级仍-0.516ns。12个必需D端点及4个实际SYNC SR记录已检查，不能称两入口已闭合。

## 连续构建零报告、数据库重载与未使用时钟

连续构建的全量报告显示零负违例；重载同一DB却显示上述负路径。
不能挑零报告签核。`evidence/constraint_replay_v2` 对旧P3与修订分别重新读取原root/IP
SDC和原分组命令，虽然进程返回0，但两组各有六条critical warning：
优化后RK PLL clock5输出已是无消费者open net，LPDT valid固定0，
旧rename仍查该时钟，并在分组中查S_rk_lp_clk，导致整条clock-group命令失败。
`check_timing`的invalid-constraint计数为0也不证明原命令曾被成功注册。

只读 `unused_clock_counterfactual_v4` 仅在证据目录的SDC副本去掉这条无消费者的rename
及一个未使用分组成员；实际gate的scalar/complex消费者均另审查为空。
原14/6/4个活动时钟族集合可正常形成，critical warning消失，分组报告变零。
它隔离了原分组命令失败的原因；生产SDC/DB/原route未改，原native日志中未找到同类报错，
不能据重载诊断推断当前route的每个内部状态或把反事实零报告当作PHY/CDC通过。
当前候选仍未提升，具体异步入口、held-data最大延迟及PHY合同须分别建立。

六个实际csi_stats_snapshot实例的12条req/ack链与各自释放链在本版native已另核；
RK发送75MHz来自独立PLL，不能因频率与视频相同而合为一个域。
60项实际优化寄存器别名查询位于 `evidence/snapshot_mapping_v1`；
held/snapshot/previous_cycles/clock_delta可被优化，不能按声明宽度假造一一FF映射。

## 六个快照的真实映射、握手保持与精确预算

G2的 `snapshot_mapping_review_v2` 将10,540个查询别名按实际Q网络解析为FF；
直接给逻辑别名加`_reg`会漏掉2,255项。实际held有5,220个FF，消费者有5,284个FF，
包含snapshot、previous_cycles和clock_delta；若某字段优化为零项，应跳过其查询，
不能把声明宽度或优化前计数硬写成门级覆盖数。

`snapshot_exports_v3` 展开scalar、整向量、拼接和buf别名，保守遍历所有LUT输出，
以及实际配置为DLUT5/SUM、没有时钟/寄存输出的PH1_PHY_LSLICE进位端口。
5,220个held Q恰好只到上述5,284个D，没有其他时序端口或未知消费者。
公共模型在文件的protected段之后；仅核对公开端口/默认值，不解密、不替换厂商实现，
端口可达性也不等于厂商加法器功能仿真。

实际native源CE为`req2 XOR ack`，目标CE为`ack2 XOR seen`；ACK D=req2、seen D=ack2。
所有数据FF的时钟、异步本域释放和reset值分别核对；req1/ack1的Q只到next D。
native request在busy时保持。`snapshot_protocol_v6` 穷尽理想二值的32个可达状态、
192个边转移，覆盖独立三段释放、任意source/destination/coincident边、停钟和共同异步复位。
源捕获后最早第三个目的边消费，因此至少有两个完整目的周期；不能外推为单边复位或模拟MTBF。

`snapshot_transport_v5`/独立`review_v7` 用实际RTL的测试副本注入32档逐bit延迟，
十二组六实例/两相位/停钟/复位，加一组不改源的零延时对照，共520次提交、638,720个快照位。
旁路ACK2、无条件覆盖held、四倍预算三组负对照均按预期失败。
v4失败来自测试模块漏timescale，保留失败，不能说是修过生产RTL；PERIOD2/7是压力测试，
不能冒充实际7500/1250000周期的更新率测量或相机帧率。

提出约束时必须覆盖整个source CLK/Q至consumer D的组合路径，包含clock_delta进位链，
不能把测试中的wire延时当作只约束连线的理由。接收周期减2ns并向下取整：
25MHz为38ns，75MHz为11.330ns，50MHz为18ns，HS111.408MHz为6.970ns。
六实例每个仅三组：request→req1、ack→ack1、held→其所有实际消费者。

只读 `snapshot_bounds_v8`/独立`review_v9` 去掉原宽clock groups和已证无消费者的RK LP5 rename，
保留其余数值/IP时钟，加入18组精确预算。实际6,288对路径全部生效、零shadow/ignored；
5,296个D（消费者+12入口）逐端点最坏setup均正，最小6.195ns。
路径对计数包含进位依赖，比目标D数量大，不能把二者混为一谈。
同一导入诊断状态setup336→142、recovery49不变，WNS/TNS -3.658/-391.027→-3.658/-265.045ns。
移除的194条负setup全属u_csi_snapshot，其余负路径及slack逐条相同，coverage仍99.69%。
这只是合理合同下的局部预算结果，不是194处RTL改动、全时序闭合或实机通过。

**TD手册SWUG105的set_max_delay章节明确：`-datapath_only`配合`-from`会自动false-path这些路径的hold。**
不能声称异步入口hold仍被检查；本例只限定上述精确入口/held路径，后级链、reset与其他域不显式切除。
稳定总线与握手数字证据支持预算实验，不能据此签MTBF、实际route或物理hold。
完整187输入G3：`projects/hci03_snapshot_bounds_20261016`，RTL/IP/引脚均与G2一致，
在post-map重新绑定root SDC，并检查18组/6288路径及每组selector/budget/active数。
实际Tcl检查器已拒绝缺组、重复组、计数错、shadow、ignored、预算错、漏datapath_only七种报告破坏。
独立native综合和拓扑/时序复核完成前，不提升该候选。

## DDR/UI复位不能直接参与其他域ready组合逻辑

剩余负路径清单 `remaining_timing_inventory_v10` 显示：UI域S_ddr_app_rst_sync[1]
经原`O_W_tready = I_ui_rstn && ...`，到视频写口数据捕获和flow_out计数CE；
这是需要本域化的实际依赖，不能给64个计数CE加例外掩盖。用户域FF也直接使用UI释放的异步reset。

完整187输入G4：`projects/hci03_dbuf_local_release_20261016`。
只在DBUF增加写/像素各三段异步置零、本域三边释放；两处写域与三处像素域reset测试改为对应本域reset，
ready采用写域释放，读valid在像素释放前保持0。FIFO共同reset、UI状态机/地址/负载数据、引脚和18组SDC不改。
可用时间增加三个本域边，不能称逐周期等价或任意半帧reset恢复。

独立 `local_release_review_v6` 可逆向恢复原DBUF完整文本，确认只改上述范围。
当前自己的真实FIFO回归：48个128-bit写字/6 bursts、48帧DE显示/12,288逐像素；
停钟v5在四种高低组合下先停双钟再assert共同reset、独立顺序恢复，64像素及user/last标记全核，
旧G3直接UI释放负对照在三本域边前ready/valid规则上失败。
首轮写测试选错top、停钟v3在FIFO内部两段reset未完成前写首字，均保留失败；
分别修正测试顶层和FDMA驱动等待，不改生产FIFO或放宽数据比对。
G4仍需自己的native新增6属性、两条私有释放链、ready/数据/计数/reset叶子、精确覆盖和全量负路径审查。
不把这些局部数字证据当真人颜色、绿点根因、摄像头同步曝光、实际FPS或游戏控制通过。

## G3自己的完整门级结果与下一批FIFO入口

G3已实际完成1424.437s综合。完整native与G2不同：不能把“RTL不改”当门级图完全相同，
更不能给G2结果换名字。`native_identity_v1` 保留差异；随后在G3自己重跑源/链/属性、六snapshot
握手、10540别名、10504数据FF时钟/reset/CE、全部held出口及busy/协议绑定。
仅source/top字节相同的数字测试明确复用；没有伪装成G3门级功能仿真。

`own_timing_review_v2`：自己的18组6288路径全部生效，5296 D最小setup6.195ns；
另查24个未切后级D和24个本域recovery，最小7.658ns，未混入SMD例外。
连续构建与重载重新读取root/IP SDC后的全部负路径及slack现在一致：
142 setup/49 recovery，WNS/TNS -3.004/-224.420ns；相对G2预算副本无新增负端点/源钟键。
优化映射不同会改变余量，不能把这个变化冒充同一网表仅改预算的隔离实验。
仍有10个继承的SYN-6024 PHY ODDR复位critical warning；不能只统计USR类约束警告后称零critical。
G3尚未签核全时序、物理hold/MTBF、route、bit或实物。

`fifo_gray_inventory_v4` 是下一步诊断，尚未添加FIFO例外/属性：实际3个FIFO、6方向，
72个保留的源Gray/首级入口，70条有完整第二级的功能链；140个功能同步FF缺少ASYNC_REG。
128→32读FIFO的rd_to_wr最低2位第二级被裁掉，首级Q既无scalar也无complex消费者，必须单列为无消费者。
v3按声明宽度假定每位都有三级实体而失败；不能为满足断言虚构第二级，或把这两位说成已通过2FF同步。
后续先证真实计数器每源边至多加1、Gray编码/解码、复位/停钟及所有实际消费者，再提出逐方向总延时/偏斜预算，
明确TD对指定入口hold的自动切除。异步FIFO在慢目的钟连续采样时可跳过多个Gray码，
不能要求相邻目的采样码的汉明距离恒为1来冒充正确合同。

## G4自己的释放图、全部目标时序与Gray合同

G4自己的完整187输入综合1457.968s完成；`own_timing_review_v1` 重新绑定六snapshot及所有源/握手，
18组6288路径、5296 D和24后级D/24本域recovery均正。连续与重载全部记录一致为73 setup/47 recovery，
WNS/TNS -3.004/-98.986ns。相对G3，71条原UI复位源setup和5条recovery消失，
但新映射暴露2条parser stat_raw/stat_crc setup（-0.334ns）及3条写域释放SR（-0.537ns）。
要同时记录新增和消失，不能把净改善说成没有新增负路径；10个继承PHY ODDR critical仍未解决。

`local_release_native_v5` 验证新增6个FF、前两级Q私有、38个实际用户reset目标及71个写域捕获D/CE依赖。
像素r_xcnt/r_ycnt与r_tuser_lock因keep仍保留，不能凭“未用元数据”猜测已裁掉。
视频缓存的PH1_PHY_MSLICE由公开端口和DRAMHARDCON的DPRAM/SIG/wclk证明为75MHz写时钟状态边界，
并核读地址叶子同域；这不证明其写数据所有权或加密RAM功能。像素读ERAM仅经addrB到达，CLKB为像素域。
原W_tuser/W_tvalid管线reset形式保留，不能外推任意运行中半帧恢复或模拟MTBF。

`local_reset_timing_review_v1` 对实际44寄存器覆盖42 D、32 CE、44 SR；两条stage0 D是常1，
已在图中证明，不伪造它们的timed D。38个用户目标SR最小+12.504ns，4个后级释放D最小+12.588ns。
两条异步flag首采样D和3条写释放SR仍负，未加reset豁免。

G3 `fifo_gray_contract_v6` 与独立 `fifo_gray_contract_review_v7` 核实际父计数器只有reset0/hold/+1，
六方向真实位宽/时钟、12组逐bit预算延时/两相位停钟、2组完全不改helper的零延时对照，
共14组正常和2组故意失败。每源Gray最多变1位，首采样必须来自当前或前一个源码，后级与独立解码一致；
覆盖完整模回绕、源/目标高低停钟和共同reset。二进制编码错误与四倍预算均按预期拒绝。
测试逐bit continuous-assignment延时有惯性语义，是有界数字模型，不是模拟亚稳态或SDF。
原版零延时case虽然日志打印名义BOUND，未注入该延时；复核明确记实际延时0。
G4自己的新inventory仍为72入口、70功能链/缺140属性。native编码/解码LUT、计数/reset图、FIFO所有权、
物理skew/MTBF仍须分别核对，不能把helper测试当成整FIFO/物理签核。

G5 `projects/hci03_parser_word_20261016` 是实际G4完整副本，仅把parser字节计数改为15位字计数加固定00。
复用既有parser源码前先逆向逐字节恢复实际G4父源码；保留原GBK注释字节和LF，不猜测CRLF。
自己的4组参数各238528周期、32768状态和203位输出逐周期等价通过，未增加event或payload延迟。
own综合已启动；还没有G5门级/时序/bit验收，不能复用另一279输入工程的+0.711ns作为本版结果。

后续G5自己的1643.891s综合完成；`parser_timing_review_v2` 绑定15字计数FF与2统计FF，
49个D/CE/SR检查均正，两统计D实际只有+0.021ns，不能拿另一个工程+0.711ns替代。
连续与重载71 setup/47 recovery、WNS/TNS -3.004/-98.331ns，恰好移除2统计负端点，无新增键。
21ps余量很小，仍须本版后续优化/实际route复核；中间G5未提升，六snapshot/DBUF/Gray图未冒充已全部重跑。

G4 `fifo_gray_native_v2` 在当前门级穷尽72位编码/70位寄存解码：370688/362496个位赋值，
按公开SDK AL_MAP_LUT INIT输入顺序核132个实际LUT。展开整向量/别名后70条首级Q仅到第二级，
另2首级无消费者。72个源二进制FF、编码FF、首/第二级与解码FF的clock/reset分别核对。
12个实际FIFO reset释放FF确为本域两级；CSI共同reset来自HS和视频父reset FF组合，
DBUF两FIFO才来自UI master，不能统一假定都是UI reset。各FIFO四个reset pin断言函数逐真值相同。
该检查不证明native计数carry/CE功能、上游reset脉宽、FIFO所有权或模拟MTBF。

G4私有 `fifo_gray_bounds_review_v4` 在相同冻结门级仅追加6个GrayQ→首级D精确预算：
HS/视频6.976ns、涉及UI的5.500ns，取min(Tsrc,Tdst)-2ns，包括CLK/Q至D全部延迟。
24组6360路径有效；72首级D最小+4.755ns，140后级D/140本域recovery最小+2.946ns。
恰好62条Gray setup负记录消失，所有剩余记录/余量不变，为11 setup/47 recovery，WNS/TNS -3.004/-67.421ns。
源与生产SDC未被这次试验改变；指定入口hold会被TD自动false-path，不能称hold仍检查或全CDC已通过。

完整187输入G6 `projects/hci03_fifo_gray_20261016` 已加入真实FIFO两级Gray及两级本域reset属性，
两源文件共12处标注，移除标注可逐字节恢复G5；功能RTL不改。生产HS预算再收紧为6.970ns，UI仍5.500ns，
共24组6360路径，reset/其他域/PHY不加例外。实际嵌入Tcl检查器用明确标注的guard-only期望摘要fixture，
接受24组并拒绝13种破坏；fixture不冒充STA报告。原私有6.976ns报告也因预算不符被正确拒绝。
TD的async_reg即DONT_TOUCH，原先裁掉的两个无用第二级可能因此保留；自己的native须区分功能链和保留但无用链，
不能直接假定属性总数或说同步链全部功能有效。

G6自己的完整综合和全部关键门级绑定已完成，见 `evidence/own_timing_review_v4/result.json`。
实际454个属性、70条功能Gray链及两个保留但无消费者的第二级；六snapshot映射/导出/协议、
本域复位/RAM边界、Gray编码/解码和共同reset均重新核对。24组6360路径有效，5296 snapshot D、
72 Gray首D、24/24 snapshot后级D/recovery、142/142 Gray后级D/recovery、49 parser及38用户reset检查均正。
两个parser统计D为+1.389/+1.391ns。连续及重载全负路径一致，剩9 setup/47 recovery，WNS/TNS -3.004/-66.761ns；
比G5恰好少62个Gray负键，无新增负键。重新优化改变了其他余量，不能说全是只改SDC产生的提升。
10个继承PHY ODDR警告、入口hold自动例外及模拟MTBF边界仍在；未选为物理候选，未生成/烧写新bit。

下一完整187输入G7 `projects/hci03_registered_flags_20261016` 在UI域先寄存idle/empty，再进现有写域两级链；
增加一个UI源周期，并给现有完成通知的前两级加属性，未改其复位行为。真实生成FIFO的读写/显示、四种用户停钟复位、
每种UI暂停profile连续6帧/288词/36burst及旧组合源负对照通过；下一SOF实际等待141周期。
这些数字检查不证明任意SOF时UI停钟恢复。24组预算保持不变，没有实现规划中的五条单bit新预算。
G7自己的综合已启动，源/链/复位与时序必须按新网表重验，不能沿用G6通过结论签核。


## v125 当前已部署与复验边界

2026-10-16当前选择：SRAM40（bit SHA bcd9c7e16ba7f4d597b1940ab05d5fecaeb55120689cbf5eb29d991557e2e382）+默认app_v18+原RK3576 NPU。Flash仍正式37。BAR0x56442501是共享ABI，当前SRAM身份须绑定成功JTAG日志和bit SHA，不能由BAR独断。

原始绿点已实拍改善但未全验收：统一RAW底值54的39版虽降绿点，却把木板蓝色均值56→14并损暗细节，已拒绝并回退；40版保留BLC50和原色矩阵，只门控线性RGB全部为0/1的最低量化值。自己的317输入完整构建setup +0.240ns/hold +0.021ns、四CSI物理路径通过。实际正常增益32/Bayer3，37与40各422/416帧完整；两块暗区绿超差比例12.69%→1.20%、13.79%→0.010%，墙面/白柱/木板没有该阈值定义下的大偏移，已保留SRAM40。该比例是绿超差代理量；残余绿点、低照纹理、人脸/眼部与九色仍待，不计M05完成。Flash37未改。

默认app_v18已实际部署并以当前模型打开的CSV文件描述符绑定会话；原RK3576 NPU权重和预处理语义未变。复制DMA后先QBUF再发布两份有界输出，整数3:1在私有副本生成640×360，RK5529600个RGB值等于原OpenCV。实际C与Python共21模拟用例通过；三次真实PCIe各141帧，接收中位9.07→2.40ms。真实无脸应用窗口输入年龄中位39.26→20.21ms，样本年龄143.86→118.02ms；不是真人FPS或控制精度验收。v1按目录mtime误选旧会话的失败记录保留，v2以实际日志恢复正确会话，v3用活进程CSV FD确认默认18新鲜运行。

G7自己的完整187输入综合和全部关键绑定复核已完成：456属性、24组6360路径，snapshot/Gray后级、parser和38用户复位检查为正；全局仍9setup/47recovery，WNS/TNS -2.340/-63.000ns。完成历史链本身无运行复位，已证明UI两周期主复位保持期间历史清零，并核对消费者原生复位D余因子，不能虚称这些FF带异步复位。完整G8副本RTL/IP/ADC逐字节等于G7，只给五条注册源到私有首D增加2ns精确预算，29组6365路径的检查器与28负例通过，自己的完整综合实际执行中；不选上板，不加宽域false path，最终PHY/reset/MTBF仍待。

RK CSI/AIQ继续停止；已确认ISP停流超时→IOMMU页错误→内核Oops，具体函数根因/修复未签核。async18在PCIe路径的复制/QBUF改进及21模拟用例不能代签RK ISP停启修复；不重跑已触发故障的6.25秒阻塞读端试验。

证据入口：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v125/progress.json`。此前本页的黄金37/app16和“缩放未集成”描述均属于v124历史。


## v126 实际续查

完整G8自己的187输入综合1216.437秒、29组6365路径实测重放通过；除严格匹配的生成时间行外，自己的综合网表全部代码逐字节等于已完整审计G7，456属性也相同，结构证据据此限定复用，并非谎称重新推导全部旧证明。五条注册源到私有首D精确2ns预算全部有效，余量1.255/1.255/1.088/1.255/1.255ns；setup 9→4且无新增负键，47 recovery保留，WNS/TNS -2.340/-60.959ns。snapshot/Gray后级与parser自己的重放均正；四条PHY setup、复位/物理/MTBF仍待，未生成/上板新bit。

旧P3完整187输入经逐SHA复核，仍含组合UI源、未修订本域复位释放与未寄存显示帧入口；旧上板恢复器还固定刷37。已按过时源码而非运行时长停止原52064及所属旧native/物理队列，8个确切任务进程核身份后退出，源/DB/失败证据完整保留，不伪造旧STA失败或最终bit。F11/T08/I03/I05/F10旧等待器已停止自动启动，固定任务保留；需在修订后的CDC与当前恢复基线上重接，禁止原样重启旧队列。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v126/progress.json`。当前选择详见根目录`CURRENT_CAMERA.json`；FPGA断电/重配后必须重新核对，Flash仍37。


## v127 实际续查

G8保持4 PHY setup/47 recovery未解决；新清单已逐条归入7个源/目标时钟组，四条PHY valid首Q各有5个直接消费者，不能仅因名字有1d就当私有同步器并加例外。原旧P3及等待器仍按过时源审计停用，后续必须重接修订CDC与当前恢复基线；全部固定任务保留。

证据入口：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v127/progress.json`；新选择见`CURRENT_CAMERA.json`，断电/重配后重验。


## v129 实际续查

v129当前摄像头恢复目标已改SRAM43/app20，见CURRENT_CAMERA.json；40作为已验证回退保留。旧P3及F11/T08/I03/I05/F10等待器仍停用，恢复37/40的旧模板不能当当前恢复选择直接重跑。G8四PHY setup/47recovery没有因另一个PCIe43工程通过而得到签核。

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


## v133 精确SR与TD全局查询边界

G10复制数据库的真实SDC试验通过30组6371条预算；22个精确私有复位入口仅SR豁免，12条级间D及12条Gray后级D/recovery保持，6条Gray首D预算6.970ns。G11完整195输入运行1361.359秒后因TD原生命令在Tcl过程内的局部参数未展开、守护报告路径缺失而终止，未进入布局/布线/位流，失败证据保留。eval/list试验仍失败；改为全局字面选择器的实际TD副本试验通过。新完整195输入G12只改构建过程与项目位置，RTL/ADC/SDC/IP完全相同；自己的27项守护反例通过，原生PID62032正在完整构建，不能提前签核STA/bit。

G10/G11都有10条厂商两路DSI ODDR复位SYN-6024警告；旧G10 runner仅匹配USR类critical，字段空列表不等于全日志无critical。新验收须逐类复核这些继承警告及光学范围。匹配SDK待取得，不能盲用July29参考内核替换May11镜像；不能将诊断保护等同原始DMA生命周期修复。

SDC条件须单物理行；MCP/SMD不列false-path，精确SR覆盖靠实际pin与数据路径报告。原生命令在过程内局部变量即使eval/list仍不可靠；采用顶层字面get_pins/get_regs和全局集合，先在数据库副本真实执行，再做新完整源构建。纯Tcl文件端点/Slack守护可以留在proc；仅纯Tcl正反例不能证明TD原生命令参数正确。G12终态以自身full_build_v1/result.json及后续自己的图/时序/PHY审核为准。

## v135 门级 SR 不能直接充当打包后的 ASR 端点

G12自己的195输入完整运行3791.094秒，最终setup −4.045ns、hold −1.291ns；路由后报告守护又拒绝了调试器新增的5组57条约束。它没有导出routed DB或生成bit，不能仅修正守护就签核。原30组6371条用户约束全部有效；额外调试器约束必须单独核对实际命令、数量及覆盖，不能放开全部未知规则。

本轮自己的gate/place导出图证明：原22个私有复位入口以外，显示读域还有r_reset_release三级及rdbuf_fifo读侧二级需要同类核对。明确列出的12条链共27个FF被打包进15个共享ASR切片。逐个验证首D常量、共同钟/复位、级间Q私有、复位极性、实际IMA/IMB数据端，以及每个切片所有可观察QA/QB均属于这27个FF，才能对这15个ASR作窄范围试验。不能把切片名字与门级FF名字一对一对应；同一切片可能有两个FF和不相关的组合LUT。

Gate的_syn_3等Q网名会在打包后消失，应通过本轮完整buf别名等价类与物理Q端交叉映射。此工具版本get_pins -of cell的NAME过滤试验没有返回ASR，不能把空集合当成已切断；以本轮图推导的真实完整pin名和原生路径报告复核。

15个精确ASR试验在自己的place副本上从−2.569ns改善到+0.540ns，15条级间数据路径和35组6428条最大延迟全部保留。此为布局估计；原路由仍有真实RK时钟lane setup −0.196ns，不能豁免该功能路径。当前physical_repair_v1从这次自己的place继续route/phys_opt high/fix_hold，明确是派生物理试验，不称作新的干净全源重编译。所有routed DB先保存再跑报告守护，避免一次报告错误丢失整轮路由。

完整critical检索须包含DRC前缀：本轮除SYN-6024/PHY-5060/USR-6019/TMR-5506，还实际出现CLKST-5093和RTCLK-5079。只从行首匹配代码会漏掉后两类；存在报告或bit不代表这些警告已审核。当前47+门限2/原NPU和Flash37未改，RK CSI/AIQ继续隔离。

证据：`projects/hci03_native_args_20261017/evidence/own_full_failure_review_v2/result.json`、`reset_physical_mapping_v1/result.json`、`packed_reset_constraints_v1/result.json`；完整任务索引以根TASKS.md为准。

## v136 全局物理约束与完整 G13

G12自己的派生路由完成1251.610秒，最终只剩RK时钟lane的一条setup −0.196ns，hold +0.020ns；高强度phys_opt没有改善这条功能路径。所有35组6428路径仍有效，完整报告no_clock/invalid_constraint均0。后续必须修实际硬件时钟/布局，不能再切这条功能路径。

27个私有复位FF的物理复核补齐CLK/CE/SSR、OFA/OFB的寄存器输出替代路径及区域SCLK_V2遍历。仅遍历GCLK会把路由后插入的SCLK分支误判成换钟；增加文档规定的固定分支后，自己的route图复核通过。OFA可选QB、OFB可选QA，不能只看OQA/OQB就宣称共享ASR全部消费者已核。

在SDC内用变量动态拼接SR/ASR名字，实际TD重放失败，不沿用纯Tcl语法完整结论。有效流程是静态27个门级SR选择器，加自己当前物理图生成的字面命令，在全局Tcl执行。实际clear_user_sdc后重放用户根SDC，IP与调试约束保留；自己的gate与route副本通过，route保留30条级间D setup/hold、6条Gray首D、24条后级D/ASR setup/hold/recovery/removal，以及35组6428有效路径。此范围不等于全局setup通过。

直接set_inst_attr修改SCLK的DELAY可改变导出参数，但这次STA仍−0.196ns，不能计为闭合。move_cells明确返回成功迁移0、位置未变，已按已证实的无改动取消后续重布，保留原始证据；不是因观察超时停止健康构建。修订调试约束纯守护通过实际30/35组报告与31个负例，缺失/重复/失效/未知规则仍拒绝。

完整G13 `projects/hci03_explicit_tx_clock_20261017`有195个注册输入和5个冻结运行时组件。只有顶层RTL配置显式150MHz BUFG+零延迟SCLK，PLL频率与300MHz数据/时钟90度关系保持；其他RTL/ADC/ROM/IP逐字节保持G12。每轮自己的gate/place/route图重新推导精确物理边界；原始DB先存，负最终时序不出bit。生成器已在自己的G12副本经过实际TD验证，G13自己的全源编译原生PID28992刚开始，最终STA/PHY/bit/实物均未验收。其他电脑可设置HCI_PYTHON，运行时只需stdlib Python与安装的TD公共模型；不能把该副本试验称作G13自己的STA。

当前选择沿用v134最后实核的47+运行时门限2/原NPU，Flash37保留；本轮没有板端或JTAG操作。RK CSI/AIQ仍隔离，匹配SDK和真人测量仍待。新动态终态见根TASKS.md和CURRENT_CAMERA.json，断电后重新核验。

证据：G12 `physical_repair_review_v1/result.json`、`reset_physical_controls_repair_v3/result.json`、`static_source_global_reset_v2/result.json`；G13 `evidence/preflight_v2/result.json`与`mapping_helper_native_v1/result.json`。

### G13 自己的门级实核补充（完整 P&R 仍运行）

同一PID28992全源运行已导出自己的gate，估算setup +0.401ns；独立解析实际报告确认27个SR所选路径为空、15条保留D最差+1.499ns、6条Gray首D最差+6.195ns、12条Gray后级D/recovery最差+12.217ns，30组6371路径全部有效。另在自己的网表执行六组快照握手与释放链、12条共27个私有复位FF、FIFO72位Gray编码/70位注册解码（370688/362496个位赋值）以及6位时钟Gray全部64状态真值检查。显式GCLK→DELAY0 SCLK和34个实际消费者、PLL分频及90度参数确实保留。

证据为G13 `evidence/own_gate_boundary_review_v1/result.json`和`own_gate_graph_v1/result.json`。上述范围仍不包括held/consumer全别名真值、最终物理时钟、完整最终STA/IO/PHY/警告、位流或实机，不能把门级估算代签路由时序。HCI05工具`probe_G13_own_full_v1.py`只完成准备/语法检查；须在本轮成功终态且其他原生TD进程数为0后，导入自己gate/final-route副本继承原SDC采集证据。它不clear/replay SDC，也不改变原始输出；结果还需独立复核。入口及源码快照见HCI05 `evidence/G13_review_entries_v2/result.json`，早期v1仅为准备记录，后续时钟检查追加后以v2冻结源为准。

补查二进制指针D/CE时，自己的gate已经包含用于加法的`PH1_PHY_LSLICE`，不能假定门级只有AL_MAP_LUT/SEQ/ADDER。当前盘点仅识别六方向72个FF及实际D/CE锥，部分D来自LSLICE SUM/carry；它不是计数器全功能证明，也不推翻此前把binary Q作为显式输入的Gray编码真值检查。保持`binary_counter_cones_v1/result.json`的function_accepted=false，完整计数器更新/使能和物理进位功能需另有覆盖证据；不能从未建模的进位节点臆测硬件错误，更不能读取/解密受保护的仿真功能段来补模型。

### G13 本轮全源终止与自己的布局复用

同一完整全源native运行2092.015秒后，在derive_place_reset_graph阶段失败；`read_sdc [file join ...]`的日志参数为空，实际物理D报告覆盖率7.92%、所需15个端点均缺失。自己的原始place DB、门级和195+5输入保留，不因失败丢弃已完成的综合/布局。随后在自己的place副本用字面root路径原生重放，35组6428路径、15个D/6个Gray首/12个后级检查恢复，布局估算setup +0.447ns；该试验的导入/更新日志仍有54条USR-8122、27条USR-8159和10条TMR-5506，不能计警告全收束或最终STA。

已有生成Tcl含绝对报告目的地，实验前必须重定位到自己的目录；首轮字面试验复用了原报告路径，但原7.92%空报告已先封存。快照manifest首版还与被拷贝的result.json同名，已保留旧manifest，并从SHA仍匹配的原始终态结果恢复到独立文件，由manifest_v2.json绑定，不能掩盖该修复。G13的`literal_place_review_v1/result.json`明确这些范围。

自己的`own_derived_route_v1`从同一原始place副本重新资格检查再布线；物理用户SDC只剔除27条gate-only SR条件式，其余字节保持，以当前图推导的15个ASR替代，所有D/Gray与35组约束仍严格检查。该实验尚非完整源码重建，不生成bit、不下载。后续完整副本应将门级27个SR在全局Tcl明确应用、物理root路径字面生成，避免SDC条件式上下文与临时路径参数问题，再验证自己的完整native/最终STA/物理覆盖和警告。

### v138 自己的正路由与完整 G14

G13派生实验已经完成，最终setup +0.063ns、hold +0.020ns，TNS均0；独立检查negative报告为空，精确SR0/D30/Gray首6/后级24全部非负，35组6428路径有效、no_clock/invalid均0。实际自己的路由图将逻辑时钟lane FF映射到唯一LSLICE寄存器侧，确认其时钟经显式GCLK与DELAY0 SCLK接PLL C2，PAD osclk接保留90度参数的PLL C4，doq0/2接同一FF Q。该图检查未把netlist注释中的LOCATION/IOTYPE当作原生属性，也不接受外部PHY、位流或实物。

完整G14 `projects/hci03_literal_root_flow_20261017`保留195注册输入和5个运行时组件；所有RTL/ADC/ROM/IP字节等于G13，仅工程路径、配置、构建Tcl与root SDC变化。root去掉27条gate SR条件式，门级精确收集27个SR后在全局Tcl施加；物理生成器新增必需root-sdc参数，在自己的生成Tcl开头写出clear_user_sdc、字面root路径和更新命令。CLI的file join只交给Tcl内建exec/Python，read_sdc本身不再接受临时表达式参数。

实际G13副本的两个native阶段已经通过G14命令复验，USR-8122/8159上下文错误为0，物理阶段10条TMR-5506仍单列。纯Tcl12项包含实际7.92%空D失败、缺失/重复D、错检查类型、负D、负hold与缺字段；只是守护测试。独立核对实际配置190个staged文件加5个控制文件、全部SHA/大小/mtime和项目内路径，source_integration_review_v2把readiness保存为快照，避免后续移除标记使历史观察失效。真实native helper与纯守护前置通过后才冻结preflight_v1、移除FLOW_NOT_READY并启动G14自己的完整全源native。最终动态终态以根TASKS.md为准，G13正标量与helper副本均不能代签G14。

证据：G13 `evidence/own_derived_route_review_v1/result.json`、`routed_clock_graph_v1/result.json`；G14 `evidence/source_integration_review_v2/result.json`、`pure_guards_v1/result.json`、`helper_native_G13_copies_v1/result.json`、`preflight_v1/result.json`和自己的`full_build_v1`。

### v139 G14 自己的 gate 与源码迁移候选

完整G14同一源编译已导出自己的gate：setup估算+0.401ns，独立实际端点/30组6371路径复核与六组握手、27复位FF、72/70 FIFO编码/解码和6位Gray当前图检查通过。自己的最终P&R仍运行，不因门级通过签核最终STA/位流。HCI05新增`probe_G14_own_full_v1.py`与`review_G14_snapshot_aliases_v1.py`用于本版自己的gate/route副本及10540别名/数据捕获控制复核，目前仅准备并通过语法检查，没有提前计实际执行通过。

源码跨目录工具为HCI05 `tools/portable_td_project_v1.py`：clone只复制冻结195+5输入，改项目/配置/构建控制路径，重算190个staged文件SHA/大小/mtime，所有RTL/ADC/ROM/IP/runtime组件字节保持；HCI_PYTHON由build启动器指向当前解释器。搬移/解压后先clone至新目录，再verify/build；直接验证旧configured_root应拒绝。目标目录必须新建，禁止XML/Tcl特殊路径字符，不复制主机license。build --check-only只检查条件，已有native时拒绝；普通build仍需自己的完整原生/时序/PHY/警告复核。

实际8项检查已覆盖空格/中文路径、两次克隆及搬移后的旧root拒绝、独立Tcl190配置校验、损坏输入拒绝和真实live TD时的check-only保护，未启动第二个native进程。候选zip `deliverables/hci03_G14_source_portable_v1.zip`共204文件，逐项解压读取SHA通过，没有bit/DB/license。它只是源迁移候选，未验证新路径原生编译，不能代签D04全流程或替换PCIe47；HCI03输出MIPI压缩图，RK接收仍受CSI内核隔离影响。证据在HCI05 `evidence/portable_G14_source_v1/result.json`和`portable_G14_package_v1/result.json`。
# v140：自己的完整源布局复核与F11诊断入口

G14同一完整195注册输入及5个runtime helper的原生进程已完成自己的place并进入route。`hci03_literal_root_flow_20261017/evidence/own_place_review_v1/result.json`实际复核本轮27复位FF/15个私有packed ASR、SR0/D15/Gray首6/后12，35组6428路径有效；布局setup估算+0.362ns/TNS0。15个D、Gray首6/后12最差余量分别+1.670/+6.269/+12.813ns。全局字面路径SDC重载正常，原USR-8122/8159上下文错误0；仍不是最终route STA或完整警告/PHY/位流/实机通过。最终route须重新从自己的最终图导出端点并核对0/30/6/24。

`review_G14_final_native_v1.py`和`review_G14_routed_clock_graph_v1.py`现仅准备/语法检查，未执行；必须自己的全源构建终态成功后才能读取，不以入口存在签核。原有own_full_query和10540别名入口仍待实际执行。当前生产PCIe47/运行时门限2、Flash37和v134最后实核的相机/模型选择保持，本轮无RK/相机/JTAG/Flash操作。

卷积F11旧队列已退出且待显式重核CDC，当前不在排队。独立`hci06_uncut_inventory_20261017`保留全部算法/RTL/IP/ADC/ROM字节，在自己的SDC移除旧宽异步组以准备实际门级路径清单；157 staged项Tcl核对和完整build入口拒绝保护已实际通过，native未运行，当前输入用`preparation_v2`。这是下一个诊断准备，不能挤占健康G14原生或借其结果签核F11。

# v141：G14全源正时序/位流与数据库重开约束丢失

G14自己的195注册输入和5个runtime helper已实际完成全源原生，3456.579秒、退出0，所有冻结输入保持。最终setup +0.084ns/hold +0.020ns、TNS均0；自己的精确SR0/D30/Gray首6/后24、35组6428路径通过。`final_native_review_v1/result.json`记录实际4850318字节的`fpga_prj.bit`，SHA256 `5715babfb50ff8a30bc204228dd262ca65391a5c4cb81e464d038e35b055250b`。自己的路由图还核对PLL C2→显式GCLK/DELAY0 SCLK→真实launch FF、PLL C4保留90度→PAD osclk及相同doq0/2；不是外部PHY或全部IO签核。源码迁移zip v1仍是无bit的源码候选，不能改称已验最终包。

**实际反例：export_db/import_db没有恢复原流程全局执行的复位切断集合。** 未重放运行约束的v1 gate副本重开后变为setup −2.805ns/TNS −30.325ns，所选27私有SR中出现35个检查、20个负值，原报告对应0个。v1正确失败，没有继续route；原始构建273文件、195+5及bit哈希全部未变。不能把这个副本结果当作原本版最终STA失败，也不能声称数据库天然携带全部运行约束。

`probe_G14_own_full_v2.py`仅在新副本重放原流程的精确运行命令：gate是原已验27个SR的全局集合；route是自己`reset_route.tcl`的字面root/私有ASR/保留D/Gray命令。必须将生成helper的8处报告前缀重定位到副本目录，防止改写原始报告；没有添加新的时序豁免。v2正在实际查询，终态及逐位/别名/PHY/IO/警告复核仍待，不以入口存在或原scalar正值签核全项。

新鲜gate补核72个binary指针FF的实际clock/local-reset/CE及D锥只到本地pointer状态，其中20个纯公开LUT位已穷举全部状态；其余52个carry位只作保守组合依赖，不虚构厂商进位模型，不计完整计数/CE full-empty真值通过。另RK只读回查确认同一boot下panic10/oops1仍有效，未启动CSI/AIQ或做故障重启。生产PCIe47/运行时2与Flash37保持最后选择，真人暂缓、匹配SDK待取。

# v142：完整副本查询通过、快照闭合与未计时min路径

G14自己的v3 gate/route副本查询已实际完整退出0。精确重放原运行约束后，gate +0.401/0.000ns和route +0.084/+0.020ns与原构建相同，原273输出保持；自己的原bit仍为5715babf...。v2在gate错误调用仅支持place后的`report_clock_utilization`而失败，v3只在route执行该命令；真实原生命令help和失败日志保留，没有重启全源编译。

实际门级get_regs别名10540条全部解析，10504个唯一数据FF的clock/local reset/CE与ACK/seen输入、六组capture/hold XOR谓词通过。5220个held Q的全部位/拼接/向量端口保守追踪到且仅到5284个已审查目标D；允许的carry只作组合依赖，不虚构其函数。证据为`own_snapshot_alias_review_v4`和`own_held_exports_v4`，二者用已封闭的成功gate阶段和不可变query快照，允许与route查询并行。

`selected_transport_review_v1`实际复核18组每阶段5296个正setup检查、其他选定downstream/Gray/flags/parser、四RX lane reset/data及TX clock路径。**路由报告中额外的5296条Min Delay/Check Type hold没有Slack/Budget，不是5296个正hold检查。** 解析必须将显式Slack检查与未计时诊断分开，不能仅数Check Type。原datapath-only规则保持，第一同步级/held跨域依赖的协议稳定性、MTBF和真实捕获边界仍独立。普通时序negative报告为空；include_ignored每组上限1000端点的报告无已报告负Slack，不能据此覆盖所有默认跳过路径。

原生RTST-5089仍提示默认跳过1个异常跨域路径；现单独用自己的route副本重放原约束，查询`report_abnormal_timing_target`，读取68个HR PAD+48个DDR PAD实际属性，再仅在分析副本关闭`ignore_aync_timing`查看被跳过检查。IO v1在启动前因只识别68 HR而正确拦下；v2在可选runtime参数getter不可用时终止，原输出仍保持；v3明确捕获此可选读取失败，保留必需异常路径/属性/更严格分析命令，当前正在执行。所有这些均不修改源、布线、bit或硬件；T04尚未完整收尾，外部I/O delay/PHY/启动警告和实机仍待。

# v143：更严格分析与实际引脚闭合完成，串行转到F11

`abnormal_IO_review_v1`已实际完成：833ps目标确为同一RK PLL C2→C4保留90度的clock lane，不是两个独立源时钟；在自己的路由分析副本显式关闭`ignore_aync_timing`并重算后，setup +0.084ns/hold +0.020ns、TNS0和include_ignored负路径0保持。异常清单仍列该预算小于1000ps的路由启发式目标，不能写成“警告消失”或声称原完整构建策略已改。原273文件、source及bit保持。

实际读取68 HR PAD+48 DDR PAD和100个内部top-pin对象；从物理网表的ipad/opad/**bpad**和简单wire assign/标量/向量别名，核对52个root ADC端口的真实连接、LOCATION、IOTYPE。仅比较location不能证明连线；仿真注释里的LOCATION也不能替代本轮native属性。PHY native模式为RK clock DDRX2L、四条data DDRX2，与自己的物理网表一致，不能假定五条lane同模式。内部top pin的DIRECTION/IS_CLOCK不能直接当开发板外部方向。电气眼图、外部I/O delay、ODDR启动对齐/真实payload及完整physical逐FF映射仍未签核。

F11独立uncut162输入工程现已实际启动自己的gate诊断，`hci06_uncut_inventory_20261017/evidence/native_gate_v1`登记owner/源SHA和实际原生进程；新增execution body只把两个audit头部路径改为字面本项目地址，并补导出自己的gate网表。原准备入口及162源保持，仍无P&R/bit/硬件操作。必须用当前CIM/命令行和终态继续同一进程，不能复活旧队列或因观察超时再启一次。
