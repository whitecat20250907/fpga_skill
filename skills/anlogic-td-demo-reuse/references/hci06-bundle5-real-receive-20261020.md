# bundle5 当前实板接收与恢复经验

2026-10-20，F11 完整 bundle5 已实际有限 SRAM 测试，未签图像/卷积通过。入口：`projects/gaze_model_migration_v1_20261014/CONTROLLED_TRIAL_REPORT.md`。动态运行代次读取根 CURRENT_CAMERA.json，不使用本文或旧报告中的 PID 作为操作授权。

两段原始 UART 严格解码给出 592 次完整测试、16 轮完整 32 档扫描，0 通过档位；内部 root27 窗口和 BYTE 握手/频率比均前进，四 lane 每个已观察测试均有 SOT/valid，却有 1249 ECC、12015 CRC 错误，只有 1 个 CRC 合格包。内部时钟正常不等于引脚波形正确，lane 有活动也不等于采样/字节顺序正确。训练没有完成时，HCKC accepted31001/31002、applied0、output_frames0 是接收故障的后果，不能靠调系数完成卷积验收。

受控试验：UART 必须在候选下载前单句柄连续读取；保留烧写前缀和未改原始串口数据，不能为解码丢掉坏前缀。可额外保存有准确区间归属的测量段，在这些段上严格验证初始同步、连续 CRC/序号，不允许中途重新同步掩盖错误。一次原 BitWriter 租约在候选后恢复 CURRENT 镜像，进程终态且原父进程回收后再 reprobe/启动；不以观察超时另开下载器。

实测暴露检查器环境问题：系统 Python 能做此前只读校验，但实际启动后的 HDMI XWD→PNG 路径需要 numpy/Pillow；在停机前必须用**将实际运行检查器的解释器**验证所有延迟导入和显示依赖。本轮使用原 app_venv 修复，不安装/升级生产依赖。恢复错误不得被原地改成 PASS：保留首次启动、F10、native end、原父进程 reap 和整棵树/FD关闭证据，修复原因后才能开始新的独立恢复事务。不得在原事务内自动二次启动、JTAG或重绑。

Windows 小 JSON 从 SSH stdout 归档时用 write_bytes 保留 Linux LF；write_text 默认换行为 CRLF 会造成真实远端内容与本地哈希不一致。保留失败，不放宽哈希。SFTP 范围限制保持；小型既有 JSON 可通过授权只读命令取回，不应扩大 helper 的目录权限。

成功后保留仍持有原始 Popen 的 supervisor；后续停止和 reap 必须由该原进程执行。新客户端可经 nonce/sequence/hash 绑定 RPC 做只读检查，但 JSON 记录不转移 wait/reap 权限。旧父进程只有在其工作已由原父回收、全树/相机FD均空且实例精确核对后才能单独退休，不能借关闭 supervisor 终止运行中的相机。

下一轮依据真实逐 tap 记录比对 accepted51 的 DDR 采样、lane 字节顺序与包 ECC；还需外部 MCLK/PHY/IO/关键告警/MTBF 和实际图像像素验证。不能修改已接受的生产颜色参数来回避新例程的接收故障。
