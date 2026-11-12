# 项目特征与三维数字孪生

目标界面展示手部、头部、双眼和控制质量。通用灰度/卷积示意已退出当前主界面验收。
`project_features.py` 复用现有 MediaPipe GestureRecognizer 的图像与世界 XYZ、手势结果，以及现有人脸对齐结果。
`project_twin.py` 将真实 XYZ 投影为关节、掌面、头部轮廓、眼部与虹膜图形；掌面/手指厚度属于可视化几何。
人脸坐标为模型相对坐标，不能当作标定后的真实尺寸。手、脸各自保留源时间戳和有效期，丢失或超过 350 ms 后清除姿态。

手部已在现有 PCIe RGB memfd 上进行实际 30 秒和 10 秒采样。未另开摄像头、USB、NPU 模型或自启服务。
10 秒复测约 5.90 样本/秒，手势任务 CPU 67.92% 单核、RSS 205.87 MiB；只读渲染器 CPU 17.59% 单核、RSS 38.63 MiB。
缓存静态中文背景后平均绘制从 42.36 ms 降到 9.26 ms；两个窗口条件和时长不同，不是严格的真人运动性能对照。
测试没有识别到手/脸，不能据此验收非空动作、头眼跟随或本人时延。
官方手势图像的真实 RK 推理 XYZ 已离线渲染并标为“离线夹具 / 非实时”。

在现有主程序保持运行时，手部只读输出可选地开启：

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 taskset -c 4 nice -n 15 \
  .gesture-v1/venv/bin/python tools/run_mediapipe_gestures.py \
  --app-dir /userdata/gaze_model_migration_v1_20261014/app_v28 \
  --model-pid <实际主程序PID> --seconds 30 --fps 6 --feature-port 29802 \
  --output logs/<未存在的采样目录>
```

先运行 `tools/run_project_twin.py --seconds 36 --output logs/<新预览目录>` 接收，`--show` 是 RK 预览窗口。
人脸出口 `tools/run_main_feature_export.py` 是可选包装入口，尚未替换当前主程序；正式切换需沿用现有锁、模型、参数及生命周期恢复流程。
FPGA MIPI 屏的新特征渲染、传输、实际手/头/眼跟随与主程序共存仍在待办中，RK 预览和离线样例不签这些项目。
