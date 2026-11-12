# P7 调度
按附件默认值保留 NPU mask：face=1、gaze=2、hand detector/ROI=AUTO。运行时包装可读取配置后设置环境和原 POLICY；不改模型、预处理或推理数值。CPU：所有者4、gaze5、hand6、engine/UI7、HUD/应用/console0–3。原生接收线程调度派生为 CPU4/SCHED_FIFO10。

engine 发布状态预算，gaze 在 RingCapture 边界节流、待机关闭 MGazeNet；hand 复用 SampleClock，无积压。附 tools/measure.py 统计真实总线观测速率与源年龄 P50/P95/max。

sys.metrics 以有界 256 样本/最近 5 秒窗口统计已观测帧率、阶段耗时 P50/P95/max，附本进程 CPU%、RSS 和可读 thermal_zone 温度。原生所有者由 Python 侧车管理，侧车 CPU 不代表 C 进程 CPU；NPU 利用率明确为 null，没有用估计值代替实测。

仅报告本机 ZeroMQ 1kHz×10s 压测的实际结果，见 evidence/bus_load.json。该数字不是 RK3576 帧率、DMA 延迟或端到端推理速度。没有真人/真机测量，不宣称达到 30fps、200ms 或温度功耗目标；没有执行 uint8/NEON 的算法路径替换。
