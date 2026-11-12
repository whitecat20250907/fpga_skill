# v161 LUT脚重排、SCL并行复制与实板可观测性

功能producer的内部LUT6 D与同步级的直连D必须分开严格检查；route可交换LUT输入脚，须比较真实六输入双射和全部64种组合，不能要求INIT字面相等，也不能放宽同步级私有Q/直连D。SCL内部并行复制寄存器必须核同D/同clock/同初始化与控制，不能把它写成外部PAD回读。聚合ACK-error history与被动wire无START同时存在时，先检查可观测性和复位/时钟，不直接判传感器NACK；250相位RTL通过和PAD配置一致也不证明实板根因。失败全源后从自己的DB派生出正STA/bit必须如实标为派生，完整修正全源仍待。每次真实JTAG后更新CURRENT_CAMERA到本轮恢复PIDs/会话/hist，保留所有失败原始报告。

# v160 监视器原生路径与门级估算边界

复制审查工具后必须核对标题与实际数值：图结构/约束覆盖PASS不能改写为正时序。本版3条同域setup负值真实保留，不加false path掩盖；后续以自己的place/route最终STA判断。新增被动监视器4FF首级私有Q、PAD到首D和普通后级D已由本版原生报告验证，仍不是输入电气/同步器MTBF证明。改变顶层后，60 native查询、held闭合、FIFO Gray和registered singlebit均重新在新gate执行，不能借旧网表相同结论。

# v159 HCK6v3四实际字节与版本边界

新版本诊断必须冻结同一源时钟沿，完整四字节可跨明确版本字段编码并在接收端还原逐包对照；旧版本reserved检查保持。联合测试应由仅观察外部SCL/SDA的从机应答，不能看master内部W_ACK：本轮第2/4字节NACK分别定位、重置监视器后完整203写初始化通过。控制和首笔总线ready仍不足以放行图像测试，实际measure必须继续拒绝RAW/ISP/完整像素缺失。新顶层改变后重新做自己的全源gate/物理审查，不能沿用父版正STA、位流或整网表相同结论。SDA首级max只是布线预算，保留后级STA与外部I/O/电气待验。

# v158 实际PAD比较及被动总线观测

F8与47实际路由PAD对应属性已核一致；被动首事务监视器14正常/逐字节NACK及8异常用例通过，尚未集成或上板。当前生产选择仍为v157实际恢复47/gate2/app20原NPU。

I2C应答诊断应由实际外部SCL/SDA驱动观察：保留首笔四字节、每字节ACK、首NACK、START/STOP及不完整状态；未观察到的ACK位0不能当NACK，必须结合完整字节数。首笔STOP后冻结并由复位清除，不能被后续写覆盖；SCL停止不伪造完成，SDA卡低不伪造START。监视器必须被动、不反馈控制，测试中覆盖真实未改动核心/延迟ACK/每字节NACK及异常。新诊断不能写入旧协议要求为0的reserved word，集成需新明确版本、输入CDC/IO审查和新的完整构建。实际PAD属性相同只排除对应配置差异，不能代替板端电压、时钟波形或传感器就绪证明。

# v157 实板配置错误与外部ACK测试边界

真实错误必须记录同版本的配置state/index和transaction ACK-error history；RAW0且所有包错误0不等于健康，数字startup RUN也不证明MCLK电气波形。ACK测试器只观察外部SCL/SDA，不能由master内部W_ACK驱动应答来代替总线时序。24/25MHz数字8用例通过不代表板端ACK根因已解决；本例核心与生产47字节相同。实际每次JTAG后更新CURRENT_CAMERA中的新PID/会话和完整hist证明，不能沿用上轮恢复状态。

# v156 实际配置诊断和错误锁存边界

诊断应沿实际startup→真实速率I2C→UART整条数字路径验证，逐包对照源冻结边沿；core ACK错误可先于transaction-end sticky latch，fixture不能在第一个error边沿假设两者已同时提交。板测先保存明确版本的配置state/index/错误，再跑图像oracle；控制ready也必须拒绝缺RAW/ISP/完整像素的场景。两个失败分支均用实际controller measure和实际恢复orchestrator验证UART关闭→47→app20→gate2顺序；此数字恢复fixture不替代真实JTAG恢复。

# v155 混合时钟位序与精确启动边界

