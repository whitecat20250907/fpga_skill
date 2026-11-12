# F16：IMX415 开窗与实际生效边界

最新入口（2026-10-16，清单v116）：选定完整terminal_output_stage F为门级工作基线，各279输入，自己的综合/13+8复核通过，setup7→4、recovery112不变，41组1958路径。新增132位全部264个D/CE/SR端点为正，最小1.047/1.822/6.002ns，三guard setup均+0.667ns；无新负端点。自己的ingress/发布边界与六时钟完整核心6检查/19968 DSI字节通过；自己的七时钟/57链名义与三种1..3拍错拍独立复核通过，共24检查/79872 DSI字节/513次hold；实际sensor-owner/PHY、4 setup/112 recovery、普通top own native、新bit/窗口/实物仍待。

独立开发工程`projects/hci09_sensor_window_20261012`从HCI08的193输入复制，当前登记207输入/十四新RTL；原八个事务/启动组件，加原生PLL wrapper、实际边沿测频/门控应答和控制集成core。clock32与控制链联合18场景通过，固定HMAX曝光协调已实现，实际源帧/通信slot生产者、亮度/按键AE producer、完整video top、帧生效、自己的STA/bit及实物待做；不把控制链通过转为F16完成。

原始Sony IMX415-AAQR-C E19504手册由Radxa公开镜像读取，SHA记录在工程 `evidence/prepared_v1.json`。第38/63页给出3040–3047的窗口字段：横起点偶数、宽24倍数；纵起点/宽是Line×2单位、为4倍数；VMAX≥1222且≥VWIDTH/2+46。先用完整输入位宽判断合法性，再取寄存器字节，不先截成13bit把非法值别名化。实际正常方向/阵列边界和基础profile须另验，处理边缘13+3行也不是可直接交给显示的记录像素。

当前父06/HCI寄存器表3020/3021/3022为1、301C为0，即binning配置；“1080P60”注释不能证明从4K原阵列直接裁切的密度。新基础模式和实际INCK/HMAX/RAW10/lane rate必须核对。第81页REGHOLD只覆盖V类；I类即时、S类在standby配置后生效。第62页明确窗口位置/尺寸改变有无效帧，第82页说明模式转换边界；HOLD释放、ACK或读回不是实际新图像生效。FIFO后的SOF也可能来自CFG提交前的物理帧，保留源边界/代次而非只比较到达时刻。

现有ui_cfg_imx415的bus_error没有用于配置索引推进；ui_i2c产生内部scl_clk并跨其两沿维护事务。不要直接把该startup/AE循环扩展为可靠运行时窗口事务。新后端保持一个owner，明确逐阶段ACK/随机读/STOP/超时/cancel/tag，窗口、AE、startup不混写。先保留旧完整组，失败执行受控整组回滚并核对；回滚失败锁住未知几何，不只释放HOLD后称旧配置仍有效。

实际窗口生效后再验证RAW WC/行数/CRC/ECC、Bayer/方向、RGB与完整buffer，并更新I05源/校准绑定、RK几何反馈。记录无效帧和有效眼区采样率；FPGA内ROI移动与传感器窗口移动分别统计，不能把每次更新的一帧过渡当成连续60Hz有效数据。

当前`window_plan_v1`的271318向量与独立允许集合一致；25MHz bank检查13字计划、忙态保持、序号回绕/半区、未知值和reset。后端当前证据`i2c_backend_v10`：实际25MHz数字时钟的100k/400k两组各384场景及2超时，共770项，加9非法参数实例；独立串行target和wire monitor。5个旧版失败在`i2c_repair_replays_v1`与新版相同输入配对复验。目前207输入仍未接新控制至完整video top，不可下板称开窗已调通。

后端保持当前单主机SCL输出/SDA开漏连接，不支持拉伸或仲裁。ceil五阶段分频使BUS_HZ成为上限；25MHz/400k配置实际约384.615kHz，不保留产生2.48µs过短周期的分数余量。重复START setup需按实际起边计量，不能把三次CE误当三个完整间隔；100k的4.7µs要求曾实际失败。原始Sony19/27页及NXP UM10204 Rev7 Table11为时序/通信范围依据，数字边沿不认证实际IO延迟、上拉或上升时间。

取消要完成正在传输的byte/ACK，读方向结束于NACK再STOP；若ACK已被target收到，最多再读一个字节，禁止对target持续拉低SDA宣称idle。任意clk到来的取消也需保证ACK/NACK的data setup，不能40ns前改SDA即升SCL。写取消可能已完成一个字节，事务守护一旦开始写就按可能触及新组处理，旧快照和整组回滚不能省略。未知slot预算在START前拒绝；读到X不输出伪造有效零字节，取消失败明确返回，reset/held response不能泄漏旧tag。

Sony27页的1H禁止区间和相对XVS推荐窗口需要真正的源调度。后端slot/budget接口当前只在合成时序中验证，不能永久授权运行通信或使用FIFO交付SOF冒充XVS。后续完整owner处理startup/AE/window，并保存旧11字节、写新/读回/释放、受控回滚和物理帧资格；字段和串行测试均不代替这些要求。

当前transaction_v5联合五模块/真实串行target：两组各45场景加batch/recovery总期限，共92项；i2c_arbiter_v1另10个packet模型场景。窗口租约跨全部snapshot/HOLD/write/readback/rollback，wire tag全局分配并恢复caller tag；startup-required、运行通道轮转、held response/取消/卡低不得中途换owner。单项ACK不能续整个batch期限。

预检还读SHR0 3050–3052；Sony71页规定master/linear曝光范围8..VMAX−4，缩短VMAX不能让已有SHR0失效。保留的window_transaction_v5不兼容时拒绝18；新首选exposure core按下节固定HMAX规则协调，亮度AE producer仍未做。基础资格必须包含master/linear；原11字节窗口恢复不意味着AE、HDR或其他模式的全部寄存器恢复。

排队计划须捕获实际base epoch，与bank同组保持；不能将当前epoch接到plan_base_epoch冒充原始资格。reset默认未知，先见reinit确认低再接受可信新确认，fatal后的确认还要求新的forward epoch。manager-only reset可让后端继续一个写字节；旧reply与旧epoch计划不得复活。transaction_v5中的资格/初始化回调和slot仍是合成边界输入；新增startup_v3另验证完整vendor表，但未证明真实AE或物理帧生效。register_commit/rollback_commit只能用作寄存器事件。

## 完整startup与模式表经验

详见工程`STARTUP_PROFILE.md`。当前`startup_v3`29项：两套27MHz INCK的891/1485Mbps四lane非binning RAW10表，在25MHz控制、100k/400k真实串行链下逐项写/读全部201字。每轮410条操作含STANDBY/XMSTA确认、至少24ms稳定等待、运行slot内XMSTA读回及九个不同的因果源帧事件。`window_request_v1`10项保存bank接受时的真实epoch，未知首序号和零/未知epoch提前拒绝；static profile12非法/2合法边界单独验证。

旧top相机输出来自原PLL的25MHz，与27MHz配置不匹配，须独立接实际27MHz/门控并验原生及IO。必须区分PLL/profile资格与实际gate stopped/running应答；请求已置高不等于时钟到达。完成报告背压期间时钟停止也关闭当前资格，但保持历史报告。SDA卡低取消失败后，报告消费与bus/lease恢复同拍不可留下空REPORT；三处真实旧版失败见`startup_repairs_v2`同输入复验。早期“溢出参数旧版接受”的假设被实际否定，不作为第四个修复计数；total-deadline测试也接受后端提前拒绝不足预算。

第55/63页限制891Mbps非binning的HMAX1100及最小VMAX1222，理论上限约55.24fps，不能沿用旧60fps注释。1485Mbps/HMAX550/VMAX2250表给出60fps配置，第78页规定≥1440Mbps发送initial deskew burst；接收PHY、实际RAW尺寸/边缘、颜色及频率仍待验。不用表和I²C成功代签高帧率目标，也不将理论约55fps替换60fps验收。


## 实际clock/gate与唯一控制core

工程`CLOCK_CONTROL.md`为本轮接口与复验入口。默认`NATIVE_PLL=1`用从正式37复制、仅改module名的native27MHz wrapper；`NATIVE_PLL=0`是显式数字台分支。不能使用主机flag代替clock资格或gate完成。计数在未门控raw时钟上，Gray经三FF送25MHz域；默认1000µs测频、连续两窗口合格，10µs无正向进度即失效，即使lock仍高。Gray物理总线延迟/偏斜和实际PLL仍需自己的STA/实物。

外部INCK转发使能在下降沿更新，正常停止保持完整高脉冲；异步失锁/停钟先将XCLR低再关转发。实际使能跨两FF回到参考域，stopped/running分别核对真实应答、物理XCLR及当前资格，不把请求电平接回。clock_guard_v4的100µs/1000µs两组共32场景覆盖正常脉冲、停高/低、频率边界、锁定不变时停钟、X请求和回绕。

sensor_control_v1的三组共18场景经过真实clock/gate RTL、全201字startup、真实base epoch、请求bank、窗口/回滚、arbiter和唯一serial master；各840条命令覆盖两次初始化和两组窗口操作。理想raw时钟、合成源帧/slot及关闭的AE端明确留边界。native_clock_interface_v1用TD自带PH1 black-box声明展开默认native分支，只有参数/端口证明；不把空模型当动态PLL仿真或自己的TD实现。

初始化永久许可只给已取得client0 lease的startup，master启动后关闭；window与AE使用真实runtime slot预算。client2是内部AE扩展接口，不是自动曝光算法/SHR0-VMAX协调完成。当前登记修复曾在v5错误拒绝audit正常生成的build_direct_config.tcl；v6核对exact AL新增、Tcl正常重生成及其余输入不变，RTL证明无需重跑。AL登记模块不会自动改变旧video top或针脚。


## 固定HMAX的窗口SHR0/VMAX协调

新首选core为`hci09_sensor_exposure_core`，旧core和window_transaction_v5证明保留。工程`EXPOSURE_COORDINATION.md`记录Sony36/39、70–71/81页：固定行周期master/linear的曝光行数VMAX−SHR0；SHR合法8..VMAX−4。完整32bit VMAX/24bit SHR检查后，新曝光取min(旧曝光,新VMAX−8)，新SHR=新VMAX−新曝光，过长限幅单独记录。不同HMAX/位深/HDR/slave不能套此规则。

2250/SHR2000→VMAX1222用SHR972保留250行；2250/SHR8缩帧限制1214行、新SHR8；扩至VMAX3000用SHR758保留2242行。窗口8+VMAX3+SHR3共14字节在一个租约/HOLD内写和逐组读回；失败恢复全部14字节并核对三组再释放。normal11操作、rollback8操作；恢复SHR读回错同样fatal并保持HOLD，单项ACK不续总期限。

当前exposure_plan_v1为27000向量/12未知拒绝；window_exposure_v2为116个真实25MHz串行场景，含SHR三个部分写字节、保留位/非法旧SHR、保持/限幅、读回及恢复错误、epoch/reset/tag/报告背压与总期限；sensor_exposure_v1三组18项各844命令，完整startup的SHR2000、真实base epoch及停钟/reinit联合通过。原v1测试台用j保存预期SHR，check_memory循环将它改写；v2另存变量修正，非RTL缺陷，不计硬件修复。

commit_group和commit_exposure_shr是同拍寄存器事件，done保存旧/新SHR和clipped；不代替物理曝光/帧生效或I05许可。模拟竞争client仅写gain，未实现亮度驱动或按键AE producer；物理CSI/1H slot/完整video top/自己的STA-bit和实物保持未验。native_exposure_interface_v1只用TD官方PH1 black-box作默认native参数/端口展开。


## 亮度报告与AE client2（当前210输入/十七RTL）

新增`hci09_luma_stats_quad`、`hci09_ae_producer`及`hci09_ae_transaction`，详细接口和复验入口见HCI09 `AE_CONTROL.md`。统计观察accepted canonical RGBX四像素，低R/中G/高B；厂商ISP高R须先用已有adapter。SOF锁存整组source/epoch/VMAX/SHR/gain；完整行/EOF、未知值和真实末帧good/token决定report-good。单深度报告backpressure保持、不阻塞像素，满时丢新报告并计数；重复SOF放弃旧帧和同拍新无效帧要累计2，luma_ae_v2→v3仅stats RTL改变同条件复验通过。

policy默认目标112±8、曝光4..128行、gain0..96步进2，暗先增加曝光再gain，亮先降gain。手动ready/valid优先，gain±1饱和0..240且保留旧曝光；不能接raw按钮pulse。held proposal有不续期TTL，1..FFFFFFFF匹配32bit age，默认20ms/25MHz；源默认最大2帧。整组报告跨video/control域CDC仍待实现，不能各位2FF或直接跨域接线。数字策略不代签实拍曝光、灯光/抗频闪或运动模糊。

