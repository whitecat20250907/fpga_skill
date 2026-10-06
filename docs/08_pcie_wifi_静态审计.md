# RK3576 PCIe/USB PHY 与 IMX415 PCIe 例程静态审计

审计日期：2026-09-30。开发板未连接；以下是板卡原理图、随包 DTB/boot.img 和源码检查，不代表已复现当前实机故障。未修改、烧录任何镜像或位流。

## 结论 1：共享 PHY 确实存在，但对象不是板载 Wi‑Fi

- RK3576 的 `pcie1` 和 `usb_drd1_dwc3` 都引用 `combphy1_psu`：前者要求 `PHY_TYPE_PCIE`，后者要求 `PHY_TYPE_USB3`。
- 随包 `dts/rockchip/mlk-rk03-rk3576-linux.dtb` 中，`/pcie@2a210000`、`/usb@23400000`、`/phy@2b060000` 的 `status` **全部为 `okay`**。随包 `boot.img` 在偏移 2048 和 40074752 各嵌有一份逐字节相同的该 DTB；因此它也包含同一冲突配置。这只证明随包镜像的内容，不能代替读取当前板上实际启动的设备树。
- MLK-AFH03 原理图第 15 页的板载 Wi‑Fi 模块使用 `D+`/`D-`，接 `HOST_D1P/M`，再接 USB2 hub 的 `USB2_HOST1_DP/DM`；它没有走 PCIe1/USB3 的高速收发对。Wi‑Fi 驱动资料也是 AIC8800 USB。**“Wi‑Fi 与 PCIe1 共用 PHY”这一表述不成立**，实际冲突是 PCIe1 与 USB3_OTG1（也可能包括 SATA1）。
- 随包 `rk03/dpnew.dtsi` 把 `usb_drd1_dwc3` 设成 host/okay，`rk03/pcie.dtsi` 同时把 `pcie1` 设为 okay。修复目标是分配 `combphy1_psu` 给 PCIe1，并根据实际 USB2 拓扑保留板载 Wi‑Fi 所用的 USB2 host/hub；不要笼统禁用 Wi‑Fi。
- `deploy/pcie1_enable.sh` 只检查/修改 `pcie1` 的 DTB 状态，而且假定 DTB 在 `/dev/mmcblk0p3`。随包 DTB 里 `pcie1` 已是 okay，该脚本不会解决 USB3 复用冲突。实际启动介质和镜像布局未核对前，不应运行此原地修改脚本。

如果当前板确实从随包 `boot.img` 启动，需要修正 DTB 并重新打包对应启动镜像；这不等于必须重编译整个内核。如果当前系统从独立 DTB 分区或其他镜像启动，必须先读取 `/sys/firmware/devicetree/base` 和启动分区布局，再选择修改位置。

## 结论 2：PCIe 相机例程有足以造成错帧/闪屏的设计缺陷

1. `uisrc/03_ip/vid_pipeline/pack4_rgb24_to_128.v` 将输入 `s_tlast` 定义为行结束、`s_tuser` 定义为帧开始；但 `flush_is_frame_last` 只在**下一帧**的 `s_tuser` 到达时置位，而 `m_frame_last` 只在随后的 flush 中输出。对于 1920/1280 宽 RGB24（每行分别 5760/3840 字节，均为 16 字节整数倍），本帧最后一行结束时不会产生帧末标志；下一帧第一行结束后才可能输出该标志。这会破坏 SGDMA 的帧边界。
2. `uisrc/01_rtl/imx415_pcie_top.v` 将 `cam_tready` 固定为 1，只有 2048×16=32768 字节的 C2H FIFO，却在帧开始仅检查半满阈值 1024；这不能保证约 6.22 MB 的 1080p RGB24 整帧进入 FIFO。`frame_completer` 的超时补尾会把损坏的帧变成短 DMA 包。
3. `deploy/v4l2_drv/milianke_v4l2_zerocopy.c` 明确允许达到预期长度 99% 的短包；即使 `xfer_len` 小于完整图像，它仍设置 `vb2` payload 为完整 `pixel_bytes` 并以 `VB2_BUF_STATE_DONE` 上报。旧缓冲区尾部可被用户态当作本帧像素显示。源文件注释自己也承认 pack4 会产生“spurious tlast”。
4. 1080p60 RGB24 裸流为 `1920×1080×3×60 = 373,248,000 B/s`，而例程驱动注释按 PCIe Gen2 x1 实际约 350 MB/s 做带宽上限判断；只封禁了 4K30，没有封禁当前默认 1080p60。此为额外的吞吐压力，不能单凭理论值认定具体板上持续丢帧。

这些是**代码层面已确认的风险/缺陷**；“紫绿”色偏的具体来源还不能仅凭源码定论。需在板上分别抓原始 RGB3 帧、核对实测 DMA 长度与 FPGA 的 `DROP_DETECT_CNT`/`GATE_DROP_CNT`，再对照已正常工作的 MIPI 画面，才能区分帧破损、Bayer/通道顺序和显示路径问题。不要以改色彩矩阵掩盖短帧。

## 下次上板的最小只读核验

1. 读 `/sys/firmware/devicetree/base/pcie@2a210000/status` 和 `/sys/firmware/devicetree/base/usb@23400000/status`，同时看 `dmesg` 中 combphy/PCIe 初始化错误；用 `lsusb -t` 确认 Wi‑Fi 仍挂在 USB2 hub。
2. 在固定 720p 模式抓连续原始帧，逐帧记录 `bytesused` 与 DMA 实际完成长度，拒绝所有短帧；对比 1080p 模式，判断带宽影响。
3. FPGA 端先修正行末与帧末标志，在仿真中断言每帧只有一次 EOF、每帧字节数精确、背压/丢帧后不混帧；再上板复测颜色。

资料基线：`03_MLK_AFH03_AFC03/02_hardware/.../02_原理图/MLK-AFH03-20251112.pdf` 第 15、27 页；`03_MLK_AFH03_AFC03/03_course/07_异构方案/` 中的 DTB、boot.img 和 `AFC03_IMX415_PCIE_X1/.../IMX415_PCIE_X1` 工程。前六项任务的 MIPI 整机路径与此 PCIe 工程独立。
