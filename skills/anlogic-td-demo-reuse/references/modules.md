# 六份基线的模块与 IP

源码根目录为 `E:/qianrufpga/fpga-lab/examples`。下文相对路径均相对于对应例程。仅有 skill 不包含供应商源码，需要一起保留六个目录及版权声明。

## 01_uart_loop

- 顶层 uart_top：`uisrc/01_rtl/uart_top.v`。
- ui_uart_rx、ui_uart_tx：`uisrc/03_ip/uiuart_rx.v`、`uiuart_tx.v`，普通 RTL，无需 IP Catalog 生成。
- 25 MHz，低有效 I_uart_rstn，顶层波特率 115200；BAUD_DIV 使用实际实例参数，不用模块默认值替代。
- RX 的 O_uart_rvalid 表示 O_uart_rdata[7:0] 有效；TX 输入 I_uart_wreq/I_uart_wdata，输出 O_uart_wbusy。多发送源须排队，按状态机确认接受周期。
- 自检：`uisrc/02_sim/verified/run.do`、`uart_loop_tb.sv`；40 ns 时钟、等待复位、按间隔发送 6 字节。原 cmd.do 有作者路径和时钟/运行长度问题。

## 02_i2c_eeprom

- 顶层 eeprom_test：`uisrc/01_rtl/eeprom_test.v`；通用 ui_i2c：`uisrc/03_ip/uii2c.v`。
- WMEN_LEN 最大写字节数包含设备地址，RMEN_LEN 最大读字节数不含设备地址；I_wr_cnt/I_rd_cnt 为本次长度，打包顺序读代码确认。
- I_iic_req 请求，O_iic_busy 忙，O_iic_bus_error 为 ACK 错误；I_iic_mode=1 为该模块随机读模式。
- 24C02 地址字节 0xA0，对应 7 位地址 0x50。SCL=N14、SDA=U16，写后保留内部写周期等待。
- 保留整个 `al_ip/cwc/` 的 XML、配置及生成 RTL。触发 TS_S[2:0]==3'b101，比较 rd_data[7:0] 与 wr_data[23:16]，同时看 iic_error/iic_bus_error。探针须与 bit 匹配。
- 已补 `uisrc/04_pin/timing.sdc` 的 40 ns 并注册 .al，不能复用时漏掉。

## 03_iic_rtc

- 顶层 rtc_clock_ds1337：`uisrc/01_rtl/rtc_clock_ds1337.v`；复用 ui_i2c、uart_tx_block、ui_uart_tx。根据 .al 精确加入源文件。
- DS1337 地址字节 0xD0，对应 7 位地址 0x68；与 EEPROM 共用 N14/U16，组合时一个 I²C 主机加事务调度。
- 启动初始化 12:00:00，周期读取并输出 `12-00-00`。要保留时间时修改初始化策略。
- 原 uart_tx_block 的 tx_index < TX_BYTES 边界及时间寄存器更新拍次，复用时须仿真核对字节数与上一轮数据问题；能看见时间不代表边界已充分验证。
- 根目录内嵌套其他 demo 为重复副本，不属 RTC 依赖。

## 04_ddr3_axi_fdma_test

- 顶层 example_top：`uisrc/01_rtl/system_top.v`；ui_fdma_test：`uisrc/01_rtl/fdma_test.v`；ui_FDMA：`uisrc/03_ip/uifdma/uiFDMA.v`。
- DDR IP `uisrc/03_ip/ui_ddr/ui_ddr.ipc`，保留整个 ui_ddr；调试保留整个 `al_ip/cwc/`。

| 项 | 基线配置 |
|---|---|
| 类型/控制器/PHY | DDR3，MC and Standard PHY |
| 物理宽度/容量 | x16 / 2 Gb，即 256 MiB |
| 接口 | AXI4，实例 ID 宽度 4、数据 128 位 |
| 存储/参考时钟 | 配置 533 MHz / 100 MHz |
| PHY 比率 | 4:1 |
| 速度/延迟 | DDR3-1066G，CL=8、CWL=6 |
| 电压/ECC | 1.35 V / OFF |

