# 实验路线

每课：读顶层 → 核对引脚/电压/时钟 → 编译看报告 → 下载 → 实测留证 → 小改动复验。
这些板级例程不等于赛题的六项硬性交付。

| 顺序 | 例程 | 学习与验收 |
|---|---|---|
| 1 | 01_uart_loop（已整理） | 工程、顶层、ADC/SDC、编译、下载、115200串口回传 |
| 2 | 00_for_starter/02_fpga_start | 从零新建、IP Catalog、PLL、派生时钟；本板无FPGA用户LED，不能靠灯验收 |
| 3 | 00_for_starter/03_td_modelsim_sim | 本机仿真库、testbench、功能波形 |
| 4 | 00_for_starter/04_use_ChipWatcher | 类似SignalTap，采样时钟、探针、触发、重编译、捕获；在已通过UART工程上练习 |
| 5 | 02_i2c_eeprom | I2C、写读完成、数据一致性 |
| 6 | 03_iic_rtc | I2C寄存器、BCD、时间递增 |
| 7 | 04_ddr3_axi_fdma_test | DDR校准、AXI/FDMA；事务计数增长且错误为零 |
| 8 | 05_tpg_dsi_7cun | 测试图、视频时序、DSI，需匹配7寸屏 |
| 9 | 06_csi_2_dsi_imx415_7cun | IMX415经VID005进入FPGA并显示，需匹配7寸屏 |
| 10 | 07_xgudp/udp_10G_sfpA_loop、speed | 扩展10G通信，需要对应光模块/网卡；缺外设标待验证 |
| 11 | 07_异构方案/415_mipi | 相机→FPGA→RK3576，匹配设备树与驱动 |
| 12 | 任务一验收 | 单路高清实时采集的源码、约束、构建与实测证据 |

外设压缩包在03_iic_rtc中重复嵌套了后续工程，使用顶层同名目录即可。
先逐一推进FPGA例程；Linux、驱动、RKNN、RKLLM、OpenCV随后续任务推进，不一次全部执行。
课程会覆盖：工程/顶层、IP、引脚、时序、综合布局布线、报告、仿真、SRAM下载、ChipWatcher、最后Flash固化。
