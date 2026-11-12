# 无接触交互的FPGA实现范围

用户方案在仓库 `tasks/plan_v3_无接触人机交互系统.docx`。完整305段已读取；严格赛题证据与实际任务拆分在 `docs/11_赛题三严格核查与FPGA任务拆分_20261010.md`。T3全部1214份导出源/JSON与历史压缩bit已逐SHA核对，但稳态溢出、压缩链路正例、原匹配native报告和raw仍缺，因此不能称旧六项全部签核。

## 实现取舍

FPGA在每个真实源帧做亮度/高斯/直方图LUT、帧原子ROI、低分位阈值/形态学、面积/矩/bbox/SAD/有界CCL、delta/LZ77/store与CRC、统一帧/事件/光电戳、按钮去抖与定时输出。RK负责ROI定位/跟踪、模型输入归一化、注视与手模型、PnP/屏幕标定、相对快测量与绝对慢结果融合、预测/语义吸附、交互仲裁/UI/语音/HID。阈值质心是有质量标志的相对测量，未验证时不得直接称为注视点。

四类完整例程均已生成：HCI01基础预处理/Sobel/阈值，HCI02眼区/脸ROI与快速测量，HCI03 ROI无损压缩/MIPI4lane/RK严格解码，HCI04命令/按钮/帧配置/统一计时/PWM互锁。HCI01 LUTguard与HCI02 readycut旧候选各有自己的数字/native/实际CSI九色及模式/精确37恢复/完整封包；新发现的真实ISP红蓝字节接口修订另建四份完整颜色候选，不能沿用旧包给新灰度/ROI接口签核。HCI03已接生产顶层并保留DDR/DSI；当前最大高熵三帧联合数字证明通过，自己的资源/STA/物理RK和模型仍须完成。HCI04当前颜色版有四份数字证明和自己的完整正STA/bit，实板/光学/外接探头与舵机分别验收。逐项动态状态以 `projects/pcie_imx415_bar_contract37_20261010/deliverables/hci_examples_current_index_v1/index.json` 为准；下列各阶段记录保留当时失败和证据范围，不把旧“待完成”状态当当前结论。每例保留完整原依赖、.al/ADC/SDC/ROM、生产顶层和独立验证入口。

选基线：当前37用于可靠CSI/ISP/PCIe采集对照；当前06 frameguard用于CSI/ISP/DDR/DSI连续帧基线；T3仅作为三种预处理和MIPI/codec源参考，不能继承其旧负时序/未签核源。MIPI新工程必须使用正确PAD本地/全局相位、真实复位和完整重新布线。源frameID/timestamp/configVersion/ROI原点必须随所有像素数据和每个压缩行保留。

## 必须由工程证明的边界

- 上一帧LUT、启动identity、边界复制/最后一行排空及合法停顿都要逐值验证；连续帧不能等前帧全部处理完才测试下一SOF。
- ROI反馈CRC/序号/尺寸/越界校验后在帧界一次提交；陈旧配置和无可信ROI输出invalid。Bayer相位按实际crop原点重新定义，不盲抄37设置。
- CCL标签/游程数与buffer有固定上限；超出容量明确报告invalid/overflow并保留ROI给RK。不伪造“总能定位虹膜”的能力。
- 默认量化0保证相对送入codec数据可逆；上游滤波/灰度并不因此变成无损sensor链。若启用有损，量化参数与模型训练/输入一致，另测识别效果。
- 压缩载荷比、在线容器字节和原RAW/RGB/GRAY分母分别报告。RGB人脸ROI比灰度预算大三倍；不为了省带宽悄悄改变模型输入。
- 25MHz微秒时基要与所有源事件明确握手/同步；保留输入同步和探头响应误差。SOF→显示光子不是动作真实发生→光子，后者需要共同可观测触发或双端测量。
- 板载普通KEY在RK连接，不能虚构FPGA球号。已有UART U11/V11可回传控制；光电/舵机/外接按键须查核心板连接器和底板原理图，默认输出关闭及超时安全态。
- 实测06接受SOF约55.56fps，37约60fps。ROI/内部时钟不提高sensor物理帧率；4K/动态sensor裁切另验。Sony官方支持窗口模式不等于本模组寄存器事务已通过。
- 资源用当前实际TD口径：本器件LUT6总64320、ERAM20K272、DSP240，不沿用方案115k LUT；眼窗缓冲与行级codec优先，脸RGB全帧双缓冲不塞进BRAM。

方案的模型耗时、≤50ms光电延迟、多用户和眼跳预判均是待测目标。ISO/Fitts测试沿用的协议和当前标准范围在拆分文档中明确，不能由13目标环程序推断ISO符合性。最终skill中只把真正完成的新完整工程及证据列入“可复用已验收”入口。

## 本轮真实工程格式经验