PLL输出可将相邻有效位合并为concat内的[1:0]，按逗号数量索引会误选open线；必须展开真实位宽再选output1，并保留常量占位。原生STA负项应按端点分类：本轮1条来自已核双触发ACK首级，不是普通同域数据；精确首D max边界不切后级D/SR。新边界须先加入expected字典再解析实际report，missing/duplicate/inactive反例须拒绝。完整构建中直接保留本轮60原生alias查询，避免为同一门级重复编译。

# v154 传感器启动与失效时钟约束

修传感器启动时把I2C和其多位状态保持同一UART参考域，避免为诊断另加不一致采样；协议用新版本启用原保留字段，旧版本仍必须拒绝非零保留字。直接检查真实NACK/超时/RUN状态字，不能从RAW0推断配置错误。功能移走后，原PLL输出可能被优化掉，继承的rename_clock会空匹配；必须据本轮实际工具修约束，不把退出0当干净时序。

# v153 无RAW且无错误仍不健康

真实F6板测把父版RAW0/ECC增长变为RAW0/错误0且video reset未释放；这说明错误计数也可能被未就绪流水线压住，不能当修好。配置错误和完成必须直接可观测，不能从下游零计数反推NACK。摄像头ADC9项一致不代表MCLK/硬复位一致；独立记录25/27MHz和XCLR启动。保留自己正STA位流与失败板测两个结论，并按实际新JTAG恢复更新CURRENT_CAMERA，不沿用旧PID/会话或仅ABI。

# v152 SCLK_V2文档证据更新

同一当前原生中，SR30/D17与clockGray边界、30组1247原生覆盖可先单独签门级范围，3条普通setup估算仍须布局布线收敛。只在完整gate body和全部CDC属性字节相同、仅排除验证过的时间头时复用限定结构结论，不复用STA/物理。普通summary含正路径，不能把全负专用解析器直接用于它。本次UG910_1.6§23.3图表实证V2默认ENABLE/ENABLE/0，补足先前protected模型无可读默认的资料缺口；源代码V1默认DISABLE不能覆盖V2，文档参数也不能代替实际实例覆盖、CE/GSR波形及实物。

精确原文来自本机同版TD的UG910_1.6，PDF页69（印刷57），渲染目检及SHA见sensor_flow/evidence/SCLK_V2_documentation_v1/review.json。这补足较早“V2模型受保护，默认未证”的资料边界，旧实测与失败记录不改写；仍不把文档默认当实物波形。

# 2026-10-17：F11板测与传感器配置器反例

F11真实板测须同时看RAW/ISP/SOF/核与屏幕计数；DSI扫描和非零RGB总和可在RAW0时继续，不能算相机有效。命令accepted也不等于SOF应用。首轮预检先拦住部署setup哈希差异；当前RK脚本使用native32 BAR写和gain32，与较早Python MMIO/gain100本地脚本不同，恢复应绑定真实部署文件，不把旧本地覆盖上去。实际恢复顺序为精确gold47下载成功→PCIe重绑→app20 STREAMON→门限2提交及完整上一帧hist tag2核对。旧配置器忽略NACK、cfg_done早于可靠唤醒且重复启流；复用真实47控制器后仍须绑定实际控制频率、保持表语义并加本地复位。NACK组件复现不证明板上本次NACK，错误分类要保留。

生产选择以根CURRENT_CAMERA.json为准；新sensor_transaction组件通过，自身原生/板测待。下面09/10为2026-10-05历史。

# PH1A CSI 时钟、复位与 BAR 接收前置

适用于本次 PH1A90SEG324 / AFC03 PCIe 相机副本。状态依据2026-10-05实测，发布整理2026-10-06；这些经验不能无条件推广到原06的PH1加密PHY。

## 状态先分开

- 07有27MHz MCLK和111.375MHz byte clock，但auto done=1/best_window=0、RAW包0，无帧；SYN-6024四条PAD常量复位警告不能因一般setup/hold为正而忽略。
- 08恢复共同PAD复位，完整STA仍有recovery/removal负余量，未下载。
- 09 local/global时钟分支与active-high共同reset通过原语数字黄金、完整STA（setup+0.067ns/hold+0.020ns，TNS0，覆盖99.96%）。实际下载后Gen2x1，但视频只读BAR寄存器0，未采集，不能称接收已修好。
- 10相对09只改读地址guard和版本0x56440a01，数字地址自检268项通过；完整构建中断在place，交接时没有10最终bit/板测。
- 最近下载09不保证SRAM现在仍有09。2026-10-05交接电脑仅枚举蓝牙COM3/4，RK串口/AL-LINK未枚举；恢复访问后重新确认。

