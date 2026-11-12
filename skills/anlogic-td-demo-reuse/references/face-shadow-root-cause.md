# v179 当前app28与异常提交边界

当前CURRENT已实际发布app28，SRAM51/stage0/gate0及原RK3576 NPU保持，模型61305、采集61347。app26试验未留用：全1080表面再缩放有CPU开销，且发现writer死亡后旧valid头可能覆盖半写像素，已干净回退app25（60370/60412）。独立app27只修原子valid0→像素/元数据→release提交；app28在此基础仅改显示表面/960×540 widget，105源104继承同27。真实ARM三RGB/原模型oracle、跨进程锁、SIGSEGV后invalid拒收及GUI像素证明通过；同一原生采集提供独立processed RGB1080预览，模型仍是等3×3均值640×360。app28实际F10正常退出和重启通过，root已查看HDMI并留用，但无正脸窗口不能验收肤色、阴影、控制或整项画质。

residual51_existing_raw_v2只使用既有椅子/窗帘RAW50和不同时刻processed51，展示低码量化、带负交叉项CCM裁切及Gamma首步能产生残余绿色的充分路径；没有同帧真实AWB/曝光、暗场或中性色标，不能唯一归因为黑电平、Bayer、CCM色度或全部51绿点，更不等于真人颜色修复。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v179/actual_app28_T08_observation.json`。全部83+12+47及status保持，未扩大画质/光学/整机验收。

# 历史v178：当前应用与限定证据

当前实际为SRAM51/stage0/gate0与app25原RK3576 NPU（模型58961、采集59003）。app25把1920×1080 RGB3按等通道3×3均值缩至640×360，原权重和NPU输入语义保持；实际F10退出及默认重启通过。局部颗粒减轻，但用户仍反馈HDMI画面不好，画质/真人肤色/操控未验收。20秒窗口18.75次更新/秒、NPU调用0及有效行0，只是无人脸预览，不能宣称推理FPS改善。三张实际帧的标量area3与OpenCV全字节一致，较中心抽样增加约2.6ms；NEON v1的编译告警失败保留，独立v2 ARM六图案及三真实帧/2300除法输入均通过，但中位加速0.96×/1.03×/1.09×无明显收益，未部署。Flash37保持，USB和RK CSI/AIQ继续隔离。

独立只读显示检查为HDMI RGB888 full/1920×1080p60，实际1920到1920无scanout缩放，CSC y2r/r2y均0，xrandr Gamma1/brightness1；这些配置不代替光学画质验收。另20秒无人脸窗口374行/18.7updates/s、NPU调用0：CPU人脸检测中位44.65ms/p95 56.35ms、输入年龄中位30.94ms、样本年龄104.06ms，是该窗口主要CPU开销，不能叫NPU低FPS。大核2.112GHz/约64℃，快照未见降频；根盘1.87GB及userdata3.61GB可用，不是当前空间阻塞。

app26高分辨率预览仅为本地候选，当前模型和HDMI仍运行app25；不得用无人脸更新率或NEON逐byte相同替代真人画质/精度/操控验收。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v178/actual_app25_T08_observation.json`。该版本保留83主项、12正式项及47 RK子检查和全部status，不增加验收。

# 历史v177：实际HDMI已切换高精度51

51高精度ISP已实际更新SRAM并留用于HDMI，原app24/RK3576 NPU已恢复（模型57543、采集57585）。修复链路在去马赛克/CCM/AWB中保留10bit，Gamma后转8bit；320源数字门、原完整native加独立物理优化、最终setup +0.009ns/hold +0.020ns且TNS0、四CSI和50ERAM均通过。root亲自查看三帧1920×1080 RGB3及真实HDMI；当前椅子/窗帘场景绿块明显减少。相同HDMI预览区域通用绿优势像素19.87%→1.15%，三帧原分辨率1.56%–1.63%；前后采集时间不同，当前无正脸，不能据此验收真人肤色/操控。Flash37保持；USB1与RK CSI/AIQ仍隔离。

以CURRENT_CAMERA.json选中的51/stage0/gate0/原app24为后续恢复目标，47仅作明确fallback；不要调用旧硬编码47/gate2恢复器。继续真人肤色/阴影/双眼、原NPU真实处理帧率及延迟、13点个人标定/20点留出/眨眼与游戏操控；另核640×360抽样预览的细节损失。全部83主项+12正式项+47RK子检查保留，内核源码/真实双CSI等依赖和未验收范围继续推进。

