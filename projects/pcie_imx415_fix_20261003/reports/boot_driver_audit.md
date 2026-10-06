# RK3576 boot、驱动与复现脚本审计

审计对象为独立工程 E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003。原始厂商例程未被本审计修改。2026-10-04 完成源码审计并交付驱动/工具候选；本文的“已修”指文件已修改，内核编译和上板回归由主任务执行，不能替代最终实机报告。

## 结论与优先级

| 优先级 | 确定问题及触发条件 | 候选处理 | 验证要求 |
|---|---|---|---|
| P1 | pcie_setup 先加载 V4L2，再写 CAM_MODE=0；若 FPGA 原来 mode2，驱动缓存 720p、硬件却成为 1080p。S_FMT 同一缓存模式不会重新写硬件。 | 将 BAR 初始化整体移到 V4L2 insmod 前。 | 从 mode2 状态运行 setup，G_FMT、CAM_MODE、WIDTH/HEIGHT 必须一致。 |
| P1 | dma_map_sg 结果必须等于 orig_nents 的判断错误；合法合并被当作失败，且成功映射分支直接 return，遗漏 unmap。 | 仅 nents==0 判断失败，保存 mapped nents；描述符遍历沿用 sgt->nents，unmap 沿用 orig_nents。 | SGDMA 重编后继续 720/1080 完整图像回环，记录结果；平台当前未证明实际发生了 SG 合并。 |
| P1 | STREAMON 在 REQBUFS 后重新修改 width/height/read_size，buf_init 的 SG DMA 长度却是旧值。直接 BAR 改模式会使元数据与真实 DMA 容量不一致。 | STREAMON 验证已配置 mode、width、height、padded bytes 与已分配格式完全一致，不在开流时重定尺寸。 | 分配 720p buffers，直接改 BAR mode0，再 STREAMON 必须 -EINVAL；不启动 DMA、不泄漏 queued buffers。 |
| P1 | 字符 C2H 的 device_open 只有字符 open/close 使用，且检查/置位无锁；V4L2 导出 DMA 提交完全绕过它。并发 open 可改变 eop_flush/竞争同一数据流。 | 新增 claim/release 导出 API；streaming 字符 H2C/C2H 与 V4L2 共用 engine->lock 下的生命周期租约。 | 两个同通道字符 open 仅一个成功；V4L2 开流与 raw C2H 双向竞争均返回 -EBUSY。 |
| P2 | 真实 DMA 负错误无限重试，应用只会等不到图，没有稳定的失败通知。 | 统计 dma_errors；连续 3 次意外负错误关闭 pipeline、vb2_queue_error。正常 STREAMOFF 导致的中断不计为运行失败。 | 人为停 FPGA stream 后应用出现 POLLERR/EIO，随后 STREAMOFF/close 回收所有 buffer；恢复后能重新开流。 |
| P2 | image_roundtrip 的 pthread_create 失败、信号终止、读写失败可能遗留 A4/20 回环状态；failed 被两个线程无锁写。 | atomic failed/stop、SIGINT/SIGTERM、统一 cleanup、先获取两路设备再动 BAR、加载 V4L2 时主动拒绝。 | 成功与终止后 A4=0、20=0、CTRL enable=0；重复回环继续逐字节正确。SIGKILL 无法执行应用清理，需重置恢复。 |
| P2 | 回环 FIFO 原来只受 PCIe user_rst_n 复位，CTRL soft_reset 不清它；错误后恢复 mux 也可能留下旧字节。 | 主任务负责将独立 loop_reset_n 接到回环 FIFO，避免重置 AXIL 响应；工具进入/退出均 CTRL=2。 | 中途终止一次回环，软复位后下一次首帧与完整图像 hash 相等。 |
| P2 | boot 补丁只更新 FIT hash，不识别实际签名；也允许 source==dest 覆盖唯一备份。 | 有非空 signature/value 则拒绝 hash-only patch；源与目标同一路径则拒绝；验证外置 payload 边界。 | 当前模板无签名 value，可以使用；真正签名镜像须转入有密钥的完整签名流程。 |