AE client2先真实读取并验证VMAX/SHR/gain，再比较proposal旧观测；窗口改动即使epoch未变也拒绝19。仅写SHR0三字节及GAIN_PCG_0两字节，不写VMAX或HDR其他gain。全租约/HOLD内10正常操作，失败7操作恢复完整五字节并复核VMAX；恢复失败保留fatal/HOLD，需LOW后可信完整startup及forward epoch reinit。commit仍是寄存器事件，不代替实际frame-applied/I05许可。

当前ae_transaction_v1共100；luma_ae_v4共25且1080p2073600像素独立亮度和264349661；TTL构造3合法/3拒绝；luma_ae_serial_v3两档各8共16，实际统计→policy→client2→serial经过独立edge target。该joint的模式、reinit、source-good/settings/slot为测试输入，没有实际完整startup/window竞争或物理曝光。旧sensor_exposure_core继续用于startup/window，新AE尚未接完整core/video top；实际源/1H slot/CDC、native/PHY/RAW/Bayer/颜色及自己的bit待验。历史207输入/十四RTL和未实现AE的说明属于前阶段，不能当当前组件缺失，也不能把组件证明转成整机通过。


## 解析器源帧与held报告CDC（当前212输入/十九RTL）

HCI09新增`hci09_source_frame_guard`、`hci09_bundle_cdc`。完整合同见工程`SOURCE_FRAME_AND_CDC.md`。在parser时钟域、像素FIFO之前观察已解码FS/FE、RAW行开始/payload-last、实际字节数和packet-done/CRC/ECC/WC/timeout；加入unpack/FIFO错误。按FS锁存预期token/宽高，每行width×5/4、FE总行数/字节数均匹配才good；重复FS报告旧帧bad，未FE固定期限和disable也bad，不随数据进度续期。静态几何最大4096×4096防32bit乘法/计数溢出；这是观察者范围，实际IMX415模式与原始边缘需另证。

233bit报告为good/sequence/token/宽高/行数/字节数/FS与终态tick/error。源sequence及Gray来自实际parser事件的本域计数，尚须目的域3FF同步/Gray skew约束；不能直接跨域总线用作AE current-frame。报告一深度不阻塞像素，满时丢新报告并记录loss；消费者处理sequence缺口、loss和独立控制域期限，不能把最后good永久授权。预期token不是frame-applied，parser tick不是光电时间或RK映射真值；源clock停时源期限也停。

bundle CDC锁存整组held数据，request/ack各3FF；目的valid/data保持至接受后ack返回才允许源改写。两域共有异步reset、各自3FF释放，停域不伪造释放或ACK；不支持单侧保留历史的独立reset。217bit亮度报告必须连同good/sum/pixels/frame/epoch/VMAX/SHR/gain整体交接。真实held-bus最大路由延时/偏斜、同步首级扇出、ASYNC_REG及复位需own native审查，不能宽泛false-path免责。

bundle_cdc_v3六组共42项（233/217/1/4096bit、75/25、111.375/25、25/75和非整数比），每组197接受事件；source_frame_v2为14小尺寸负正例加1944×1096/3888×2192完整独立ECC/CRC RAW，共16；source_constructor_v1为3合法/4拒绝。旧CDC v1只是期望总数198而fixture脚本实际197，v2修oracle、RTL不变；不计硬件修复。source v1全尺寸通过后收紧静态几何界，v2完整复验，旧结果保留。

实际PHY字节、曝光-applied/过渡帧、控制域源资格与身份映射、亮度报告跨域接入、完整startup/window/AE与video/UART、原生与实物仍待验。CSI FS/FE不等于XVS/XHS；1H通信slot需要真实相位依据，不能永久置真或直接由FIFO图像SOF推算。


## 源资格、亮度跨域与真实AE/window排队

HCI09当前216输入/23新RTL，优先控制core为hci09_sensor_ae_core/runtime_base；详见项目CONTROL_RUNTIME_AND_SOURCE.md。source_qualifier18/实际parser→guard→233CDC→consumer15、video75→control25的217bit亮度policy/真实serial20、完整startup/window/AE双向竞争39数字通过，仍未接完整video top/真实源帧身份/通信slot或本工程own native/实物。

source-good不能永久保持资格：同步源Gray/loss的最后一级，核对完整tuple、序号连续/年龄、token与形状，在独立control时钟设不随重复报告续期的期限。首次good过期清除streak，期限边界的新good优先；source_qualifier_v1实败和相同条件v2修复保留。配置token与终态tick不等于曝光真值或frame-applied。

video统计good/sum/pixels/frame/epoch/VMAX/SHR/gain一次打包217bit，经held request/ack交接；settings与final-source-good必须先与实际像素身份对齐。报告可在video停钟后完成交接，AE许可另由当前源资格/年龄决定。reset两域共同断言、各自同步释放；原生held路由/skew仍待约束和检查。

共享owner要检查两个方向的真实排队。原2ms等待在合法窗口/AE全组事务后提前超时：sensor_ae_v3及sensor_ae_queue_v1实败保留。独立runtime_base/core将window/AE lease-wait改50000us，而整batch/recovery有限期限、source-age和旧寄存器比对不放宽；39项真实启动、forward epoch、SHR协调、旧RGB19拒绝和两路部分写恢复通过。旧组件/core默认及212份旧输入除AL/生成Tcl保持原SHA。

禁止用dummy竞争、外部reinit常高、synthetic source-good或永久runtime-slot代替完整接入。当前39项这些source/power/slot/settings接口仍是台输入，default native展开仅官方black-box接口证明；下一步需要真实RAW→ISP身份、配置/过渡帧、XVS/XHS相位slot、video/UART/物理约束与实际RGB/60fps。


## 独立capture/config视频候选

新候选projects/hci09_sensor_video_20261013从已复核216输入/23组件父工程复制并保留父源；当前219输入/26组件。详情CAPTURE_CONTEXT.md。实际startup新增capture_allowed和sensor_master_started状态端口：完整201表核对/clock/gate有效即可允许初始parser，base_verified仍等待9个源帧。不能用等待帧的base_verified关闭产生这些帧的parser。

context owner用实际start接受生成非零token，base低→高后才发布epoch；运行begin推进token并关闭设置已验证，寄存器commit/restore不自动frame-applied。202bit整个descriptor用held request/ack跨域，禁止输入静止时初始未知发布、源停钟伪ACK和各位同步。34个快慢clock/stop/reset/未知/合并场景、24个代次/待生效组件场景通过。旧RTL的初始零输入未知问题由同一修订bench复现；测试台同拍旧ACK修订另外记录。

完整startup→202配置CDC→实际parser/guard→233报告/qualifier→startup的9幅1944×1096联调独立执行，必须看它自己的result；等待进程不算通过。错误接base_verified的构造variant已拒绝，不冒称历史上板旧cfg_done故障。RAW→FIFO→ISP身份、source_alive与geometry许可拆分、真实runtime-applied及1H slot、完整video/UART/native/bit/RGB仍待验。


## Runtime存活、准入与实际写owner

独立候选projects/hci09_sensor_video_runtime_20261013登记225输入/32组件，父219源冻结，详见RUNTIME_PERMISSIONS.md。新source_liveness对完整233bit报告仅排除配置bit2/几何bit3，用协议完整/非零有界行字节、3FF末级Gray/loss、序号连续/年龄和独立控制期限证明存活；该资格不授权像素或新的设置请求。source_monitor让两consumer同时ready才消费一次。43组件场景及真实parser/guard/CDC两consumer23场景通过；裸合成报告不代替实物。

Runtime descriptor不能在请求入队就begin：旧全事务接口可能让两个排队owner同时使context pending。新的window/AE runtime transaction在实际租约第一条非恢复写被backend接受时begin，非法字段/旧观测拒绝不会fence，回滚不重新begin。新请求同时需要source_qualified与source_alive；在途用source_alive/有限年龄，不能因同一更新关闭geometry而自我取消。旧窗口准入只检查geometry，同一修订bench复现断流仍入队；修复同时保护ready和送入valid。另构造在途geometry-abort变体，保持正确准入，实际窗口恢复17/commit0；这不是历史板测故障。

两组400k/891与400k/1485完整startup/serial/context联调各9项通过；100k看自己的终态，等待不计通过。startup源事件、source_alive、runtime_applied和通信slot仍为台接口，不能复制合成applied/永久slot到生产top。真实monitor到owner联合、RAW FIFO/ISP身份、真实设置生效/1H slot、完整video/UART、own native/bit/RGB尚待完成；1485模式表数字通过不认证PHY/deskew或高帧率。


## RAW/ISP身份与裁切EOF后的CRC（2026-10-14）

独立完整候选projects/hci09_sensor_pixel_identity_20261013登记230输入/37组件，父runtime225冻结。FS抓取234bit源seq+202bit context；真实RAW FIFO74bit带source seq，另设头FIFO按seq配对。目的域SOF次数不是源身份；元数据live改变、空FS、RAW/meta溢出与32位wrap都需验证，溢出时整帧失效。实际parser/RAW10/FIFO/crop两帧1944×1096→1920×1080的4147200像素通过，合成111.375/75MHz及有限backpressure；不是PHY/CFA/实拍通过。

保留的ui_isp_top没有输出tdest，hci09_isp_identity一次只容一帧并保持FS快照至最后RGB接受。启动不能以active门控ISP输出ready再等第一输入建立active，否则可能形成ready启动依赖。正常背压的数据/metadata保持已在真实完整ISP联调验证；放弃/超时reset是显式frame abort，局部abort分支还需专项测试。

RAW帧尾在crop EOF之后，source CRC可能比RGB统计晚。新geometry stats仅provisional并携带token，249位统计与真实233位终帧报告用seq+token有限配对，两种顺序/同时到达/坏CRC/错token/缺失/溢出/重复不续期分别检查。held output payload稳定，但消费者必须在handshake同周期检查m_usable（当前源age/loss/固定期限）；不能把此前的good长期沿用。15配对/10统计场景、真实CSI+完整ISP+CRC报告CDC+join8场景/576 RGB像素/3对报告通过，末尾坏CRC不获许可。这不证明AE owner实际消费或新设置生效。

下一步为真实monitor→owner联合、249报告/许可跨控制域及token-aware AE准入/第一写、实际applied与Sony1H slot、完整video/UART/top、own native/bit/实拍。禁止用常量final_good/applied/永久slot补齐。详见候选PIXEL_IDENTITY.md和pixel_registration_v1、pixel_review_v1。


## 统计报告到曝光控制的身份检查（2026-10-14）

候选 hci09_sensor_identity_control_20261014 登记234输入/41组件，完整继承pixel230。统计报告249位加视频侧握手当拍usable共250位走bundle CDC；控制侧每次消费重验源存活/资格/时钟、token、epoch、帧龄与固定hold期限。报告payload背压稳定，usable可撤销，禁止把旧good当永久许可。该CDC+AE producer的15场景通过，边界报告/monitor仍为合成输入。

AE proposal携带FS的context token。完整串行owner在准入与第一笔HOLD写接受前再次检查token，零/X/不匹配报告拒收；读取快照后token变化也不得落下第一笔写。第一笔实际写才触发begin，使自己的token递增不会反过来自取消；恢复写不触发第二次begin。13场景/481条实际数字I2C命令通过，包括正常窗口/AE、拒收、NACK回滚与队列。两个分项通过不等于真实ISP→monitor→AE→sensor整链通过；real_monitor_owner_v2全RAW联合验证单独看实际结果。实际Sony1H slot/runtime applied/fulltop/native/实拍仍需完成。


## 真实monitor与视频到AE子系统联合（2026-10-14）

camera_ae_pipeline候选完整235输入/42组件，父identity_control234保持。real_monitor_owner_v3通过10场景：11帧1944×1096/23436864RAW像素，201表启动410命令+窗口11命令=421。先前v2测试错误只计8命令，漏了SHR快照/写入/校验；保留FAIL并加入11事务逐条寄存器/读写/字节数/数据oracle后重跑通过。不能仅根据error0把失败测试改签PASS。源monitor实际报告/Gray/超时维护窗口owner存活；几何恢复不等于settings物理应用。

hci09_identity_ae_video把CSI/parser/RAW FIFO/crop/full ISP、源monitor、provisional stats/terminal join、250位CDC和AE producer连为子系统。233位终态报告向video/control两个bundle CDC原子广播，两边同时ready才各接受一次，不能用裸valid分别驱动。identity_ae_video_v1的7帧/1344RGB像素/8场景通过：连续两好帧资格、末尾CRC在crop EOF后撤销、两好帧恢复、未applied与token不符拦截、背压稳定，正确生成两次127行曝光proposal。此处真实指RTL链路，数据/描述符/clock-qualified边界仍合成；没有接到实际串行AE owner，更不是整板、实际1H/applied、native或光学通过。四份不同范围数字证明合计46场景，禁止拼接成未测整链结论。

## 视频与串行owner直接联合

