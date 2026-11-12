# RK3576 全模型 NPU 迁移（2026-10-22）

本目录保存原始 TFLite 权重、转换后的 ONNX/RKNN、自编转换器、部署适配器和实测证据。详细性能与限制见 [TEST_REPORT.md](TEST_REPORT.md)。

六个原先运行的 CPU 网络改为 RKNN FP16：BlazeFace、478 点脸部、手掌检测、21 点手部、手势特征嵌入和静态分类头。MGazeNet、8 类轨迹保留原 RKNN。Blendshape 原本关闭，仍关闭；附带实验转换结果不纳入全 NPU 运行承诺。

## 转换与复验

脚本针对本目录 `source_manifest.json` 中的固定模型，不是任意 TFLite 的通用转换器。不改变学习权重，不采用 INT8，不需要编造校准数据。ARM64 Toolkit 2.3.0 不支持本机直接导入 TFLite，因此采用 TFLite → 自编静态 ONNX → RKNN。

在板端独立工作目录运行，原程序环境不变：

```sh
# 原 task 包存在时可重新提取；交付目录已包含提取后的模型。
python extract_models.py
/userdata/gaze_model_migration_v1_20261014/venv/bin/python build_all.py
/userdata/gaze_model_migration_v1_20261014/app_venv/bin/python validate_all.py
/userdata/gaze_model_migration_v1_20261014/app_venv/bin/python profile_placement.py
```

编译依赖 RKNN Toolkit 2.3.0、ONNX、ONNX Runtime、NumPy、FlatBuffers；`tflite_schema.py` 是已安装 MediaPipe 所带的生成文件，来源哈希见 `schema_provenance.json`，随附 `MEDIAPIPE_LICENSE`。参考执行器是工作目录 `reference_packages` 下隔离安装的 `tflite-runtime==2.14.0`（ARM64 wheel），只用于数值对照，不参与部署推理。每个模型使用独立编译子进程，避免 2 GB 板端同时编译导致内存峰值叠加。

`models/*.build.json` 记录原权重和目标权重 SHA256；`*.onnx_validation.json`、`*.npu_validation.json` 是实际数值结果。部署 `sync_package.py` 必须通过最终权重哈希、数值检查和六个模型的算子放置检查。`placement/*.txt` 是 RKNN C API 性能明细，而不是仅凭 `.rknn` 后缀判断执行端。

`build_results.json` 和早期日志保留了首次构建过程；最终权重以各模型 `*.build.json`、最终验证和 `benchmark_release` 内绑定的哈希为准。

## 运行

板端新主程序为 `/userdata/gaze_model_migration_v1_20261014/app_v32_npu_20261022`，独立模型包为 `/userdata/all_models_npu_20261022`。原 app30 保留，默认启动器改为 app32。模型失败直接报错，不自动转回 CPU。

脸部上限 2；每张脸有独立眼部质量门控，一次 MGazeNet 推理使用该人的脸、左眼和右眼。额外人物输出写入 `/dev/shm/gaze_npu_people_<PID>.json`，只有当前主人物进入既有个人校准和光标路径。空间跟踪 ID 不代表身份验证，不声称完成两个人独立校准。

共享预览手部入口可同时识别至多 4 只手，一次手部推理结果同时供应静态手势和四路独立轨迹状态；不打开第二个相机，不发送游戏动作：

```sh
/userdata/gaze_model_migration_v1_20261014/app_venv/bin/python \
  /userdata/all_models_npu_20261022/run_hands.py \
  --seconds 30 --fps 10 --output /home/linaro/pcie_fix_20261003/hand_run_unique_directory
```

手部是可选消费者，不设为后台自启。既有游戏静态手势入口与旧轨迹入口也默认使用 NPU，并共用 `gesture.lock` 防止重复运行。旧单笔轨迹入口遇到多手拒绝混用；四笔独立跟踪使用上面的统一入口。八类轨迹尚未绑定快捷键，符合用户要求。

`lifecycle.py`、`request.py`、`prepare_app.py`、`promote_launcher.py` 是这次部署的审计脚本，包含明确的旧版本和状态路径，不应不加检查地重复执行。当前运行实例以仓库 `CURRENT_CAMERA.json` 和本目录最终选择证据为准，不能复用历史 PID。

## 证据范围

`benchmark_release`：最终权重下 11 种板端真实推理组合；固定图片重复输入，不是双人现场动态测试。

`fixture_final`：官方样例与双脸/四手拼接图；原 TFLite 和新 NPU 对照、关键点叠加图。`evidence/no_cpu_networks.json`：禁止构造 CPU 神经网络后，仍能完成两脸眼动及四手推理。

`live_v1`、`evidence/lifecycle`：真实 PCIe 相机共享预览、主程序正常退出、原生采集清理和最终运行状态。无人脸/手的运行不用于声称真人性能。

预处理、ROI、NMS、坐标变换、平滑、跟踪、游戏规则仍在 CPU。这些是小规模控制与几何计算；“全 NPU”限定为当前启用的神经网络计算。