- 输入 T13/T14 差分 100 MHz，主 ADC 列正端，负端和 DDR 资源由器件/IP 约束处理。
- 等 S_ddr_init_cal_done 后访问，保留初始化和复位。FDMA 请求/busy/valid/ready 方向按封装代码，不直接套 AXI。
- ui_FDMA 默认 DATA_WIDTH=64、ID_WIDTH=6 不等于本工程实例。
- 原 TEST_MEM_SIZE=2*1024*1024*1024 与物理 256 MiB 不一致，整理时未改动。新工程核实地址单位、截断、环回范围及缓存布局，不能宣称验证了 2 GiB。
- 比较仅低 16 位，test_error 非粘滞，比较有效有一拍寄存。光标计数 640、数据 639 须结合有效拍解释。工程级自检增加全位宽比较及累计/粘滞错误。
- 此 FPGA DDR3L 不等于 RK3576 内存。

## 05_tpg_dsi_7cun

- 顶层 system_top：`uisrc/01_rtl/system_top.v`，保留视频源与整个 `uisrc/03_ip/dsi/`。
- PLL：`uisrc/03_ip/alip/pll/pll.ipc`；输入 25 MHz，当前生成代码 C0=50、C1=100、C2=200、C3=200 MHz/90°、C4=10 MHz。
- 屏 ROM：`uisrc/03_ip/dsi/hdl_source/display_config/rom/instruction_rom.ipc`，连同初始化数据保留。
- 有效区 1024×600，总时序 1344×635；S_tgb_mode 在 0–9 循环，每 121 帧切换。屏接 VID005 的 FPGA DSI，不是 RK DSI。
- 替换源保持 RGB/DE/HS/VS 与像素时钟对齐，先保持屏参数和 PHY。

## 06_csi_2_dsi_imx415_7cun

- 顶层 system_top：`uisrc/01_rtl/system_top.v`；25 MHz 系统输入、100 MHz DDR 参考。
- 通路：IMX415 I²C → 4 lane MIPI RX/CSI 解包 → RAW10/ISP → 像素打包 → DDR/FDMA → 7 寸 DSI。
- 相机寄存器：`uisrc/03_ip/ui_imx415_cfg/ui_cfg_imx415.v`、`ui_imx415_reg.v`，同时核对上层参数。
- MIPI aligner/RX/TX 有加密文件，保留 include 和 wrapper，不能用空 module 或黑盒假装实现。

| IP | 配置路径 |
|---|---|
| PLL | uisrc/03_ip/al_ip/ui_pll/ui_pll.ipc |
| DDR | uisrc/03_ip/al_ip/ui_ddr/ui_ddr.ipc |
| Demosaic RAM | uisrc/03_ip/ui_isp/ui_demosaic/ui_ram_demosaic/ui_ram_demosaic.ipc |
| 整合 RAM | uisrc/03_ip/ui_isp/ui_demosaic/ui_ram_zhenghe/ui_ram_zhenghe.ipc |
| AWB 延迟 RAM | uisrc/03_ip/ui_isp/ui_awb/ui_ram_awb_delay_signal/ui_ram_awb_delay_signal.ipc |
| 屏 ROM | uisrc/03_ip/dsi/hdl_source/display_config/rom/instruction_rom.ipc |

DDR 内 ui_ddr_cfg_rom.txt/.mif、DSI 的 hdl_source/display_config/config_data_nes.mif 都是依赖。RAM 宽深、输出寄存器、读延迟从 IPC/实例核对，不猜测。

**PLL 不一致，重生成前处理：**

| 输出 | 顶层连接名 | 当前生成代码推得频率 |
|---|---|---|
| C0 | S_clk_70m | 75 MHz |
| C1 | S_clk_25m | 25 MHz |
| C2 | S_clk | 50 MHz |
| C3 | S_clk_x2 | 100 MHz |
| C4 | S_clk_x4 | 200 MHz |
| C5 | S_clk_x4_90d | 200 MHz，90° |
| C6 | S_lp_clk | 10 MHz |

IPC 的 C0 仍写 70 MHz；生成 ui_pll.v 的 FIN/反馈/分频参数对应上表；SDC 将 C0 命名 S_clk_25m、C1 命名 S_clk_70m，与顶层互换。此处不是实测频率。克隆先保留；修改时交叉核对原语与 TD 时钟报告，在副本统一配置、产物与约束后回归，不直接 Generate 覆盖基线。

缓存参数：W_DATAWIDTH=128、W_XSIZE=480、W_XSTRIDE=480、W_YSIZE=1080；R_DATAWIDTH=32、R_XSIZE=1024、R_XSTRIDE=1920、R_YSIZE=600。地址/长度单位按封装确认。读出 1024×600 区域不等于自动将 1920×1080 全幅缩小。

本例不证明高帧率眼动、注视算法、RK NPU 或 FPGA→RK CSI 发送已完成。
