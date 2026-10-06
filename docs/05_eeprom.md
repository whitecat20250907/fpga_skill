# 第二个实验：EEPROM + ChipWatcher

UART已由用户确认实机回环通过。剩余六组按EEPROM、RTC、DDR、DSI测试图、IMX415、10G UDP推进；10G含loop/speed两个子工程。使用examples的顶层目录，不使用RTC下重复嵌套的工程。

## 准备与改动

打开 E:/qianrufpga/fpga-lab/examples/02_i2c_eeprom/fpga_prj.al。
2026-09-22准备：项目旧F盘路径已改为当前目录；补入40ns的timing.sdc并注册到约束集合。保留RTL与现有ChipWatcher，源码引用均存在。尚未重编译/下载/实测。
这个例程会循环写板载测试EEPROM并读回，地址按字节递增；它不是只读实验。普通开发板测试用途下按例程运行，若该EEPROM已存自定义数据则先保存。

## 1 看代码

VS Code打开uisrc/01_rtl/eeprom_test.v。顶层eeprom_test，端口只有I_sysclk、O_iic_scl、IO_iic_sda，没有UART端口。
参数SYSCLKHZ=25_000_000，旁边100MHz注释错误。O_test_led/O_error_led残留赋值不是实际顶层LED端口，可能产生未使用/隐式网络警告，不能据此寻找LED现象。
状态机TS_S：0请求写→1等待写忙→2等待写完成及间隔→3等待读忙→4检查读回值→5等待下次周期。
wr_data[23:16]为写入值，rd_data[7:0]为读回值，iic_error为数据比较错误，iic_bus_error为总线错误。约每500ms启动下一轮。

## 2 约束与编译

1. 保存关闭上一工程，TD打开本工程，核对顶层eeprom_test、PH1A90SEG324。
2. Sources中应有eeprom_test.v、uii2c.v、al_ip/cwc/cwc.xml；Constraints有fpga_pin.adc和timing.sdc。cwc就是已生成并例化的ChipWatcher，不需再新建一个。
3. 双击Read Design。Tools→IO Constraint核对T16时钟、N14 SCL、U16 SDA，均LVCMOS18。SDC的I_sysclk周期40ns。
4. 运行Syn Opt，再Phy Opt（或逐项Optimize RTL、Gate、Placement、Routing、Generate Bitstream）。看首条Error与最终时序，不把压缩包旧bit当新结果。
5. 本次位流应在本工程fpga_prj_Runs/phy_1/fpga_prj.bit；检查生成时间。

## 3 下载并打开调试

1. 用BitWriter PROGRAM_SRAM下载本例新bit，确认路径含02_i2c_eeprom。当前板上UART功能会被替换，串口停止回环正常。
2. 在本工程打开ChipWatcher，再点Watch。必须使用与本次bit匹配的调试信息，不沿用UART的描述。
3. 在Name区右键Add Signals，将下面七个probe加进来：

| 探针 | 信号 | 位宽 |
|---|---|---|
| probe0 | rd_data[7:0] | 8 |
| probe1 | wr_data[23:16] | 8 |
| probe2 | TS_S | 3 |
| probe3 | iic_error | 1 |
| probe4 | iic_req | 1 |
| probe5 | iic_bus_error | 1 |
| probe6 | t500ms_en | 1 |

4. 将probe0/probe1显示进制改为Hexadecimal，状态probe2用Unsigned/Decimal。
5. Add Triggers选probe2，Operators选相等（==），值为5（按当前进制填写），表示进入读后等待阶段；保证触发位置后还有采样点，不放在窗口最后一个点。
6. 启动捕获，等Finished。若从等待态立即触发也正常，在状态5内检查结果即可。原理上比较结果和TS_S在同一个时钟更新，观察状态5稳定后的采样点。
7. 读值probe0应等于写值probe1；probe3和probe5为0。重新捕获，间隔约1秒，至少观察3个不同数据值仍相等。
8. 不用深度几千点的单次波形硬看500ms完整循环；25MHz下4096点只有163.84us，用指定状态触发或多次捕获。

## 通过条件

下载成功；捕获到读完成后的状态5；多轮不同地址/数据的读回值等于写值；比较错误和总线错误未出现。iic_error不是粘滞历史标志，几次截图不能证明永远无错，但足够初步bring-up；后续严谨压力测试加完成/错误累计计数。
仅看到error=0不算通过，因为复位/没运行时它也可能为0。
若长期触发不到，先立即捕获看看状态，再检查I2C应答、供电与匹配bit，不能盲改引脚。

下一步截图：先提供本例Generate Bitstream的结果或首条Error；通过后再看ChipWatcher Watch完整界面并设置触发。