HCI02 native v1 在 open_project 阶段实际报 `PRJ-8641 XML tag File is invalid`：新增12项被写在 Source_Files 直属层。TD要求它们放入相应 Verilog/System_Verilog 等源类型组。泛用XML能解析不等于TD能打开；原audit使用 Source_Files/*/File，会漏掉直属File。当前helper已拒绝错误层级，实际失败 .al/log、修复前脚本和新注册留在 HCI02 evidence/native_registration_repair_v1；只移动注册项，没有改RTL。修复后的 native v2独立构建，不继承v1通过。不要整体XML重写丢掉TD的UsedInP&R和自定义标签。

真实CSI/ISP/并行ROI/时间/DBUF联合 `hci02_frontend_isp_dbuf_joint_v3`通过两帧96words/12user FDMA突发；启动旧半帧不泄漏。64×3的人工极短帧距触发右眼第二窗busy skip1，左眼2报告/右眼1报告逐23word和RAW accepted时间准确，两个整窗及CRC仍完成。早期v1/v2错误要求此人工节奏无skip而失败，原log保留；这是文档承诺的忙窗策略，不声称一般畸形流恢复。正常全HD/120Hz测试另有六报告/skip0的独立精确证据。不能为消除计数而丢整个ROI，也不能把任意测试输入帧距都叫实际sensor帧率。

## 本轮真实存储映射经验

HCI02原并行工程native v2在place阶段MSlice48368超过器件26880而终止，未产生通过位流。独立`projects/hci02_ram_20261011`把小FIFO改为每bank同步读并加BRAM属性，完整功能比对通过，但自身native v1仍有8项SYN-5105拒绝大缓存BRAM推断，MSlice40720再次超限。属性、RTL语法或数字通过都不能证明实际资源映射。两次日志、gate.qor、输入清单和失败结果均保留，不改小窗口或删算法来代替原目标。

独立`projects/hci02_eram_20261011`用官方PH1_LOGIC_ERAM显式绑定每眼双灰度缓存、两个形态学缓存和四bank像素FIFO，保持原读使能暂停时的数据不被槽位重写污染。供应商公开模型的FORMAL_VERIFICATION功能分支已实际验证32768×8、256×243以及CE保持；该宏名不表示做了形式证明。正常加密物理启动、SDF和实板仍独立验收。SDK原文件不修改；仿真helper从本机SDK提取精确公开module前缀到仓库外缓存，记录原文件/前缀SHA，不打包供应商模型或license。

此显式ERAM候选自身buffers v3、features/bounds v5、vision v8、fullHD v5和真实CSI联合v5均已通过；全HD保持6220800RGB像素、最大双眼/脸、六份逐值报告、名义120Hz且等待/忙跳过0。其实际native结果与后续修订见下段，不得用候选源变更推断映射、时序或上板通过。一次旧fullHD v3由300秒主机运行预算实际杀死，保留失败和raw；v4以新600秒预算完成，不把主机预算事件称为RTL断言失败，也不因观察超时重启仍在运行的进程。最终动态选择看追加HCI索引中的自身native和实板证据。

后续显式ERAM自身native v1已完成route：221/272 ERAM、47908/64320 LUT6、95/240 DSP，资源问题解决；setup −2.485ns、STNS −17.515ns、11个端点仍失败，hold +0.020ns。该bit仅诊断，不上板。自身pr.timing的10条最差路径均来自total_pixels，进入target/cdf的常数除100逻辑；独立`projects/hci02_divider_20261011`改为32拍逐bit精确除法，保留32bit分子、deadline、所有算法/窗口/时钟/并行度。自身眼区features/bounds v6及vision v9已通过，所有0..32768像素数量、百分比1/8/50共98307次精确取整及32个除法复位阶段通过。其fullHD/真实CSI/native/实板仍独立签核，不降时钟或删约束。Windows subprocess使用裸工具名时，即使子进程env PATH已有工具目录仍可能查找失败；用已经核实的可执行文件绝对路径，并将未执行RTL的主机异常与RTL结果分开留档。

逐拍除法版fullHD v6与真实CSI联合v6随后均已通过；17项数字验收及69项生产文件SHA绑定在`hci02_divider_digital_binding_v1.json`。六份最大眼窗报告每份175766周期，名义75MHz约2.343547ms，精确只比前版增加32周期；全HD等待/skip0、峰值193保持。当前native/实板仍待自身结果，除法的穷举数学检查不能替代完整流/物理/时序。

HCI04接线预查在`hci04_pin_precheck_v1/result.json`。底板J35:G15/G16分别到H16/H15，J35:H31/H32到J13/K13，母板/核心板原PDF42/29/5页及旧正native IO报告可核对；它们只是候选线路，当前插入的VID005子卡占用尚未查到匹配原理图，未写入ADC或实际驱动。BANK13接FPGA_ADJ，原图默认1.8V但未作仪器测压。没有被当前RTL用到不等于整块子卡线路空闲；普通KEY仍走RK，T13时钟不改。外设缺失不阻塞数字按钮/计时/互锁实现，实际光电/PWM接线与动作到光子测量另验。

## HCI03当前可变行codec单元

`projects/hci03_roi_codec_20261011`独立复制当前170项完整源/IP/ROM/ADC/SDC/.al，并正确注册`hci03_lz1_lane.v`；顶层仍是父HCI02数据路径，生产压缩尚未接入，不能称为合格HCI03。新单元以物理容量N和实际start_length分离，支持0..N的真实ROI尾部，不用固定行补零替代变宽目标；8bit delta可逆，offset1 LZ77 token长度3..130，FF转义，压缩不省字节则store原delta。实际`hci03_codec_lane_unit_v1`有839组输入，在64/112/480容量执行2085次核心检查，字节/mode/length/bank均匹配独立旧Python规范；包含每个0..112长度、长匹配边界、随机/奇数/短/空行、capture暂停及非法长度/地址/复位flags。非法/忙启动与同bank编码期间capture公开sticky错误。

该单元自身不证明整条行bank所有权、三路吞吐/CRC或物理4lane/NPU。后续已完成的实际数字层见下段，物理签核仍独立。分开报告选中字节的无损、载荷压缩率、容器在线字节及原GRAY/RGB/RAW分母。RK现机模型`/home/linaro/t3_basic6/models/yolov5s_relu.rknn`的实际SHA仍为418ccc10ddd9aea78658fb477a09b12d613e3e359eb5c829b4ddd00b3ef8cfe7，与旧正例模型一致；文件存在不等于新压缩输入已出识别正例。后续4lane/RK捕获/稳态溢出/匹配输入SHA/当前NPU正例/native/physical仍是硬要求。

实际`hci03_row_codec_unit_v3`有176组GRAY/RGB可变行、181次检查，CAP/WAIT_ENC/ENC/READY/SEND/FREE保留两个bank，发送未释放前不可重写，第三行明确计数丢弃并保留源FID。奇数ROI原点会让紧凑输入成为先3像素、后4像素且下一拍local_x=3；必须按实际local_x选择pixel_mod4通道和地址，并在各通道首地址0重置delta。不能把每拍紧凑下标直接当条纹通道。普通分组单元的通过不能替代真实crop。

`hci03_roi_transport_v4`在实际ROIquad后接三路真实行codec及roundrobin包：两帧最大双眼256×128/人脸448×448RGB和一帧短尾，在完整全HD源上输出1423包，源FID/配置/64bit微秒/原点/尺寸/行号、全部模式/长度/载荷/rawCRC/headerCRC逐值与独立Python及zlib一致。输入625000周期/帧、等待0；功能TB100MHz，该周期容量折算名义75MHz为120Hz，不是sensor实测120fps。故意阻塞第四个完整源帧丢126/126/446行，保留各路前两行并最终完整排空6包，held字稳定；8406次逐字节/长度破坏被严格拒绝。协议72字节头和variable实际最大编码长度的2字节条纹见工程HCR3_PROTOCOL.md；补齐是在线包字节，不能隐去开销或把人工场景比率称实景保证。

新`hci03_packet_async_bridge`的独立v3单位证明使用官方PH1_LOGIC_ERAM公开功能ASYNC模式，在203包/2476个64bit字、三个真实独立时钟比精确校验32bit输出/边界/长度。逐字数据读指针和逐包描述符指针各自一次加1过Gray同步，完整提交前无数据可见；禁止把跳过整行长度的Gray提交指针当作只变一位。接收暂停用ready保留已接受的字，整行过载由上游bank策略报告；实际wordFull2173时钟、descriptorFull5398时钟、sourceWait5706、destStall951、峰值64槽，部分包和已排队包复位后没有旧RAM泄漏。早期测试先装小包，描述符满时占用不到32，错误的峰值断言失败；另一版把源提交计数放在发送task尾部，快接收端可能在测试记录前读到合法包。最终在实际source last握手边沿记提交，保留原失败，不修改RTL绕过测试。功能分支不代表正常加密模型/SDF/MTBF或物理PHY通过。

上述v2为较早五项数字阶段。最新`hci03_transport_progress_v4/result.json`已有十份当前源SHA绑定：完整生产顶层和crop/feature/CDC/CSI已接通并通过并发全HD与真实前端联合。实际PHY/pad/RK采集/稳态溢出/当前model正例/tensorSHA/自身native尚未签核，仍不能选为完整已验收例程。

RK侧`hcr3_frames.py`只发布已集齐全部ROI行且源ID/配置/时间/原点/尺寸/通道/使能一致的图像，并给出完整row-major RGB24/GRAY8字节SHA。实际`hci03_roi_frames_unit_v1`将1423个RTL行包重组为9个完整图像，逐字节对独立源像素公式通过；删第一帧face某一行只阻止该图像，另8个通过，重复/已完成旧FID/混用time/config/origin/disabled六种情况拒绝，每路最多2个未完整源帧，超额记录丢弃源FID。不要将最后一行的lane长度/CRC/包序号保留成整图属性，不能把图像SHA当归一化模型tensorSHA，也不能将人工RTL输入的精确重组当当前模型识别正例。

## HCI02剩余ready路径的实际修订

逐拍除法候选自身完整native最终仍失败：setup−0.006ns/STNS−0.006ns、仅1端点，hold+0.020ns。完整170输入冻结/165阶段文件无漂移；位流仅诊断、未上板。真实17层最差路径始于DBUF读指针Gray同步，经过used-count carry/ready，再经后级行RAM/卷积到bank_select。不能将很小的负裕量计通过。

独立完整`projects/hci02_readycut_20261011`保留全部算法/最大窗/时钟/约束，只在视频与DBUF之间加入两个145bit已接受拍的缓冲，保存128bit RGBX、SOF/last/EOF和14bit配置。上游ready只来自寄存占用，打断反馈组合路径；稳定连续每拍一组，满到有空间时保守一拍反压。实际buffer v2通过6000随机停顿+1555200连续全HD组/暂停稳定/两拍在缓存中复位/ready不受下游同周期变化；实际75MHz单时钟。新fullHD v7在实际75MHz仿真时钟下通过三帧6220800RGB、六眼报告逐23word/CRC/输入等待0、skip0。真实CSI/ISP/时间/ROI/异步DBUF联合v8仍保留96words/12突发与启动旧半帧拒绝；人工64×3 cadence右眼busy skip1策略保持。18个实际数字门禁、72项当前生产文件SHA绑定在`hci02_readycut_digital_binding_v1.json`。自身171输入native已启动，最终STA、实板/恢复/封包仍待自身结果，不继承父位流。两个早期新测试有明确编译失败：测试函数concat中的未定宽算式，以及工具对先用后声明的新wire解析失败；原log/输入保留，修复测试宽度与声明顺序后另建新证据。不要将测试编译错误当RTL执行结果。


## HCI03整行容器与逐测量报告的实际经验

独立包桥v4加入共同异步复位断言、每域两拍同步释放，重新执行203包/2476字/三时钟比的完整提交、word/descriptor满和旧RAM拒绝。只在module端口加同步器且验证新的生产字节；不能继承旧reset版本SHA。

压缩器的变长包不能在CSI长包内部暂停等待。`hci03_csi_carrier`用供应商同步ERAM预填完整1440字节载体行，再用两字队列和pending读信用连续预取；`hci03_csi2_frame_tx`按真实PHY ready保持valid/data/last和整个状态机，下一个长包头须等下一整行已准备。HCS3含实际字节数/bodyCRC/headerCRC/首包offset、载体行和帧；补齐字节必须0，已开始的128行载体帧会完成，无输入后不持续空帧。跨载体行/帧的HCR/HCE须按源FID重组，载体FPS与源FPS分开。实际重放1423RTL行包得到640行/921600容器字节、857712内容字节和9完整图，4320次字节破坏拒绝；供应商公开功能模式不是加密PHY/SDF/物理证明。

UART五slot每眼2Hz是诊断频率，不能拿来承诺逐帧相对快测量。生产新增真实measure结果脉冲→每眼8个144字节HCE3整包槽→与HCR3包原子公平仲裁。独立ERAM串行写完整24项结果/源FID/配置/微秒和drop/skip/deadline计数，忙/满丢整报告并记源FID，禁止阻塞分析引擎。实际178报告/100行混发逐字节CRC准确，4个整包丢弃、公平性/回绕/复位/held、864次损坏拒绝。HCE3质量标志有效不等于已标定注视。

实际75MHz并发3×1920×1080、625000周期源帧预算，在完整HCI01/两眼测量/3ROI后接codec/公平包/双时钟ERAM/整行容器/ready CSI，6220800 RGB像素、2112行、6真实特征及9整图全部准确，无源等待/行或特征丢弃。内容310824、容器552960字节，含160个完成载体帧空chunk，不能隐去在线开销或将人工场景比率当实景保证。执行495.859秒，初次后处理只漏载独立ECC parity常量；原始run/tb/bytes/失败JSON保留，另做独立复核，无RTL修改或重复健康运行。

真实CSI前端联合保留高字节协议、RAW10/ECC/CRC/GrayFIFO、完整ISP/RAW SOF时间标签/异步DBUF，再接新链路：两帧96个精确RGB128字/12突发、旧半帧拒绝、3个真实眼报告/源戳准确。人工64×3极短行间距使两路各丢1行，实际sent[5,6,5]+dropped[1,0,1]逐路等于6，所发16行GRAY/RGB、元数据和3特征严格解码通过，不能把极短fixture计数丢弃抹去。此小测试只将载体完成参数加速到1行/idle16；默认128行生产载体的无丢失全HD证据独立保留。旧真实前端时钟100MHzUI/71.4286MHzvideo/160MHzHS，不冒称物理sensor120fps。

完整新顶层保留DDR/7寸DSI和所有算法，独立RK16项引脚沿用旧T3连接器，第二个供应商75/150/300MHzPLL仅改模块/生成文件名，不改频率算术/IPC/VHDL配置。真实PHY ready必须接，不复用面板引脚。静态冲突检查只读注册ADC与已选IPC GeneratedFiles里Enable=true的ADC；完整保留树中的未注册DSI参考pin.adc不能混进当前约束，最初误纳入的helper失败保留。静态显式无冲突不能替代native差分伴脚/IO检查。各参考PLL保持关联时序，不扩大异步cut。七slot UART全部52/16项链路/缓冲/错误统计经14真实供应商TX记录/1824字节逐值CRC验证。

RK只读预检：milianke_mipi为builtin，源pad只列1920×1080、TRY也夹紧该尺寸；video22的TRY接受720×128/1440stride/184320字节。ACTIVE未修改；这个不一致必须用实际CSI抓取证明，既不能假设不可用也不能把TRY接受当上板通过。

## HCI02当前native与串口失败边界

D5 readycut自身171冻结输入/166阶段文件native实际完成，SWNS+0.190/STNS0、HWNS+0.020/HTNS0、覆盖99.66，53117 LUT6/221 ERAM/95 DSP。当前bit SHA d61b8216317226ecab3ed8311150bee2f24fb85757692fa59d35a4476a2f3301；不继承父−0.006位流。板上v1通过九色/前三模式后有1个UART CRC坏记录，v2扩大主机SetupComm到请求1MiB、记录所有ClearCommError仍在白色阶段有坏记录；每次均恢复精确37元组并新抓32帧通过。两个缺口均是1020字节，随后CRC有效记录序号跳10，第二次OS错误flags0/最大RX队列1356；这些事实不足以宣称RTL坏、USB根因已证明或队列增大修复。不能内部resync后计通过。

第三轮实际板测和独立复核通过：一个COM4句柄和持续后台接收线程，场景SSH/SFTP/睡眠期间保存全会话原始字节，2592记录/298672字节全部CRC/序号/slot连续，OS错误flags0，应用接收队列峰值11680。每个ROI/模式阶段独立核验，9色/6模式/7HCIC/16HCIR全部通过，名义时基源帧率55.561fps、眼FIFO峰值194；完整结束接收后恢复精确37元组/位流/驱动/boot并新32帧准确。相同bit/源码/时钟/native没有因串口失败修改。两次1020字节失败原始记录保留，成功证明该持续接收条件下无缺口，不能宣称USB根因已完全证明或内部resync修复。D5自身数字/native/CSI记录与复核完成；光学面板外观、MTBF/SDF技术证明仍独立。


## HCI03 长期帧号与当前布局失败的实际经验

每眼首次新 epoch 的报告必须和重启后第一个 SOF 比较，拒绝旧报告；实际单眼引擎/FIFO 保证顺序，首次新报告接受以后用 per-eye epoch_seen 保持后续接受资格。固定首次 FID 的 signed 差持续比较会在超过 2^31 帧后把新报告误当旧报告。修订后专项 epoch 单元拒绝 SOF 前/重启旧报告，并接受 2^31+1 帧龄；当前完整 fullHD v2 和真实前端 v2 又实际通过，11 份当前数字绑定见 hci03_current_joint_progress_v1。

改 RTL 后须重新生成当前 SHA 的 native 配置。HCI03 native v1 在初始化就正确拒绝旧配置；不能把它说成综合失败。刷新配置后独立 v2 的 185 输入/180 staged 无漂移，真实布局阶段 PHY-7027 指出 SLICEL 超限、PHY-9002 退出，无 route/bit。gate.area 的 slice* 85778/64320=133.36%，gate.qor 的 #slices29883/46.46% 与此不是同一统计，不能挑较小百分数当可实现。预布局 WNS−20250ps 和234 ERAM/99 DSP 保留；额外 GCLK 警告也保留，不把最终失败只归因于等待或包路径。新候选必须完整重编译和上板。

完整 hci03_quarter_memory_20261011 保留 DDR/DSI/第二 PHY/全部算法/最大 ROI，新增显式供应商 DRAM：CHECK 的前一/current/后两字节分属四个 quarter bank，EXTEND 单字节复用 primary 读；独立 next 读用另一复制端口，encoded even/odd 各一个写端口。原 row bank 所有权与无时钟读接口保持。实际新 codec v2 在839向量/64、112、480容量逐mode/长度/编码字节与独立旧 Python 规范一致；new row v4 的176组GRAY/RGB、SEND+READY保护、忙/满、CRC/元数据和复位通过。完整吞吐/真实前端/native/资源下降仍须看新候选自身结果，不能以结构推算当实现通过。

## HCI04 完整数字控制与计时例程

完整 hci04_controls_timing_20261011 保留 HCI01 相机/ISP/预处理/DDR/DSI/IP/ROM/约束。顶层只使用已知 U11/V11，PIN_CONFIG_VERIFIED=0 在构建结构上关闭按钮/探头/PWM。CRC正确 ARM 的命令层接受与应用层拒绝分开计数；UART不能解除引脚核实。实际接线版本须在独立完整工程核对 VID005 占用、Bank 电平、设备规格、ADC/SDC 后重新验收。

同一25MHz时基分频25为1µs，先寄存 Gray 再同步到75MHz视频和50MHz显示，禁止从二进制计数器组合编码后直接跨域。三路采 acceptedRAW SOF/acceptedDDR writeSOF/panelfirstDE，默认抽样1/4并报告所有流计数。各域邮箱保持完整232bit，通过2FFtoggle返回；停目标时钟保留首事件、明确丢后两件，共同停钟异步复位清掉旧数据的实际单位通过。面板帧计数是独立显示计数，没有源图像ID映射；首DE不是光子到达探头。

事件队列每源一个待发槽可保留同时边沿，随后轮转写32个完整64字节ERAM包；无法接收的新事件整件计drop/type，不撕裂旧时间戳/ID。实际8同时输入、容量32、忙/满17次丢弃、保持/复位共47包按独立zlib和原始字段核对。HCC4 32字节命令 CRC、版本、保留、seq半范围和20ms超时先检查；256单比特命令破坏、回绕、重放、旧DISARM不倒退seq和部分命令复位通过。ARM/UPDATE/re-ARM只在PWM周期边界提交，TTL/停止/复位立即关闭；命令不能复活已到期的心跳。默认1–2ms脉宽、最少100µs低电平，UART例程不宣称未接舵机通过。

实际三时钟联合使用真实供应商115200 RX/TX；同一RX上的HCIC/HCC4交替正确，三个实际流各12帧抽样9事件，加4个明确UART软件MARK，无事件丢弃。发送24条完整记录=13事件+11状态，12288次记录单比特破坏被严格拒绝；不得内部resync忽略CRC/seq缺口。MARK的来源是串口命令到达，不冒称真实动作。按钮记录首个最终合格候选和确认时间，默认5ms过滤；光电过滤0仍有2FF采样延迟/微秒量化，外部校准、共同物理触发、探头响应以及动作→光子独立待验。

HCI04四份当前数字证明绑定见 hci04_current_digital_progress_v1；自身完整TD已发起，native/板测/探头/舵机不能继承父工程。输入过滤与PWM的v1/v2失败是测试首tick释放假设和缩短参数违反生产100µs低电平的实际断言；另建v4通过，生产默认100µs保留。命令/队列v1仿真已输出PASS，但JSON后处理WindowsPath不可序列化；原日志保留，修复后独立v2通过，不改旧证据为PASS。

## 真实 ISP RGB 接口与当前完整候选

以实际 `ui_Saturation_adj`、`ui_data96_128` 的赋值追踪为准：ISP 的每个32bit像素是 `{alpha,R,G,B}`，R在23:16、G在15:8、B在7:0。HCI灰度/ROI/行压缩的 canonical RGBX 是 `{alpha,B,G,R}`，R在7:0；旧灰度模块注释称“real ISP R at bit0”与实际赋值矛盾。直接把ISP接算法会把红色灰度算29、蓝色算77。此前真实九色RGB旁路保留ISP原字节、灰度fixture红蓝相等，不能覆盖这个错误；合成canonical输入的算法测试仍只证明其明确输入约定。

四份独立完整 `hci01/02/03/04_rgb_contract_20261011` 在整个预处理/ROI fork之前例化无时延 `hci_rgbx_swap`，仅全幅视频输出再交换回DDR/DSI格式。保持alpha、像素次序、全部握手和算法，ROI送RK时按真实R,G,B字节发送。旧已封包父工程不覆盖；新工程必须自己的native/STA/bit与物理验收。声明须先于新增例化，避免供应商公开模型环境下工具拒绝先用后声明的wire。

实际 `hci_real_rgb_contract_v4` 汇总两份已终止PASS的真实仿真：6帧384个命名颜色像素/3个奇数原点ROI，全字段/灰度/alpha/RGB旁路、140次输出停顿保持通过；红绿蓝灰度分别77/149/29。真实CSI RAW10→完整ISP→正常化/灰度→异步DBUF，在75MHz视频测试时钟下两帧96字/12实际FDMA突发逐字正确，99个ISP像素R/B不等、96个会检出旧错误权重，2230次背压，无丢字/重复/CSI错误且启动旧半帧拒绝。前两次只是测试新增wire声明顺序导致编译失败；第三次两个仿真通过后，host按同名文件假定HCI03额外crop/feature端口的vision模块也同SHA而失败。保留原失败，独立后处理只绑定实际相同文件（52/58/57/52项），不同vision明确排除，不重复健康仿真或改RTL绕过断言。

四分区DRAM候选真实长测试已终止通过：三ROI transport v6执行1201.203秒，1423包/857712线上字节，源等待0；刻意整帧堵塞明确丢126/126/446行并保留各路首2行。fullHD link v4执行1251.390秒，三帧6220800RGB像素/2112行/6特征/9整图逐字节与独立规范一致，源等待和行/报告丢弃0，容器552960/内容310824含160空chunk。当前11份数字证明不等于任意难压缩实景的稳态120FPS。旧600/700秒host超时后，独立诊断实测推进200000周期/2ms并继续产生行，按3600秒预算另建完整测试；不能因为stdio文件暂时0字节就重启健康测试或改数据规模。

HCI04父工程自己的167冻结输入/162 staged最终完整native通过：setup +0.249ns、hold +0.020ns、TNS0、覆盖99.55%，bit SHA `81b66414498adba00b271d19458cac9f4f3dcc71b442aef1a9a8920f34c2c7ba`。这是加RGB转换之前的构建，不能继承为颜色新候选通过。当前新HCI03冻结187输入构建中；HCI04/02/01按168/172/157输入冻结并串行排队。完整颜色版fullHD与实际RK抓取/模型正例仍须收取自己的结果。

颜色版HCI04物理入口先要求自己的正STA/bit/源码SHA，再用持续单句柄UART验证九色/六模式、14个HCC命令/5MARK/CRC/序号/时间/默认外设关闭；新增稳定HDMI红绿蓝各RGB前→灰度→RGB后全帧统计，按77R+150G+29B均值与原错误交换均值独立比对，要求前后漂移有界且红蓝信号足够分辨错误。它是实际相机粗颜色权重证明，不代替逐像素数字规范、光学面板观察、探头/舵机/动作到光子验收。当前仅脚本准备和编译检查通过，尚未执行，finally仍恢复精确37和新32帧。动态结果见 `hci_colour_current_progress_v1/result.json` 及统一索引，不把排队和规划写成验收。

## 最大难压缩面部突发与双行载体

颜色版完整fullHD联合v1已实际通过：1039.031秒、6220800 RGB、2112行/6特征/9图、无源等待或丢行，容器与HS迹SHA和四分区父版本一致。独立最大448×448 RGB面部高熵源（保持合法眼区像素和同样75MHz/120Hz人工源节拍）却在2.056509ms出现真实face丢1行：received23/sent20/其余2行仍占有bank。`hci03_incompressible_link_unit_v2` 实际编译0、执行1、90.156秒，原log保留；不能把容易压缩fixture的绿灯扩大成任意图像无丢失。v1的层次诊断字段写错及先用后声明cycles只导致测试编译失败，不是溢出证据。

独立完整 `hci03_dual_carrier_20261011` 保留全部算法、窗口、色序、时钟、PHY行间隔、IP/ROM/DDR/DSI；两份完整512×32供应商ERAM由独立bank所有权管理，下一行填充/CRC与前一行发送并行，整行预填后仍不会在CSI包内等源数据。prepare计数与已送计数分开，描述符按提交次序发；复位只清所有权和元数据、不复位RAM。包桥8KiB改64KiB吸收有限突发，Gray指针仍一次加1，high-water扩为14bit、遥测零扩展保持原32bit字段。资源、STA和任意输入能力必须看自己的实现与实测，不用缓存大小推断通过。

实际carrier replay v3按1423个原RTL行包/857712源字节通过严格CSI ECC/CRC16、HCS/HCR CRC、9图逐字节重组、PHY ready停顿、chunk/frame回绕和quiet drain：640行/921600容器字节、30空chunk，4320损坏字节拒绝，24.375秒。独立reset v1在两个完整bank占有且输出停止时共同复位，不清供应商RAM；随后704个全新源字节/2880容器字节含半行及完成帧空行，CRC/首次offset/元数据准确，1393次输出保持，无旧数据泄漏。frame_rows=2/idle20仅是该复位测试加速，生产128/2000保持。当前完整最大高熵联合v3正在执行，原颜色父native及其它候选串行队列继续原进程；不改正在构建/仿真的父输入。当前阶段见 `hci03_dual_carrier_progress_v1`，尚未native/物理验收。

双行/64KiB版最大高熵v3终止仍face丢1行（3.214967ms、received204/sent201），v4仅增加合法层次计数复核同一次条件：bridgeUsed2864个64bit字、peak2910、wordFull0、descFull1，16描述符先满；数据RAM未满，不能盲目再放大数据RAM或说双行已解决整个稳态要求。原失败记录和实际SHA保留，新的相邻RAM候选将DESC_BITS从4改7为128槽。数据与描述符两个独立容量都需要看实际峰值/完整提交，不用data容量推断descriptor容量。

颜色四分区父的187冻结输入/182staged自身native已真实终止失败：slice*69020/64320=107.31%，寄存器54870、ERAM234、DSP99；仍为SLICEL超限/PHY-9002，无route/bit/finalSTA。映射阶段的54750LUT计数不等于实际可布局slice，不以中间较小数宣称通过。旧85778已降低，但仍未实现。

独立完整 `hci03_paired_memory_20261011` 以真实caller的 `read_addr_next=read_addr+1` 合约替代不需要的复制读RAM：raw四分区分别给当前/next字节所在quarter选择地址，encoded偶/奇分别选各自地址；编码bank的四相邻CHECK/单字节EXTEND和对侧SEND bank读取并行。删除raw/encoded全部secondary副本，无时钟/编解码/数据修改；不再承诺任意互不相关的next地址。实际codec v3仍839向量/容量64/112/480全部精确，row v5仍176组GRAY/RGB的CRC/元数据/两bank所有权/held/flood/drop/reset精确；新carrier两份真实unit按相同SHA绑定。当前128描述符/paired RAM的最大高熵v5执行中，native资源改进与实际RK/模型仍待自身结果。见 `hci03_paired_progress_v1`，没有继承旧完整native或旧carrier生产验收。

## 加长载体、满负载与容量位宽修订

上述paired/128desc高熵v5已真实终止失败：4.207017ms、face received359/sent356/drop1，bridgeUsed/peak8192个64bit字，wordFull1/descFull0。描述符扩容消除了先前16槽瓶颈，继而暴露64KiB数据队列满。不能仅扩大缓存承诺无限稳态。独立 `hci03_wide_carrier_20261011` 保持源/目的75MHz、四lane600Mbps、PLL/PHY与行间隔200/帧间隔4000、全部算法和最大ROI；CSI载体改1920×128、每行3840B以摊薄固定封包保护间隔。两行bank各1024×32 ERAM，桥预取计入同拍pop及待读，减少32bit输出补读空拍。RK解码必须显式 `line_bytes=3840`；旧默认1440仍严格检查，不能猜长度或搜索magic修复中间损坏。

wide真实replay v1以1423包/857712源字节通过CSI ECC/CRC、9图完整字节、元数据、held输出、回绕和排空，983040容器字节/256行/30空chunk；11520次单字节破坏均拒绝。wide reset v1用两个完整952字bank停住后复位，未清RAM，新704源字节/7680容器字节精确、3693次保持；原JSON克隆时遗留1440/2880文字，原文件不改，由 `hci03_wide_host_geometry_v1/wide_reset_scope_correction.json` 绑定实际3840B TB与raw纠正范围。桥v5在三对独立时钟、203包/2476字、data/desc满、回绕、等待及未提交/已排队复位通过。真实CSI→完整ISP→颜色正常化→vision/DDR/ROI/特征→3840B发送的wide联合v1通过两帧96字/12实际FDMA、16行/3特征；极短fixture的1/0/1行丢弃明确计数，与正常全高清无丢失证明分开。RK只读GET/TRY/GET真实接受1920×128 YUYV、stride3840、size491520且ACTIVE仍0；TRY不是STREAMON或物理接收验收。

独立 `hci03_compact_codec_20261011` 保留wide全部功能，仅把codec内部位置/长度/输出地址按N=64/112/480实际容量取位宽；CHECK以quarter组地址±1代替宽字节地址多路选择，EXTEND仍按实际字节组。codec v4的839向量与row v6的176组仍按独立旧规范精确。自身高熵全HD联合v3实际运行948.266秒通过：3×1920×1080、6220800 RGB、最大双眼及448×448 RGB人脸、2112行/6份逐值眼报告/9图逐字节、源等待0且行/特征丢弃0，768 CSI长包/6载体帧；容器2949120、内容1676568字节、324空chunk。container SHA `142774e8570340c552dedabd167c6ba5c0d1fa856b4e58d66c5bba33c62b03ea`。这只证明同样75MHz/625000源周期的完整人工负载，不证明sensor物理120fps、无限任意实景、器件资源改进、时序或实际RK/NPU。187项当前输入已冻结，自己的native排队，不修改运行中工程或缩小ROI/帧率绕过容量问题。

wide首轮高熵联合v1在25.002376ms终止于面部CRC/计数/颜色和的复合断言：输入已从渐变换成高熵，最终golden却未更新。原失败保留。另一份compact v2仍使用相同错误golden，核实实际TB及精确拥有的VVP PID/父进程/创建时间后主动取消，保留部分raw/log及 `cancellation.json`，原因是已确认错误预期值，不是观察超时。v3在编译前独立计算三帧全部ROI的zlib CRC/像素数/面部RGB和，保留 `high_entropy_oracle_summary.json`；所有原断言继续执行，额外用RK解码逐完整图像比较。不能放宽断言、回写旧失败为PASS或因日志暂时无输出停止健康仿真。

当前颜色版HCI04自己的168冻结输入/163 staged完整native已实际通过：setup +0.192ns、hold +0.020ns、TNS0、覆盖99.55%、输入无漂移；bit SHA `befa1d2d7a018705079780726f1cc2baf8375c2ccdb8720f3ed8016cbc8c9fc0`。物理流程在同一个HCI02 native完成后串行执行当前06九色/灰度权重/控制验收和原05测试图观察，分别finally恢复精确37及新32帧，再继续HCI01和compact自己的native。协调进程改排只停止核实身份的等待协调器，保留实际TD及其launcher；receipt与旧状态均保存。未实际加载和观察面板时不询问用户是否已见当前位流，不把DSI接入确认当光学通过。

compact自己的真实CSI/完整ISP/DBUF/ROI/特征/发送联合v2随后实际82.015秒通过，与wide短fixture发送16行/3特征、明确1/0/1丢行计数和96字/12FDMA逐字相同；只绑定当前自己的模块与供应商公开功能模型。当前七份硬件数字证明124项源SHA绑定见 `hci_wide_compact_progress_v1/result.json`，自己的资源/STA/PHY/RK稳态仍待完成。汇总host第一次误把legacy独立 `line_codec.py` 当当前RK生产文件，未写索引即失败；记录后只按实际角色分别列独立oracle与当前生产SHA，不复制旧文件伪造同名生产依赖。

## 当前 RK 抓取、推理绑定和存储容量

`hci03_compact_codec_20261011/rk/capture_hci03.c` 已在实际RK gcc12.2以 `-O2 -std=c11 -Wall -Wextra -Werror` 编译aarch64 ELF，71936B、SHA `9e75664408b56f378694cfafecbd5534ca38499dcb9bce242435618e7fc2ec1c`。保留V4L2单plane多平面API的bytesused/data_offset、flags、全部sequence/内核timestamp/主机DQ时间，无warmup丢弃；抓取阶段预分配RAM，STREAMOFF并释放buf后再保存所有实际字节，错误也保存已经取得的部分。实际STREAMON仍需自己的正STA/匹配bit和正式37恢复guard，不能把编译当板测。初始化QUERY/SET返回必须严格1920×128/YUYV/3840stride/491520size/1plane。

`decode_hci03_capture.py` 显式3840行，按严格HCS/HCR/HCE和ROI identity重组并保存RGB24/GRAY8、FID/配置/源时间/原点/尺寸/整图SHA；完成FID必须连续，端点partial包和初末partial ROI明确计数，中间不搜索magic重同步。实际RTL满载容器9图/全部SHA已独立对照通过；V4L2元数据测试使用明确合成六帧、含32bitsequence回绕及19类flags/长度/offset/序号/format错误，不能标为实板来源。

`hci03_uart.py` 对实际vendor TX单元的14个变长七slot包，14592次单bit损坏全部拒绝；239B最大初始prefix/31B尾部及整包丢失/重算CRC的sequence gap检查通过。HCL3/HCD3分别解出52/16word源/目的drop/error/highwater/wait及snapshot/clock字段。测试distinct sentinel不代表实际负载，实际armed/reset/reserved和稳态进度另验。一次单bit改变HCD3类型为更长HCL3时，旧host测试把None误作有效完整记录；保留v1失败，当前在16B完整头到达时即检查版本/声明长度，不把矛盾的96B类型藏成待240B半包，独立v2通过。

当前RK全局python3无rknnlite；原T3 README给出的 `/home/linaro/t3_basic6/.venv/bin/python` 实际可用，OpenCV4.6.0/NumPy1.24.2、RKNN inference支持data_format，当前model SHA418ccc10…已核对。只上传本任务新helper、检查SHA/语法/import/签名，不另装SDK、不初始化NPU。`infer_hci03_roi.py` 保留原vendor letterbox黑padding/后处理，完整绑定源图像与实际送入API的uint8 NHWC RGB tensor/SHA、模型/SDK/helper SHA、每次输出/耗时和person class0正例；SDK内部归一化/量化未独立观测，不把API tensor称为设备内部normalized tensor。推理尚未执行，当前模型存在和旧正例不等于当前压缩输入识别通过。

本轮RK根文件系统100%导致SFTP上传返回size mismatch 0，不是SDK编译错误；source parent tools为root-owned时也先出现mkdir权限失败。新helper仅以sudo创建明确新目录并将该目录交给linaro，不改父目录、runtime或权限树。先将本任务五次已关闭的HDMI场景目录163个文件/491441699B流式tar到电脑，逐成员长度/SHA核验，archive SHA `fe42457e21d5160c3c3c7881e1579387dab81c8e05ab0627ad70dbe0c30d384b`；再次确认远端全部文件未变、无该目录的活跃窗口，只unlink其中已验证的actual_NNNN.xwd副本，释放489557161B。保留全部本机原物理证据/封包和完整新archive、远端JSON/PNG；不删除用户原文件或runtime/boot/kernel，不递归清目录。release后普通可用128606208B、含root保留块791232512B只是当时容量，后续捕获/恢复须重新检查，不能用root可写推断普通用户仍有空间。

新C1/C2自己的颜色版physical guard和independent reviewer已经准备：要求本工程自己的正STA/bit、真实颜色top/module SHA、九色/六模式及C2最大ROI命令，分别界定初始UART prefix≤63/159B，finally精确37和新32帧。不继承旧父bit SHA；实际执行和颜色权重的C4实板结果仍分别收取。当前完整状态见 `hci_host_readiness_v1/result.json`，所有684项冻结native输入再次逐SHA确认没有因host/README/skill更新而变化。

## 颜色版 native 完成与弱蓝色物理对照

颜色版HCI02同一个TD PID63708真实完成4097.922秒，172冻结输入/167 staged无漂移，最终setup +0.007ns、hold +0.020ns、TNS0、覆盖99.66%；自己的bit SHA `b8007959d8dc6ed95242dc26aa0fba97b3be3b1970ac2719002f2b5d415b77a8`。这是本次最终STA通过，setup余量很小，不能扩大为跨条件稳定性保证或继承父位流的物理验收。

颜色版HCI04物理v1真实通过九色粗RGB响应、UART控制以及红/绿亮度方程，但BLUE单独区分旧红蓝权重的信号不足，整轮保留FAIL。蓝色实测104.1644、当前方程104.2414、旧交换方程107.9417，前后RGB最大漂移0.11753，误差容限2.11753；当前方程符合，3.70036的假设差未达到额外2的判别余量。不能把“接近新方程”改写成旧权重已被蓝色单场景排除，也不覆盖原session/raw。新独立v2另拍BLACK/RED/GREEN/BLUE前后RGB和亮度，保留四个绝对方程及漂移门槛，额外要求RED绝对和RED→BLUE对照均以显式容限区分旧交换，BLUE单独判别是否充足照实记录。准备就绪不等于v2板测通过。

v1失败后finally精确37恢复及新32帧通过；原05第二轮120秒UART/TPG源帧与同样恢复也真实通过。两者都未取得实体7寸屏外观确认。当前排队先等待同一个C1 native PID43572终止，再依次新C4对照、原06、原05、当前C1/C2自己的板测，最后compact自己的native；保持当前TD与launcher，无观察超时重启。屏幕接入确认不能替代加载期间的外观证据。

关闭的失败物理v1场景另有39文件/124942090B逐成员SHA归档，archive SHA `e7b9fbe83d28b76e15c7ea90d1c3841ad71be9d6f00c9bdf1779ec0c86f43d7b`；再次确认远端一致和无活跃拥有窗口后，仅释放124463685B已验证XWD副本。通用入口 `archive_closed_physical_hdmi.py --folder 明确已终止物理目录 --release-verified-xwd` 同时要求实体guard终止、37已恢复、源窗口已关闭；保留本机原证据和完整archive，禁止删除尚在执行的场景或用存储压力放宽这些条件。实际进度与失败边界见 `hci_physical_retest_progress_v1/result.json`。

颜色版HCI01同一native PID43572实际1826.984秒完成，157项输入无漂移，setup +0.301ns、hold +0.020ns、TNS0、覆盖99.49%；自己的bit SHA `ac01352a014a883724b649ed9ff000c54d2106395261c5f277a907957af6ec75`。当前01/02/04均有自己的最终STA/bit，不借用历史父工程通过记录；01/02自己的新物理仍在队列中。

HCI04新物理v2及独立原始复核实际通过：19420记录，prefix0/tail7，完整CRC/序号，来源事件分项panel5443/RAW5159/DDR5158；九色/六模式、四绝对亮度方程、14完整命令/一次部分包超时、5MARK、默认GPIO关闭、精确37及新32帧。红→蓝实测差−4.51635、当前方程−4.69487、旧交换+8.11216，合并容限5.11046，足够区分；BLACK→BLUE和BLUE单场景仍不足额外判别余量，明确false。名义源55.56067fps/panel首DE58.58643fps不扩大为物理120fps或光子。旧v1仍FAIL，实体屏幕/外部探头/舵机仍不由这些数字代验。独立review执行前发现期待YELLOW，而实际固定协议为ORANGE(255,128,0)，保存旧review并只修正未执行review的颜色名；所有数值/CRC/恢复断言未变。修正边界及三候选结果见 `hci_colour_verified_progress_v2/result.json`。

`guarded_hci03_compact_physical.py` 与 `hci03_physical_uart_review.py` 已准备，强制本工程正STA/bit、187冻结输入/七当前数字证明/实际RK工具SHA、其它板测队列终止、只使用核对过的video22拓扑，捕获期间保存每个V4L2缓冲及整个七slot UART。观测到STREAMON/OFF链路复位时明确切分active epoch，要求连续active段的三ROI/双特征/CSI容器/TX进度；全部错误/丢弃快照照样必须为0，不丢包或内部重同步。完整ROI必须匹配实际HCIR最大几何、配置和捕获SHA。可选NPU从同一捕获在RK解码，绑定实际API输入/模型/20次person正例；单色源不能用作person正例。finally恢复37/new32。`hci03_physical_guard_preparation_v2` 仅语法/help和三段生成RK脚本静态通过；v1静态求值器漏列str的NameError保留，均无上板动作。实体捕获、引脚enable、压缩模型正例和自己的native不能由这份准备记录推断。

## 当前颜色板测收取与后续相机模型准备

颜色版HCI02自己的物理v1及独立复核实际通过：九色/六模式、7HCIC/16HCIR、256×128双眼和448×448 RGB人脸、全部CRC/配置/窗口与逐眼报告、眼FIFO峰值194、持续2245条五slot UART完整序号；精确37及新32帧通过。bit仍是本候选b8007959…，没有改RTL或继承旧d61b父位流。HCI04完整包v1为108367203B、1294源文件/1296成员，SHA `4403caaa958d77edf1e908e896aac2dde4633c3e53bb960b33d73c63aefce878`，两64MiB分片按序复拼SHA相同。包内skill是当时冻结快照，后续live经验不回写旧包。

颜色版HCI01物理v1在初始20秒raw里失败：7个完整CRC记录后offset448的header9坏，offset510才出现有效header23，后续199条CRC/序号有效；与834字节缺失相容。不能把len模64的63直接认成只丢1字节，首次host取证这种假设已失败并保留v1，新v2按真实header序号距离诊断。无修复raw、无内部resync验收，根因未证明。finally精确37/new32通过。新独立持续句柄/后台接收/SetupComm/OSerror监视和整个原始会话CRC序号追加检查已准备，同样本候选ac01352a…位流及全部原数值断言保留；待同一个compact native终止后实际复测，不能以准备或后段诊断CRC有效把v1升为PASS。

原06物理repeat v2和原05 repeat v3数据独立复核实际通过：06九色、RAW/ISP/DDR/source计数/全幅614400及新32恢复；051200条完整UART/源帧33→7058、纯R/G/B/WHITE与新32恢复。原05是TPG，注册native top明确CSI snapshot `src_stats(192'b0)`，UART word9是RAW源packet数而非DSI TX数，必须连同word10..14核对为零；初次host review套用06的word9前进断言失败，保留旧review和失败receipt，依据本工程实际已冻结top改为05专属零字段合同，仍保留全部CRC/序号/全幅/颜色/恢复门槛。两者未收到加载期间实体屏幕外观确认，原13仍12/13，#9/#10只是用户明确计通过口径。

额外person显示helper使用原已给定 `person_s2.yuyv` SHA326ed025…，仅显示旧场景，绝不把旧fixture直接冒充新codec模型输入。helper已上传/语法/import/源SHA核对，尚未显示。`guarded_hci03_person_model_physical.py` 先核本工程自己的正STA与队列终止，拥有独立600秒X11窗口；采前/采后fresh XWD逐全幅RGB与已保存显示参考相等，source副本全部传回核SHA，finally只关精确拥有PID。当前新CSI缓冲→严格解码完整ROI→实际uint8NHWC API tensor/模型/20次person正例仍由K3 guard另行绑定。四段RK脚本静态检查见 `hci03_person_model_guard_preparation_v1`，未代验板/模型。

compact自己的TD PID89288/launcher4428实际已启动，187输入不改，观察到gate映射/综合进度不宣布最终资源或STA通过，不因观察时间重启。队列37422完成此前所有物理finally恢复后继续它；队列46562等待其真正终止，然后C1新raw复测/独立review、封01/02自己的包，再仅当K3自己的native positive才进行新person/CSI/model。最近只读实际板37空闲元组再次和C2恢复结果相同。进度/句柄/失败/准备边界见 `hci_current_physical_queue_progress_v3/result.json`；全扩展goal未完成。

## 三份颜色工程已验与共享读口候选

后续实际结果取代以上排队快照：HCI01同一ac01352a…位流在新持续单句柄UART物理v2及独立复核通过。149220原始字节中2331条完整记录全部CRC/序号连续，初始prefix36/tail0，Windows线路错误列表为空；请求1MiB接收队列返回成功，但未独立测量驱动实际分配。九色/六模式/7HCIC/源计数/精确37及新32帧通过。v1的834字节缺失相容诊断和原FAIL保留，同位流复测成功不证明旧失败的根因。

01/02/04当前颜色完整包与自身native/物理/逐成员SHA复核全部通过。01包v2为95071348B、990源文件/992成员，SHA `4dfea0b28052dc5991fe596f630c57e643127373e217724943f2d2b5b3dc06be`；02包v2为140749802B、1360源文件/1362成员，SHA `0cd66fd3401d5af3ffe2b245a8e4806b877b760bdcb8052f4ae7106ec1d17922`；04包v1保持4403caaa…与旧快照。01/02在README记入真实物理结果后另建v2，原v1包不覆盖；各包分片按序复拼SHA已核对。仅限各工程已记录的算法/控制/数据合同，不扩大为实体面板、光子、外部舵机、动态SDF或NPU整体通过。

compact自己的native PID89288真实1379.468秒终止失败：gate.area slice*68571/64320=106.61%，ERAM258/272，DRAM9928/移位96，总RAM10024；place PHY-7027/PHY-9002，未生成自己的bit、route或最终STA。gate.qor中42.09%的另一slice统计不是实际可布局用量。其完整最大高熵数字PASS仍保留，但不能执行旧K3上板入口或把旧准备记录继承为新候选验收。

独立完整 `hci03_shared_spatial_20261011` 保留187注册输入、全部IP/ROM/DDR/DSI、算法、ROI容量、色序与时钟。`hci01_spatial_quad` 的bottom_active本来排斥正常emit；提前选择唯一read_col并让bottom别名使用同一读值，消除同一bank两组异步读地址，保持逐周期握手/数据/元数据不变。`hci02_eram_sdp` 使用供应商真实MODE("PDPW")，PortA固定wea=1且实际写入仍由cea=wr_en控制，PortB web=0/ceb=rd_en。不要臆造MODE("SDP")：官方公开模型只有DP/SP/PDPW/FIFO等明确模式，PDPW的写A/读B合约必须按官方端口要求核对。

新候选真实供应商公开PDPW模型已通过32768×8/256×243、全初写、20000次随机双端操作、读CE停止及slot复用；六组几何/STAGE逐周期空间模块对比均通过，每组24帧含全部模式、停顿、bottom drain、动态配置和不清RAM复位。真实CSI/完整ISP/DBUF/源标记/ROI/特征/发送联合v3实际68.547秒通过，两帧96字/12FDMA/16行/3特征，极短fixture明确丢弃1/0/1，与正常全高清无丢失验收分开。当前最大高熵全尺寸v4和自己的TD PID68852分别仍执行中；这些功能证据不证明资源节省、最终STA、实际RK STREAMON或NPU正例。新证据见 `hci_three_colour_verified_shared_progress_v1/result.json`；动态索引03只指向新工程，旧compact native失败与K3专用guard明确保留为历史。

## 共享候选终止与同步ERAM行缓存

shared/PDPW最大高熵v4实际951.422秒终止通过，与compact同为三帧6220800 RGB/2112行/6特征/9整图精确，源等待与行/报告丢弃0，container SHA142774e8…完全相同。新PDPW backend另行实际通过839codec向量/176行codec案例/203包2476字跨时钟桥/1423包重放/11520单字节破坏拒绝/两满bank占用复位与3693次输出保持。连同供应商PDPW/六组空间逐周期对比/真实CSI联合，`hci03_shared_digital_progress_v1`绑定九份终止证明、124项当前源与187冻结输入，无父native继承。host binder最初只识别tb.v/tb.sv，而frontend实际文件是tb_full_joint.sv，失败前未写索引；保存旧binder，只改文件发现并绑定六空间case的全部compile/run日志，RTL/TB/断言/原result未变。

shared自己的native PID68852实际终止place失败：gate.area估算Slice65704/64320=102.15%，ERAM206/272，DRAM7240；相比compact实测减少2867个Slice、52个ERAM，但仍无自身route/bit/最终STA。gate.area声明需以Optimize-place进一步核实，观察到进入preplace不等于资源通过；最终PHY-7027/PHY-9002保留在自己的log/result。S3-only板测入口另建且只静态检查，未执行，也不能用于下一份ERAM工程。

独立完整 `hci03_eram_spatial_20261011` 保留187注册输入、全部功能/最大ROI/色序/容量/75MHz/载体协议，仅空间滤波三行bank改真实PDPW同步ERAM。高斯保存4×10bit横向和，后处理保留76bit和/差值；一个pending阶段同时锁存bank/op/h_now/config/SOF/EOL/EOF，使同步读结果与控制对齐。pending满且下游停顿时RAM读CE与控制保持；允许每拍流水推进，帧末pending和输出排空后才接受下一SOF，不复位RAM。增加一个对齐周期须重新测吞吐/源标记，不声明逐周期等价。

实际 `hci03_eram_spatial_unit_v3` 在WIDTH/HEIGHT=(4,1),(8,2),(64,7),(1920,3),(4096,3)各STAGE0/1，共10组、每组24完整帧，全部模式/配置/边界/下一SOF/独立源停顿/输出保持，通过与旧生产模块的每个输出像素、配置、SOF/EOL/EOF序列比较；两级占用停住后共同复位、不清RAM，新八帧无旧数据泄漏。v1还因Path的JSON序列化不能写result，compile/run/TB/entry仍保留；v2增加计数发现old9/new0，两个fork driver误用了static task共享参数。仅把frame/series改为automatic并修报告序列化，全部RTL和断言保持，v3实际通过10组。失败范围见 `hci03_eram_spatial_test_driver_correction_v1`，不通过放宽断言或改RAM模型代验。

当前ERAM工程自己的TD PID44884与全尺寸高熵v5/真实CSI联合v4分别执行中，187输入已冻结不改。新工程自己的native/STA/bit、物理RK/同捕获NPU和完整包仍须实际结果；动态状态 `hci03_eram_running_progress_v1` 与额外索引为准，旧01/02/04包保持冻结，原13仍12/13含用户#9/#10暂计，全扩展goal仍active。

## ERAM全部数字证明及组包时序备用优化

以上运行快照的数字测试现已实际终止通过。`hci03_eram_completed_digital_progress_v1`绑定12组真实证明：最大高熵三帧全高清6220800 RGB、2112行、6特征、9整图，源等待/行与特征丢弃0，container SHA `142774e8570340c552dedabd167c6ba5c0d1fa856b4e58d66c5bba33c62b03ea`；真实CSI/ISP/DBUF/源戳联合v4通过，短64×3 fixture仍明确报告每ROI丢1行，不冒充正常全尺寸零丢失；六几何26帧全部模式与停顿376376像素、两帧完整1920×1080灰度/高斯/直方图/Sobel 4147200像素、四帧真实视频/ROI/特征均与独立oracle相符。功能总计4523576预处理oracle像素；其中vision sim本身rc0/PASS，最后CLI打印Path的TypeError发生在保存真实PASS文件之后，另留host-only修正receipt，没有重跑或覆盖实际证明。

本ERAM候选自己的gate.area Slice62382/64320=96.99%、ERAM215/272、DRAM4552；place实际Slice61700=95.93%、RAM216（含观察器）、DSP99，资源进入器件范围。place setup WNS −10.513ns及路由迭代的负裕量仍是未签核观察，不能代替最终route STA，也不允许因此下载。自己的TD44884/launcher76168保持健康执行，187冻结输入不能修改、不能因观察超时重启。最新不可变日志/进程/候选源比较与索引更新在 `hci03_route_packet_standby_progress_v1`。

物理排队v2只等待本ERAM候选自己的正最终STA/bit与全部源SHA后串行执行颜色/六模式/七slot持续UART、独立复核、精确37/new32恢复；归档关掉的自有HDMI场景后，仅释放已经逐文件复制核SHA的自有XWD，再进行256个实际CSI缓冲与新解码ROI的20次NPU person正例。连续UART证据窗覆盖编程、配置、STREAMON/全部捕获、STREAMOFF后一秒，在离线拷贝与NPU推理前关闭；不把4095帧ROI安全TTL到期当成捕获中失效。旧等待队列v1在没有任何板动作前经精确PID/父进程/创建时间/WAIT/空steps检查后取消并保留receipt，只更新自有等待助手，TD完全未动。场景helper自有900秒finally关闭，所有既有CRC/完整ROI/零错误/所需person class及恢复门槛保留；这些准备不是物理通过。

独立备用完整工程 `hci03_packet_pipeline_20261011` 针对gate实际39级的row-sequence到packetizer/actual_wire路径，仅改生产 `hci03_row_packetizer.v`：IDLE先锁存全部12个9bit长度，已有17个CRC_HEADER周期内每拍归并一个max/sum，第12拍锁存pair-count/payload，第13拍用移位加法生成8/24字节factor。原包头/CRC、状态周期、ready、发送/释放、ROI最大容量和75MHz保持；全部187输入比较中另外两项变化是自身根路径.al与重新生成的直接构建配置，不隐去其SHA。该备用没有继承ERAM native，也未切换当前选择。

备用实际逐周期测试96包/112192字节通过：所有ready/地址/data/valid/first/last/release/activeROI/四累计计数逐拍等于被冻结ERAM生产参考，独立zlib CRC与奇偶1..480长度及三ROI轮转核对通过；另在CRC0/11/12/13/16、保持HEADER0/BODY3/BODY239八个占用边界异步复位，清零归并/包/累计状态，随后96新包得到相同wire SHA `a6cec90cd6ff46e5be5acd9b90734b8f744409bfd6115bf794f15d3377b86d3d`。备用真实CSI联合v5实际73.703秒通过，container SHA46ec3e16…与ERAM相同；其最大高熵v6仍独立执行，自己的native/最终STA/上板/完整包尚未验。不要重复启动丢失session输出但仍健康的VVP；按已记录PID、父进程和最终result观察。

备用最大高熵v6现已真实1018.187秒终止PASS：三帧6220800 RGB、2112行、6特征、9整图精确，源等待/行与报告丢弃0，container SHA142774e8…仍与ERAM完全相同。`hci03_packet_pipeline_completed_digital_progress_v1`绑定14份实际证明、187个本工程注册输入及相同RK工具；10份未变模块只按确切SHA复用，两份改组包器整链重新运行，加上两份组包逐周期/忙reset。当前选择仍是运行中的ERAM候选，备用数字通过不继承父native/位流/板测。

两份自有串行助手已创建：P3 native仅等ERAM自身真正终止失败与原队列TERMINAL_NO_PHYSICAL后，保留所有负结果、核187源/14证明再选择并启动自己的TD；若ERAM正STA则跳过。P3物理助手仅等P3自己的最终正STA后执行新的P3-only颜色/七slot持续UART/独立复核、归档闭合自有场景、实际256CSI与新ROI20次person正例及finally精确37/new32；所有门槛保留，静态7段RK脚本未代验。两助手可以在父native健康期间等待，不能因此重启或并行调用TD/编程器。自有句柄与进程快照见 `hci03_packet_queued_progress_v1`。

后续准备 `tools/review_hci03_current_capture_model.py`，按eram/packet选择自身12/14证明和native/bit，而非旧K3父验收。实际运行必须重新严格解码256个原始V4L2缓冲、比对本机/RK/新解码所有ROI图字节与源元数据、复核整个UART捕获证据窗、逐像素核person自有窗口的前/后fresh XWD；在RK只读使用OpenCV直接重建640×640 RGB/黑边，要求1228800字节与实际API tensor完全相等，核固定模型/SDK/helper SHA及20次class0≥0.35、恢复37/配套ko/boot/gain32与新32帧。BGR重排是否可区分只是张量场景观察，九色同bit的正式颜色证明仍另行必需，不能用灰场景同值代签色序。此复核不再次执行NPU，不将旧显示fixture作为推理输入。

`hci03_capture_independent_review_preparation_v1`目前只有Python help/syntax和一个未执行RK脚本的编译，STATIC_PLACEHOLDER不是实际ROI。初次help因else14语法错误未运行，静态读实际UARTLease.finish发现raw/bytes/queue_peak/句柄标记，SHA实际在UART_review；旧未执行reviewer与修正原因另存 `hci03_capture_review_static_correction_v1`。修正只按真实schema检查，不放宽任何CRC/序号/张量/正例门槛。没有实际抓取、RK张量复算或独立复核PASS，后续必须执行并保留新目录原始结果。

## 连续传输长测工具与SSH结束条件

256缓冲的实际源图/模型对应证明不能单独代签更长稳态。另建 `capture_hci03_stream.c` 保持1920×128载体、原8个capture缓冲、源时钟和最大ROI；连续60..600秒，每个实际DQBUF先连同原序号/flags/bytesused/offset/timestamps写成64字节CRC保护SHF4记录，错误缓冲也先保留。全部原始字节流归档到本机，RK在STREAMOFF后保存每条原始元数据，不在RK采集循环写大体积视频或丢warmup。恢复仍须同一正STA位流及精确37/新32，不能在运行中的native旁调用编程器。

实际RK GCC12.2 `-O2 -std=c11 -Wall -Wextra -Werror`编译已通过，ARM64二进制71992B，SHA `e64655f2a407874411344e1b193730c71c8140fe1c01a00fd35dc327b3b303ab`；`--emit-record-fixture`只输出三条合成缓冲、明确hardware_capture=false，未打开video。记录单元逐字段/逐1474560载荷字节和32bit序号回绕通过，21个CRC/flag/长度/offset/index/截断/尾随/假物理变体被拒绝。长解码器将已有实际RTL最大高熵六容器包进明确合成SHF4，重新核九张图SHA、六特征，通过六项CRC/真实padding/后来chunk/未授权配置/假物理拒绝；不将这些单元升为实际长抓取。初次unit只传cfg600而真实冻结fixture有600/601/602，原FAIL和raw保留，仅新attempt按实际三配置绑定，生产允许命令门槛未放宽。

`rk_byte_stream.py`新增逐块接收和落盘。首次320MiB纯字节预检在远端returncode0时只收322863104B，父测试正确拒绝；旧exit_status_ready加瞬时空队列不能证明stdout结束。保留原部分归档/旧代码，改为实际EOF且stdout/stderr队列排空，缺EOF不得PASS。新320个唯一编号1MiB块335544320字节全部比对通过，SHA `e0fa31731ec7424f0d0c4c3dd34de349e4978fa57641b87dfa1f888fc899e1c1`，本次编译负载下6.344秒/50.441MiB/s；没有达到60MiB/s，也不作未来突发接收保证。纯Python远端stdout未触碰video/GPIO/时钟/服务，旧短SSH工具和E3/P3全部187冻结输入保持。

`guarded_hci03_long_stability.py`现在仅静态ready：要求本工程自己的正STA/bit、同位流九色及实际短捕获20person独立复核先通过；一个STREAMON默认300秒，每30秒按递增HCIR序号刷新4095源帧TTL，几何/模式/源时钟不缩减。新长UART reviewer保留原全部CRC/全局序号/七slot/error/drop/activeepoch门槛，并核每个实际续租序号及单调确认；原短reviewer和已排队入口不改。严格解码全部归档缓冲与RK原元数据逐项对应，计算有效lane、ROI wire和全容器各自带宽/压缩分母。finally只在自有采集实际终止后恢复；quiesce在QUIESCE_BEGIN前拒绝时不编程。实际300秒、独立长测复核、六项综合报告与完整包仍未完成。

所有原buffer元数据保留，ERROR标记表示数据可能损坏，不能默默丢弃后继续声称全会话通过；该字段按[Linux V4L2 QBUF/DQBUF官方说明](https://docs.kernel.org/userspace-api/media/v4l/vidioc-qbuf.html)处理。当前长测工具的实际/合成/静态范围及健康原TD44884和三个条件队列见 `hci03_long_tool_progress_v1`；goal仍active，不因工具准备增加原13或六项验收完成数。

## P3自身功能RTL延迟与测量起点

`hci03_full_pipeline_latency_v2` 已真实终止PASS，`independent_review_v2` 不导入生产RK解码器：另做CSI parity/表CRC16、HCS header/body CRC与padding、2112行LZ/delta/raw CRC、9幅完整ROI SHA、6份原特征报告。静态oracle为23个稳定word，第24个engine cycles逐条对原DUT日志；首次按24word比较失败保留，修的是复核器，没有重跑或改生产RTL。

起点是HCI02处理接口接受的post-ISP四像素RGB SOF，不含上游CSI/RAW10 ISP/DDR。配置8193的视频支路是RGB旁路，SOF到视频输出26.668ns仅属于这一旁路。双眼各256×128完整图像到CSI行CRC接受为2.859717..2.859784ms，448×448 RGB脸为4.849230..4.849857ms，完整眼特征报告为5.219449..5.219729ms；三幅fullHD高熵源、最大三个ROI、异步FIFO/实际公开vendor ERAM、强制PHY背压及所有原断言保持。末ROI包data word到CSI行CRC接受的本组最大额外界为7.067020µs。

实际仿真周期13334ps，帧周期625000拍=8333750000ps，约119.994fps；这不是实际IMX415的120fps，也不是实体PHY、RK V4L2、NPU、光子或SDF/native验收。P3尚在条件队列，E3主候选不继承该度量为自己的实机结果。完整原HS functional trace/container SHA与父高熵v6逐字一致，单一仿真时间轴下重算全部9组时延；实体源到RK仍需实测时钟映射/误差界。

2026-10-11用户另行要求恢复掉线PCIe：已验收37 SRAM与原runtime恢复、Gen2×1/32完整新帧及独立空闲复核通过；原native44884同PID且CPU前进、187输入保持。该次独立恢复持有真实BW硬件队列租约，例程测试队列的串行guard未移除；不把此特定恢复过程推广为允许任意native/JTAG并发。当前两路CSI范围、USB退出及CSI1失败/回退见[双路例程](dual-csi-sync.md)。
