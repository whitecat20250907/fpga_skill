# 原模型输入布局与当前 app23

用于 RK3576 NPU 推理反复打印 NCHW→NHWC 转换、图像拷贝和耗时排查。先核对实际模型每个输入的布局，不能把所有模型或输入一律改成 NHWC。

此原 MGazeNet 的输入顺序为 left、face、rect、right。三个 RGB 图像以 float32、/255、NHWC 连续数组提交，尺寸分别112、224、112；第三个 rect 保持 `[1,12]`，`data_format=['nhwc','nhwc','nchw','nhwc']`。右眼水平翻转、矩形请求值与裁切、通道、归一化和权重均保持。

app22 原先先转为连续 NCHW，运行时又转回 NHWC。app23 直接保留预处理产生的 NHWC，避免两次布局拷贝。仅改 `RKNNGazeEstimator.py`，其他102个运行文件保持；实际ARM采集程序仍为6e1d118f…，沿用app22的持久sigaction与幂等停止。

先验证值，再比较耗时：实际原模型16组输入、全部258维输出逐位相等；实际旧/新预处理24组覆盖RGB通道、右眼/边缘裁切、矩形12维及错误输入拒绝。不使用CPU替代NPU。

实际同一RK3576原模型ABBA交替，各80次，包含布局准备和inference：中位24.308→19.309ms，P95 32.965→24.919ms；转换警告306→0。NPU调用中位减少20.57%，不能换算为真人应用帧率；人脸检测、采集、显示和控制仍分别测量。

完整GUI固定照片160个有效NPU样本、真实PCIe153个无人脸样本，两者均经真实全局F10正常退出，转换警告0。默认app23完整103文件已实际安装并通过启动→F10→再次启动。原模型SHA9eeeaedd…保持，新launcher SHA667feced…；app22和app20回退目录保留。

恢复操作读取根CURRENT_CAMERA的app/native/adapter/estimator/model/launcher SHA和实际owner；测试后在真实STREAMON之后重设47门限2、核验完整2073600像素直方图。app22专用恢复脚本只能当模板，不能据它签核app23。Flash37保持，自动断电恢复仍待。真人绿点/肤色/FPS/精度/跟手、游戏和RK CSI内核修复仍未验收；GPU DRI回退和静态模型动态范围查询未因此消失。

证据：模型项目 `evidence/NPU_layout_v1/independent_review.json`、`app23_inputs_v1/result.json`、`app23_GUI_job_v1/independent_review.json`、`app23_default_job_v2/independent_review.json`、`app23_runtime_delivery_v1/result.json`。运行包为 `deliverables/gaze_app23_rk3576_runtime_v1.zip`。

归档经验：`result.json`生成不等于tar/gzip写入结束。本轮首个GUI下载遇到SFTP SHA不匹配，同一job当时仍写归档；保留部分文件，不重跑实机测试。收集器改为先确认job日志输出归档关闭后的最终SHA，再读取相同文件并校验传输SHA。
