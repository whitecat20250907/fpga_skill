# 六例复用 skill 验证记录

日期：2026-09-23。所有编译和仿真都在独立临时目录进行，未改原例程、未重新烧板。

## 输入检查

六例 .al 直接文件引用为 5/5/6/7/18/66，显式项目/IP fileSet 引用无缺失。输入 SHA-256 清单位于 skill 的 references/baseline_manifest.json。整理结束六例输入无变动。

## UART 真实构建

目标：E:/qianrufpga/tmp/skill_validation/uart_reuse_20260923

通过 helper 从 01 复制 14 个输入文件，重定位 .al 并产生 build.tcl；本机 TD 6.2.2.200067 完成 syn_1、phy_1，进程退出 0，日志有 BIT-1004 的 fpga_prj.bit 生成记录。

时序：`Timing info: SWNS 33.003ns | STNS 0.000ns | HWNS 0.061ns | HTNS 0.000ns.`

- fpga_prj.bit：4850270 字节；SHA-256 `c6b09df1d04fd6659a8aa37ccac02b93c0d3f49f6cb1331d7574895fdc455a27`。
- fpga_prj_compress.bit：326352 字节；SHA-256 `2f91e221e504cca59e2d326f0efe130f945ea53679dca8800c125692ae0cb510`。

## UART 真实仿真

在目标 uisrc/02_sim/verified 运行：

```powershell
& 'D:/Modelsim/soft/win64/vsim.exe' -c -do 'do run.do; quit -code 0 -force'
```

ModelSim 10.5，退出 0，Errors 0 / Warnings 0；25 MHz / 115200 波特率下 55、AA、00、FF、31、95 六字节回环比较通过。已有自检按间隔发字节，不是满速压力测试。原 transcript 保存在上述临时目标内。

## 相机工程复制

目标：E:/qianrufpga/tmp/skill_validation/camera_reuse_20260923

从 06 复制 132 个输入文件，除重定位 .al 外逐文件哈希与基线一致，显式依赖检查通过，ROM/加密文件/IP 内部 ADC/SDC 均随目录保留。保留原宽泛 exclusive 时钟组警告。此目标未重新编译、仿真或上板，原相机例程的实机成功来自用户确认。

## 保护行为检查

- overwrite_rejected：PASS。
- source_drift_rejected：PASS。
- missing_adc_detected：PASS。
- camera_dependencies_copied_exactly：PASS。
- camera_reference_audit_pass：PASS。
- six_originals_unchanged：PASS。

负向测试仅修改独立测试副本。记录目录：E:/qianrufpga/tmp/skill_validation/guard_tests_412aqjco。

## 检查范围

audit 只检查显式项目/IP fileSet 引用及直接 ADC 冲突；不是 Verilog 编译器，不能证明所有 include、黑盒、差分/DDR 引脚展开、时序约束完整或功能正确。全局和仓库 skill 的结构校验结果在最终交付前核对。

结构检查：skill-creator quick_validate 全局副本通过；UI YAML、Python 语法、Markdown 本地链接检查通过。工作区 skill 与全局文件逐字节一致。