DMA 合并语义及 unmap 原始条目计数依据 [Linux DMA API](https://docs.kernel.org/core-api/dma-api.html)。V4L2 开流失败返还 QUEUED buffers、停流返还已接收 buffers，以及队列错误通知依据 [videobuf2 文档](https://docs.kernel.org/driver-api/media/v4l2-videobuf2.html)。

## 实际源码位置

以下为本次冻结候选时位置；主任务后续改动可能改变行号，driver_audit_manifest.json 保存该候选文件哈希。

- fpga/deploy/sgdma_drv/anlogic_pci_lib.c：sgdma_xfer_submit；sgdma_init_request 已按 sgt->nents 构造描述符；transfer_destroy/unmap_sgl 使用 orig_nents。新增 sgdma_client_engine、sgdma_engine_claim、sgdma_engine_release。
- fpga/deploy/sgdma_drv/anlogic_pci_lib.h：device_open 注释、claim/release 声明。
- fpga/deploy/sgdma_drv/cdev_sgdma.c：char_sgdma_open/close。原函数位于 697/718；现在检查 char_open 的返回，并在 streaming 两方向调用租约。
- fpga/deploy/v4l2_drv/milianke_v4l2_zerocopy.c：milianke_dma_thread、milianke_start_streaming、milianke_stop_streaming。buf_init 原始 DMA 长度在 547；当前 start_streaming 从约 613 开始。
- tools/pcie_setup_fixed.sh 与 fpga/deploy/pcie_setup.sh：两份内容相同，Python BAR 初始化后才加载 V4L2。
- tools/image_roundtrip.c：完整图像比较、原子停止、信号和统一清理；禁止 echo 输出与 input 原文件相同 inode。
- tools/patch_boot.py：源目标保护、FIT payload 边界、非空 signature 拒绝、报告记录 before/after property presence。

## 互斥与释放路径

engine->lock 是现有 IRQ/poll 共享的自旋锁，仅短暂保护 ownership/eop_flush/list 状态，使用 spin_lock_irqsave。不在该锁内等待 DMA、不跨整个采集长期持锁。desc_lock 继续只序列化一笔 DMA 的描述符提交、完成及销毁。V4L2 ioctl 的 mdev->lock 保护视频配置；它不是 raw 字符设备和 V4L2 之间的共享锁。

字符 streaming open：claim 成功才开放该通道，release 在最后一个该 file 引用关闭时执行。H2C 和 C2H 各有独立 engine，正常图像回环可同时持有两路。

V4L2 start：先确认尺寸不变，再 claim C2H，并在 claim 内设置 EOP flush；然后 soft_reset，创建 DMA worker。创建 worker 失败时关闭 pipeline、释放租约、将全部已交给驱动的 buffers 以 QUEUED 返回。V4L2 stop：先发布 streaming=false，等待 worker 停止，返还全部 queued buffers，关闭 pipeline，再释放 C2H 租约。错误状态不能提前放开租约让另一个客户端与未退出的 worker 竞争。

持有租约是软件驱动约定；root 直接 mmap BAR 仍能改 FPGA 寄存器。流程因此要求相机和全图回环分阶段使用，不能同时操作 mux/模式。SGDMA 模块卸载、PCIe controller unbind、重新下载 FPGA 都必须在应用退出与 V4L2/SGDMA 模块顺序卸载后执行。

## Boot 离线复核

本审计重新解析实际两个本地镜像：

- 原备份 boot_before.img SHA256：faebf16428deb61867f57f17f79b7d27ba0faf9503853284a697aa83e882abec。
- 当前 boot_pcie_cma64.img SHA256：acd036d8de113cfd4166a5e34a71e7222429297dc1ed13de7db51828b35cd247。
- 两者均为 67,108,864 bytes；所有 FIT image SHA256 与边界通过；kernel payload 39,778,816 bytes 完全不变。
- DTB 位于 2048 及 resource 内 40073728。当前 PCIe1 okay、USB1 disabled、chosen bootargs 包含 cma=64M。
- resource 的 rk-kernel.dtb hash 改变；两份 logo 内容及其 hash 保持不变。
- /configurations/conf/signature 有 algo=sha256,rsa2048、padding=pss、key-name-hint=dev、sign-images，但没有 value。它是未填值的签名模板；此验证是内容 hash 验证，不能宣称 RSA 签名已验证。
- patch_boot.py AST 解析通过，同源同目标拒绝保护已执行验证；本审计没有重写或刷写 boot 镜像。

PCIe1/SATA1 与 USB OTG1 包含 USB2 的总线互斥是硬件限制。板载 Wi-Fi/BT 和 USB-A 设备挂 USB1 hub，PCIe1 开启时无法靠 boot.img 同时保留它们；OTG0 Type-C 是独立通路。[Rockchip RK3576 USB 开发指南](https://docs.bit-brick.com/pdf/rk/usb/Rockchip_RK3576_Developer_Guide_USB_CN.pdf)

## 编译与回归建议

必须先重新编译 SGDMA 再编译 V4L2，后者使用前者新的 Module.symvers；只替换一个模块会缺失新导出符号。以 RK 根目录 /home/linaro/pcie_fix_20261003 为例：

~~~sh
cd /home/linaro/pcie_fix_20261003/deploy/sgdma_drv
make KDIR=/usr/src/linux-headers-6.1-rockchip clean
make KDIR=/usr/src/linux-headers-6.1-rockchip
cd ../v4l2_drv
make KDIR=/usr/src/linux-headers-6.1-rockchip clean
make KDIR=/usr/src/linux-headers-6.1-rockchip
cd /home/linaro/pcie_fix_20261003
gcc -std=gnu11 -O2 -Wall -Wextra -pthread -o image_roundtrip tools/image_roundtrip.c
bash -n deploy/pcie_setup.sh
~~~

若目标时钟错误、对象来自未来日期，先 clean，再确认日志确实出现本轮 CC/LD/MODPOST，并记模块 hash。本机 bash 指向未安装发行版的 WSL，无法在 Windows 完成 bash -n；不能据此判脚本语法失败或通过，需在 RK 执行上述语法检查。

建议补齐负测：

1. 从 FPGA CAM_MODE=2 运行 setup，检查驱动和 BAR 尺寸同步。
2. S_FMT 720、REQBUFS 后再 S_FMT 1080，返回 -EBUSY；REQBUFS(0) 后切换成功。
3. 分配 720 buffers 后直接 BAR mode0，STREAMON -EINVAL 且没有 kernel warning；重新设置正确硬件模式并清 buffer 后可恢复。
4. V4L2 开流期间 raw C2H open -EBUSY；raw C2H 占用时 STREAMON -EBUSY；H2C/C2H 各自两进程 open 不会两者同时成功。
5. 真实负错误、终止回环、重复启停后，再运行完整 720/1080 图像回环，逐字节比较和 SHA256 相等。
6. 相机连续图像回归必须独立进行。全图回环 0 误差证明传输字节，不证明相机 ISP 的颜色正确。
7. 最后保存 AER/链路状态、DMA error/rejected/delivered、CMA free 与模块/位流 hash。

## 仍须分清的测试边界

capture_verify.c 的 green/purple fractions 仅用于筛选图像，真实绿色或紫色场景也会触发；颜色验收需查看图像或使用金标准。当前该工具对每个阈值触发帧同步保存整个 RGB 到 eMMC。大量保存会阻塞 DQBUF/QBUF，耗尽四个 queued buffers并施加反压，可能降低测试帧率。纯吞吐测试应禁用/限频 raw 保存，彩色异常定位再另外采样。

capture_verify.c 虽对统计采样进行了 buffer 边界限制，写 raw 文件时仍直接使用 bytesused；若未来换驱动返回异常 bytesused>buffer length，应先拒绝这帧再写文件，不能由测试工具越界读取。目前严格驱动仅交付 exact pixel_bytes，当前正常路径不会触发。

标称 fps 来自 driver mode table，并未自动测量实际帧率。g_parm 的 60 与测量得到约 26.7 fps 不一致时，应分别核对 sensor 设置、采集时间戳、测试 I/O、丢帧和处理吞吐，不能以 ioctl 声明为性能证据。

SGDMA engine_stop 有“dummy read flush”注释但原代码未做实际 read_register(status)；主任务已收到建议，需检查 posted stop 写真正完成、超时撤销后的设备停止和重新提交。该路径尚不能只凭正常图像回环断言通过。