独立camera_engine候选登记236输入/43组件，camera_engine_v4通过9场景：12帧72×20 RAW经64×18 crop/full ISP产生13824 RGB像素，201表启动410命令，第9个真实源报告签启动，第10帧的统计报告产生127行曝光建议，经真实AE owner的10条数字I²C命令提交SHR2123。token推进2，未提供physical applied时后2帧仍不能再授权AE；实际source monitor/liveness、原子context CDC、独立边沿target、RGB背压和descriptor均在同一个bench核对。

v1/v2无RGB定位到测试时钟初始复位不足；v3已走通12帧但最终断言误要求rejected_pairs=0。前9个启动未生效帧及后2个运行未生效帧应精确拒绝11，v4修正bench预期后完整重跑通过；没有修改冻结236 RTL去迎合错误预期。pixels变量计128bit四像素组：3456组=13824像素，报告不可混淆。

仍使用合成runtime slot/power/理想时钟/NATIVE_PLL0；实际Sony1H slot、settings-applied生产者、完整board top/PHY/UART/DSI、自身native/bit和光学验收继续待办。不能将这份9场景数字联合证明扩展为整板可用。

## 相机共享UART与实际引擎连接

独立候选 `projects/hci09_camera_host_20261014` 完整继承236输入，新增5个RTL，共241输入/48累计组件。共享接收路由保留HCIC/HCC4/HKB7/HLS8和首字节时间戳，HCM9固定40字节/CRC32命令体内的magic不能重新分包。HCA9通过camera/legacy ACK保持缓冲和轮询仲裁接原UART调度器；背压期间不能因另一类回复到达而替换正在发送的包。完整字段见该工程HOST_PROTOCOL.md。

同一非零序号与同一完整命令只能重放缓存回复，不得重复启动或写寄存器；相同序号不同内容拒绝，前进按32位半空间比较并跳过零。STATUS/ABORT在忙态仍处理，取消与尚未发出的owner握手同拍时须阻止提交；真实在途事务交给owner执行有界取消/恢复。请求接受error=0仅表示入队，必须另读完成序号/代码。手动gain的policy-consumed不等于寄存器commit，饱和时可能没有写；commit也不等于frame-applied。窗口/手动请求在实际owner握手前重查epoch和固定期限。

host_protocol_v2通过27场景，包含真实115200 UART RX、276字节旧协议逐周期比较、重复/冲突/绕回/零序号、忙态、取消、背压及半包复位；此项owner终态是合成边界。host_reply_tx_v1实际UART位中心独立采样5包640字节并核对CRC。host_engine_v2将真实UART启动/开启AE/查询接实际CSI/完整ISP/AE/串行owner，同一bench核对12帧/13824RGB像素/420命令及一次SHR2123提交，未applied的两帧不能再授权AE。host_review_v1验证这三项及全部登记输入SHA，不能把分项数相加冒充更多整链场景；UART窗口到传感器完整联合尚待。

host_engine_v1因确认无数据时完整ISP仍逐拍仿真的性能开销而主动中止，原记录保留，不能称RTL失败或签PASS。v2在断言视频和报告路径已排空后，只于串口发送期间暂停视频测试时钟，控制/源监测/MCLK继续；原RTL冻结并重跑原功能断言。它不证明连续视频时钟或实板时序。当前system_top仍保留父版，需继续接共享旧hub、PHY/DDR/DSI，核对真实power/Sony1H slot/applied，补约束、own native/bit及实拍。不得将登记、wrapper或上述数字联合通过称为整板已启用。

## 共享旧服务与窗口拒绝终态

camera_services候选完整243输入/50组件，在camera_host唯一RX之后将旧HCIC/HCC4/HKB7/HLS8字节交给保留的配置、事件、租约、按键和执行器服务，并接真实ACK合并/旧调度器/唯一TX。执行器物理资格默认关闭，HLS8首字节时间戳继续来自同一个router。整链测试包含相机和旧LOAD/ARM/CRC/DISARM；实际通过与否必须看 `evidence/services_joint_v3/result.json`，不能把已登记或执行中记为通过。v1/v2失败分别为Windows include路径和bench声明顺序，修正测试入口而未改RTL。

真实window bank的ready只表示接收请求进行校验。非法几何会增加rejected但不创建plan，因而没有下游done。原host对此永久停在WINDOW_WAIT，ABORT也无法结束不存在的事务；已用真实request/bank/validator复现。独立camera_window_host246输入/53组件增加v2控制和连接wrapper：握手时快照window_rejected，等待时发现变化则持久报告本次序号/0x10009并返回空闲。初始排队ACK仍不是写成功，host必须查终态；不得把该代码的bit16单独当成功标志。

backend_reject_v1复现旧卡忙，新版13项覆盖9拒绝/2有效plan/重复/查询，合法plan的owner完成仍是合成边界。修复版27项实际UART RX回归另过；两项不能相加称全链通过。修复版真实UART非法窗口接实际engine并继续ISP/AE/旧服务的联合看 `camera_window_host/evidence/services_joint_v1/result.json` 自己的终态。最终板级还需处理运行窗口几何与固定DDR帧尺寸的关系，不能只改寄存器却继续假定缓存大小相符；详见camera_services/BOARD_CONNECTIONS.md。物理slot/applied/power与own native仍待，原正式37未更换。

## UART背压、有效窗口平移及固定尺寸输出

camera_services/services_joint_v3已终态通过：8条旧服务命令、12帧/13824 RGB像素/420串行命令，实际TX1600字节（3 HCA9、8 HLA8、3个64字节包）。它是原host范围，不能代替修复版完整联合。

camera_window_host/services_joint_v1因测试台把“输入STATUS结束”当成“全部ACK已握手”而失败。真实TX背压可以使第4包仍保持；ack_backpressure_v2从解码命令输入复现3已握手/第4待发送，有限排空后实际TX4包512字节及CRC通过。完整services_joint_v2保持RTL，改为有限等待真实ACK握手；查其实际终态。暂停已排空源/视频测试时钟只是仿真性能措施，不能推广成连续时钟硬件证明。

services_joint_v2随后终态通过：真实UART非法窗口返回完成序号2/0x10009，继续12帧/13824 RGB像素/420条串行命令及8条旧命令；实际TX1728字节含4 HCA9、8 HLA8和3个64字节包，逐包CRC通过。修复版完整联合已具有自己的证据，仍不包含物理帧生效或连续源时钟验收。

uart_window_pan_v1同一bench验证真实UART窗口平移→11条寄存器事务→元数据/完整ISP→AE恢复：14帧、16128 RGB像素、431串行命令。未applied的4帧仍阻止AE；合成token2应用脉冲是明确边界。它只验证同尺寸平移，不证明动态尺寸或物理设置生效。

新完整camera_geometry候选249输入/56组件增加普通方向、无binning WINMODE4几何与固定RAW画布。Sony E19504第62页的上13行/下3行与旧binning式crop skip1不能混用；左4像素为继承的取景策略，不宣称完整光学边缘标准。按源帧元数据计算有效矩形，大窗裁剪、小窗右/下RAW零填充；有效尺寸与FS快照随帧保持。默认1920×1080的5帧10368000 RAW像素独立坐标oracle通过；实际CSI/parser/unpack/异步身份FIFO/新画布另过3种尺寸1536像素。末行坏CRC仍是坏源帧，canvas完成只能作为临时结果。

新画布尚未接入完整ISP/AE/DDR：RAW零经黑电平、去马赛克和gamma后不一定为RGB零；RGB统计应排除补边并处理邻域边界，否则小窗会错误驱动AE。frame_abort要求下游reset/invalidate未完成帧，不能继续提交DDR或消费旧统计。仍须验证CFA相位、实际通信时隙/applied/power、完整top、自身native/bit与实拍。详见camera_geometry/README.md及各独立证据，不能把分项拼成未测整链。

## 窗口有效区域、白平衡及画布完成条件

后续完整候选 `hci09_geometry_pipeline_20261014` 登记260输入/67组件，保持geometry249冻结。新AWB窗口版只筛选统计像素，AE亮度统计同时保留完整画布形状检查及独立有效像素计数。两者排除补边和有效矩形1像素边界；3×3去马赛克邻域不能跨补边取样后仍当纯有效像素。ISP后将有效矩形之外明确置为黑色RGB，不能仅依赖RAW零。5帧明亮中性RGB专项通过，AWB与AE分别核对372/84/0/372/84有效像素，微小区域无内部像素时禁用AE统计许可。

geometry_video_v3实际CSI→RAW canvas→完整ISP→masked stats通过7源帧/6完整RGB帧/3072像素。统计参考独立地累计实际RGB输出，不等于独立的完整ISP颜色数值oracle。异常行触发画布abort后，ISP立即阻断握手并flush；最终DDR仍要废弃残帧。

裁剪图像EOF、完整RAW画布接收和CSI帧末校验是不同事件。新canvas join匹配统计与真实canvas_completed产生的seq/token事件，再接原CSI终态join、CDC与AE。不能用画布完成伪造sensor-good，也不能仅凭CSI终态良好忽略视频端丢弃。完成关联8项专项已过；实际事件产生、整链AE及新版UART/串行owner的通过与否分别查geometry_ae_v1和uart_window_pan_v1/result.json，运行中不计通过。完整engine/host/services模块已经连接，但board system_top/DDR、物理时隙及applied仍待。CAM005/VID005精确资料由用户之后补充，不据此猜测引脚。

geometry_ae_v1和新版uart_window_pan_v1现已各自终态通过并经pipeline_review_v2复核。前者12个RAW源帧中11个完整RGB帧，仅第2/4/8/11帧产生127行AE建议，实际ISP在处理异常行时取消后恢复；后者14帧16128 RGB像素、431串行命令，含11条窗口写入和后续AE owner提交。上述结果没有改变合成power/slot/applied和理想时钟的边界。宽高同时改变另查uart_window_resize_v2，不能由平移结果推断。

uart_window_resize_v2随后通过：实际UART把Hwidth72→48、Vwidth的Line×2单位40→48，实际RAW72×20→48×24；固定RGB64×18保持，AE内部有效像素124→252，14帧16128像素及431条串行命令闭环通过。resize_review_v1复核实际日志、命令CRC、窗口字段及全部260登记输入。此项源RAW和设置应用脉冲仍为合成，不证明实物镜头、Bayer相位或Sony寄存器实际生效。

## 固定画布的DDR提交与显示租约

相机旧ui_FDMA的wbusy仅覆盖数据发送，最后W拍结束不等于所有AXI B响应成功；不要直接据此发布新帧。`hci09_frame_store_20261014`完整262输入中保留旧模块，新增仅更名的demo04_full_capacity响应校验版FDMA；它包含B计数、响应/ID粘滞错误及AW/W背压保持，来源和已有测试SHA可追溯。

新frame_publish_guard在单一UI域保留显示、待显示、写入三个bank的独立占用。用同seq/token的canvas接收完成、真实CSI终态、完整RGB形状与全部DDR响应四项共同提交。显示帧边界还要等旧读事务排空；失效或超时不能提前释放仍有写事务的bank，缺失B时必须保持占用。AE统计有效性不能代替显示资格：很小的有效窗可能无内部统计像素，却仍可显示。

frame_publish_v1通过9个合成帧身份配实际FDMA/AXI模型，72写拍、18响应、4提交、5丢弃，覆盖延迟B、坏CRC、错token、重复/旧事件、超时、显示未排空及错误响应锁定。实际像素写入、abort后完成已接受burst的填充/排空、真实事件跨域/仲裁和DDR/DSI/top尚未连接；这份专项不能扩为整板帧缓存验收。保持完整262输入来源与父260输入不变，在后续独立候选完成集成。

后续 `hci09_frame_writer_20261015` 完整264输入把固定画布RGB写入、实际FDMA和guard连接起来。每拍四像素128bit，canonical与显示存储红蓝字节按原hci_rgbx_swap转换；地址/stride单位是字节。FDMA请求还要同时限制行尾、最多16拍及4KiB边界，不能只按整行请求后假定旧FDMA会拆地址边界。data_available是有效数据输入，data_consumed是实际W握手输出，不能混作ready。

输入短帧、错身份、错EOL/SOF、超时或abort时，保持已经向AXI呈现的拍直到握手，再给剩余固定画布补零并等待所有B；RGB终态置坏而不是将半帧提交。缺失B时保持占用，B错误锁住新帧。`frame_writer_v1`实际writer/FDMA/guard通过10帧600拍70响应，2提交8丢弃，明确覆盖W停顿中abort及晚到坏CRC。`fullhd_writer_v1`独立颜色/位置参考核对默认1920×1080全部8294400字节、33480写请求及响应、2025地址页边界；两者范围分别保留，不能合并为真实相机全链证明。

