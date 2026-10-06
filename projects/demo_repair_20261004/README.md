# 原03/04例程独立修复

2026-10-04：基于skill正式baseline校验后clone，原六examples哈希均不变。03修精确UART包长/快照和RTC读完成后报告；04修128bit检查、28bit字节地址和256MiB边界。三项ModelSim实际自检通过；两目标未TD构建、未新上板，不能写成“所有例程已修好”。

| 工程 | 数字证据 | 下一关 |
|---|---|---|
| [03 RTC](03_iic_rtc/reports/validation.md) | UART54字节、RTC20字节，无额外/旧值 | TD、新bit、实际I2C/RTC走时 |
| [04 DDR](04_ddr3_axi_fdma_test/reports/validation.md) | 12burst/4轮，5个全宽单bit故障、边界/复位/非法配置 | TD、新bit、真实DDR至少完整一轮 |

保留原约束/IP和managed build.tcl；提供独立build_direct.tcl，模板实际TD能力已在UART01验证，不能冒充03/04编译证据。06 CSI→DSI需完整receiver/ISP/ready/constraint迁移，见PCIe工程 reports/demo_reuse_impact.md；此次没有半搬06 PHY。
