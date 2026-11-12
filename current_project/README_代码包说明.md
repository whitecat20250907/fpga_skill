# 完整代码包 · 2026-11-04

本包按最终独立启动提交版整理，保留应用代码、算法代码与模型权重、医学资产、游戏完整源码、FPGA RTL/IP/ROM/约束、驱动源码和启动脚本。
最终 FPGA 位流为 exposure765.bit；最终显示与自启动补丁来自 submission920，登录配置来自 access921。没有修改开发板或原工程。

## 目录

- `RK/userdata/hmi_v2`：统一入口；采集所有者、眼脸/手部模型、交互引擎、网页控制台、HDMI/MIPI 协议、医学三维应用、测试及文档。模型在 `vendor/models`、`vendor/vision_npu/models`、`vendor/gesture8/model` 和 `models` 等原路径，保留必要重复路径以兼容现有代码。
- `RK/userdata/freeciv-g03-v12-candidate_20261024`：修改后的 Freeciv 3.2.6 完整源码、游戏场景、交互桥接及资源。
- `RK/drivers`：SGDMA/V4L2 源码与加载脚本；SGDMA 包含最终 poll_idle_us 修改。
- `FPGA/production_765`：最终位流对应的完整 TD 源工程。
- `FPGA/release/exposure765.bit`：最终写入 Flash 的位流。
- `FPGA/release_flow_original`：实际使用的 748 布线收尾、765 位流导出脚本及约束，保留原路径以记录原构建流程。
- `FPGA/standalone_tasks`：独立图像预处理与 ROI 压缩专项源码、协议、TB。与 production_765 分开存放，不是自动启用的主链路。
- `model_tools`：模型转换和静态手势融合脚本；八类轨迹构建脚本在 hmi_v2/vendor/gesture8/build_model.py。
- `deployment`：自启动/免登录配置脚本与用户确认的演示映射示例。
- `SOURCE_MANIFEST.json`：全部文件的字节数、SHA256、来源和建议 Unix 权限。

## 构建入口

1. RK：使用 Linux/aarch64 与对应版本依赖；参阅 hmi_v2/requirements.txt、docs/USER_GUIDE.md。`python3 native/fpga_io/build.py` 构建 C 所有者和共享环；Freeciv 在游戏根目录执行 `sh build-rk3576.sh`。驱动需用目标板匹配的内核头文件构建，不能跨内核直接复制模块。
2. 模型：已包含部署用 RKNN 及已有 ONNX/原始权重。转换工具使用 RKNN Toolkit2 等外部依赖；脚本原始模型路径保留，迁移机器时按包内目录调整。
3. FPGA：安装 Anlogic TD 2026.1 SP2 与 PH1A90 器件库；在 production_765 内执行 `python prepare_build.py`，再运行 `td_commands_prompt.exe build_direct.tcl`。prepare_build.py 会重建路径、引脚及源文件校验清单。原布线收尾/导出脚本需将数据库路径指向本次构建输出；数据库未打包。重建是否满足时序以本次正式 STA 为准，现成位流可通过 SHA256 与最终提交匹配。
4. 启动：目标板项目原路径为 `/userdata/hmi_v2`，统一入口 `tools/hmi up` / `tools/hmi down`。自启动服务在 hmi_v2/systemd，部署脚本保留目标机路径；移植时先配置 Python、游戏、驱动与显示路径。解压或查看文件不会自动启动、写 Flash 或安装服务。

## 打包范围

保留最终代码、模型权重、页面/医学/游戏运行资产、必要供应商 IP、测试源码、许可证及构建说明。排除虚拟环境、依赖安装包、编译缓存、布局布线数据库、运行日志、录制视频、历史交付包及个人标定数据。原生二进制和驱动模块可由包内源码重建，最终 FPGA 位流单独保留。

本包以本地最终源码及已保存部署清单整合，打包时开发板 SSH 不可达，因此没有声称重新拉取板上当前运行状态。演示映射是用户确认的示例；网页后来保存的个人映射/标定不作为代码纳入。未合格的 1080P ROI 构建分支不混入最终工程。

解压后可运行 `python verify_package.py` 校验文件完整性。RAR 上的 Windows 属性不能表达所有 Linux 权限；恢复脚本执行权限可参考 SOURCE_MANIFEST.json 的 unix_mode。