当前writer/guard是单UI时钟域。真实CSI/ISP跨域必须连同seq/token/帧行标志保留像素，早到的canvas/CSI终态也要缓存到对应帧admit后才能交给guard。事件口ready不等于未来帧已分配bank；start同拍的事件不能直接注入旧guard。后续还要连接残帧FIFO排空/新SOF重新同步、溢出与失联处理、显示读停止与实际响应排空及完整top/CDC约束。264输入保留父262冻结，本阶段没有own native/bit/实拍通过。

后续完整 `hci09_video_store_20261015` 登记266输入，复用实际mipi_sfifo，把有效/applied、seq/token、SOF/EOL/EOF和RGB128组成同一个197bit像素字；canvas、abort及233bit源终态使用独立事件FIFO。video/source/UI三域各自释放复位，早到终态保留到对应帧已admit后再消费。旧帧事件按32bit半空间序号丢弃，未来事件等待；不能在start同拍消耗对应终态。

新SOF打断未写满旧帧时保留新帧头，旧writer补零并等B，释放后恢复；旧帧已写满只等DDR响应时，新帧头不取消它。未applied帧、源loss和事件FIFO不可背压脉冲溢出均有明确处置。ingress_v2通过三个独立时钟下10帧600写拍70响应；resync_v2通过残帧/新SOF、未applied及失联6帧；overflow_v2再覆盖12个未来canvas脉冲溢出并禁止新admit。范围重叠不重复计数。

验证取消时须区分“被像素FIFO接受”与“被writer接受”：abort后未被writer消费的FIFO字节可以合法丢弃，独立存储oracle应在UI真实握手处分界，不能要求它们继续写入。完整实际CSI/ISP/真实canvas与终态→跨域→DDR联合另查csi_store_v2终态，运行中不得计通过；显示读排空仍是模型，完整top/AE/预处理/共享UART、own native和实拍继续待验。

csi_store_v2现已终态通过并经csi_store_review_v1复核：7个合成RAW源帧通过实际CSI/完整ISP/真实事件生产者/CDC/FDMA，6个RGB帧3072像素写入，5提交1丢弃。微小窗虽然没有AE内部统计区，仍可发布；晚到坏CRC不发布，异常源后恢复。存储参考取实际ISP输出，仍不替代独立Bayer/色彩数值或光学验收。

## 显示读事务、代次与bank释放

后续 `hci09_display_reader_20261015` 完整269输入增加UI viewport reader、display read session和共享FDMA读写接口wrapper。读端设置checked FDMA的B2B_SET=1，按行尾、16拍及4KiB拆请求；默认1024×600视窗按源stride1920像素读出，不能把viewport宽度误用为源stride。

显示边界先取消旧读、排空已接受R请求，再允许guard切display_bank，随后发新读。取消不能提前释放缺R响应的bank，也不能改变已经向下游呈现的持有像素；输出保留generation、source seq/token和viewport index。旧像素可能在新bank获准后才被下游消费，因此像素端必须按generation丢弃旧帧，不能只观察实时display_bank。R错误形成粘滞故障并阻止新读/释放许可；此前已经送出的像素无法撤回，后续像素端还需错误空白控制和遥测。

display_reader_v1用实际reader/session/guard/FDMA读端验证2完整帧、2取消、1错误及无图边界，18 AR/139 R；viewport_v1独立核对默认窗口全部2457600字节、10200 AR/153600 R及输出背压。读端source发布条件仍为合成。实际CSI/ISP写入并从同一FDMA/同一内存读回的联合看csi_readback_v2终态；运行中不计通过。pixel-clock扫描消费、边界跨域和DSI、完整top及native/实拍仍待，不能把UI读回等同于屏幕正确显示。


## 像素时钟域扫描与DSI字节顺序

display_reader/csi_readback_v2现已终态通过，并由csi_readback_review_v1核对全部源码绑定：7个RAW源帧通过实际CSI、完整ISP、真实帧事件、写入与读出共用一个checked FDMA/同一AXI内存模型，仅1/2/3/4/7读回且每拍匹配ISP输出。UI读回通过不等于屏幕光学通过。

后续完整pixel_scanout候选登记272输入/79累计组件。像素组连同generation、source seq/token、位置及SOF/EOL/EOF一起跨UI→pixel；VSYNC创建generation并原子跨回UI。消费位置只由真实DE推进，缺数据填黑，迟到位置丢弃，未来位置等待，避免少一个quad导致后续整行移位。旧代次可以在新bank已经生效后才从FIFO出来，必须按携带的generation过滤。身份/形状错误或上游故障使剩余帧变黑；数据和所有同步信号同拍延迟。边界请求已提交的值保持，未提交的积压可合并成最新generation并计数。

复用原video_source/video_tpg时序、rgb_24b_to_32b及真实FIFO和DSI packetizer。显示存储为{X,R,G,B}，24bit为{R,G,B}；DSI载荷按R/G/B字节序，32bit低字节先发送。依据赋值和逐字节oracle确认，不能用FIFO字面注释推断lane顺序。默认1024×600 viewport从1920像素stride读，不能因此宣称全1080p缩放显示。

pixel_bridge_v2覆盖8场景252像素及边界积压；dsi_readout_v1实际reader/FDMA/CDC/时序/转换/DSI通过2帧1024像素及16个CRC，独立位置/颜色参考。默认视窗dsi_viewport_v1也已终态通过：两帧1228800像素、3686400载荷字节、1200行CRC全部匹配。完整CSI→DSI csi_dsi_v2另查自己的result.json终态，不把运行中状态或分项证据合并成未完成整链。完整顶层、AE/预处理/共享UART、CDC约束、own native与实物另待。已有物理37与父候选冻结。


## 预处理延迟、事件分发与完整服务连接

pixel_scanout/csi_dsi_v2现已终态通过并独立复核：7个源帧的合格身份为1/2/3/4/7，坏5/6不显示；实际CSI/ISP/真实事件、同一FDMA内存、像素跨域和实际DSI串行载荷/CRC一致。19次完整有效显示对应9728像素，载荷核对30816字节包含初始黑帧。它使用缩短消隐的64×8和合成source context，不等于整机、物理传感器或屏幕验收。

完整processed_store候选274输入改4个相机层次模块，导出真实canvas事件并把terminal原子交给控制监测、AE视频域和DDR事件队列。多分支不能各自消费同一valid后只等待最后一支；本连接要求三支都ready才发生同一个源握手。新增端口store_terminal_ready必须接真实消费者，旧测试实例漏接会使源终态停住。

预处理有行缓存和输出背压，不能直接把实时ISP metadata绑到其输出。新preprocess_identity在输入SOF握手锁存234bit身份，直到输出EOF消费；输入完整而输出未完时，下一SOF合法等待。显式abort、错身份、过早SOF或形状错误flush处理状态与历史LUT；非SOF孤立拍丢弃到下一个SOF恢复。异常判断按时钟沿生成abort，避免刚接受首拍后组合状态改变把仍保持半拍的SOF误判为新帧。处理后还需重置补边为黑，防止邻域算法把有效像素扩散进无效区。

preprocess_identity_v1实际hci01通过5完整帧320像素、2帧独立77/150/29权重灰度和3残帧取消/恢复，包含下一SOF等待及持有metadata/config。camera_display_core已连接相机owner/完整ISP/AE/共享UART、预处理、帧缓存和DSI；camera_display_core_v4联合结果另查实际终态。board system_top与物理时钟/复位/引脚仍待接，不能将逻辑core接通称为完整板级工程已通过。


## 板级顶层替换与资格边界

board_integration_20261015 完整274输入独立接入单个camera_display_core、单checked FDMA与保留的DDR/CSI RX/DSI TX/显示初始化。旧相机I²C/ISP/dbuf/UART实例移除后，必须把CSI错误统计、RAW握手、实际store握手、配置序号重新从真实新层次导出；不能继续引用已删除信号。ADC及供应商IP保持冻结。

实际头文件端口检查发现旧DDR实例11个悬空输入，副本显式连接时钟/复位、未使用刷新/PZQ/DFX和UART空闲。外部PZQ完成保持0不表示已校准；控制器仍使用实际自身完成信号。完整默认尺寸数字层次编译退出0。严格检查的3条供应商FIFO警告单独保留和复核：cea(1)、ocea(0)、web(0)从32位常量截到1位仍为1/0/0；只能按精确文件哈希和诊断接受，不忽略其它宽度问题。物理叶模块仅公开接口模型，因此不是native、PHY、DDR校准或面板验收。

当前核心复位依赖系统PLL与DDR校准，所以UART也等待DDR就绪；连续时钟启动/恢复和DDR未就绪独立诊断仍待，不能凭父core仿真暂停时钟的结果补签。引脚S_clk_25m名称保留但目标为受保护27MHz；旧内部25MHz改名S_core_clk25。SDC不引用已移除I²C分频实例，不继承宽泛异步组；新跨域仍计时，待具体同步器/Gray/bundle路径及原生PLL集合审查，不能当最终STA。

用户确认CAM005/VID005精确原理图稍后提供。power_good、运行中slot、实际帧applied仍保持未资格化，相机候选停用；这不影响板上正式PCIe37。原理图未到不能把读回或合成VSYNC当作实际电源/XVS/XHS/寄存器生效依据。新core联合仿真终态继续以processed_store/evidence/camera_display_core_v4/result.json为准，与板级结构编译分开。


联合core_v4最终失败：12帧处理、source10入库及288拍读取已发生，但DSI完整帧为0。测试在UART阶段暂停UI/pixel时钟后没有恢复就检查显示完成。v5恢复测试时钟并以100000像素周期为上限等待实际完整DSI帧；是否修复以processed_store/evidence/camera_display_core_v5/result.json终态为准，不能预先归为纯测试问题或计为通过。v4原始失败及全部输入保留。


## DDR 未就绪时保留诊断、掉线后结束旧操作

board_recovery_20261015 完整276输入、83累计组件（不是新增83项任务）把控制面与相机/存储复位分开。原顶层把UART也绑到DDR校准，使失败时无法查询；新board_reset仅按PLL给25MHz控制同步释放复位，DDR另控制camera_rst_n。相机引擎、预处理/存储/扫描在DDR掉线时复位，视频处理本地三拍释放；FDMA保留原DFI同步复位。单个共享UART和旧服务存活，无额外发送器抢占输出。实际power/slot/applied仍待原理图，相机候选未放行。

只让UART存活还不够：host可能停在START_WAIT或WINDOW_WAIT，而已经复位的engine永远不会返回完成。host_control_v3在后端失效时以原操作seq和done_code=0x0001000A结束等待，保持序号、待发送payload及重放缓存；不把旧ACK改写为新结果，需STATUS查询当前done。后端无效不发起新操作，STATUS/ABORT/auto-off仍可处理；恢复后不自动续接旧AE或启动许可。HCA9 flags bit7标识本版backend_available，旧版保留位为0不能解释为DDR故障。

recovery_v1实际UART RX/router/CRC/host通过20检查、11命令；recovery_uart_v3增加真实共享TX并逐字节/独立CRC验证11个ACK1408字节，包含未就绪、启动/窗口等待丢后端、持有ACK、半包跨DDR恢复、短脉冲丢校准及PLL恢复。所有backend完成为明确合成输入；停钟测试TX/RX共用暂停时钟，不证明外部接收器停钟容忍。实际完整数字层次编译和单项通过不等于连续时钟相机/DDR整链恢复、native或实机通过。

Icarus中初始化表达式引用的wire应先声明。测试打开组合ready条件后，要在稳定后或真实posedge握手处观察；立即读取旧ready再等待下一negedge可能漏掉已经发生的一拍握手。恢复UART测试v1/v2的声明和观察失败分别保留，v3只修正测试，不能将失败日志删除后宣称首次通过。


## 完整服务核心联合终态与连续恢复验证边界

processed_store/camera_display_core_v5 已终态通过并由 camera_display_review_v1 核验：12个RAW帧、13824处理像素、410启动加10AE串行操作、仅已applied的源10发布，恢复测试显示时钟后1120像素周期完成完整DSI帧。UART实际1728字节，4个HCA9、8个HLA8、DSI6/HCT4/DSIF各1包全部独立CRC匹配。保留v4最终DSI帧数0的失败；v5仅补测试显示时钟恢复/有界排空，274输入功能RTL不变。黑色RAW与测试时钟暂停边界仍在，不能因为终态PASS就宣称连续时钟板上整机通过。

board_recovery/image_recovery_v1 另测六路连续时钟、真实CSI/ISP/预处理/共享FDMA/像素/DSI链路、DDR保留旧内容、待读响应和部分写入时的校准丢失。先通过实际UART配置，再检查复位后无旧帧读取、先黑后新token，且配置序号保留。该专项只在engine.source_capture_enable/source_context_valid/source_context三处明确提供合成owner描述符；不覆盖其余功能逻辑，也不能据此补签物理电源、传感器初始化或applied资格。相同帧seq在复位后可能重用，必须同时核对token和FIFO/帧发布有效位；单看帧号变化不够。状态以本专项自己的result.json实际终态为准，运行中不计通过。