详细证据在仓库 `projects/pcie_imx415_fix_20261003/reports/` 和 `evidence/`；当前修复顺序及操作在 `docs/09_开发板修复_新对话完整交接_20261005.md`。这些是带时间的状态，不替代新会话读取最新日志。

## PAD本地时钟不能被fabric用户的全局分支代替

实际PH1A布线中，给fabric寄存器的PCLK经GCLK/SCLK分支，比本地SCLK晚约1.7ns。缩短reset数据只改善recovery却恶化removal，不能盲加寄存器或cut相关检查。

按官方UG910 §19，09使用D0 LCLK DIV2/DIV2TO8：clkout→local PAD PCLK，clkdivout→global fabric PCLK；D1 DIV4/BYPASS：clkout→HS sampler SCLK，clkdivout→byte clock。约222.75/222.75/445.5/111.375MHz，实际约束和实例以该完整工程为准，不在运行期mux时钟。

global n0采PAD nibble，n1采n0，byte由n0/n1组成；不能混用local本拍与global上一拍。共同3级reset改active-high存储而保持异步断言、释放边沿，使PAD.rst得到Q直连并去掉反相LUT。完整恢复/保持和nibble/byte路径仍受STA约束，不能靠独立小工程或数字仿真替代整机。

## BAR偏移与不可变版本是接收前置

实测BAR0 0x21200000..0x212fffff，1MiB对齐。CQ转发请求地址，SGDMA内部加密，不能假定ARADDR高16位为零。

10按本工程1MiB BAR0契约检查低20位offset：高offset nibble[19:16]为0、低16位0x0040..0x011c。兼容0起始、完整BAR地址和CQ26位残余地址，排除64KiB/0x80000高offset及0x128 IRQ别名。不要将这个契约推广到不同BAR大小。

setup写0x98后回读100可以来自原app RAM回显，不证明video read mux正常。先读取immutable 0x5c实际版本、0x44/48尺寸、0x4c格式1及bytes/padded，正确才采集。setup返回0、PCIe Gen2x1或可写RAM都不是通过结论。

CHAR_USER旧pread/pwrite加0x80000，而mmap不加；10只验证当前V4L2/setup/诊断所用mmap/直接BAR路径，不认证旧fops全部兼容。继承写地址别名、WSTRB忽略和RREADY stall时RDATA稳定性另列问题#13，不与当前接收定位同时大改。

## 诊断不能把无数据判健康

- 0x50低24位是frame count，高8位是pipeline sticky。当前read_csi_diag10.py仍整32位标frame_count，此观察工具修正待完成；一次读出再分别报告raw32/count/sticky，不能两次读形成不一致。
- E4为diag0 bookend，100为diag1，A8为CSI；11C属于diag0。SEQ应持续增加，busy可短暂置位。
- RAW previous/current payload行数不等于CRC-good或最终裁切高度；previous在下一FS锁定。binning输入1097行可以输出720/1080。
- manual override时auto scanner仍运行但tap被固定，best_window甚至32也不证明真正眼窗扫描。关闭override不会重跑scanner；自动验收需override关闭的fresh reset/完整扫描。
- 真实DMA运行后、tap稳定/auto done/新FS后的稳态比较CRC/ECC/WC/timeout/overflow增量。扫描启动ungated错误另记；无RAW包、无帧且错误0不是健康。不要开启CTRL却不准备DMA，把无消费者的overflow误判为PHY。
- 用实际完整帧bytes/序号/错误buffer验证；WC错误计数仅检查非零/整除5，不证明实际WC2430/4860。#1接收通过不包含色彩正确或双向通过。

## 保留工具限制

09b匹配SDF/网表已真实注入timingcheck，但ModelSim10.5在time0两次native SIGSEGV，无一个字节验收；没有关闭检查绕过。MTBF隔离入口亦native crash，无合格报告。数字原语黄金、完整STA、实机三个证据分开。

TD OOC/debugger关闭async_reg全局directive时，重新打开RTL/PLACE参数可恢复原准确集合；不能晚补属性伪装优化掉的链。逻辑232属性与物理104cell是不同映射粒度。99.96%覆盖及外部delay、PLL/IO/动态Gen1→Gen2警告仍需逐项记录，不写零警告全面合格。
