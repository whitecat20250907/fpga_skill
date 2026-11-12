# VIDEO人脸丢失与眼部质量

用于眼控在丢脸、眨眼、遮挡时仍产生有效结果，或定位耗时异常的排查。现用应用及所有恢复哈希从根`CURRENT_CAMERA.json`读取；不要沿用旧app23/app22标签。

`BlazeFaceAlignment.py`的备用实现只估计眼框，直接把左右眼开合度设为100。它不能证明眼睛睁开，也不等价于原MediaPipe密集关键点得到的眼区。旧VIDEO路径在Tasks结果为空或异常时会调用它，可能让后续`eye_openness_threshold`判断失去意义；额外执行备用模型也会增加无人脸处理耗时。此源码事实不能直接证明某次真人误触的根因。

app24只修改`MediaPipeFaceAlignment._get_fallback_blazeface`：VIDEO模式返回None；缺少密集结果时沿原失效路径返回status=False/can_gaze_estimation=False、清空有效眼部条件并重置过滤器。有效密集结果的几何、RGB、右眼翻转、原MGazeNet及NPU输入保持。IMAGE模式保留原兼容接口。不要为“连续输出”补固定开合度、复制上一帧有效脸或改变时间戳配对。

当前证据在`projects/gaze_model_migration_v1_20261014`：

- `evidence/app24_dense_face_tests_v1/result.json`：8项实际类控制流测试，Tasks/Image/备用结果为明确替身；覆盖空结果、异常、旧备用误准入、IMAGE兼容、正几何和恢复，不是真实检测精度。
- `evidence/app24_dense_validation_v1/independent_review.json`：实际MediaPipe的同一478点结果重放，16组原RK3576 NPU全部258维逐位一致；照片→黑画面→照片对照中，候选24个黑画面均无效/NPU0，64个照片样本实际推理并在首张恢复。黑画面不能替代真人眨眼、遮挡或精度验收。
- `evidence/app24_GUI_job_v1/independent_review.json`：完整GUI照片163次有效NPU、真实PCIe163个无人脸样本，均经真实全局F10正常结束；测试后已恢复当时的app23。
- `evidence/app24_default_job_v1/independent_review.json`：实际完整103文件安装、默认启动/F10/重启、原NPU、47运行时2档完整直方图和同boot内核日志检查。当前默认app24；app23立即回退，app22/app20历史目录保留。
- `deliverables/gaze_app24_rk3576_runtime_v1.zip`：实际ARM采集程序、模型、全源及逐文件SHA，启动脚本保留0755；依赖现机venv/驱动及已有回退目录，不是跨电脑完整系统安装器。

性能与数值要分开判断。实际8轮并行CPU对照中，大核3线程照片吞吐仅提高7.07%，P95样本年龄降低9.70%；未过该次预先设定的10%吞吐门槛，没有更改CPU4默认设置。相同默认配置也有1像素裁切波动，不能声称每次MediaPipe结果逐位确定；此轮候选全部裁切+258维联合组合都能在默认基线池中找到。原始资料见`evidence/CPU_affinity_profile_v1/independent_review.json`及`CPU_overlap_profile_v2/independent_review.json`。这些是重复照片容量，不是真人FPS。

采集证据时，原生库线程可能在枚举`/proc/self/task`与读取status之间退出；记录已退出tid，在模型存活时读取其余线程和owner的亲和性，不把ENOENT当模型或内核崩溃。任务result.json写完不代表tar已关闭；等待打印的最终归档SHA并核对下载字节。原生库退出刷新的日志可能排在完成行之后，应在全日志中找匹配的完成行，不能只检查末几行。观测失败时继续同一任务，只有真实终态失败并修正原因后才建立新实验。

真人颜色/绿点、实际FPS/跟手、眨眼和遮挡、个人20点精度与游戏仍待。此用户态质量修复不代表RK CSI停流/IOMMU内核故障已修复。