连续恢复终态补充：image_recovery_v1 已通过，image_recovery_review_v1 核对276输入及实际日志。六时钟连续运行，DDR读事务/部分写入中断两次，恢复token101/202/404各至少两完整显示帧，6项检查，DSI载荷19968字节在HDL内逐字节和CRC验证，配置序号77保留。复核脚本独立校验UART配置CRC；没有归档DSI字节供二次独立重放。三处owner描述符模型边界保持，不能补签传感器启动/物理applied、独立ISP算法或native/板测。


## 像素域复位释放、LP配置与统计短复位

pixel_reset候选完整276输入仅改变scanout与顶层观察逻辑。父版把控制域释放的reset直接接video_source、RGB打包和DSI封包，像素停钟时会提前释放；顶层dsi_frame_stats使用同步reset，会漏掉停钟期间1ns脉冲。pixel_reset_v1与observer_reset_v1均用实际叶模块/从实际top原样提取的连接复现父版失败；修复版新增三拍本地释放、两级配置同步，业务不取第一级。15项停钟/短复位/8相位检查、统计恢复和实际两帧DSI独立RGB/CRC通过。元稳态与MTBF没有在RTL仿真中证明；完整连续图像回归以该候选自己的result终态为准。

时钟审查不能只读顶层SDC。该工程构建配置还导入DDR IP SDC，其MCU时钟异步组和PHY例外仍在；不能宣称整个工程所有路径均未豁免。实际FIFO Gray同步模块有keep但没有ASYNC_REG，二者不等价；需核对原生属性、源Gray至第一级的延迟/偏斜以及后两级实际布线。握手保持总线也需逐实例的具体路径约束。DDR IPC的533MHz/4:1给出名义DFI133.25MHz；100MHz UI数字回归不代替实际带宽/STA。手工27MHz PLL同样不能以算术正确代替生成、锁定与物理频率测量。


## FIFO同步属性与每位清单

pixel_reset连续图像恢复已终态通过并复核，session56040关闭；六时钟、两次DDR中断、三次新token显示和19968字节DSI载荷/CRC符合原断言，三处owner模型边界不变。

后继fifo_cdc完整276输入仅给实际csi_integrity/sfifo的四个复位同步寄存器，以及Gray目标域sync_r1/primary_addr_gray_sync加ASYNC_REG=TRUE，原keep保留；源域Gray生产寄存器不是目标同步级，不标记。剥离新增属性后文件与父版逐字节相等，不重复无逻辑变化的长图像仿真。完整层次有7FIFO、14Gray跨域，共224个需要确认的同步位。

总属性数非零不证明指定链完整。check_fifo_native_attributes.py要求gate/place清单全部预期位存在，缺位、重复、错误phase、虚报count或false属性都拒绝；正反测试使用明确合成fixture，不签核native。预期层次_reg[bit]名称必须再用该候选真实网表确认，若被改名/优化不可直接放宽匹配。Icarus语法/层次成功及仅对部分非虚拟信号显示属性均不能代替TD属性/拓扑、Gray路由偏斜和MTBF。当前原生构建脚本启用了属性并核对gate→place保留，但该候选尚未运行自己的native。


## 实际TD隔离综合与约束调用验证

fifo_native_probe_v2已使用当前完整sfifo源，在PH1A90SEG324/-2对地址宽度4/10/13的三个8位数据FIFO做实际综合，无place/route/bitgen。120个同步位在gate及第二次debugger后重新启用属性时全部存在。fifo_native_review_v3解析真实401KB门级网表及348条buf别名，对60条两级链核对首级Q唯一接次级D、同一目标时钟和异步复位、常开时钟使能，并确认Gray输入来自源域注册器。初版Tcl路径反斜杠转义失败、复核器对共享时钟别名和_reg_reg生产寄存器名称的错误假设均保留；修正工具依据实际网表，未修改功能RTL。

gray_constraints_effect_review_v1确认read_sdc中精确NAME相或表达式把6组max-delay约束绑定到54条实际gate路径，全部Dominated，Shadowed/Ignored均0。直接Tcl拼接查询名称后调用约束时曾得到空from/to；regex括号转义在SDC中也失败。观察涉及调用入口和集合构造变化，不能仅归因某一个Tcl操作。必须检查有效路径报告，不凭返回0或查询列表长度签核。

set_path_skew在当前gate探针仍无报告条目。get_regs实际查询12组共108个源/目标对象，数量正确；移除max-delay后skew报告仍空。尚未证明根因或布局后行为，不能宣称偏斜通过。诊断10/7.5ns时钟、6ns最大延迟与0.5ns偏斜不是板级生产预算；datapath_only按TD文档会切除所选源到第一级的hold分析，不能扩大到同步器级间。原gate DB哈希保持，完整板工程224位、原生布局布线和物理验收仍未完成。


## FIFO 布局打包与约束选择（实际隔离探针）

`hci09_fifo_cdc_20261015/evidence/fifo_physical_review_v1/result.json` 对真实TD布局/布线网表复核：120个逻辑同步寄存器映射为66个带ASYNC_REG的PH1_PHY_LSLICE；逐QA/QB槽位追踪60条两级链，首级Q只到次级D，同钟、同异步复位、常开使能均保持。不能拿gate的120个cell与place/route的66个slice直接比较数量来判丢失；必须追踪实际寄存器槽位。此处仅是三个8位数据FIFO，不替代完整7 FIFO/224位的物理实现或MTBF验证。

gate有效的`get_cells -filter {NAME == ..._reg[n]}`在打包后全部变为零路径，check_timing报告144条invalid；正常退出和正WNS仍不能签核。`fifo_register_constraints_v2`对原gate/route DB只读重新分析，以`get_regs {实例/primary_addr_gray_reg[*]}`到`get_regs {实例/sync_r1[*]}`约束同一组逻辑信号，两个阶段均为6组54条有效max-delay路径、无shadowed/ignored、invalid为0。`clear_sdc -user`仅用于该独立探针内存中的旧诊断SDC，原DB哈希未变；不要据此清除板工程或IP约束。源到首级的datapath_only隐含hold豁免，不能扩大到两级同步器之间。

本探针gate和place的path-skew报告均空，route首次列出6组；测试预算0.5ns下5组失败，实际0.490/0.817/0.641/0.988/0.683/1.282ns，最差slack -0.782ns。逻辑信号约束修复后偏斜数据不变；重新分析SWNS 2.406ns/HWNS 0.036ns不抵消偏斜失败，也不覆盖无input/output delay的诊断IO。生产预算需按实际源时钟及协议推导，不照搬或随意放宽0.5ns求通过。保留原失败证据，未bitgen、未下载、未修改完整候选276输入。


## 完整 Gray 约束候选与时钟纠正

完整候选 `hci09_gray_constraints_20261015` 保留276输入与全部RTL，按真实层级连线定位7 FIFO/14方向/98源到首级路径。使用逻辑get_regs信号选择，预算按两端较快配置周期的80%向下取整到1ps；这是工程预算，不能替代实际时钟/route证据。其原生构建在gate/place/route检查每组集合宽度及有效路径，报告缺失、宽度错误、Shadowed/Ignored或零路径会停止；exact guard在真实隔离gate/route中分别通过正例及四种负例。原0.5ns探针偏斜失败保留，不用新预算改写旧结果。

完整gate-only综合暴露未使用的PLL C1被移除，旧rename产生空集合警告；DDR实际派生倍率约1.3333，而IPC摘要的533MHz/4给出133.25MHz，两者不能混用。新完整副本 `hci09_gray_clockfix_20261015` 移除无效C1 rename并把DDR相关10方向预算从6.003ns收紧到6.000ns。所有时钟定义及其余约束保留，原运行输入未改；最终必须核对实际周期及源/目的路径，未计原生或物理通过。

`held_bus_inventory_v1`枚举当前5个hci09_bundle_cdc和7个csi_stats_snapshot；后者的held除snapshot外还驱动previous_cycles及含减法的clock_delta。约束仅覆盖snapshot会漏掉真实路径；需连同控制同步链和保持期限验证，不能用Gray FIFO结果替代。此清单仅覆盖这两类模块，不是全设计CDC穷举。


## 保持总线的合并寄存器与约束覆盖

`hci09_gray_clockfix_20261015/evidence/held_union_review_v3`使用未修改的hci09_bundle_cdc和csi_stats_snapshot实际综合/布局/布线；在8位数据/8位统计探针中，snapshot高32位与previous_cycles合并，拆成三条snapshot/previous_cycles/clock_delta约束会让32条路径被重复覆盖。真实门级出口经输出PAD由同一previous_cycles寄存器驱动已逐位核对；不能假定导出网表保留原snapshot内部网名，也不能混淆HP与普通PAD参数。

将目标集合联合后，568条独立快照路径（包括clock_delta减法）加8条bundle数据和4条握手首级路径，共580条在gate/place/route均有效，invalid/shadowed/ignored均0。诊断10/7.5ns时钟、6ns数据预算下route内部SWNS2.903ns/HWNS0.033ns；未覆盖外部IO、全板CDC、MTBF或实机。首版探针超出148可用IO，后版合并诊断输出保留待测数据；路由执行脚本曾因全局替换OUT误改ROUTE结束标记，原FAIL保留，真实退出0/route日志/报告/DB独立复核通过。后续模板使用有边界的占位符。

完整`hci09_held_constraints_20261015`继承276输入与全部RTL/14 Gray约束。当前12实例的保持数据按接收时钟分4组，24逻辑握手首级路径分5组，避免同钟跨实例寄存器合并导致重复覆盖。数据预算为接收周期80%，而协议最早采样距held更新为snapshot2个、bundle3个接收间隔；源端保持至消费确认或下一合法请求。仅对异步控制到首级做datapath_only，后续同步级保留普通时序分析。

完整流程检查9组的实际有效路径与预算，并拒绝缺失/覆盖/忽略；准确检查器用真实route报告及预算错误、缺组、旧重复覆盖、孤立报告误作整板四负例验证。组内非零不能证明每个实例和每条扇出已覆盖，最终仍需逐实例原生映射及合法常量优化审查。其他CDC模块仍需继续检查，不能以这两类模块覆盖全部设计。


## 完整门级报告与实际时钟精度

`hci09_native_clock_budget_20261015/evidence/full_gate_review_v1`复用了全部RTL/IP/ADC字节一致的真实system_top门级DB，重新加载用户SDC并保留IP约束。14组98条Gray、9组773条保持数据/握手路径有效，224个FIFO同步FF与112条两级链已在完整网表核对；组数或有效总数仍不能代替逐实例扇出及优化审查，24逻辑握手只剩22条原生路径的原因尚需逐项解释。

TD本版本把输入2.244669ns量化为2.244ns，CSI字节时钟实际报告8.976ns；80%预算按ps向下取整为7.180ns。DDR报告7.500ns对应6.000ns，75MHz报告13.333ns对应10.666ns。预算必须从实际报告重新计算，不能只用输入小数或IP摘要。PH1_PHY_GCLK_V2未显式覆盖PRESELECT时，本机arch/ph1_macro.v默认CLK0，分析网表时应绑定对应库版本。

`report_clock_utilization`仅能在place之后调用，gate阶段用get_clocks/report_property读取时钟。诊断命令失败前已导出的完整DB可用于只改约束的重新分析，但这不是新约束驱动的新综合或物理验收。原始失败保留；未来gate-only脚本已改为v2，此次没有重跑综合。当前综合SWNS -4.326ns，最差是视频同钟canvas active_height到ISP rgb_count使能；13条soft FIFO告警和跨域复位恢复路径仍需逐条审查，不可用全局时钟切断来换取通过。


## ISP行位置与被关闭的整板采集链

完整门级最差路径从canvas active_height，经raw_valid/start和32位`(start?0:raw_count)%480`进入ISP错误清除/计数使能，19级逻辑、17.600ns数据延迟。`hci09_isp_columns_20261015`将RAW/RGB列位置改为仅在各自握手时递增并于行末清零的计数器；首拍、flush和复位一起初始化，保持吞吐和逐拍接口时延。4/12/1920/4096行宽与原RTL逐拍比较，16完整帧、24中止场景通过。该对照使用ISP传输模型，只证明包装器行为；真实整链回归和新原生时序必须分别检查，不能据此宣称时序关闭。

完整原生24逻辑握手只有22路径的追查已发现to_control/to_video请求同步首级D为常量0。其来源是当前生产顶层physical_power_good固定0，startup guards_ok及capture_allowed必为0，等待CAM005/VID005供电依据。不能把缺失报告/数据寄存器简单当作别名优化，也不能用这份完整源的门级DB代表相机启用后的全部控制/CDC/资源/时序。原有连续像素回归在三处显式force源描述符，只覆盖像素/存储/复位链。补充原生诊断应使资格输入可激励并明确非实物证明；生产顶层必须以实际硬件依据接入power/slot/applied信号。


