# RK3576 迁移与维护

当前 2026-10-21 扩展版以 [CAMPAIGN_V2.md](CAMPAIGN_V2.md) 为启动与回滚入口。
默认启动会先显示 GTK 开始页，选择单人战役或双人轮战，确认开始后才创建本地服务器。
需要 `python3-gi python3-gi-cairo`；本板已有 GTK 3.24 的系统 Python 环境，未替换主程序环境。
下文“完整战斗已通过”指 10 月 19–20 日旧军事版，新版已测与未测以报告顶部为准。

## 状态和目标

原始 Windows 版已完成编译和整局试玩；本维护分支也已在 RK3576 的真实 X11 桌面完成 ARM64 构建、完整战斗及资源验收，范围和未测项见 [BOARD_TEST_REPORT.md](BOARD_TEST_REPORT.md)。真人视线、原手势与真人 NPU 并行延迟仍待验证。仓库包含完整源码，目标为有 GTK 3 桌面的 ARM64 Debian/Ubuntu；服务器启动成功不能代替可玩验收。

## 首次迁移

在开发板普通桌面用户下运行，源码目录不要使用 root 所有权：

```sh
git clone --depth 1 https://github.com/whitecat20250907/freeciv-rk3576-gaze-demo.git
cd freeciv-rk3576-gaze-demo
uname -m
cat /etc/os-release
free -h
df -h .
printf 'DISPLAY=%s WAYLAND_DISPLAY=%s\n' "${DISPLAY-}" "${WAYLAND_DISPLAY-}"
sh build-rk3576.sh
python3 launch.py --build build-arm64
```

本板的常规运行入口为 `sh start-rk3576.sh`，将游戏放在 CPU 0–3、nice 10、空闲 I/O 优先级下；不启动模型或摄像头。先关闭已有游戏实例再启动。

2026-10-20 新增、按用户授权部署的独立 MediaPipe 手势模块使用 `sh start-gestures-rk3576.sh`；默认仅观察，`--send-actions` 才向游戏发送动作。原视线继续使用 NPU，新手势使用 CPU，详见 `GESTURE_RK3576.md`。真人视线与手势联合验收仍待现场配合。

构建脚本只用 apt 安装构建依赖，不执行系统全面升级。默认单任务编译，减少 2 GB 板卡编译峰值；内存充足可用 `JOBS=2 sh build-rk3576.sh`。已装好依赖后用 `SKIP_APT=1 sh build-rk3576.sh` 重建。首次编译可能较久，保留终端日志；建议至少预留 3 GB 磁盘空间。

从 SSH 启动时，先查当前桌面会话和所属用户，沿用该会话的 DISPLAY/XAUTHORITY 或 Wayland 环境。不要猜测固定 DISPLAY=:0，也不要使用 `xhost +`。通过桌面终端启动是最简单的验证方式。

## 验收顺序

1. 记录 `git rev-parse HEAD`、系统、内存、桌面环境和编译结果。
2. 确认战场、中文提示、城市和部队正常显示，日志无致命错误。
3. F1 唤起，鼠标模拟视线，Space 确认后休眠；Esc 取消；Tab 换部队；Enter 推进回合。普通注视/点击不下达命令。
4. 完成移动、攻击、城市生产/加速、占领 Border Keep，结算并在服务器日志验证胜利。战斗含随机性，不能强行要求固定 4 回合。
5. 按 INPUT_PROTOCOL.md 接入 UDP 归一化地图坐标及五种事件。测试坐标中断超过 350 ms 后不能确认，重复事件不会重复执行。接入前对主程序做可回滚修改，沿用其真实手势定义。
6. 分别测试静置、选点和战斗，再测主程序单独运行与主程序+游戏同时运行。记录推理帧率/延迟和游戏输入体验；不能仅凭 Windows 数值判断预算。
7. 写 BOARD_TEST_REPORT.md，列出实测、失败和未测项目。没有实机画面/输入条件时明确停留在哪一步。

## 性能采样

在游戏已运行的另一个终端执行：

```sh
python3 tools/profile_linux.py --seconds 30 --output logs/perf-board-idle.json
# 唤起圆环后再采样，输出另一个文件。
```

脚本只读取本仓库启动的原生客户端与服务器 `/proc` 信息，不含 Python 启动器；RSS 汇总可能重复计入共享页。CPU 以单个逻辑核心为 100%，采样间隔内进程退出会单独标记。主程序性能应使用项目自身指标测量。

## 常见问题

- 无法显示窗口：先检查图形登录用户和显示会话；不要把游戏作为 root 后台服务。
- 中文方框：确认系统已安装 `fonts-noto-cjk`。
- 编译内存不足：保持 `JOBS=1`，先检查可用内存；不要未经用户同意更改系统 swap 或停止主程序。
- 缺少动态库：用 `ldd build-arm64/freeciv-gtk3.22` 和 `ldd build-arm64/freeciv-server` 查 `not found`。
- 端口占用：TCP 5557 为本地服务器，UDP 29778 为输入。用 `ss -lntup` 确认占用方，只关闭本项目的旧实例。
- 数据路径/场景错误：通过仓库根目录的 launch.py 启动，查看 logs/server.log 与 logs/client.log。
- GPIO/NPU 推理故障：与游戏构建隔离排查，不改驱动来修复游戏界面。

## 更新和回滚

维护前先 `git status --short`，将自己的修改提交到维护分支；不要覆盖用户改动。记录已验证版本的 commit。更新使用 `git fetch` 后检查差异，干净工作树可 `git pull --ff-only`，然后 `SKIP_APT=1 sh build-rk3576.sh`。关闭自己的旧游戏实例，再启动新版本验证。

回滚可在旁边新建工作树保留当前修改：`git worktree add ../freeciv-known-good <已验证commit>`，进入新目录重新构建。浅克隆缺少该提交时先获取对应版本。不要复用旧目录的二进制假装回滚成功。

完成维护后提交变更、更新测试记录和用户操作说明。公开报告前移除板卡地址、账号、令牌等环境信息；发布回 GitHub 需要用户已授权。
