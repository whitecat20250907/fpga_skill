# 赛题三六项基础功能：PH1A90 + RK3576

器件为 **PH1A90SEG324**，相机为 VID005 子卡上的 IMX415。此目录保留每个阶段的独立 TD 工程，沿用已上板例程的引脚、PLL、MIPI RX/TX 和相机配置 IP；不会改动原 `examples/`。

## 当前验收边界（2026-09-27）

| 赛题要求 | 目录/模块 | 当前证据 | 状态 |
|---|---|---|---|
| 1. MIPI 高清采集 | `s1_noddr_passthrough` | IMX415→FPGA→RK，30/30 帧 1920×1080 YUYV；片内无 DDR | **实机通过** |
| 2. 三种 FPGA 图像预处理 | `rtl/gauss3x3_yuyv_quad.v`、`rtl/histeq_yuyv_quad.v` | 灰度、高斯、上一帧 LUT 直方图均衡；64 档整机经真实相机输入连续解码 10 帧 | **整机实机通过** |
| 3. FPGA 硬件压缩 | `rtl/lz1_lane_engine.v`、`rtl/lz4_line_packetizer.v` | 四路行差分+受限 offset-1 LZ77；75 MHz 发送版实机 10,800/10,800 行 CRC 通过，载荷比约 1.83–1.86:1 | **实机通过，溢出计数补测中** |
| 4. 压缩帧 FPGA→RK | `s4b_f3_csi_75m`、`rk/capture_decode.py`、`rk/line_codec_fast.cpp` | 1280×1080 CSI-2 YUYV 字节容器；RK 收到帧号 3–12 连续，10 帧全部解码；内核无新增 CSI 包 CRC 报错 | **实机通过，溢出计数补测中** |
| 5. RK NPU 目标检测 | `rk/npu_probe.py`、`rk/live_detect.py` | 直通实拍画面已输出 person 框；压缩链路解码画面已送 RKNN，但当前取景仅局部头肩，暂无链路正例 | **实拍直通识别通过，压缩链路正例待验** |
| 6. 测评报告 | `rk/build_report.py`、FPGA `TICK`/`OVFL` 元数据 | FPGA 实测输入约 60.006 fps、CSI→首包约 332 µs；75 MHz 版 SWNS +0.002 ns；最终溢出计数及光电延迟待测 | **大部分实测，光电延迟待探头** |

这张表只把已在板上复现的部分标为实机通过。最初 `s4_f3_csi_container` 用 125 MHz 发送时，RK 内核报告 CSI 包 CRC 错误，完整帧亦有行 CRC 失败；失败记录为 `evidence/s4_125m_failed_crc.json`，该位流不能作交付版。改用厂商现成 75 MHz PLL 的 `s4b_f3_csi_75m` 后，`evidence/f3_75m_10.json` 记录 10 帧全部通过。该版 FPGA 错误标志 bit 3 曾置位且黏滞，无法单凭它判断稳态是否再丢字；`s4c_f3_csi_75m_monitor` 增加累计硬件计数，但按用户要求收尾，已在布线阶段停止，尚无可下载 bit 或实机证据。`s1`/`s2` 的时序报告存在厂商 MIPI 时钟路径负余量；75 MHz 整机版本已路由到 SWNS +0.002 ns，但余量很小，新版还需重新复查。任一新工程均须检查最终 `fpga_prj_pr.timing` 的 STA 覆盖率、SWNS/HWNS 和实际抓帧结果。

实机 JSON 记录：`evidence/s2_meta10_report.json`。NPU 正例 `evidence/npu_person_fixture_offline.json` 明确是离线图片；压缩预算 `evidence/f3_camera1_offline_estimate.json` 也明确是 OpenCV 近似，二者均不能代替 FPGA 压缩链路上板验收。

## 数据路径

```text
IMX415 RAW10 → 厂商 CSI RX/ISP → 4 像素/拍灰度 → 3×3 高斯
             → 直方图均衡（整机版 64 档，使用前一帧 LUT）
             → 四路 delta + LZ77 → 1280×1080 CSI-2 字节容器
             → RK V4L2 → 行 CRC/解码 → 1920×1080 GRAY8 → RKNN YOLOv5s
```

F3 每路宽 480 字节。编码未比原行短时自动退回存储模式。整机版设 `QUANT_BITS=4`，是**有损近似**：每像素最大误差 15；`QUANT_BITS=0` 才不量化。压缩行含 32 字节 `LZ4R` 头、1920 字节四路交错区和尾部填充，首行尾部还有 40 字节 `TICK` 监测记录。RK 必须先解码，不能把容器当正常 YUYV 图像显示或送模型。