ISP列计数版已进一步通过`hci09_isp_columns_20261015/evidence/image_recovery_review_v1`真实六时钟连续图像回归：实际CSI/RAW/ISP/预处理/共享DDR/DSI链、6次图像检查、2次校准丢失与101/202/404恢复，配置77保持。三处owner源描述符force仍明确保留，因此不是实际启动或物理资格证明。

为避免物理资格固定0让综合移除启用后的控制链，`hci09_enabled_gate_diagnostic_20261015`保留全部276输入及业务RTL/ADC/SDC，只在隔离的诊断顶层增加3个未分配引脚的输入，经67位串行字独立提供power、slot_valid/cycles、applied_valid/token。MSB先移入，最后移位之后单独提交；71字和67行走位验证提交前保持、复位清空。普通build入口明确拒绝物理构建，专用runner只到gate；它必须逐实例检查启用后的寄存器/扇出恢复，不能把可激励输入本身当作验证成功。诊断数据不构成真实供电、通信窗口或设置生效证据。


## 终帧校验的DDR时钟流水线

旧整板门级终帧FIFO到发布guard/bad路径包含width×height×5/4与合法性比较，SWNS -3.517ns。`hci09_terminal_pipeline_20261015`在FIFO后加入4级弹性校验：锁存报告、13×13面积（先保留16位范围检查）、29位乘5/除4字节计算、最终比较。sequence/token随每级保持；未来帧/错误帧也保持顺序，复位清空未消费报告。每拍可接受1报告，固定无停顿延迟4个UI时钟；CRC/尺寸/行数/字节数不合格仍拒绝，原SDC/ADC未放宽。

独立64位算术oracle验证4000报告，3992输出及8复位清空、4196次停顿；真实三时钟FIFO/写入器/FDMA/guard的10帧600 AXI beats/70 B回复、6帧重同步及12事件溢出测试通过。7.5ns孤立实际TD布局布线保留失败：全IO SWNS -0.934ns/HWNS -2.814ns；在同一DB和相同约束下单独报告684寄存器间1114路径，SWNS +2.373ns/HWNS +0.103ns。后者仅证明孤立内部路径，不覆盖诊断IO、完整工程互连或真实板级接口，不能改写整份STA失败或宣称整板通过。


ISP列计数版完整原生综合现已完成（evidence/native_gate_review_v1）：WNS -3.107ns、TNS -284.015ns，相比此前门级重分析-4.326/-2200.303改善，剩余最差明确为terminal FIFO→guard。14 Gray/9 held组共871路径有效，224 FIFO同步位/112链重新按新网表核对；旧仅14组的检查器必须从新增9保持约束中明确选择Gray行，不能把23组报告当成14组。结果仍是采集资格固定0的顶层综合，不证明启用相机链或物理时序通过。


完整门级CDC复核不能只数set_max_delay路径。启用诊断工具`gate_handshake_graph.py`从实际网表解析寄存器、buf别名和PLL/GCLK祖先，逐条核对12个held实例的24握手：源寄存器真实存在、目标域2/3级同步、async_reg、复位与使能，以及前级Q仅进入下一级D。旧ISP列计数网表验证22条有效/2条常量0请求，与先前缺失报告一致；额外首级扇出和错误目标时钟反例均被拒绝。另对这12实例的24条本地复位释放链核对72位、常量1入口与3级私有串接，不能据此替代recovery/removal STA或实物停钟测试。启用后的网表必须重新执行，并要求24握手均有效；不能复用旧22条结果签核。


启用控制链完整综合Q现已完成：24握手真实源/级间扇出、24复位链72位和FIFO224位/112链均通过，保持路径从773增至1674，说明仅数旧约束不足以覆盖启用逻辑；98Gray+1674held=1772路径均实际有效。整体仍WNS -5.068/TNS -993.377ns，最差21级为metadata→RGB补黑→灰度DSP→48位亮度sum/report_sum。Y生产候选hci09_luma_observer_20261015在统计入口增加366位逐周期采样，输入握手/元数据/idle错误一起延迟1拍，像素流不变，report_ready按当前拍消费。9帧协议验证包含idle错误、X valid/ready/RGB、满报告槽丢弃及EOF入流水线后复位，均通过；实际AWB/整链和完整启用时序仍需各自新证据。不可只锁存成功握手而漏掉无数据拍的错误，也不可把诊断输入当真实供电/slot/applied。


2026-10-15 时钟监测约束与亮度流水线复核：Y的实际AWB五帧、连续全链六检查/19968 DSI字节、两次DDR中断恢复均通过。Q clock_guard原生图需正确展开PLL clkc拼接中的[1:0]切片，不能把逗号元素直接当单比特；32×3 Gray、请求应答4位、复位9位共109同步位已逐一检查。源注册Gray→gray_ref1及请求/应答仅到第一级，按较短周期37.036999ns的80%向下取29.629ns。直接Tcl调用set_max_delay（变量和内联get_regs两种）虽命令返回成功且端点查询32/1/1正确，实际异常报告仍23组，均不接受。完整user SDC通过clear_sdc -user/read_sdc导入才得到26组1806有效路径，旧1772保留、新34有效且无shadow/ignored；IP约束保留。证明位于projects/hci09_enabled_gate_diagnostic_20261015/evidence/clock_guard_constraints_review_v3/result.json。Z生产候选hci09_luma_clock_bounds_20261015只改SDC和构建检查，HDL/IP/ADC与Y逐字一致；gate/place/route检查新三组精确路径数和预算，缺失/数量错误/ignored/shadowed/预算放宽/重复六种坏报告均拒绝。A hci09_enabled_luma_clock_20261015启用诊断等待完整新综合，新网表仍需重验，复位recovery/removal和整体时序/实物均未计通过。


2026-10-15 复位端点分类：X终帧流水线完整启用网表WNS从Q的-5.068改善到-4.417ns，但TNS由-993.377恶化为-1163.095ns，不能只看WNS宣布时序收敛。Q真实报告46条负recovery中25条落在已独立证明的复位同步器SR上，1条为自有identity_fifo/active_reg.sr，20条为加密CSI PHY反序列器或内部地址寄存器；报告受端点数量限制并非全部路径。同步链清单共109 SR引脚，只可在独立DB试验精确例外，必须查看report_timing_ignored，不能仅依赖report_timing_exception（后者主要列MCP/SMD）。功能寄存器不能套同步器例外。hci09_csi_identity_stream虽然已有3级source_reset/video_reset和运行使能，功能always块仍原先直接用rst_n；新生产hci09_identity_reset_20261015改为各自末级本地复位，保留异步断言，FIFO自身跨域复位不改。实际Gray FIFO/RAM的11场景109beats通过；双时钟停止时复位、两种先后恢复顺序各两次，共30beats验证旧描述符清空和新帧身份正确。停钟测试v1生成器end/always间缺空格导致编译失败已保留，v2修正后通过。独立DB复核109精确SR查询及ignored报告的109端点/145recovery路径、0removal路径，26组1806延迟路径保持，自有功能寄存器/PHY仍接受时序检查。此只证明门级作用域；生产未加入该例外，布局布线后命名、新网表和既有DDR IP的例外须分别审查。完整图像、完整新网表和整板仍须单独验收。


2026-10-15 identity本地复位后续：hci09_identity_reset_20261015完整连续图像回归通过，6检查/19968 DSI字节、DDR中断两次，101/202/404身份恢复；UART配置77保留。依然有明确的3个源owner描述符force边界，不能计为真实传感器资格或PHY验收。hci09_enabled_identity_reset_20261015复制278输入后只替换已测67bit诊断transport并禁用普通物理build，71字传输验证通过。新增review_functional_reset_graph_v1按真实门级逐一检查identity_fifo直辖功能FF的SR驱动，追溯同域3级async_reg复位链、常量1入口和私有级间连接；不能凭RTL局部命名或仅enable门控断言复位安全。审计器对真实旧Q门级负向运行，明确因reset_supervisor/camera_release_reg[0]的目标时钟不匹配拒绝，证明能捕获本次缺陷；新完整网表正向证据仍须等待，保持该差别。


2026-10-15 亮度完整native与AWB后续：A hci09_enabled_luma_clock_20261015已完成完整门级/五项图审计，26组1806约束有效，WNS/TNS为-2.734/-749.989ns；相较X的-4.417/-1163.095改善但仍失败。新最差数据路径CCM输出→ui_awb/stats_a_neutral为-2.630ns、21级，需针对真实新瓶颈处理。D hci09_awb_parallel_20261015把原3*min>=2*max改为六个有序通道对3*c_i>=2*c_j，并行做所有8..240范围检查；已知RGB全部16777216种在实际HDL函数穷举精确等价，1555313中性色由按最大通道的组合公式独立复算一致。288个X/Z注入明确排除，区别于旧函数可能忽略未知第三通道；像素和统计延迟未改。实际窗口AWB五帧通过。独立同13.333ns小route显示逻辑10→4级、数据8.343→8.194ns、内部setup4.800→4.871ns，但两个含IO的probe均有hold失败，不能替代完整工程收敛。原始基线route完成后get_regs match_out别名查询失败，保存原route.db和报告，改从真实物理寄存器时序行复核，未重跑基线；失败日志不覆盖。旧供应商AWB注释含非UTF8字节，函数替换须保持其余字节，不能误转码。另Q PHY图补齐四lane：28内部地址SR和4输入DDR rst均来自LP状态bit4（PAD前一个反相LUT），非109已证明复位链；32端点涉及36时钟配对，不把受限timing报告20条当全部。全部PHY timing仍未验。


2026-10-15 并行AWB完整链验证：hci09_awb_parallel_20261015的278项输入逐一SHA冻结；完整连续时钟图像回归已通过，2次DDR校准失效、token101/202/404恢复、6次检查和19968字节DSI输出校验，UART配置序号77保留。该测试沿用3个明确的合成owner描述符force，不证明真实CAM005窗口生效或DSI屏光学颜色。审计通过后才创建hci09_enabled_awb_parallel_20261015完整启用诊断副本；实际业务RTL/ADC/SDC字节保持一致，71组67位资格传输检验通过，综合依赖上一轮确切进程句柄，后续七项审计包含功能复位图及最终约束/时序汇总。完整图像通过仍不能替代全工程时序收敛或上板验收。CAM005/VID005精确电源和XVS/XHS资料由用户之后提供，暂不推断引脚可用性。


2026-10-15 identity功能复位完整门级证明：C复位修正版完整启用综合及6项审计通过结构检查：337个功能寄存器均由本域3级复位链释放，26组1806约束有效；WNS/TNS=-2.723/-581.735ns，仍未时序收敛。D并行AWB整链图像6检查/19968字节通过；E完整新版native71684执行，7项自动审计等待。 原始raw reset不再直接连接身份流功能寄存器SR；每一实际网表端点均向上追到同域三段常1、async_reg、私有中间级链。该结构证明不等于完整recovery/removal或物理MTBF签核；供应商FIFO同步链/PHY32端点仍需其自身证据。


2026-10-15 并行AWB完整native精确端点复核：E完整278输入、26组1806约束和7项结构审计完成。对C/E已完成gate.db只读update_timing，同一SDC，以4个AWB logical register查询得到4个D、4个CE setup及4个SR recovery，不能把逻辑寄存器数误当setup检查数。全部D/CE最差从-2.630到+3.232ns，21级到12级；AWB实际改善成立。整体WNS/TNS仍-2.723/-908.499ns，比之前TNS -581.735更差。32个u_post数据D端点均负裕量，最差-2.321ns，来自像素FIFO写指针经组合ready，17级、扇出2160。局部改善不等于完整时序通过；后续在完整独立副本插入注册弹性边界并覆盖metadata/config/abort与DDR恢复，不能用false path掩盖数据路径。


2026-10-15 像素FIFO入口ready切断：独立hci09_pixel_ready_cut_20261015有279输入，在hci09_stream_cdc加默认关闭REGISTER_INPUT，仅197位pixels实例开启。两拍缓存将128像素+3标记+32帧号+32token+2有效位一起注册；上游ready只看本地占用及同步释放，稳定每拍一笔，满后pop一拍再开放。保留已接受像素和独立abort事件排队，不在上游abort时把前帧尚未排出的EOF清掉。数据寄存器不复位，占用由原src_release[2]清空并同步释放。4096控制字/20000随机/1024连续/20次满队列复位和真实FIFO不同先后恢复的4次停钟复位通过；完整CSI/DDR/DSI图像6检查、19968字节及两次DDR故障恢复通过。G启用诊断副本综合和原7审计继续，必须核对真实新缓存路径/原u_post端点与整体TNS，数字通过不是时序通过。


