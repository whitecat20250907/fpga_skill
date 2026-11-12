# 8类轨迹手势：RK3576迁移

2026-10-21。来源 `D:/8类手势快捷键`，四份原始文件原字节保存在 `original/`。
用户本次明确只要求迁移并运行模型，暂不绑定快捷键。

已部署：`/userdata/gesture8_rk3576_20261021`。
模型保持原7912个参数，八类顺序为 `0, L, L_rev, L_up, L_rev_up, M, W, Z`。
使用 RK3576 NPU 的 FP16 RKNN 分类器，不在板端运行 PyTorch 分类。
MediaPipe手部检测使用CPU；复用现有官方资产和原app28 PCIe共享RGB，不新开摄像头。

## 运行

先核实当前原主程序PID；以下118016仅是本轮实测值。

```sh
cd /userdata/gesture8_rk3576_20261021
sh start-rk3576.sh --model-pid 118016 --seconds 60 --output evidence/manual_01
```

输出目录必须不存在；`--seconds` 为1至300秒，默认30秒；`--fps` 为2至8，默认6。
无需桌面窗口，结果打印到终端并保存JSONL，完成的轨迹保存28×28 PNG。
Ctrl+C或SIGTERM只停止本进程，正常释放自己的MediaPipe/NPU和预览读端。
不自启、不发游戏事件、不发系统按键。当前已结束有界测试，没有留下手势后台进程。

操作：先松开拳头或暂时移开手，连续握拳3张新帧→向上指2张新帧→画轨迹→握拳3张新帧结束。
分类概率至少0.60才标为accepted；冷却1.2秒后要求再次中性释放。
不要求分类结果必定为训练集中某个有效快捷键：低置信、短轨迹、过期结果会拒绝。

八类方向采用原demo镜像视图：共享图像不做整帧翻转，食指x坐标只镜像一次，保持图像宽高比。
实际MediaPipe在镜像/非镜像输入下的检测等价性未验收；本人画各方向的效果仍需实测。
初始多手不进入记录，记录期间按腕点连续性和可信左右手标签关联；歧义、丢失、超时取消。
腕点/左右手关联不是生物身份验证，不能保证同侧两个人的手交换时仍能识别身份。

## 与现有系统共存

- 与五动作采样器使用同一个 `freeciv-rk3576-gaze-demo/logs/gesture.lock`，防止重复手部推理。
- 使用现成 app_venv 的MediaPipe/RKNNLite依赖，没有安装/升级主环境中的任何包。
- NPU实例只在一条轨迹结束时推理；MediaPipe循环不重复运行轨迹分类网络。
- 如果原主/采集进程身份变化，预览读端退出，不自动拉起或接管任何相机。
- 帧序号来自实际采集metadata，源时间保持CLOCK_MONOTONIC；重复帧不增加确认次数。
- 此独立观察入口暂不同时向孪生发布关键点；后续整合应把现有MediaPipe结果直接交给 `TrajectoryRecorder`，不另开识别器。

## 实测

| 检查 | 结果 |
|---|---|
| 原PyTorch→ONNX | 26组输入，最大logit差4.292e-6 |
| RK3576真实NPU→PyTorch | 26/26分类及0.60接受决策一致；最大概率差0.002848，小于预设0.005门槛 |
| NPU分类耗时 | 首次之外25组，中位2.092 ms，P95 3.894 ms；含输入处理与softmax，不含手部推理 |
| 轨迹栅格 | 120组与原函数逐像素一致 |
| 状态机与预处理 | 8项主机测试通过 |
| PCIe共享画面 | 30.099秒，168帧，约5.58次/秒；陈旧/重复/非法帧均0，忙锁11次跳过 |
| 该轮资源 | CPU 78.18%单核，最大RSS216.32 MiB |
| 主程序保留 | boot、主程序/采集出生ticks一致，7项本地/板端源码与模型哈希一致；后续CSV仍新鲜 |

本轮共享画面没有完成轨迹，实际轨迹触发NPU次数0；上面的26次NPU验证来自独立合成测试输入。
这不是本人8类准确率、真人绘制成功率或完整并行性能验收。源JSON的val_acc=0.9487属于原训练元数据，未带验证集，不能作为本次板端实测准确率。
3×3下采样的预览读端沿用项目现有实现。6Hz左右的关键点采样可能漏掉快速笔画，需真人数据决定是否提高采样率，不能用插值伪造新的识别帧。

证据：`model/manifest.json`、`model/npu_validation.json`、`evidence/live_shared_v1/`、`evidence/runtime_after.json`、`evidence/local_tests.json`。
静态RKNN模型的dynamic-range查询警告已保留；本轮实际inference和数值门槛均通过。

## 复现与恢复

`build_model.py` 在既有 `/userdata/gaze_model_migration_v1_20261014/venv/bin/python` 工具链运行。
输出model目录必须不存在，避免覆盖已验证模型。它仅从原脚本AST提取GestureNet定义，`weights_only=True`加载权重，保留原类别顺序、/255、LINE_8及padding。
`validate_npu.py` 用现有app_venv执行，读取固定vectors并实际调用RK3576 NPU，没有CPU回退。
停止本次独立进程即可退出新功能；原app28、相机位流、Flash、NPU注视权重、游戏入口均未替换。