证据：`projects/pcie_imx415_linear_precision51_20261019/evidence/actual51_pixel_review_v1/result.json`、`projects/gaze_model_migration_v1_20261014/evidence/current_precision51_actual_v1/current_camera_selection.json`。HDMI与DSI同时启用时，应保存完整XWD并按实际HDMI viewport无损裁取，不能要求根窗口等于1080高。app24软件RGB/BGR往返抵消，未发现预览独有颜色滤镜；中心抽样640×360再放大的细节损失仍需另验。

# 真人阴影、绿点与源头分级诊断

v174：actual_v4已完成扣黑前/后各2张1080p RAW，共8294400像素逐一验证lane/stage标记和高6位。每stage31接收/81原生捕获/50软件丢弃，原生结束和清理0；同一BW85744恢复47/gate0/app24，CURRENT记实际56475/56519。stage1/2是不同时刻，不能逐像素当成BLC同帧验证。完整证据在模型项目 `evidence/raw50_actual_v4_independent_review_v1`。

同一RAW按GBRG/共同unity增益重放37、47和10bit方案：统一RGB8绿超差 `G-max(R,B)>12 且 G>20`，四帧当前47为31.43%–32.62%，10bit为8.40%–9.07%，暗部连续轮廓也恢复。不是只统计某一个绿色码值；分箱、通道黑率及边缘分布见 `evidence/actual_raw50_summary_v1`。这批是椅子/窗帘，没有正脸；实际AWB未知，重放为CNR前，不能代替新ISP实机验收。51源码正在集成，HDMI仍为旧47时不会呈现离线改善。

当前诊断候选为 `projects/pcie_imx415_isp_probe50_20261019`。49最终setup−0.887ns/TNS−55.082ns，另有CSI时钟lane−0.025ns，失败bit没有上板。50完整319输入已终态，setup+0.040ns/hold+0.020ns、TNS0，四CSI物理路径和50个缓存原语复核通过，bit SHA256 `85188a640748ddcc40329a8acb29a722259af17086d4353278926c7fa8908d2e`。这只证明所列静态范围。

**真实上板发现诊断读路由缺陷，不能照旧helper继续尝试：** `imx415_pcie_top.v` 的读选择只拦截至0x188，新增0x18c/190/194虽然存在case，却返回SGDMA fallback。实际actual_v3的helper正确拒绝能力号，RAW帧数0；同一BW已恢复47/gate0/app24。原CSR测试覆盖了case和写逻辑，没有覆盖最终read mux，不能当作完整BAR接口通过。需要修正完整读路径后重新构建，或严格限定精确50 bit和同一JTAG租约，仅在CTRL0/无客户端时写stage1/2，逐像素全帧RAW标记验证实际tap；这种替代证明不签核CSR读回、拒写计数或processed stage身份。后续实际结果以对应试验归档为准。

2026-10-19 真人实拍已推翻“47门限2适合人脸”的假设：阴影大面积变为纯黑，类似碎块。实际2→1→0时恢复暗部信号却恢复绿点，因此增加黑阈值不能签为修复。现用以根CURRENT_CAMERA为准：47 SRAM、诊断门限0、app24原RK3576 NPU，Flash37未改。历史恢复器固定gate2的部分不可照搬。

已取得105幅完整1080p模型前RGB3，三张原RGB与PNG逐像素一致。绿点在模型缩放/预览之前存在。恢复后115条真人样本均调用原NPU且有效，源时间跨度内处理率约15.51次/秒，样本年龄中位145.18ms/P95 192.27ms；这是处理观测，不是曝光FPS、眨眼正确性、个人精度或跟手验收。人脸位置变化会显著影响检测率，不能把两段不同姿态窗口作同一输入性能因果实验。

## 已证实机制与尚未定位之处

- 当前去马赛克已保留RAW10至邻域求和，随后在CCM/AWB前输出RGB8。不要沿用“仍在RAW解包时直接丢低2位”的旧结论；真正需要检查的是后续量化、通道裁剪及噪声。
- 当前Gamma2.6的实际RTL含查找表执行4356像素测试，低线性码0/1/2/3分别为0/35/42/48DN。各通道细小取整差异会被放大成彩色台阶。这是确定的放大机制，不是“传感器黑电平错误已证明”或唯一根因。
- 实际BLC/native10去马赛克/CCM/Gamma/saturation运算已复现一条完整数值路径：合成且相位正确的RAW相位值(52,54,52)，BLC后(2,4,2)，提前量化为RGB8(0,1,0)，CCM变成(0,3,0)，Gamma得到(0,48,0)，饱和度0最终得到(0,47,0)。这不需要假设Bayer错误；但仍不是实际传感器RAW测量，不能宣称已定位实拍首发原因。
- 保留10bit到CCM/AWB、使用既有Gamma表低2bit插值的参考方案已通过全1024码/256旧锚点及RTL对照；上述合成输入可变为约(39,37,37)。另有明确反例RAW(50,51,50)：旧路径纯黑，保留精度后仍可能呈绿色25DN，说明精度修正不能单独保证光学去噪。AWB舍入和saturation0改为恒等也不是完整根因修复，不应单独上板后称绿点已解决。
- 后级色度CNR保持整数Y，不能恢复前级已置零的阴影，也不能消除已经编码进亮度的噪声。不能只统计暗区绿超差像素减少就接受；必须保留暗部轮廓、肤色、双眼/眼镜边缘及运动细节。
- RAW10四Bayer相位的黑偏置/噪声、真实相位与裁切、颜色矩阵/AWB的中间结果仍需实测。之前矩阵旁路38导致更绿，RAW底值54损伤颜色；不能重复这些已拒绝方案并当成新修复。