2026-10-15两槽ready边界的实际gate验证：enabled_pixel_ready_cut候选279输入、26组1806有效约束未改；u_post 32 D/32 CE最差setup -2.321→+0.347ns，缓存头/尾/计数+4.694/+5.382/+8.157ns，整体仍有-2.723ns recovery和其它负setup。TD将generate层级导出为registered_input$queue，head输出别名为m_data，载荷FF的SRMUX=0时没有sr端口；按实际网表查询，保留旧名称检查失败证据。读回过滤时序查询可正常结束却不创建报告；不能把缺文件解释为零路径。本次以所有目标端点报告及332个映射FF本域复位图为依据，不扩大为布局布线或实物通过。详见projects/hci09_enabled_pixel_ready_cut_20261015/evidence/ready_cut_timing_review_v2与ready_cut_reset_v2。


F16剩余时序完整清点使用report_timing_summary -ep_num100000 -path_num1 -viol_only -slack_less_than0，实际命令各选项和值分开。G得到808路径/804端点、696setup/112recovery，与报告统计和一致；26组1806有效约束保持。report_timing_path无from/to返回成功却无文件，不代表零路径；全寄存器查询较慢，已运行进程不能凭观察超时重启。terminal FIFO与四级校验器的ready反馈形成最差setup -1.783ns，新完整hci09_terminal_ready_cut_20261015在输出以65位整体缓存good/sequence/token切断反馈，5000报告独立算术/身份/背压/两次复位通过；图像、native和实物仍分别验。不得把FIFO复位链/PHY recovery合并成同一种违规或加宽泛例外。


终帧ready隔断生产版连续图像6检查/19968 DSI字节/两次DDR失效/token101,202,404及独立复核通过，保留三处合成owner注入边界。enabled_terminal_ready_cut完整279输入和71组67位资格传输通过，自己的gate及后续审计独立进行。G实际monitor Gray三组各32位（video g1/g2/g3及monitor geometry/live gray1/2/3）已逐位核对源注册器、真实时钟、async_reg及私有中间级，共96位；只证明结构，不自动证明Gray生成单比特变化、reset例外、延迟预算或物理MTBF。下一约束必须精确源到第一级，并保留原26组1806约束及其有效性。


源帧Gray最高位在G实际映射为observer/frame_sequence[31]（Gray MSB等于binary MSB），不能要求所有位都以source_sequence_gray_reg命名。按实际96个源/首级目标逐位concat get_regs，源周期8.976ns取80%向下7.180ns；私有DB重载完整用户SDC得到29组1902有效路径，原1806保持，新增96无忽略/覆盖，G TNS -778.446→-708.130但全时序仍负。实际观察器4129步骤含4096连续与33进位/回绕状态注入检查，复位不假定单比特。完整生产monitor_gray_bounds保留终帧缓存全部RTL/IP/ADC，只加SDC及严格构建守护；6组130监测路径对36种错误均拒绝。必须在自己的enabled完整native后重验别名、结构、实际时钟和约束，私有DB结论不能冒充新工程通过。

### 两槽缓存仍可能保留载荷使能长路径

2026-10-15，`hci09_enabled_terminal_ready_cut_20261015/evidence/terminal_timing_review_v1/result.json` 的完整端点统计：负路径808→548（436 setup、112 recovery），TNS -778.446→-492.806ns，WNS仍-2.723ns。终帧FIFO读指针最差setup已到+3.371ns，但新缓存head使能仍有-1.407ns路径。原因是“上游ready仅看本地占用”只隔断ready反馈；搬移式head/tail载荷更新仍依赖下游pop，不能据模块名或ready表达式宣称载荷路径也隔断。

针对该路径，独立完整候选 `hci09_terminal_ring_20261015` 仅把终帧65位缓存改为双槽循环读写指针；写数据仅看push和本地写指针，旧像素缓存不变。5000条独立终帧报告以及200000周期对旧队列逐拍ready/valid/有效载荷等价通过，含满队列、同时进出、背压和复位。此时仅为数字证据，图像恢复和本版native须分别检查结果；不要把该结构推广成任何场景必然更快的结论。

循环缓存增加输出槽选择逻辑。综合后除检查134位映射状态的本域时钟和复位（130位载荷无复位、2位占用和2个指针由ui_release[2]清空），还须同时查询所有terminal目的端点及以output_queue寄存器为起点的下游路径；完整负路径统计保留RAM/DSP/PHY端点。不能只展示bank写使能转正而忽略输出mux路径。若TD优化了预期名称或数量，查看真实网表并留存失败记录，再修正具体别名检查，不直接放宽数量断言。


### DSP 输入寄存器合并后的保持总线约束

2026-10-15，完整启用循环缓存 `hci09_enabled_terminal_ring_20261015` 的独立端点复核得到260条负路径（148 setup、112 recovery），终帧目的端点负setup由196降至1；但输出槽选择仍有3条负setup，最差-0.109ns。通配 `get_regs output_queue/*` 返回201个别名对象，不等于真实134个寄存器。读取网表后分别查询bank0、bank1、count、wr、rd，才得到134个精确对象；保留原查询失败及修正版证据。后续empty/full替代count版另行综合，不能沿用此结论。

这148条负setup中48条落在两个DSP的输入上。TD已将保持总线的部分目标寄存器合并进DSP：XA低13位对应held[148:136]，Y低11位对应held[164:154]，高位补零。`get_regs dst_data[...]` 不能据此推断已覆盖这些输入；实际端点使用 `get_pins {实例名.xa[位]}` 和 `get_pins {实例名.y[位]}`，TD此处以点连接实例与引脚。不要用RTL寄存器名猜映射后端点。

添加保持总线预算前，`review_dsp_capture_v1.py` 在真实网表核对XAREG/YREG启用、各输入寄存器选择的CE与复位、目标时钟、源位和补零；与本束100多个剩余普通捕获FF逐一比较同一CE/复位/时钟。继续展开CE组合LUT，对valid/request/seen的8种组合证明其等于 `!valid && request != seen`，并核对源held寄存器属于源时钟。只看DSP名称或参数XAREG=1不足以证明多位保持协议。

私有旧gate.db重载完整用户SDC后，对to_video使用既有10.666ns预算、to_control使用既有32.000ns预算，新增4组13/11/13/11条精确路径。`evidence/dsp_bounds_review_v1/result.json` 证明原29组1902有效路径原样保留，合计33组1950，无ignored/shadowed；负路径260→212，恰好移除48条DSP输入违规，其余负路径的起终点、类型和裕量多重集合完全一致。WNS/TNS仍-2.723/-215.037ns，整体未通过。上述预算仅适用于已证明的这两束保持协议，不适用于普通任意异步多位信号。

生产候选 `hci09_dsp_capture_bounds_20261015` 将4组约束与构建守护一并注册，10组178条监测/DSP路径的60种缺失、数量、忽略、覆盖、预算或重复反例均拒绝。新完整启用工程必须重新执行自己的DSP捕获图、96位Gray图及33组1950有效约束审计。私有DB、源码检查与守护反例都不能代替新网表、布局布线、物理采样或传感器窗口验收。

### 元数据捕获、行计数与 FIFO 输出后续

2026-10-15，`hci09_enabled_metadata_capture_20261015`（E）自己的279输入综合与13项审计已完成。精确寄存器查询中，metadata 223位最差+4.720ns，input_x/output_x最差+0.302/+1.118ns；gap_age仍有22条setup:sr，最差-0.257ns。全局WNS/TNS=-2.723/-206.603ns，完整184条负路径为72 setup、112 recovery，尚未整体收敛。输入计数查询必须先从实际网表筛选AL_MAP_SEQ，不能把同名前缀下的LUT `_syn_*` 当寄存器。

`hci09_enabled_gap_accept_20261015`（F）将已证明的gap条件因式简化放入完整候选，自己综合及13审计也结束；gap只改善0.025ns，却新增4条input_x D违例，整机负路径184增至189。因此F未晋级，E保留为门级比较基线。不要只按目标端点或TNS微幅改善选择候选；保留完整负路径、计数器D/CE/SR及新增端点对照。约束仍为33组1950有效路径，未通过增加例外消除这些负路径。

下一独立完整候选为 `projects/hci09_enabled_ingress_output_20261015`：默认关闭REGISTER_OUTPUT，仅对pixels(197位)、canvases(64位)、aborts(64位)开启两个本地输出槽，复用现有循环缓存。将FIFO读使能从身份匹配/存储写入ready组合中隔开；像素、SOF/last/EOF、seq/token和应用有效位保持同字一起缓存。额外容量和延迟会改变握手时刻，不能宣称逐周期等价。`evidence/ingress_output_v3/result.json`的六组数字回归通过，包含197/64位真实FIFO随机背压与停钟复位、旧直通正对照、10帧/600个AXI字和错误恢复、失效元数据/新SOF中止及事件溢出。自己的native综合、三组新缓存映射/复位/使能图和整体时序比较仍需检查实际结果；没有新bit或板测通过。

保留v1/v2测试失败记录：旧随机源结尾只执行两次空offer，满时仍可能留下sv=1，导致最终排空检查失败；应等最后一个持有字完成后再停止源。新增64位旧直通正对照没有额外槽，四次满队列复位丢弃量应精确为4×7=28，不能沿用新增缓存的至少32字覆盖条件。此处修正测试夹具及对照覆盖量，候选RTL在三轮测试间未变；不得以删除顺序/有效载荷断言来使其通过。

输出双槽候选的本轮结果已经完成：自己综合1488.782秒、279项输入保持、原13审计通过；连续六时钟CSI/ISP/预处理/DDR/扫描/DSI恢复6检查、19968字节及两次DDR失效通过，仍有三处明确的合成owner描述符注入。新像素/画布/中止缓存目的端点最差setup分别+0.723/+0.580/+1.283ns，全部读出扇出与FIFO读指针setup也为正。metadata/input_x/output_x/gap_age最差分别+4.743/+0.868/+1.627/+1.168ns。全局负setup由72降到16，recovery仍112，WNS/TNS=-2.723/-186.120ns。但新出现parser/O_packet_error D=-0.332ns，故`timing_decision_v1`明确保留改进继续修，未晋级正式位流，E仍为所选门级比较基线。不能以总违例减少为由忽略新增端点。

新增队列必须按真实映射核对：generate层级为`registered_output$queue`。pixels保留197×2+4=398位，canvases为64×2+4=132位；aborts只有原本实际使用的sequence[63:32]保留，两个32位bank加4标志共68位，token[31:0]在原ingress就不参与abort匹配。必须要求每bank精确存活位集合，不能放宽为“至少一些寄存器”。四个RGBX填充字节的D又被TD折到同一s_data[24]，其余位保持直接对应；失败的旧假设与修正前源码保留在`output_audit_alias_repair_v1`/`output_audit_development_v1`。

FIFO empty表达式可能被折入rdusedw位，也可能直接折入读地址与同步后的写地址；只把命名empty_flag当边界会使审计漏掉真实组合锥。`output_queues_v4`以本实例同宽指针的精确FIFO代数绑定这些别名，对两指针和release/full/wr的全部组合证明实际bank CE只等于本地容量、非空、写槽及释放条件。像素每个使能覆盖8388608组合，画布/中止每个2048组合。位并行真值另由`output_enable_truth_review_v1`用gray(read_ptr)与同步写Gray相等的独立公式逐摘要复核，不复用Gray译码/减法借位公式。该逻辑证据不代替CDC采样、recovery/removal或MTBF。

普通完整工程`projects/hci09_ingress_output_20261015`已从普通生产前版独立生成279输入，与上述启用诊断副本的业务RTL/ADC/SDC同字节，保留原普通top。其`.al`和`build_direct.tcl`可作为工程入口；前版没有可选`build.tcl`，初次复制因此中止后已在原隔离目录核对恢复，未启动第二份布局布线。普通top自己的native/bit/板测仍待，诊断top不能签代；Flash37没有修改。

### parser字计数与后续CDC/复位检查

对已完成E/Z数据库的精确端点复查，O_packet_error D由+0.267变为-0.332ns，两个版本parser源码相同。新路径从bytes_read[0]经加法/比较及CRC判断进入错误脉冲；整个字节计数器只清零或加4，低两位从复位后恒为0。独立`hci09_parser_word_20261015`保持原始非UTF8注释字节，仅改为15位words_read和`bytes_read={words_read,2'b00}`，不改CRC公式、输出延迟或接口。实际新旧RTL四组（四VC、两种drain模式、GAP8/64）各238528周期/203位输出及内部计数/状态/CRC一致，包含全部32768种编码计数状态注入、模回绕、最大65535包长、CRC/ECC/WC/timeout、reset/disable/count变化及X/Z数据。另保留真实vendor DSI CRC、RAW10逐像素/边界、8191缓存/809溢出拒收及复位恢复oracle，不只依赖新旧同错比较。

本版连续六时钟整链6检查/19968字节/两次DDR故障恢复通过，仍保留三处合成owner描述符边界。启用诊断副本自己的综合1655.485秒、279项输入保持、原13审计及7项新端点/缓存复核完成。parser D从-0.332到+0.711ns，无新增负端点；当前setup15、recovery112，WNS/TNS=-2.723/-185.812ns。此副本作为后续门级比较基线，不能将该选择写成完整STA/普通top/bit/实物通过。

