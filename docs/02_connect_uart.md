# 接板与UART回环

当前用户未接板。第一课编译完成后再进入此步骤；接口不明确时先核对板卡照片与本版原理图。

1. 断电检查核心板、VID005和排线；FMC、CSI排线和外置JTAG端子不要带电插拔。
2. 按板卡手册接DC12V电源；电脑USB接板载FPGA OneCable/JTAG+UART接口，不混用RK OTG/调试口。
3. 设备管理器记录新增USB与COM设备。板载OneCable集成JTAG/UART，通常不需另购下载器。
4. TD打开BitWrite，Debug Server选择AL-LINK-FT(Local Host)，选择实际Cable，教程本地端口5555，Apply and Close。
5. 识别到目标FPGA再下载；Cable为空先检查供电/线/口。驱动错误时核对FTDI A接口硬件ID，按手册安装WinUSB；不要批量替换驱动或改UART B接口。
6. 首次用SRAM配置方式加载本次编译bit并Run，不选PROGRAM_FLASH。掉电后测试配置消失，原Flash内容保留。
7. FPGA UART端口设115200、8N1、无流控，关闭本地回显；RK串口1500000不是同一个端口。
8. 分次手动发送短字符串hello123，收到相同内容。该例无完整流控队列，先不做长串满速压力测试。
9. 记录COM号、bit路径、发送/接收结果。无回传检查COM归属、下载状态、RX活动；乱码先查波特率与时钟。

不要短接板上TX/RX代替FPGA逻辑验收。后续ChipWatcher观察接收有效、数据与发送请求定位。
