# 硬件回归与启动等待修正（离线交付）

此记录只证明脚本设计及本地源码更改，不代表已编译或已上板通过。原厂例程、boot.img、公共等待宏和异步 DMA API 未因这次补丁而改变。

## 启动等待的确切问题

V4L2 每次 STREAMON 对视频链路执行软复位，然后立即提交 DMA；CSI 校准/传感器启动尚未结束时，100 ms 等待可能超时。此前两个同步 SGDMA 等待调用丢弃返回值，默认分支将真实超时和信号都返回为 `-ERESTARTSYS`，使日志不能区分原因。更早的公共等待宏还会重试负返回，延后真实信号退出。

修正只作用于 `sgdma_xfer_aperture` 与 `sgdma_xfer_submit` 两个同步函数：原生等待返回用 `long wait_rv` 保存，完成/失败仍在原 `engine->lock` 下判定。仍在提交中的 default 路径保持原 abort/stop/descriptor cleanup；定时等待返回 0 对应 `-ETIMEDOUT`，负返回保持原 errno，非负但非完成的异常状态对应 `-EIO`。完成状态优先，保留原部分完成返回规则。未修改异步完成路径。

V4L2 首个有效完整帧交付前等待 1000 ms，之后恢复 100 ms。短包不增加 `delivered_frames`，不会错误进入稳态。真实启动等待仍有上限，持续错误仍触发原三次错误退出；没有无限忽略超时。等待 API 的返回语义与 [Linux 官方文档](https://docs.kernel.org/driver-api/basics.html#c.wait_event_interruptible_timeout) 一致。

源码候选 SHA-256：

- `fpga/deploy/sgdma_drv/anlogic_pci_lib.c`：`a0d8bd64fe815bfd86881f145f21b20b5980fffc8149e6fed5f4bdbebdcd142f`
- `fpga/deploy/v4l2_drv/milianke_v4l2_zerocopy.c`：`dce3bf1460f8fc608c74cd275746e3849be7e97b7d24c4ef9ec8066eddc2fe19`

RK 上编译建议（由主任务操作）：

```sh
cd /home/linaro/pcie_fix_20261003
make -C deploy/sgdma_drv -j2
make -C deploy/v4l2_drv -j2
```

必须使用与运行内核匹配的已准备 headers，并先编译 SGDMA 的 `Module.symvers`。替换模块后通过既有 `deploy/pcie_setup.sh` 正确初始化，再做负测/回归。

## 回归脚本运行

新脚本 `tools/hardware_regression.sh` 不刷 boot、不下载 FPGA、不重载驱动。它要求修复后的诊断版本 `0x56440401`、已加载匹配的 SGDMA/V4L2、正确的 PCIe1/USB1 设备树和至少 64 MiB CMA。自动唯一识别 `1edb:abcd` 的 BDF、`resource0` 和 `Milianke PCIe Capture` 对应的视频节点；拒绝节点不存在/不唯一及其他应用正在使用的状态。

```sh
cd /home/linaro/pcie_fix_20261003
bash -n tools/hardware_regression.sh
CAPTURE_SAVE_MODE=none bash tools/hardware_regression.sh
# 需要抽样 RGB 文件时使用 bounded（长测不允许 all）：
CAPTURE_SAVE_MODE=bounded bash tools/hardware_regression.sh
```

输出放在新建的 `evidence/hardware_regression_<monotonic_ns>/`；也可传入 task_root 和新 output_dir 两个位置参数。所有失败非零退出，保留原始日志及 JSON，不能以“无数据”标记通过。

默认执行：

- 720p、1080p 各 1000 帧；只通过 V4L2 RGB24 S_FMT 请求分辨率，采集中读回 FPGA mode/width/height/bytes 核对。
- 每档长测采到至少 10 帧后，同时运行既有 `bar_roundtrip.c` 1000 轮；确认压力完成时相机仍在采集。只访问 0x300–0x3fc 中已经验证的 63 个 scratch words，避开 0x328 的 IRQ 别名；正常或异常均校验/恢复 scratch 内容。
- 四轮 720/1080 切换，每档再采 32 帧，每次新打开、STREAMON、STREAMOFF、close，核对退出时 CTRL/mux/mode。
- 每阶段前后读取 CSI、CMA、endpoint/rootport AER、dmesg；持续 CSI 采样要求采集窗口中快照与 RAW 计数实际递增，CRC/ECC/WC/timeout/FIFO overflow 均为零。STREAMON 初始复位另建 epoch，不将上一轮的错误混入；采集期间新的复位会失败。
- 要求完整帧长度、连续序号、实际正向时间推进及新鲜的驱动 delivered/rejected/dma_errors 记录；任何 DMA 错误、短包、AER 错误增加或新 kernel warning/fault 都失败。
- 每阶段和整个测试的累计 CMA free 损失均不能超过显式阈值（默认 1024 kB，可用 `REGRESSION_CMA_LEAK_KB` 修改）；允许范围在报告中写明，不能将其描述为绝对零泄漏。

可增加 `REGRESSION_FRAMES`（最低1000）、`REGRESSION_CYCLES`（最低2）、`REGRESSION_CYCLE_FRAMES`（最低16）、`REGRESSION_TIMEOUT_S`（最低20）、`REGRESSION_BAR_ROUNDS`（最低1000）。输出真实 FPS，未将驱动声明的 60 fps 当作实测值。

脚本成功仅表示 `transport_and_csi_pass`。相机颜色/紫绿闪屏必须另用图像和场景判定；RK→FPGA→RK 图像双向完整性必须另外跑 `image_roundtrip`。JSON 明确保留这两个未自动验收状态，不能把 BAR 双向控制回环等同于双向图像验收。

## 本地检查范围

Python heredoc AST、LF 行尾和 15 个独立判定输入已验证：空数据、旧计数不增加、序号间断、CRC 错误、中途复位、缺失驱动记录、DMA 错误、kernel warning、累计 CMA 损失和 AER 增加均拒绝；正确输入和合法启动复位可接受。记录见 `hardware_regression_offline_validation.json`。Windows 无可用 Bash，因此 Bash syntax 必须由主任务在 RK 执行 `bash -n`。本次未执行任何板卡、上传、编译或硬件命令。
