# RK3576 可选 MediaPipe 手势模块

**2026-10-22 双核与解除限帧更新：** 当前主程序为 app33，手部包为 `/userdata/npu_dualcore_20261022`。两个独立 NPU ROI 实例自动跨核处理最多四手，人脸固定 Core0、MGaze 固定 Core1。手部、轨迹入口和特征发布默认 FPS=0（不限速），共享画面生产者也取消原20Hz限制；界面重绘独立限速。固定照片复测：仅单手56.20、双手42.60、四手21.52批/s；一人双手眼动27.36/手部22.99，双人四手13.35/11.31。每个四手批次含全部四手；不是真人同帧端到端FPS。新入口为 `/userdata/npu_dualcore_20261022/run_hands.py`，仍可选、不自启、不发送动作、不映射八类轨迹快捷键。详见[双核实测报告](C:/qianrushifpga/fpga_skill/projects/npu_dualcore_20261022/TEST_REPORT.md)。下面app32与10Hz描述是前一版本历史。

**2026-10-22 更新：** 当前默认已改为 RK3576 NPU FP16，使用六模型迁移包中的手掌、21 点、嵌入和分类头；不再默认构造 CPU MediaPipe 神经网络。最大 4 只手，主程序默认 app32，启动脚本使用已有 `app_venv` 的 RKNNLite，手部目标 10 Hz。仍共享同一 PCIe 预览、不自启、动作发送默认关闭；多手时不猜测游戏操作者。双人四手图片压力测试中，四手整批约 8.97 Hz，双人眼动整批约 14.35 Hz；真人身份/校准/动态使用仍待验收。转换脚本、权重和完整条件见[迁移测试报告](C:/qianrushifpga/fpga_skill/projects/all_models_npu_20261022/TEST_REPORT.md)。四路独立轨迹入口为板端 `/userdata/all_models_npu_20261022/run_hands.py`，八类轨迹不绑定快捷键。下文 2026-10-20 的 CPU、app28、3 Hz 和初版结果均为历史记录；动作语义和安全门控仍保留。