原 256 档直方图版 `s3b_f2_pipelined` 综合通过，但详细布线持续出现约 -2 ns 负余量，已中止；整机改用 64 档。`s4b_f3_csi_75m` 最终布线约 20,466 LUT、34 ERAM、58 DSP，已完成 10 帧实测；`s4c` 仅增加 FIFO 累计溢出计数。64 档版不是与 256 档完全相同的像素映射，不能套用旧版数值预期。

实机原始链路记录上一帧跨度 1,754,933 RX 时钟，约 1626 时钟/行；行内有效数据 480 时钟，留约 1146 时钟。四路压缩加 1280 宽装帧的最坏仿真为行尾后 802 时钟。高斯模块最后一行默认会在前一行之后立刻补发，因此整机专设 `BOTTOM_WAIT=1024`，让压缩器先完成前一行；`tb/tb_f2_f3_lastrow.v` 已用两行 Python 黄金包确认末行和 CRC。以上节拍是可行性预算，仍须在板上检查 `overlap_count=0`。

在一帧实采画面上用 OpenCV 近似 F2 的**离线估算**为：LZ77 载荷 1,404,533 B / 原灰度 2,073,600 B，压缩比 1.476:1；CSI 固定容器为 2,764,800 B，比原 YUYV 的 4,147,200 B 少 33.33%。这是预算，不是 FPGA 上板测量。工具 `rk/estimate_f3.py` 会把结果标记为 `offline_surrogate_not_fpga`。

## 编译与烧录

TD 版本为 `Release_2026.1_SP2`，工程器件与原例程约束已写入 `.al`。在 PowerShell 中，从此目录运行：

```powershell
& 'E:/qianrufpga/TD/bin/td_commands_prompt.exe' 'E:/qianrufpga/fpga-lab/projects/t3_basic6/s4c_f3_csi_75m_monitor/build.tcl'
```

编译成功后 bit 通常位于 `s4c_f3_csi_75m_monitor/fpga_prj_Runs/phy_1/fpga_prj.bit`。本目录 `program_sram.ps1` 使用 AL-LINK 与 BitWriter 命令行向 **SRAM** 下载，断电会丢失；先确认该路径确实对应本轮成功编译：

```powershell
./program_sram.ps1 -BitPath './s4c_f3_csi_75m_monitor/fpga_prj_Runs/phy_1/fpga_prj.bit'
```

若 `Connect server failed`，检查板上供电、AL-LINK USB 和 Windows 设备管理器；脚本会在未找到 `hwserver.exe` 时隐藏启动它。下载日志出现 `Chip validation success: PH1A90` 并走到 100% 后，仍须进行 RK 抓帧验证。

## RK 实机验收命令

把 `rk/` 内的解码、推理脚本及 `line_codec_fast.cpp` 放在 RK 的 `/home/linaro/t3_basic6/`。使用已有 `.venv` 与模型 `models/yolov5s_relu.rknn`，先编译本地双线程解码库：

```bash
cd /home/linaro/t3_basic6
g++ -O3 -std=c++17 -fopenmp -fPIC -shared -o libt3codec.so line_codec_fast.cpp
```

然后抓 10 帧做 CRC 验收，再对解出的末帧推理：

```bash
cd /home/linaro/t3_basic6
.venv/bin/python capture_decode.py --frames 10 --warmup 1 --capture data/f3_11buffers.yuyv \
  --gray data/f3_last.gray --json data/f3_10.json
.venv/bin/python npu_probe.py --frame data/f3_last.gray --gray \
  --model models/yolov5s_relu.rknn --runs 30 --json data/f3_npu.json
```

`capture_decode.py` 应得到 10 个连续帧号、10800 行 CRC 通过、`overlap_count=0`，且 `bridge_overflow_words_added_during_capture=0`。启动期如曾溢出，黏滞 `error_flags` bit 3 可保持为 1；不能把它误读为每帧都在丢数据。把摄像头对准完整的人或常见物体，`npu_probe.py` 的 `detections` 应有非空识别框。将 `--capture`、`--npu`、TD 最终 `fpga_prj_pr.timing` 与 `fpga_prj_phy.area` 交给 `rk/build_report.py` 生成六项测评表。

连续演示可运行 `live_detect.py --model models/yolov5s_relu.rknn --frames 30 --json data/f3_live.json`。它使用 GStreamer 原始 YUYV 字节流和 C++ 解码器；由于 NPU 推理低于相机 60 fps，`appsink` 主动丢弃旧帧，不能用其帧号跳跃判断 MIPI 丢帧。链路完整性以单独运行的 `capture_decode.py` 为准。

`TICK` 测的是 CSI 帧起始到 FPGA 首包装帧的片内延迟。用户计划中的光电端到端延迟还需要外接探头和对应 FPGA 引脚，不能用上述片内时间或 V4L2 软件计时替代。