## 完整诊断工程

`projects/pcie_imx415_isp_probe49_20261019`：完整319输入，复制稳定47，只增加分级导出与CSR，不改变颜色算术、传感器表、PLL/PHY、ADC/SDC或原NPU。48首次工程File元素不完整，native在HDL分析前终态失败；49补全File元素，所有HDL与48相同。不能把48的失败目录/bit当当前49产物。

| stage | DMA承载数据 |
|---|---|
| 0 | 原完整处理RGB |
| 1 | 裁切后、BLC前的原始RAW10 |
| 2 | BLC后RAW10 |
| 3 | 去马赛克RGB8、CCM前 |
| 4 | CCM后、AWB前 |
| 5 | AWB后、image cut前 |
| 6 | Gamma后、contrast前 |
| 7 | saturation后、CNR前 |

stage1/2用RGB3无损承载每个10bit样本：R=低8bit、G=高2bit（高6bit必须0），B=0xA0+p或0xB0+p，其中p=x%4。先逐像素验marker和高位，再重建RAW=R|(G<<8)，不能把编码图当正常颜色照片。原始四像素P0在40bit字低10bit，packer后字节为R/G/B；按实际定义验证顺序。

预期CSR定义：0x18c为stage[2:0]及reg_enable[3]，0x190为ISP8能力0x49535038，0x194为拒绝计数。50真实read mux没有覆盖这些地址，读值不能用作上述定义的实物证据。写逻辑独立解码0x18c，必须STOP后配置，再执行正常S_FMT/STREAMON软复位清空管线；启用期间硬件写逻辑拒绝。不是热切换接口。原helper24项仅文件映射测试；能力号也不能代替bit/JTAG身份。

自己的probe+padding+packer32768像素、八stage、每lane全部1024RAW码、孔洞/背压/帧标记与7个破坏反例通过；top CSR case/写逻辑曾仿真，但最终读选择漏测，已由实际失败纠正。另有实际probe/padding/packer两帧完整1080p共4147200像素传输通过。级间ready/valid为源码绑定检查，不冒充完整加密ISP物理仿真。完整native/四CSI路径/缓存/实际导出须分别核对。

## 实测和修正判据

1. 先按CURRENT_CAMERA停止唯一模型客户端，验证video节点无人占用；保持USB和RK CSI/AIQ隔离。诊断bit完整静态检查通过后才受控上板，保留47和当前app24恢复路径。
2. 对原RAW记录四相直方图、低码截断、行列/周期相关性与时间噪声；明暗/中性场景分别检查。需要光学黑时再安排实际遮光，不能从BLC参数50等于传感器寄存器50推断黑电平已标定。
3. 从同一RAW在软件重建四种Bayer，结合已知相位/实际色卡核对；颜色矩阵、AWB和Gamma的导出逐级比较。相邻时段采集有运动/曝光差异，不能声称逐像素同帧物理等值；区分单帧重建、数字注入及统计光学证据。
4. 根据实测选择源头修正，例如保持线性精度、校准黑偏置、在Gamma前处理真实噪声和连续暗部曲线。不能在尚无RAW证据时把这些候选写成已定位/已修复。
5. 恢复探针stage0、47/诊断gate0及原app24全部关键哈希，STREAMON后检查完整hist/唯一所有者/新鲜状态。暗部、肤色/九色、双眼细节、真实NPU更新/样本年龄和控制分别验收；没有真人通过，M05仍PARTIAL。

证据：模型项目`evidence/live_face_root_analysis_v1`、`actual_gamma_shadow_v2`、`current_face_root_selection_v1`；诊断49 `evidence/preparation_v1`、`digital_v1`及自己的native结果。初次观察器把CSV的True/False按1统计，原CSV保留，分析器已纠正；初次Gamma仿真常量0未触发Icarus always@*的启动X已保留，v2显式输入跃迁后执行实际RTL通过，不能把这个测试台初始化问题写成板端Gamma故障。
