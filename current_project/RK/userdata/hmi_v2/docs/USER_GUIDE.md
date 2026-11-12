# 使用与验证

> **2026-10-25 更新：当前操作请读 [USER_GUIDE_CURRENT.md](USER_GUIDE_CURRENT.md)。以下为附件原说明，保留用于追溯，不能代表当前部署、UI11 配对及多人功能状态。**

## 当前交付范围
这是本地整合候选源码。Windows 单元测试、ARM64 交叉编译和 RTL 仿真有证据；没有执行 RKNN 真机推理、X11 真机交互、物理屏幕或真人标定验收。TD 完整构建的实际结果见 FPGA_BUILD_STATUS.md。不能把交叉编译成功当作上板成功。

## 目录
- `board_root/userdata/hmi_v2`：统一运行入口、冻结算法/权重、新服务、测试和文档。
- `board_root/userdata/freeciv-g03-v12-candidate_20261024`：原游戏源码、场景和资源；新运行服务仍调用原协议。
- `workstation/fpga_skill/projects/hmi_v2_fpga`：原工程副本、新 CSR 和显示叠加层、仿真及 TD 构建入口。
- 发布包内 `rollback/`：完整原项目的无损归档，用于恢复历史代码，不参与新运行时。

## Windows 本地复查
在 hmi_v2 目录运行：
```powershell
python tools/hmi verify
python tools/local_check.py
python tools/cross_build.py --zig <zig.exe 的路径>
python tools/compare_numerics.py --baseline <原项目完整提取目录>
python tools/check_web.py --browser <Edge或Chromium路径> --node <node.exe路径>
```
交叉编译保留 `-Wall -Wextra -Werror`。`fpga_io`、`libring.so` 是 ARM64 Linux 文件，不能在 Windows 执行；ring_test.dll / panel_test.exe 专用于 Windows 单元测试。

在 FPGA 工程目录运行：
```powershell
python validation/run_hmi_sim.py --modelsim D:/Modelsim/soft/win64
python prepare_build.py
E:/qianrufpga/TD/bin/td_commands_prompt.exe E:/路径/hmi_v2_fpga/build_direct.tcl
```
TD 的脚本参数使用正斜杠。搬迁后必须先运行 prepare_build.py，重新审计文件/引脚及生成带 hash 的构建清单。

## 以后上板的步骤（本次未执行）
1. 正常停止原 owner/relay/视觉链路，保留原 FPGA 位流及恢复资料；不要让两套硬件所有者并行。
2. 将 hmi_v2 放到 `/userdata/hmi_v2`；原游戏路径已在板上存在时不覆盖。在原 Python 环境安装 requirements.txt 的新增依赖；原 RKNNLite、OpenCV、MediaPipe、scikit-learn、pygame 等仍需存在。配置 `paths.python` 指向该解释器。
3. 执行 `python tools/preflight.py`。此命令只检查依赖、节点、X11；不打开设备、不加载模型。
4. `sudo <配置的 python> tools/hmi install` 安装服务文件，**不启用开机自启**；`sudo <配置的 python> tools/hmi up` 等待有效首帧及八项心跳。若没有首帧或健康服务，启动失败并顺序停服。
5. 默认 `mipi.csr_enabled: false` 可继续用原显示 ABI。只有新位流经本地构建和 SRAM 上板回归后才设为 true；C 侧还要求 `0xCF0=0x55493130`，不向未知 UI 寄存器提交。
6. `hardware.panel_start: true` 在 C 所有者中执行原四步 panel 顺序，检查相机 ABI、空闲状态、读回及独立时钟监测。该功能只通过本地寄存器模型测试，首次上板需核验屏幕实际显示。
7. `python tools/measure.py --seconds 60 --output docs/evidence/board_bus.json` 收集真实总线源年龄和速率。再按 P8_REPORT.md 完成物理验收。
8. 停止：`sudo <配置的 python> tools/hmi down`。先适配器，再 engine/视觉，最后 C 所有者。SendSIGKILL=no 避免超时后强杀 DMA 所有者；若停机超时需诊断，不能继续启动另一个 owner。

## 操作
默认 DEMO + POINT + 单人。入座稳定后进入引导；保持居中、合适距离、睁眼，👍 开始标定。标定结束后 ✌ 评测或 👍 使用。☝ 唤醒，注视目标，✊ 确认并回待命；👎 返回，✌ 下一个，✋ 休眠，🤟 菜单。每次提交后必须中性释放至少 0.3s。

全局 F10 紧急待机，F5 菜单。恢复可在 `http://127.0.0.1:8766` 控制台操作，令牌位于 `/run/hmi/console.token`（0600）。标定窗口保留 R 重标定、V 评测、空格使用/开始；F6/F8 与原鼠标点击出口禁用。控制台写操作均需令牌。医学演示路径 `/demo` 沿用原 canvas 和图像。

进入 WRITE 后，✊/☝ 由原录制器处理，不执行桌面确认/唤醒。游戏 WRITE 默认无映射。第二人登记、K4 物理键、P6 新预处理不在本版已验收范围。

游戏源码包不包含已安装 GTK/SDL 系统环境及 ARM64 成品。需要时在板上运行原 `build-rk3576.sh`；缺失原生成文件时先按原 DEPLOY_RK3576.md 补齐。Launcher 找不到游戏二进制会明确报告，不能伪称已启动。


## 2026-10-28：确认手取消、重复与撤回

轨迹仍用操作手握拳结束。另一只手张掌入镜后，握拳确认，拇指向下取消待确认指令；已经张开的手不必重复张掌。

收到实际执行成功回执后，保持确认手在画面中。再次张掌→握拳重复上一指令；再次张掌→拇指向下撤回刚才一轮。每次重复都独立执行、等待回执。离镜超过短检测间隙即结束连续操作。

医学演示的撤回恢复本轮前的完整视图并停止旋转；不越过其他操作撤回。桌面只向执行本轮动作的同一窗口发送 Ctrl+Z，能否撤销由该应用决定。原生游戏已提交的移动、战斗及回合暂不支持撤回，收到拒绝提示时棋局未改变。
