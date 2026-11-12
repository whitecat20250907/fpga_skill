# v51：三维医学演示与原生游戏目标重构

2026-10-26（北京时间）。本次修改已部署到 RK；交付的是原医学展示应用的三页全屏交互版本，不是静态 PPTX 文件。FPGA 位流、唯一 C 所有者、摄像头/DMA、模型权重保持原版。本次 UI 不代表整个项目历史未完成项全部验收。

## 医学演示

- 心脏、脑、肾脏三页，使用 Human Reference Atlas 的真实开放解剖表面网格。心脏14个、脑283个、肾脏26个网格；原GLB字节保留，颜色/归一化/局部放大属于显示改编。
- 每页6个结构目标，错落分布于画面四周；另外6个操作目标：上一页、下一页、放大、缩小、旋转、整体视图。1920×1080下目标矩形不重叠，中心最小间距至少180px。HTML按钮和引擎语义目标共用medical_spec.json，随页面同步，局部放大不让按钮四处漂移。
- 聚焦实际选中的解剖网格，用青色高光、局部扩大、缓动及半透明整体参照显示；可继续旋转/缩放，再回整体视图。翻页清除上一页局部结构状态。
- 医学按钮点击通过同一引擎与适配器，并显示实际执行回执。眼控接管/原手锁定/手势点击或聚焦流程延续v49；本轮未调整识别模型、手势确认门限或个人标定。
- Three.js r160本地加载，无运行时CDN。静止画面不持续重绘三维场景；只有视图变化、窗口变化和短缓动触发绘制，隐藏页不轮询/渲染。

这是真实参考解剖表面模型，不是患者CT/MRI体数据，也没有生成病灶诊断。“全息”是屏幕上的视觉效果，不是物理悬浮显示。

## 调研与授权

Mayo Clinic的真实工作流体现CT/MRI到三维模型的空间规划价值，3D Slicer说明了体渲染与表面模型的区别；《良医》S1E9仅参考空间演练的画面组织，没有复制剧照或将电视剧当医疗流程依据。

- Mayo Clinic: https://newsnetwork.mayoclinic.org/discussion/mayo-clinic-minute-how-3-d-imaging-helps-doctors-and-patients/
- Mayo Clinic: https://newsnetwork.mayoclinic.org/discussion/mayo-clinics-3d-printing-operations-growing-changing-medicine-along-the-way/
- 3D Slicer: https://slicer.readthedocs.io/en/5.6/user_guide/modules/volumerendering.html
- Human Reference Atlas: https://humanatlas.io/3d-reference-library
- 电视剧构图参考: https://the-good-doctor.fandom.com/wiki/Intangibles

医学资产为Browne与Schlehlein（2024）的CC BY 4.0数据，Three.js为MIT，原生Freeciv仍为GPL-2.0-or-later。逐模型DOI、原始元数据和显示改编说明在console/assets/medical/ATTRIBUTION.md与对应metadata文件中，页面保留署名。

## 游戏

- 保留原Freeciv GTK客户端、服务器、地图、原生战斗/招募/收入/四兵种/双人轮战规则。
- 可吸附目标改为两侧大卡片，每页最多8个，加底部“更多目标”。当前战役24个候选分3页，没有为了拉开距离删掉移动/招募候选。1920×1080最终实测最小中心间距175px。
- 地图小编号对应侧栏目标；编号只是注释，不加入吸附候选。当前选中的卡片连到原地图位置，避免密集地图点直接竞争。菜单改为不对称大间距布局，进入战役保持全屏。
- UDP携带真实卡片尺寸、标签和原地图锚点，原nonce/序号与五种输入动作保持。kind14仅为现有确认动作中的目标分页。
- 实机发现并修复原启动器以root运行Freeciv服务器的问题：由既有linaro用户启动，保持CPU0/1亲和性。无需另启动模型或采集实例。

## 验证与限制

最终HMI板端完整回归257通过、1跳过；眼控/锁定点/聚焦相关既有测试保留。医学三页实际浏览器/WebGL显示，已验证结构点击、翻页、放大、旋转、整体恢复及真实回执，保存1920×1080板端画面。

原生ARM64游戏实际启动战役，遍历3页、24个目标；进入招募后确认四种兵种候选存在，并执行一次真实生产切换，收到服务器状态变化。使用原UDP协议的合成坐标进行软件联调，不能当作真人眼控精度或完整新战役通关证据。本轮未重测双人真实交接或四手误触率。

旧Meson缓存含另一个工程绝对路径；首次ninja反复再生后停止，没有算作构建成功。最终使用当前工程的GUI主文件实际编译命令和客户端链接命令完成ARM64构建，准确命令留存在game_v51_compile_commands.json；不宣称干净全量重编译上游所有源文件。

## 文件与恢复

最终HMI源文件表：V51_CURRENT_SOURCE_MANIFEST.json。游戏源文件表：GAME_V51_CURRENT_SOURCE_MANIFEST.json。最终二进制SHA见game_v51_final_build.log，维护分支及提交见game_commit_v51.log。部署前副本分别保留hmi_v51_previous、hmi_v51b_previous、hmi_v51c_previous与game_v51_previous；恢复源码时使用对应发布阶段，不把阶段补丁清单当最终总表。

回退医学/启动器需停止其应用适配器，按备份恢复变更文件并重启engine/console/adapters；游戏恢复原menu、demo_control与二进制三件套。无需回退或重刷FPGA。本轮八项服务最终状态与原生owner连续性见runtime_v51.json。

确认手无限次重复、完整真人/两人四手验收、P6、compat-up与DMA长期恢复等历史范围仍按WORK_PLAN_v17与最新总账保留，本次不将其计为完成。

## 最终短窗口并行观测

当前自然场景、已有模型服务运行，每场景6次只读采样；并非单人/双人四手压力矩阵，也不是图形渲染FPS。

| 前台应用 | 模型图像交付Hz | MIPI场景包/s | 全CPU归一负载 | NPU0忙碌率 | NPU1忙碌率 |
|---|---:|---:|---:|---:|---:|
| 医学3D静态首页 | 40.8–41.0 | 29.0–30.0 | 46.8–52.8% | 38.0–41.0% | 0.0–2.0% |
| 原生战场 | 40.6–41.8 | 29.7–30.0 | 51.4–58.2% | 38.0–41.0% | 0.0–2.0% |

两组显示协议错误增量均0。唯一native owner PID2708、硬件epoch13349717123306135891及native二进制SHA保持；八项服务运行。未测GPU帧率或功耗，不据此宣称节能或长跑DMA已修复。
