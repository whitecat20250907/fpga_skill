# 最新项目入口（2026-11-12 同步）

完整算法、模型权重、医学/游戏应用、FPGA 源工程及最终位流位于 [`current_project`](current_project/README_代码包说明.md)。项目 FPGA skill 位于 [`skills/anlogic-td-demo-reuse`](skills/anlogic-td-demo-reuse/SKILL.md)。

请先读 [最终交接文档](docs/眼手协同医学交互_最终交付与新会话交接_20261105.md)。历史工程/待办记录不是要求重新执行的任务；当前部署基线是 765 位流、匹配的 720 主机补丁和 920 显示/自启动版本。代码包的逐文件来源与 hash 见 current_project/SOURCE_MANIFEST.json。

此次仅同步源码与 skill、整理本地存储，没有修改开发板程序。个人凭据、软件许可证、环境、构建数据库和运行日志不上传。

---

# 安路 PH1A90 / RK3576 FPGA 工程与复用 Skill

平台：MLK-AFH03/AFC03、PH1A90SEG324 -2、VID005、IMX415、7 寸 DSI 屏，安路 TD 6.2.2.200067 Release_2026.1_SP2。

本仓库保存六个历史上板成功例程、独立修订工程、赛题三六项基础功能、PCIe 图像修复工作和可复用 skill。发布整理日期为 2026-10-06；硬件状态依据截至 2026-10-05 的实际记录，发布并不增加任何上板通过结论。

**尚未全部修复。** 当前 PCIe 源码为 10 候选 `0x56440a01`，完整构建中断、没有合格 10 bit；最近实际下载为 09，其完整时序通过，但视频 BAR 前置读取失败，未采集。RGB 颜色、紫绿条纹和最终双向图像仍待验收。按问题清单一次只修一项，先完成 #1。

## 从这里开始

- [任务和验证状态](TASKS.md)：六项基础功能、六个 demo 与 13 项修复队列。
- [完整新对话交接](docs/09_开发板修复_新对话完整交接_20261005.md)：接线、板端目录、版本、哈希、证据与继续操作步骤。
- [问题清单](projects/pcie_imx415_fix_20261003/reports/issue_queue.md)：每项根因、状态和完成条件。
- [TD、引脚和 IP 复用 skill](skills/anlogic-td-demo-reuse/SKILL.md)。
- [通过静态检查或历史实测的产物说明](artifacts/README.md)：不得将其都视为当前相机修复交付版。

## 目录

```text
examples/                         原六个成功例程的完整可复用源与 IP
projects/demo_repair_20261004/     RTC、DDR、CSI→DSI 修订副本
projects/t3_basic6/               六项基础功能分阶段系统与 RK 解码/推理工具
projects/pcie_imx415_fix_20261003/  CSI/ISP/PCIe/驱动修复候选、测试与证据
skills/anlogic-td-demo-reuse/       SKILL.md、参考、审计/完整克隆/构建脚本
docs/                             TD 教学、经验、规划与完整交接
tasks/                            最新项目方案与赛题附件
artifacts/                        选定 bit、压缩 CMA64 boot 与哈希/状态
records/                          原始来源、进度和复用记录
EXPORT_MANIFEST.json               本地来源、逐文件 SHA256 与导出范围
```

原作者版权声明和加密 IP 文件保持原样，参见 [第三方说明](THIRD_PARTY_NOTICE.md)。TD/ModelSim 安装包、工具许可、仿真缓存和大型中间数据库不属于此源码发布包。相机实拍原图与原始串口会话留在本机，已发表的报告保留结论和相关哈希。关键通过/失败的文本日志和源快照保留，不能把导出精简当作验证结果改变。

## 在另一目录复用

先安装本机对应 TD、ModelSim 和需要的下载器驱动。把 `skills/anlogic-td-demo-reuse/` 复制到 Codex 的 skills 目录即可读取；其脚本只需 Python 标准库。

克隆并审计原例程：

```powershell
python ./skills/anlogic-td-demo-reuse/scripts/td_reuse.py verify --examples ./examples
python ./skills/anlogic-td-demo-reuse/scripts/td_reuse.py clone --examples ./examples --demo 06 --dest ../my_imx415_design
python ./skills/anlogic-td-demo-reuse/scripts/td_reuse.py audit --project ../my_imx415_design/fpga_prj.al
```

clone 使用完整源/IP/约束并重定位工程，目标必须是不存在的目录；不会自动下载。原 `.al`、历史报告和部分 Tcl 保留原本机路径，首次使用新位置应按 skill 审计/重定位，不能只双击旧作者绝对路径。参考 [构建工作流](skills/anlogic-td-demo-reuse/references/workflow.md)。

RK 工具的内核头、设备树、CMA、模型权重和设备编号必须按实际板卡准备。RKNN 模型路径记录在早期工程 README 中，权重未在本机此源目录内，不应将源码发布称为已附带全部运行时模型。

## 验证等级

“用户历史上板成功”“数字自检通过”“完整 TD/STA 通过”“bit 已下载”“最终连续实机验收”分别记录。旧位流的零差异回环不能认证新位流；生成 RGB 回环不能认证相机颜色；Wi-Fi/USB1 与 PCIe1 硬件互斥不能仅靠修改 boot.img 消除。

本仓库不包含第七个 10G 网络 demo。继续修复从完整交接的 #1 开始，再依次验收颜色、条纹、帧边界、模式切换、双向图像、恢复及剩余例程。