2026-10-20，按用户新增授权部署。官方实现：[MediaPipe](https://github.com/google-ai-edge/mediapipe)、[Python Gesture Recognizer](https://developers.google.com/edge/mediapipe/solutions/vision/gesture_recognizer/python)。原视线继续使用 RKNN NPU；本模块使用 **CPU**，独立环境为仓库内 `.gesture-v1/venv`，没有更改原 app28 环境或驱动，没有打开 USB/CSI/V4L2 摄像头，也没有配置自启动。

模块通过另一个进程的只读描述符，读取已运行 app28 的同一 PCIe RGB 预览。非阻塞记录锁、提交字、完整头部、单调帧号和源时间共同检查画面，锁忙便丢帧。只在锁内复制 640×360 RGB，推理在锁外进行；模型/采集进程退出或更换时立即终止，不自动重连和重启主程序。

## 首版五种手势

| 手势 | MediaPipe 标签 | 动作 | 最短保持 |
|---|---|---|---:|
| 食指向上 | Pointing_Up | 唤起 | 0.4 秒 |
| 握拳 | Closed_Fist | 确认 | 0.6 秒 |
| 拇指向下 | Thumb_Down | 取消 | 0.4 秒 |
| V 字 | Victory | 下一部队 | 0.4 秒 |
| 拇指向上 | Thumb_Up | 结束回合 | 0.8 秒 |

置信度至少 0.70，且至少三张新画面满足保持条件。默认 3 Hz，因此实际触发时间还受采样间隔影响。触发后需移开手，或保持模型明确识别为 `None` 的中性姿势至少 0.3 秒，才能再次触发；直接切换姿势不会连发。低置信度抖动不算释放。源帧到结果超过 350 ms 时不发动作，超过 750 ms 的帧间断清除未完成保持。

初始上电也需先释放一次。已经唤起时重复唤起被阻止，休眠时不发送确认。游戏负责动态中心吸附、陈旧视线拒绝、命令执行和确认后休眠；手势模块不提供坐标，不控制系统鼠标。事件编号先与游戏读回的全局编号同步。

旧 `input_bridge.gesture()` 是另一套未启用的示例映射；本模块以 `gesture_control.py` 和上表为准。张掌样例只得到 0.603，低于保护阈值，因此没有为了接受张掌而降低阈值。五个实际采用的标签在板端官方静态样例中均超过 0.70；这不是用户本人识别准确率。

## 当前板端启动

先让原 app28 和游戏按原命令正常运行。仅观察识别结果：

```sh
cd /userdata/freeciv-rk3576-gaze-demo
sh start-gestures-rk3576.sh
```

明确开启游戏动作：

```sh
sh start-gestures-rk3576.sh --send-actions
```

Ctrl+C 仅退出此手势进程。默认绑定 CPU4、nice 15、空闲 I/O 优先级；可用 `GESTURE_CPU`、`GESTURE_FPS`、`APP_DIR` 指定已有环境。锁防止同时启动两份手势模块。日志保存在此次打印结果对应的 `logs/gesture-时间-PID/`，包括 `samples.jsonl`、`ready.json`、`result.json`。可以添加 `--seconds 30` 做有界测试。

默认主程序尚未替换为 `tools/run_main_with_freeciv.py` 包装入口。真人视线与手势一起玩仍需正常退出原主程序后，按 `INPUT_PROTOCOL.md` 启用可选包装入口并完成个人标定。当前用户已要求延期真人验收，不能声称已经完成真人控制。

## 安装、维护与回滚

本板已安装成功，无需再安装。新板可在仓库目录执行：

```sh
python3 tools/install_gesture_rk3576.py --prefix "$PWD/.gesture-v1"
```

仅允许 ARM64 的 `/userdata` 独立目录，已有目录拒绝覆盖。依赖锁定在 `requirements-gesture-rk3576.txt`，官方 MediaPipe 为 0.10.18，CPython 3.11 ARM64 wheel 的 SHA256 为 `a251c9abde6d75534adcdc814e1d7853fa04774558600e29af51a7600eaa5b65`。模型是官方 float16 version 1，SHA256 为 `97952348cf6a6a4915c2ea1496b4b37ebabc50cbbf80571435643c455f2b0482`。

官方示例仓库固定到 `1675dd30f602848d0674de5c88dbc395f0877e59`；示例和 Apache 许可证保存在 `.gesture-v1/assets/`。本板安装时 GitHub API 连接超时，依赖及模型已完成；随后经工作站下载、传输并核对官方源码/许可证 SHA，生成 `installation.completed.json`，原失败 `installation.json` 保留。若遇同样失败，只在完整传入并验证这两个固定源码文件后运行安装器的 `--complete-provenance`，不重装或覆盖原主程序环境。

升级前退出手势模块，保存 Git 修改，在新版本独立环境验证后再切换。回滚只需 Ctrl+C 退出手势模块，游戏和原视线主程序继续使用原入口；没有默认环境或开机项需要回退。若需要回退模块代码，使用旧提交的新工作树，禁止 reset/clean 覆盖修改。新板全新安装和 Git 工作树回滚命令尚未专门执行。

## 实测边界

RK3576 上完成 6 张官方样例推理、五个采用标签的置信阈值检查、真实 PCIe 共享画面推理、UDP 几何回复、无手误触发检查，以及新手势策略→真实游戏五动作测试。动作测试输入是软件标签与测试视线；完整战斗仍依据原先两次真实板端胜利记录。Linux 共 27 项检查通过，其中新增手势策略 11 项、memfd/多进程锁及主程序入口识别 6 项；可选视线包装入口尚未实际替换原主程序。

最后 15 秒共享画面测试处理 41 帧，136 次 UDP 查询均收到回复，0 个动作、0 个过期结果，约 207 MiB 峰值 RSS、单核 CPU 34.32%。这是当前无脸、无手场景的短时结果，不能替代真人手势、视线标定或真人 NPU 并行延迟。详细 A/B 和限制见 `BOARD_TEST_REPORT.md`。验收后已退出辅助手势进程，未留下后台常驻任务。
