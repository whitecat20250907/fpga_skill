# Freeciv · 边境要塞

2026-10-21 项目版新增 **开始页面、单人扩展战役和同一块 RK3576 的双人轮战**。
默认 `sh start-rk3576.sh` 先进入开始页面，选择模式后显式唤起、确认“开始”；关闭一局后回到开始页。
双人双方使用独立的原生军队、城市和国库，结束行动后遮住地图，由下一位重新唤起并确认交接。
2026-10-23 冻结版已在RK3576实测通过单人完整原生胜利、同机两Human完整战斗与24次交接、终局返回开始页。真人视线/手势联合验收与两位真人标定仍待完成，详见板端报告顶部和固定SHA的验收JSON。
新开始页使用 Linux GTK 3 / PyGObject；下面的 Windows 运行包与旧整局记录属于历史版本，当前源码 Windows 可显式用 `--direct` 维护入口，未签新开始页的 Windows 验收。

当前玩法与实测见 [CAMPAIGN_V2.md](CAMPAIGN_V2.md)、[BOARD_TEST_REPORT.md](BOARD_TEST_REPORT.md)。
项目手/头/眼可视化见 [PROJECT_TWIN.md](PROJECT_TWIN.md)。

2026-10-21 算法更新：实际游戏目标现采用按源时间衰减的支持度、领先差距和持续确认；模型输入不再重复平滑，重复/过期帧及丢跟踪不能确认。已完成ARM构建与7项真实游戏保护条件/单次移动检查，见[语义吸附优化报告](SEMANTIC_SELECTION_20261021.md)。真人标定与误吸附率仍待实测。

基于 Freeciv 3.2.6 原生 GTK 3.22 客户端、服务器和 classic 规则改造的离线军事演示。单张 24×40 等距地图，开场已有城市、军团、骑兵、投石车和守军。战斗、行动力、生产、金币、城市占领都由原游戏规则执行。

## 从 GitHub 迁移

仓库包含完整修改源码，无需 Git 子模块或再次下载上游。板端执行：

```sh
git clone --depth 1 https://github.com/whitecat20250907/freeciv-rk3576-gaze-demo.git
cd freeciv-rk3576-gaze-demo
sh build-rk3576.sh
python3 launch.py --build build-arm64
```

- [端侧助手可直接使用的完整 prompt](PORTING_PROMPT.md)
- [RK3576 部署、验收、更新与回滚](DEPLOY_RK3576.md)
- [Windows 已测项目与尚未验证项](TEST_REPORT.md)
- [RK3576 实机验收、性能及当前联动边界](BOARD_TEST_REPORT.md)
- [可选 MediaPipe 手势部署、五种映射与实测限制](GESTURE_RK3576.md)
- [Windows 运行包下载](https://github.com/whitecat20250907/freeciv-rk3576-gaze-demo/releases)

默认单任务编译；已有依赖可用 `SKIP_APT=1 sh build-rk3576.sh` 重建。游戏需要图形桌面，SSH 无显示环境时不能直接完成窗口试玩。原始 `freeciv-demo.patch` 为首次修改的来源记录；维护应编辑仓库内实际源码。

## 本机启动

Windows 运行包解压后双击 `Start-Windows.cmd`。需要 Python 3（仅使用标准库，无 pip 依赖）；游戏所需 DLL 已随包提供。关闭游戏窗口会关闭本次本地服务器。再次启动会重新开始固定场景。

开发目录可执行：`python launch.py`。

## 只用五个键

| 按键 | 对应手势动作 | 用途 |
|---|---|---|
| F1 | 唤起 | 显示当前可操作目标的圆环，再按一次退出选择 |
| Space | 确认 | 执行当前吸附目标，随后视线回到休眠 |
| Esc | 取消 | 关闭选点或城市栏 |
| Tab | 下一部队 | 快速切换仍可行动的部队 |
| Enter | 结束回合 | 让对方行动、恢复行动力并推进生产 |

本机试玩时，**移动鼠标模拟视线位置**，F1 唤起后圆环会吸附到目标中心，再按空格确认。鼠标左键不会执行地图动作。无需把光标精确放在地块中心；模型坐标进入相应目标的距离优势范围即可。普通注视不会移动或攻击。

选点有短时间平滑、切换滞回和确认阈值。候选边界附近不能明确区分时，稍微移向希望选择的目标再确认。圆环是游戏内的吸附指示器，不移动操作系统鼠标。

## 展示路线

1. 骑兵向东推进，攻击城外守军；军团向城堡方向推进。
2. 行动力耗尽后按 Enter。也可用 Tab 切换其他部队继续操作。
3. 唤起后选择己方 Westwatch 城市，选择军团或骑兵生产。进入第二回合以后，可以按费用用金币加速，下回合获得增援。
4. 用军团攻击 Border Keep。击败守军后，再移动进入城堡完成占领。
5. 占领后按 Enter 结算。本机完整测试在第 4 回合占领、第 5 回合结算胜利；战斗保留原版随机性，具体损失和回合数可能变化。

两分钟展示可覆盖选部队、移动、攻击、增援和结束回合。熟悉后再演示整局占领；不用展开科研、外交、工人改地和帝国管理菜单。

## 视线/手势接入

见 `INPUT_PROTOCOL.md` 与 `input_bridge.py`。游戏监听本机 UDP 29778；原推理程序发送归一化地图坐标与五种离散事件即可。游戏不运行摄像头、模型或浏览器。

## RK3576

源码包内提供 `build-rk3576.sh`，针对 ARM64 Debian/Ubuntu 的 GTK 3 桌面环境：

```sh
sh build-rk3576.sh
python3 launch.py --build build-arm64
```

首次需要下载编译依赖并编译，之后直接启动。Windows 的 `.exe` 不能复制到 Linux 运行。源码使用跨平台 GTK/GIO/Cairo，关闭音频、额外工具和 SVG 旗帜；不依赖 NPU、WebGL 或独立显卡。

本维护分支已在 RK3576 完成原生构建、两次完整战斗、三种状态单独/并行资源采样，见 [板端报告](BOARD_TEST_REPORT.md)。板端日常启动可用 `sh start-rk3576.sh`。真人视线、原手势和真人 NPU 延迟仍需联调，不能把 UDP 测试坐标视为模型联动通过。原始 Windows 记录保留在 `TEST_REPORT.md`，新维护修订尚未重新进行 Windows 整局试玩。

## 来源与许可

- Freeciv 官方源码与下载：https://www.freeciv.org/download.html
- 官方项目：https://github.com/freeciv/freeciv
- Debian ARM64 支持：https://packages.debian.org/bookworm/freeciv-client-gtk3

保留 Freeciv 的 GPL-2.0-or-later 许可及原素材归属，修改源码随源码包提供。Windows 依赖的许可在 `licenses/` 中。本包是短场景改造，原版完整菜单不属于演示操作流程。