`recovery_classification_v4`在真实Z网表逐项区分112条恢复检查、108个物理脚：复位释放链54条、FIFO两级复位标志16条、数据CDC链的异步复位6条、PHY功能RAM地址复位28条、IDDR复位8条检查。最后8条实际对应4个IDDR的上下沿；因此PHY部分合计36条检查、32脚，不能把计数当成36个不同寄存器，也不能把功能PHY复位混入同步器例外。旧通用解析器的字符串包含检查会把source_reset与source_reset_n或同总线其他位误认作首级扇出；修正版按完整网名、位/范围和别名根逐项检查，保留原失败记录。

对仍负的五个sticky丢帧标志入口，`loss_cdc_bounds_v3`只在已完成的旧Z私有DB试验：4个源为observer/report_loss_sticky，一个为ingress/video_loss，源都注册且只在复位清零或置1。三个接收链复位值1、两个复位值0；全部async_reg、同目标时钟，首/次级Q只接下一级D，复杂拼接端口也按精确网名/位检查。geometry和live两个monitor都实际运行于25MHz，不能按名称猜video时钟。预算取实际较短周期80%向下取整：3条7.180ns、2条6.000ns，仅源寄存器到第一级D；不改后两级、复位、PHY或整时钟域。

本机TD附带`doc/SWUG/SWUG200_Timing_Constraints_User_Guide.pdf`，2026.01版4.3.3（PDF57/印刷52页）给出了异步寄存器之间的`set_max_delay -datapath_only`用法；这里80%是本工程设计余量，非手册指定数值。私有试验的原33组1950有效路径逐组保持，增加5组5路径至38组1955；完整负检查128→123，恰好只移除指定5条setup，其余起点/终点/类型/预算/余量多重集合完全不变，112条recovery全保留。80个实际网表守护正反例检查了属性、时钟、复位值、链路、首级额外扇出、复杂端口/相似前缀/同总线末级等边界。该试验尚未并入最新word候选，不能把私有Z的11条setup与最新候选15条混为一个已验组合结果，后续需完整SDC/守护集成和自己的native。

TD本轮曾在增量set_max_delay后立即report_timing_path时崩溃；保留v2日志/小转储及原DB。v3在私有目录复制完整用户SDC并追加精确规则，`clear_sdc -user`、`read_sdc`后先update_timing，再查询/导出，实际完成。不要为单个私有查询失败重启原综合或改写正在执行的冻结工程；所有生产SDC及Flash37均未改变。


## 2026-10-16：精确CDC入口守护与seen位译码

5个sticky loss第一级入口预算正式并入完整副本，守护同时检查完整
`set_max_delay -datapath_only`命令、精确source/target、预算、路径数及
ignored/shadowed/重复项；15组183条monitor/DSP/loss入口守护的150反例拒绝。
其余FIFO/held组继续独立守护，总38组1955条路径，不包含reset或后级FF例外。
SDC改完之后再audit生成build_direct_config索引，再冻结所有输入；首次在
initialize被旧索引拦住的记录保留，不能把未开始综合的退出算时序失败或通过。

3个store_diag位已在旧W私有DB验证：3FF、同目的时钟/复位、前两Q私有、
各位来自UI域active/pending_valid/fault，只作采样遥测，不声称三位同时一致。
6ns预算仅改变对应3条负setup，其余负检查逐条不变。完整8入口版本仍需自己的native。

帧发布seen动态索引候选改为连续固定相等译码、按选中位写入，并用掩码归约判断重复。
不能用`always @*`未触发的初始mask，或把整向量OR当作X/Z状态完全等价：
保留旧失败，修订后实际旧新RTL3组各136389周期、全部207输出位及内部状态一致，
包括16384个四态注入情形。该证明仅支持等价；是否改善guard的负setup必须由
完整新工程的实际端点及全局报告决定，不能用逻辑改写直接宣称时序通过。

新的原生reset图把负recovery集合所涉18条constant-one释放链重新核对，
其中UI的8链及HS的7链分别共享clock/assertion根；这是重新汇合复核的范围，
不直接认定存在错误，也未添加例外。该清单不包括所有正时序释放链或held/FIFO复位链，
完整复位复核应继续扩图，不能把这两组选中结果当作全设计已经穷尽。


## 2026-10-16：完整复位集合与已知选择的源序号

不能只从负recovery列表推断全设计复位链。B原生DB枚举105条常量驱动多级异步链，
其中102条带齐ASYNC_REG；缓冲及一输入反相LUT规范化后，9组内有144对释放链到达共同状态单元。
这不等于功能错误，也不是复位例外授权；多输入布尔等价、opaque sink及跨级状态协议须另查。
三个未标记候选中，DSI同步FIFO实际复位为I_rst | I_vsync，而不是单一pixel_release。
自己的B库组合输入锥到达两个同像素时钟寄存叶，两个SR recovery最小+18.135ns；
DDR两组厂家keep四级链只有级间setup报告，8个SR未报，不能把缺报告当作恢复/MTBF通过。

数字核心复核采用独立理想UI133.333MHz（0.229ns相位）和aux100MHz，另保持25/27/75/50及HS时钟。
初始无错拍基线与57条显式非generate首级链的1..3本地沿保持计划通过；三次backend释放共171次保持，
各6检查/19968 DSI字节，保留原三处owner描述替代和原合格流量到达间隔。
这不覆盖任意更早的相机流量、所有错拍组合、模拟亚稳态、SDF、PHY或真实开窗。

guard负路径仍从terminal输出槽读指针出发。上游t_match为已知1时，t_sequence必为已知并等于当前sequence_；
仅t_match已知0且c_match已知1时，canvas序号也已知相等。因此可在这两种严格已知选择下用当前序号，
其余X/Z选择保留旧mux。禁止直接无条件替换，或只用tm已知1或cm已知1：当tm未知但cm已知1时旧mux可能仍含X。
实际旧/新ingress两个模块67位事件端口1148576组四态对照通过；74240个逐位超集情形独立推导覆盖任意向量宽度。
它证明组合表示等价，不证明native时序改善；完整新工程必须保留全部41组1958条约束并重查全局端点。


## 2026-10-16：终止报告的输出寄存候选

`hci09_terminal_output_stage_20261016`及enabled副本各完整279输入，继承row_counter E，
只改`hci09_terminal_check.v`：保留原65位ring，再接同65位两槽`hci09_ready_cut`。
先保留本地容量ready边界，再寄存ring读MUX输出；不可直接回退为旧ready_cut替代ring，
旧方案曾把下游匹配/ready反馈送到65位head使能，必须查本版真实D/CE及全局路径。
报告总容量6→8，最短输出多1 UI周期；这是有序事务/背压/复位契约，不是逐周期等价。

旧/新各5000条Python独立good/id oracle通过。新输出4991、复位清空9条；旧输出4993、清空7条，
不是无复位情况下的数据丢失。另填满6/8容量、异步清空、唯一新epoch及额外1周期均实测。
本版自己的三组实际FIFO/写DDR/最终B/故障/恢复/溢出夹具与两个发布边界夹具通过；
错误源token、好/坏重复报告丢弃坏帧；guard直接自检覆盖四类seen齐全后的第一个可finalize周期
仍有重复/错token事件时不commit。不是“已经commit之后来的所有重复”都可追溯撤销。
自己的64×8完整数字核心恢复6检查/19968 DSI字节、两次DDR失效和UART配置保留通过，
仍为六时钟、三处owner描述符替代；不沿用C的七时钟/57链错拍结果。

新增132位输出存储的复位/单域图、原ring RD到guard是否被真实寄存边界截断、
head D/CE和全局STA均待自己native。F队列使用当前E作业的真实HANDLE/创建时间等待其终态，
前版失败则停查；不重启前版/P3，不并行启动第二份F native，不把仿真通过写成时序/实板通过。

## 2026-10-16：四条MIPI入口不能借普通私有同步链规则豁免

选中C自己的native图中，四lane均为75MHz `S_lp_state[4]`直接到111.408MHz
`S_iddr_hs_valid_1d` D，当前-0.893ns setup的预算仅0.097ns。
每个首采样Q直接进入一个valid LUT和四个delay counter输入LUT；没有私有下一级D，
也没有ASYNC_REG，且本级无复位、常开采样。名字含`1d`不能证明两级同步结构。
当前加密接收器SHA与工作区配套附件压缩包成员相同；公开wrapper只转发DEVICE。
需确切LP到HS资格/时钟契约或受支持的源级同步选项，再做独立完整候选、native和实测CSI字节/颜色。
不添加广泛clock-group/reset例外，不从该结构观察归因用户所见绿点。
证据在选中C的`vendor_valid_cdc_review_v1`，F数字证据在`functional_scope_v1`。

## 2026-10-16：全局否决与三种释放错拍

源序号表示改写在实际端口/四态推导中等价，但完整D门级从C的7条setup变9条，新增
`preprocess/m_abort_reg.d` -0.056ns及`preprocess/algorithm_/u_post/m_data_reg[15].d` -0.051ns；
guard三条仍约-0.091ns，全局TNS -181.092ns。因此不采用。后续专用审计还因保留了旧ingress整文件SHA相等预设而停止；
这是预期改源后的checker契约问题，与真实全局回归分开报告。已足以否决时，不为追绿重复综合或放宽checker。
下一步先看真实ready/identity锥，若增加事件队列须明确接受、优先级、重复/错误tag、背压及复位协议，再做完整验证。

复位错拍profiles0/1/2使用同一冻结C核心二进制，使57个选中首级分别经历1/2/3本地沿保持。
三个模式各三次backend释放，合计513次保持；加无错拍基线，四次独立运行24检查/79872 DSI字节。
仍非全部联合错拍组合、任意早到源流量、模拟亚稳态/MTBF/SDF/PHY或实际owner/窗口验收；不增加复位例外。


## 保留terminal ring后增加输出寄存与实际PHY资格边界（v116）

完整启用工程 `projects/hci09_enabled_terminal_output_stage_20261016` 的
`evidence/working_selection_v1/result.json` 是当前门级工作选择；普通对应为
`projects/hci09_terminal_output_stage_20261016`。原ring保留本地ready切断，
后接 `hci09_ready_cut #(.WIDTH(65))`，good/sequence/token整组交接。
它使报告容量6→8、最短增加1UI周期，不能称逐周期等价；满队列reset
多清掉的两条是额外存储容量，不应计为活流丢报告。不能退回直接替换ring的
旧head/tail方案，旧方案曾引入像素RAM ready反馈和大量terminal setup违例。

自己的综合和13+8审查后，全局setup7→4、recovery112不变，无新负端点；
三guard D均+0.667ns。新增count2/head65/tail65共132位必须核真实CLK/CE/SR，
head/tail无本地SR但受复位后的count遮蔽；count用自己的UI三段释放。
精确264个D/CE/SR端点全覆盖，最小D/CE/recovery余量1.047/1.822/6.002ns。
选择仅针对门级工作基线，普通top native、新bit、真实窗口与物理验收仍需另做。
七时钟和57链错拍必须读F自己的 `evidence/reset_skew_v1` 及独立review，
不能把C的成功重标成F；三处sensor-owner描述符替代仍是明确的测试边界。

四MIPI入口不是私有两级同步链。C的 `evidence/vendor_contract_review_v6`
通过实际native抽取和安装目录未改动的公开LUT6/SEQ_GSR模型，核256个二值组合、
212992个四态输出位、4096个独立扇出分配与显式停钟。F的
`evidence/vendor_qualifier_binding_v1` 另核48个实际原语/参数/规范连接完全相同，
重查sample/counter闭合岛；它绑定同一数字合同，不把C仿真称作新的F实测。
令s为首级采样、q为已资格输出、c为四位counter，实际组合关系为：

```
c_next = s ? ((q && c>=14) ? c : ((c+1)&15)) : 0
q_next = s && (q || c==15)
```

`O_iddr_hs_valid_n` 是正极性注册valid的下一态D，名字后缀n不是低有效。
已知一致低采样才能在一拍清counter/valid；从LP源算需要两个运行的HS沿。
清除后从源高到注册资格需17个HS沿。HS停钟时整个LP低间隔可能完全未被观察，
仅看valid低也不能证明counter清零。F top的PHY reset仅为主PLL lock反相，
runtime standby/camera_reset并不自动复位该PHY。实际LP低/HS沿重叠、启停/SOT/
deskew和传感器资格还需核；这些数字结论不是MTBF/PHY通过或绿点根因，
不能据此新增宽泛false-path、异步clock-group或两级同步豁免。

安装SDK的公共module后可能还有无关的protected尾部。Icarus若在尾部报错，
可保留原copyright并逐字截取所需的公开module，以原始body SHA绑定；不要
解密protected内容、替换厂商逻辑，或将编译前失败计为模型通过。
