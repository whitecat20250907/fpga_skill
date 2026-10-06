# BAR0 读译码最小候选

当前实际 RK BAR0 为 `0x21200000..0x212fffff`，大小 1 MiB，按 1 MiB 对齐。原 09 诊断读选择要求 AXI 地址高 16 位全零；若地址保留分配基址或 CQ 26 位掩码后的前缀，视频寄存器会落入原应用 RAM，出现版本、宽高和状态全零，而软件曾写入的 gain 仍能返回 100 的现象。

`imx415_pcie_top.v` 仅把读选择限定从 `[31:16]==0` 改成 BAR0 偏移 `[19:16]==0`。保留低 16 位 `0x0040..0x011c` 的范围及全部寄存器 case；允许基址 `[31:20]` 非零。使用 bytes 替换，原始所有字节保持不变，仅增加 ASCII 契约注释与一处表达式变更。冻结源实际使用 LF；候选保持这一换行格式。版本仍是 `0x56440901`，下一版版本号由集成人更新。

## 实际数字验证

ModelSim SE-64 10.5 实际编译和运行 `selfcheck.do`，退出 0，编译和仿真均 0 errors / 0 warnings。268 次读检查全部通过：

- 基址 0、`0x21200000`、`0xfff00000`、CQ26 掩码残余 `0x01200000`；每种地址形态覆盖全部 56 个已定义视频寄存器。
- 读范围前后边界、`0x128` vendor IRQ、偏移 `0x1005c`、`0x8005c` 及其它 BAR0 高偏移均不截获为视频寄存器。
- 独立 `old_negative.do` 用原生产读译码运行同一人工地址/数值黄金，确实触发预期 Fatal：168 次不匹配，三种非零前缀下版本读均返回应用 sentinel，而不是正确版本；基址 0 下没有误报。宿主工具返回非零 1；DO 退出处理打印代码 3。两者如实保留，不把负对照列为普通通过。

生产 selector、读寄存器 always block、active frame count 及 RDATA mux 从冻结真实 top 按字节抽取，没有另写等价实现。TB 黄金由人工寄存器表定义；输入计数、状态等使用确定 fixture，应用读响应使用 sentinel。实际日志及 SHA 见 `validation.json`，源和候选 SHA 见 `manifest.json`。

## 重现

候选和生产读片段已经冻结，可直接分别执行以下命令重现数字验证：

```powershell
& 'D:/Modelsim/soft/win64/vsim.exe' -c -do 'E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/tools/bar_decode10/selfcheck.do'
& 'D:/Modelsim/soft/win64/vsim.exe' -c -do 'E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/tools/bar_decode10/old_negative.do'
```

第二条命令应非零退出并包含 `EXPECTED_OLD_UPPER16_ZERO_REGRESSION_DETECTED`。每次运行创建全新日志目录，失败日志也保留。

`prepare_candidate.py` 是候选生成记录，仅在主 top 仍匹配冻结 09 SHA 时允许运行。主工程已由集成人推进至 10 后，脚本会拒绝混用新源；重跑上述 bench 不依赖当前主工程，只读取本目录的冻结生产读片段和参数。

## 验证边界

这是正常即时读条件下的生产读块测试，没有全 PCIe/AXI engine、PHY、真实相机或完整 AXI 背压模型。未启动 TD、未改主工程、未上板，不是问题 1 已修复或所有信息链路通过的证明。读背压、写高位别名和 WSTRB 仍为排队的问题 13。

实际接收、V4L2 和诊断当前使用 BAR0 mmap 加零偏移契约。旧 CHAR_USER pread/pwrite 内部额外加 `0x80000`，该 API 不能继承本次结论；CQ 固定 26 位 aperture 也没有被本候选修复。实际 AXI 地址形态仍需后续硬件诊断证据。
