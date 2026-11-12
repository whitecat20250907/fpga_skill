# 三路不同接口摄像头时序对齐

适用：用户已增加RK原生CSI IMX415和此前调通的USB摄像头，需要与FPGA IMX415 PCIe图像一起对齐和预处理。完整入口为`projects/hci05_three_camera_sync_20261011/README.md`，实际状态以该工程`evidence/*/result.json`为准。

## 当前实际经验

- 2026-10-11RK实际清点中，PCIe/ANLOGIC与USB设备没有枚举，media0/1无新增IMX415 sensor，media2仍为FPGA-MIPI。73个video sysfs目录并不等于73台摄像头；未连接的CIF节点可返回ENODEV。只读清点不启动采集，不改boot/设备树，也不从历史“USB调通”推断当前存在设备。
- 用户确认RK CSI与FPGA同为IMX415；本机当前资料未找到旧USB型号/VID/PID/格式，不捏造旧配置。重新枚举后用driver、bus_info/by-id、media链路绑定实际物理源。CIF及其ISP输出是同一物理源的派生路径，不算两路独立摄像头。
- 后续只读启动诊断进一步确认：新boot_id与约1943秒uptime，实际IMX415 `5-001a`读id000000/ret0、`8-001a`读id000000/ret-5；PCIe两次Link Fail/LTSSM0x3。内核已内置IMX415/UVC/xHCI/DWC3/PCIe驱动，不能把没有外设枚举一律归为“缺驱动”。活动DT USB1 disabled、USB0 otg，两个原生IMX415节点存在却未probe成功；这些证据只证明本次失败阶段，具体排线/供电/时钟/端口与电源顺序仍须核对。不要重刷boot或结束健康TD来试错。
- 当前37 PCIe驱动`rk_runtime/v4l2_drv/milianke_v4l2_zerocopy.c`在DMA接收完成时调用`ktime_get_ns()`（521行），queue设置MONOTONIC（865行）。此接收戳不能替代相机SOF/曝光开始。其他CSI/UVC buffer的时钟与TSTAMP_SRC分别读取，不凭timestamp字段猜来源。
- 正式37驱动的sequence在成功交付时递增，连续的driver seq并不证明上游sensor/FPGA未丢帧。软件例程的driver gap只检查驱动提供的序号；要证明源帧连续还须有实际源FID/累计溢出与对应时间戳。
- 三路必须从原始V4L2 metadata统一到同一已知时钟域；不要用OpenCV `VideoCapture.read()`返回时刻代替传感器戳。UNKNOWN/COPY默认拒绝；arrival fallback须显式启用并将范围写为到达时间配对。

## 可复用例程

`rk/capture_native.c`实际RK gcc严格编译通过，支持single/multiplanar MMAP、真实returned format、各plane stride/data_offset/bytesused；每个原始缓冲在stdout MCF1记录中保留flags/sequence/timestamp/dequeue，SIGTERM/HUP后STREAMOFF、释放和原格式恢复。部署仅创建自己的小工具目录并chown自己的新目录；已有父目录root所有时，第一次普通mkdir失败保留，不递归改旧目录权限。

`rk/time_align.py`提供3路有界、每帧只用一次的时间戳配对。选择慢路为reference，等待其他路时间推进再选最近候选；三元组最大跨度≤tolerance，不能把各距参考≤tolerance解释为两端≤tolerance。记录正常帧率适配丢弃、reference过期、驱动seq gap/ERROR和队列overflow，各种情况不混为同一个“丢帧”。模32位sequence回绕合法；重复/逆序和驱动timestamp/source变更拒绝。

`rk/preprocess.py`统一RGB8定点灰度、高斯、上一帧256档直方图。首帧LUT identity，恒定帧下一帧使用identity。NV/YUYV显式解释BT601/BT709和full/limited量程，保留stride；不能把Bayer、私有字节容器或其他colorimetry按普通YUYV转换。当前三路后端是RK软件参考；不声称USB/RK原生CSI像素进入FPGA处理。

实际RK NumPy全高清三算法中位76.589ms是性能缺口，保留v4记录。新增`preprocess_native.c`分离RGB灰度、行级1-2-1高斯、LUT/直方图循环，保持定点输出与边缘/跨帧规则；实际gcc共享库和16张合成图9654304像素全部参考一致，fullHD中位12.692/max13.936ms（v5），未降低输入尺寸/算法。Python从自身目录加载该库，逐帧记录实际backend；缺库降回NumPy不能沿用C性能数值。该计时还不包含YUV/JPEG解码、SHA、PCIe复制和三路并发，不从合成算法测试推断实际摄像头吞吐量。

`rk/run_three_camera.py`保存所有原始metadata与SHA/直方图，使用独立采集线程和有界队列，抽样保存真实RGB及预处理PNG。异常后仅终止自己的采集child并保留PID/退出/恢复状态，不能结束其他人的采集、健康TD或系统服务。

`rk/review_three_capture.py`独立检查所有buffer身份、timestamp域/源稳定、序号、三元组不复用与跨度；由保存RGB重算三算法，并利用每个先前frame的直方图还原应用LUT。未保存的原始像素不能仅凭SHA称为可重解码全字节证据。

算法自检已经覆盖60/60/30fps异步合成流、30三元组、seq回绕、重复/倒序/时钟变更/队列溢出/ERROR，以及独立标量预处理和RGB/YUYV色彩/stride。这是算法证明，不是三台实际摄像头上板通过。

## 实测收尾

先检查3个实际物理源及无占用，与原HCI03下载/抓取队列串行执行；分别记录实际buffer FPS、timestamp源、配对率/最大/P95跨度、CPU预处理耗时、驱动gap/ERROR、队列drop、至少300秒漂移。固定偏移须来自有证据的共同视觉事件/触发校准，不自动从任意帧率或相似帧内容估算后宣称同步。

没有共同硬件触发时交付“时间戳配对”，曝光同步另列待验。实际曝光对齐需相机触发能力/连接/驱动模式以及示波器/共同可见事件；FPGA us时基与RK ns时基也不能直接相减，必须另保存时钟映射和误差。SDK/boot/设备树变更不属于当前例程默认操作。

API出处：[V4L2 buffers](https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/buffer.html)、[MMAP streaming](https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/mmap.html)。
