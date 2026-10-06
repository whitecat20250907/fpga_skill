# 六例引脚索引（带来源）

本表来自 2026-09-23 当前成功例程的 ADC。源码根目录为 E:/qianrufpga/fpga-lab/examples。只适用于相同板卡、封装与连接。

主时钟：01/02/03/05/06 为 T16、25 MHz、LVCMOS18；04/06 为 T13 正端的 100 MHz LVDS18（配对负端 T14）。UART TX/RX 为 U11/V11，主板 I²C 为 N14/U16；相机 I²C 为 B14/A14。

以下分开列出每一个保留的 ADC，并非把所有表同时合并使用。标为“IP/目录内约束”的文件可能含模板或备用映射，需由 IPC fileSet、TD 导入日志和 IO 实现报告确定参与关系。差分负端可能由工具成对占用，表中只列正端不代表负端空闲。

使用时打开原 ADC 保留完整属性；本索引附其原指令，不能只抄球号。脚本 audit 仅自动核对直接工程 ADC 的显式冲突，IP 展开和专用资源冲突仍须 TD 检查。

## 01 01_uart_loop

顶层：`uart_top`；器件：`PH1A90SEG324`。

### uisrc/04_pin/fpga_pin.adc

直接注册于 .al 的约束。

| 信号 | LOCATION | IOSTANDARD |
|---|---|---|
| I_sysclk | T16 | LVCMOS18 |
| O_uart_tx | U11 | LVCMOS18 |
| I_uart_rx | V11 | LVCMOS18 |

<details>
<summary>原 ADC 引脚指令（保留全部属性）</summary>

```tcl
set_pin_assignment	{ I_sysclk      }	{ LOCATION = T16; IOSTANDARD = LVCMOS18; }
set_pin_assignment	{ O_uart_tx       }	{ LOCATION = U11; IOSTANDARD = LVCMOS18; }
set_pin_assignment	{ I_uart_rx       }	{ LOCATION = V11; IOSTANDARD = LVCMOS18; }
```

</details>

## 02 02_i2c_eeprom

顶层：`eeprom_test`；器件：`PH1A90SEG324`。

### uisrc/04_pin/fpga_pin.adc

直接注册于 .al 的约束。

| 信号 | LOCATION | IOSTANDARD |
|---|---|---|
| I_sysclk | T16 | LVCMOS18 |
| O_iic_scl | N14 | LVCMOS18 |
| IO_iic_sda | U16 | LVCMOS18 |

<details>
<summary>原 ADC 引脚指令（保留全部属性）</summary>

```tcl
set_pin_assignment	{ I_sysclk        }	{ LOCATION = T16; IOSTANDARD = LVCMOS18;}
set_pin_assignment	{ O_iic_scl       }	{ LOCATION = N14; IOSTANDARD = LVCMOS18; }
set_pin_assignment	{ IO_iic_sda      }	{ LOCATION = U16; IOSTANDARD = LVCMOS18; }
```

</details>

## 03 03_iic_rtc

顶层：`rtc_clock_ds1337`；器件：`PH1A90SEG324`。

### uisrc/04_pin/fpga_pin.adc

直接注册于 .al 的约束。

| 信号 | LOCATION | IOSTANDARD |
|---|---|---|
| I_sysclk | T16 | LVCMOS18 |
| O_iic_scl | N14 | LVCMOS18 |
| IO_iic_sda | U16 | LVCMOS18 |
| O_uart_tx | U11 | LVCMOS18 |

<details>
<summary>原 ADC 引脚指令（保留全部属性）</summary>

```tcl
set_pin_assignment	{ I_sysclk        }	{ LOCATION = T16; IOSTANDARD = LVCMOS18; }
set_pin_assignment	{ O_iic_scl       }	{ LOCATION = N14; IOSTANDARD = LVCMOS18; }
set_pin_assignment	{ IO_iic_sda      }	{ LOCATION = U16; IOSTANDARD = LVCMOS18; }
set_pin_assignment	{ O_uart_tx       }	{ LOCATION = U11; IOSTANDARD = LVCMOS18; }
```

</details>

## 04 04_ddr3_axi_fdma_test

顶层：`example_top`；器件：`PH1A90SEG324`。

### uisrc/03_ip/ui_ddr/ddr_ip.adc

IP/目录内约束；不是独立要求再添加一次。

| 信号 | LOCATION | IOSTANDARD |
|---|---|---|
| ddr_dq[0] | U8 | SSTL135 |
| ddr_dq[1] | T8 | SSTL135 |
| ddr_dq[2] | U9 | SSTL135 |
| ddr_dq[3] | U7 | SSTL135 |
| ddr_dq[4] | V10 | SSTL135 |
| ddr_dq[5] | P10 | SSTL135 |
| ddr_dq[6] | V9 | SSTL135 |
| ddr_dq[7] | R10 | SSTL135 |
| ddr_dq[8] | U6 | SSTL135 |
| ddr_dq[9] | V5 | SSTL135 |
| ddr_dq[10] | T5 | SSTL135 |
| ddr_dq[11] | V4 | SSTL135 |
| ddr_dq[12] | V1 | SSTL135 |
| ddr_dq[13] | U1 | SSTL135 |
| ddr_dq[14] | V2 | SSTL135 |
| ddr_dq[15] | U2 | SSTL135 |
| ddr_dqs_n[0] | T9 | DIFF_SSTL135 |
| ddr_dqs_p[0] | T10 | DIFF_SSTL135 |
| ddr_dqs_n[1] | U4 | DIFF_SSTL135 |
| ddr_dqs_p[1] | U3 | DIFF_SSTL135 |
| ddr_dm[0] | N9 | SSTL135 |
| ddr_dm[1] | V6 | SSTL135 |
| ddr_ck_n[0] | N7 | DIFF_SSTL135 |
| ddr_ck_p[0] | P7 | DIFF_SSTL135 |
| ddr_ras_n | T6 | SSTL135 |
| ddr_cas_n | R1 | SSTL135 |
| ddr_we_n | R2 | SSTL135 |
| ddr_reset_n | P9 | SSTL135 |
| ddr_cke[0] | R8 | SSTL135 |
| ddr_cs_n[0] | R5 | SSTL135 |
| ddr_odt[0] | P1 | SSTL135 |
| ddr_addr[0] | T4 | SSTL135 |
| ddr_addr[1] | N4 | SSTL135 |
| ddr_addr[2] | R6 | SSTL135 |
| ddr_addr[3] | T3 | SSTL135 |
| ddr_addr[4] | N3 | SSTL135 |
| ddr_addr[5] | P5 | SSTL135 |
| ddr_addr[6] | N5 | SSTL135 |
| ddr_addr[7] | P8 | SSTL135 |
| ddr_addr[8] | M5 | SSTL135 |
| ddr_addr[9] | R7 | SSTL135 |
| ddr_addr[10] | P2 | SSTL135 |
| ddr_addr[11] | N6 | SSTL135 |
| ddr_addr[12] | P3 | SSTL135 |
| ddr_addr[13] | N8 | SSTL135 |
| ddr_ba[0] | T1 | SSTL135 |
| ddr_ba[1] | P4 | SSTL135 |
| ddr_ba[2] | R3 | SSTL135 |

<details>
<summary>原 ADC 引脚指令（保留全部属性）</summary>

```tcl
set_ippin_assignment { ddr_dq[0] } {LOCATION = U8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[1] } {LOCATION = T8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[2] } {LOCATION = U9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[3] } {LOCATION = U7; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[4] } {LOCATION = V10; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[5] } {LOCATION = P10; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[6] } {LOCATION = V9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[7] } {LOCATION = R10; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[8] } {LOCATION = U6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[9] } {LOCATION = V5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[10] } {LOCATION = T5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[11] } {LOCATION = V4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[12] } {LOCATION = V1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[13] } {LOCATION = U1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[14] } {LOCATION = V2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[15] } {LOCATION = U2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dqs_n[0] } {LOCATION = T9; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dqs_p[0] } {LOCATION = T10; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dqs_n[1] } {LOCATION = U4; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dqs_p[1] } {LOCATION = U3; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dm[0] } {LOCATION = N9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dm[1] } {LOCATION = V6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ck_n[0] } {LOCATION = N7; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_ck_p[0] } {LOCATION = P7; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_ras_n } {LOCATION = T6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_cas_n } {LOCATION = R1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_we_n } {LOCATION = R2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_reset_n } {LOCATION = P9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_cke[0] } {LOCATION = R8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_cs_n[0] } {LOCATION = R5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_odt[0] } {LOCATION = P1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[0] } {LOCATION = T4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[1] } {LOCATION = N4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[2] } {LOCATION = R6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[3] } {LOCATION = T3; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[4] } {LOCATION = N3; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[5] } {LOCATION = P5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[6] } {LOCATION = N5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[7] } {LOCATION = P8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[8] } {LOCATION = M5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[9] } {LOCATION = R7; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[10] } {LOCATION = P2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[11] } {LOCATION = N6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[12] } {LOCATION = P3; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[13] } {LOCATION = N8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ba[0] } {LOCATION = T1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ba[1] } {LOCATION = P4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ba[2] } {LOCATION = R3; IOSTANDARD = SSTL135; }
```

</details>

### uisrc/03_ip/ui_ddr/ui_ddr.adc

IP/目录内约束；不是独立要求再添加一次。

| 信号 | LOCATION | IOSTANDARD |
|---|---|---|
| ddr_dq[0] | U8 | SSTL135 |
| ddr_dq[1] | T8 | SSTL135 |
| ddr_dq[2] | U9 | SSTL135 |
| ddr_dq[3] | U7 | SSTL135 |
| ddr_dq[4] | V10 | SSTL135 |
| ddr_dq[5] | P10 | SSTL135 |
| ddr_dq[6] | V9 | SSTL135 |
| ddr_dq[7] | R10 | SSTL135 |
| ddr_dq[8] | U6 | SSTL135 |
| ddr_dq[9] | V5 | SSTL135 |
| ddr_dq[10] | T5 | SSTL135 |
| ddr_dq[11] | V4 | SSTL135 |
| ddr_dq[12] | V1 | SSTL135 |
| ddr_dq[13] | U1 | SSTL135 |
| ddr_dq[14] | V2 | SSTL135 |
| ddr_dq[15] | U2 | SSTL135 |
| ddr_dqs_n[0] | T9 | DIFF_SSTL135 |
| ddr_dqs_p[0] | T10 | DIFF_SSTL135 |
| ddr_dqs_n[1] | U4 | DIFF_SSTL135 |
| ddr_dqs_p[1] | U3 | DIFF_SSTL135 |
| ddr_dm[0] | N9 | SSTL135 |
| ddr_dm[1] | V6 | SSTL135 |
| ddr_ck_n[0] | N7 | DIFF_SSTL135 |
| ddr_ck_p[0] | P7 | DIFF_SSTL135 |
| ddr_ras_n | T6 | SSTL135 |
| ddr_cas_n | R1 | SSTL135 |
| ddr_we_n | R2 | SSTL135 |
| ddr_reset_n | P9 | SSTL135 |
| ddr_cke[0] | R8 | SSTL135 |
| ddr_cs_n[0] | R5 | SSTL135 |
| ddr_odt[0] | P1 | SSTL135 |
| ddr_addr[0] | T4 | SSTL135 |
| ddr_addr[1] | N4 | SSTL135 |
| ddr_addr[2] | R6 | SSTL135 |
| ddr_addr[3] | T3 | SSTL135 |
| ddr_addr[4] | N3 | SSTL135 |
| ddr_addr[5] | P5 | SSTL135 |
| ddr_addr[6] | N5 | SSTL135 |
| ddr_addr[7] | P8 | SSTL135 |
| ddr_addr[8] | M5 | SSTL135 |
| ddr_addr[9] | R7 | SSTL135 |
| ddr_addr[10] | P2 | SSTL135 |
| ddr_addr[11] | N6 | SSTL135 |
| ddr_addr[12] | P3 | SSTL135 |
| ddr_addr[13] | N8 | SSTL135 |
| ddr_ba[0] | T1 | SSTL135 |
| ddr_ba[1] | P4 | SSTL135 |
| ddr_ba[2] | R3 | SSTL135 |

<details>
<summary>原 ADC 引脚指令（保留全部属性）</summary>

```tcl
set_ippin_assignment { ddr_dq[0] } {LOCATION = U8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[1] } {LOCATION = T8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[2] } {LOCATION = U9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[3] } {LOCATION = U7; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[4] } {LOCATION = V10; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[5] } {LOCATION = P10; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[6] } {LOCATION = V9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[7] } {LOCATION = R10; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[8] } {LOCATION = U6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[9] } {LOCATION = V5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[10] } {LOCATION = T5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[11] } {LOCATION = V4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[12] } {LOCATION = V1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[13] } {LOCATION = U1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[14] } {LOCATION = V2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[15] } {LOCATION = U2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dqs_n[0] } {LOCATION = T9; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dqs_p[0] } {LOCATION = T10; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dqs_n[1] } {LOCATION = U4; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dqs_p[1] } {LOCATION = U3; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dm[0] } {LOCATION = N9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dm[1] } {LOCATION = V6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ck_n[0] } {LOCATION = N7; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_ck_p[0] } {LOCATION = P7; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_ras_n } {LOCATION = T6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_cas_n } {LOCATION = R1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_we_n } {LOCATION = R2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_reset_n } {LOCATION = P9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_cke[0] } {LOCATION = R8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_cs_n[0] } {LOCATION = R5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_odt[0] } {LOCATION = P1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[0] } {LOCATION = T4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[1] } {LOCATION = N4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[2] } {LOCATION = R6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[3] } {LOCATION = T3; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[4] } {LOCATION = N3; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[5] } {LOCATION = P5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[6] } {LOCATION = N5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[7] } {LOCATION = P8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[8] } {LOCATION = M5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[9] } {LOCATION = R7; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[10] } {LOCATION = P2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[11] } {LOCATION = N6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[12] } {LOCATION = P3; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[13] } {LOCATION = N8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ba[0] } {LOCATION = T1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ba[1] } {LOCATION = P4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ba[2] } {LOCATION = R3; IOSTANDARD = SSTL135; }
```

</details>

### uisrc/04_pin/fpga_pin.adc

直接注册于 .al 的约束。

| 信号 | LOCATION | IOSTANDARD |
|---|---|---|
| I_ddr_clk | T13 | LVDS18 |

<details>
<summary>原 ADC 引脚指令（保留全部属性）</summary>

```tcl
set_pin_assignment  { I_ddr_clk	}		{ LOCATION = T13;  IOSTANDARD = LVDS18; } 
```

</details>

## 05 05_tpg_dsi_7cun

顶层：`system_top`；器件：`PH1A90SEG324`。

### uisrc/04_pin/fpga_pin.adc

直接注册于 .al 的约束。

| 信号 | LOCATION | IOSTANDARD |
|---|---|---|
| I_sys_clk_25m | T16 | LVCMOS18 |
| O_clk_hs_p | E16 | LVDS18 |
| O_clk_lp_n | B13 | LVCMOS18 |
| O_clk_lp_p | A13 | LVCMOS18 |
| O_data_hs_p[0] | F18 | LVDS18 |
| O_data_hs_p[1] | K16 | LVDS18 |
| O_data_hs_p[2] | D17 | LVDS18 |
| O_data_hs_p[3] | J17 | LVDS18 |
| O_data_lp_p[0] | G14 | LVCMOS18 |
| O_data_lp_n[0] | G13 | LVCMOS18 |
| O_data_lp_p[1] | H14 | LVCMOS18 |
| O_data_lp_n[1] | J14 | LVCMOS18 |
| O_data_lp_p[2] | D18 | LVCMOS18 |
| O_data_lp_n[2] | E18 | LVCMOS18 |
| O_data_lp_p[3] | J15 | LVCMOS18 |
| O_data_lp_n[3] | K15 | LVCMOS18 |

<details>
<summary>原 ADC 引脚指令（保留全部属性）</summary>

```tcl
set_pin_assignment	{ I_sys_clk_25m }	{ LOCATION = T16; IOSTANDARD = LVCMOS18; PULLTYPE = PULLUP; }
set_pin_assignment	{ O_clk_hs_p }	{ LOCATION = E16; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; }
set_pin_assignment	{ O_clk_lp_n }	{ LOCATION = B13; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = NONE; SLEWRATE = FAST; }
set_pin_assignment	{ O_clk_lp_p }	{ LOCATION = A13; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = NONE; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_hs_p[0] }	{ LOCATION = F18; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; }
set_pin_assignment	{ O_data_hs_p[1] }	{ LOCATION = K16; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; }
set_pin_assignment	{ O_data_hs_p[2] }	{ LOCATION = D17; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; }
set_pin_assignment	{ O_data_hs_p[3] }	{ LOCATION = J17; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; }
set_pin_assignment	{ O_data_lp_p[0] }	{ LOCATION = G14; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_n[0] }	{ LOCATION = G13; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_p[1] }	{ LOCATION = H14; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_n[1] }	{ LOCATION = J14; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_p[2] }	{ LOCATION = D18; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_n[2] }	{ LOCATION = E18; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_p[3] }	{ LOCATION = J15; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_n[3] }	{ LOCATION = K15; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
```

</details>

## 06 06_csi_2_dsi_imx415_7cun

顶层：`system_top`；器件：`PH1A90SEG324`。

### uisrc/03_ip/al_ip/ui_ddr/ddr_ip.adc

IP/目录内约束；不是独立要求再添加一次。

| 信号 | LOCATION | IOSTANDARD |
|---|---|---|
| ddr_dq[0] | U8 | SSTL135 |
| ddr_dq[1] | T8 | SSTL135 |
| ddr_dq[2] | U9 | SSTL135 |
| ddr_dq[3] | U7 | SSTL135 |
| ddr_dq[4] | V10 | SSTL135 |
| ddr_dq[5] | P10 | SSTL135 |
| ddr_dq[6] | V9 | SSTL135 |
| ddr_dq[7] | R10 | SSTL135 |
| ddr_dq[8] | U6 | SSTL135 |
| ddr_dq[9] | V5 | SSTL135 |
| ddr_dq[10] | T5 | SSTL135 |
| ddr_dq[11] | V4 | SSTL135 |
| ddr_dq[12] | V1 | SSTL135 |
| ddr_dq[13] | U1 | SSTL135 |
| ddr_dq[14] | V2 | SSTL135 |
| ddr_dq[15] | U2 | SSTL135 |
| ddr_dqs_n[0] | T9 | DIFF_SSTL135 |
| ddr_dqs_p[0] | T10 | DIFF_SSTL135 |
| ddr_dqs_n[1] | U4 | DIFF_SSTL135 |
| ddr_dqs_p[1] | U3 | DIFF_SSTL135 |
| ddr_dm[0] | N9 | SSTL135 |
| ddr_dm[1] | V6 | SSTL135 |
| ddr_ck_n[0] | N7 | DIFF_SSTL135 |
| ddr_ck_p[0] | P7 | DIFF_SSTL135 |
| ddr_ras_n | T6 | SSTL135 |
| ddr_cas_n | R1 | SSTL135 |
| ddr_we_n | R2 | SSTL135 |
| ddr_reset_n | P9 | SSTL135 |
| ddr_cke[0] | R8 | SSTL135 |
| ddr_cs_n[0] | R5 | SSTL135 |
| ddr_odt[0] | P1 | SSTL135 |
| ddr_addr[0] | T4 | SSTL135 |
| ddr_addr[1] | N4 | SSTL135 |
| ddr_addr[2] | R6 | SSTL135 |
| ddr_addr[3] | T3 | SSTL135 |
| ddr_addr[4] | N3 | SSTL135 |
| ddr_addr[5] | P5 | SSTL135 |
| ddr_addr[6] | N5 | SSTL135 |
| ddr_addr[7] | P8 | SSTL135 |
| ddr_addr[8] | M5 | SSTL135 |
| ddr_addr[9] | R7 | SSTL135 |
| ddr_addr[10] | P2 | SSTL135 |
| ddr_addr[11] | N6 | SSTL135 |
| ddr_addr[12] | P3 | SSTL135 |
| ddr_addr[13] | N8 | SSTL135 |
| ddr_ba[0] | T1 | SSTL135 |
| ddr_ba[1] | P4 | SSTL135 |
| ddr_ba[2] | R3 | SSTL135 |

<details>
<summary>原 ADC 引脚指令（保留全部属性）</summary>

```tcl
set_ippin_assignment { ddr_dq[0] } {LOCATION = U8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[1] } {LOCATION = T8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[2] } {LOCATION = U9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[3] } {LOCATION = U7; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[4] } {LOCATION = V10; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[5] } {LOCATION = P10; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[6] } {LOCATION = V9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[7] } {LOCATION = R10; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[8] } {LOCATION = U6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[9] } {LOCATION = V5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[10] } {LOCATION = T5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[11] } {LOCATION = V4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[12] } {LOCATION = V1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[13] } {LOCATION = U1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[14] } {LOCATION = V2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[15] } {LOCATION = U2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dqs_n[0] } {LOCATION = T9; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dqs_p[0] } {LOCATION = T10; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dqs_n[1] } {LOCATION = U4; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dqs_p[1] } {LOCATION = U3; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dm[0] } {LOCATION = N9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dm[1] } {LOCATION = V6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ck_n[0] } {LOCATION = N7; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_ck_p[0] } {LOCATION = P7; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_ras_n } {LOCATION = T6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_cas_n } {LOCATION = R1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_we_n } {LOCATION = R2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_reset_n } {LOCATION = P9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_cke[0] } {LOCATION = R8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_cs_n[0] } {LOCATION = R5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_odt[0] } {LOCATION = P1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[0] } {LOCATION = T4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[1] } {LOCATION = N4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[2] } {LOCATION = R6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[3] } {LOCATION = T3; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[4] } {LOCATION = N3; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[5] } {LOCATION = P5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[6] } {LOCATION = N5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[7] } {LOCATION = P8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[8] } {LOCATION = M5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[9] } {LOCATION = R7; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[10] } {LOCATION = P2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[11] } {LOCATION = N6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[12] } {LOCATION = P3; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[13] } {LOCATION = N8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ba[0] } {LOCATION = T1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ba[1] } {LOCATION = P4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ba[2] } {LOCATION = R3; IOSTANDARD = SSTL135; }
```

</details>

### uisrc/03_ip/al_ip/ui_ddr/ui_ddr.adc

IP/目录内约束；不是独立要求再添加一次。

| 信号 | LOCATION | IOSTANDARD |
|---|---|---|
| ddr_dq[0] | U8 | SSTL135 |
| ddr_dq[1] | T8 | SSTL135 |
| ddr_dq[2] | U9 | SSTL135 |
| ddr_dq[3] | U7 | SSTL135 |
| ddr_dq[4] | V10 | SSTL135 |
| ddr_dq[5] | P10 | SSTL135 |
| ddr_dq[6] | V9 | SSTL135 |
| ddr_dq[7] | R10 | SSTL135 |
| ddr_dq[8] | U6 | SSTL135 |
| ddr_dq[9] | V5 | SSTL135 |
| ddr_dq[10] | T5 | SSTL135 |
| ddr_dq[11] | V4 | SSTL135 |
| ddr_dq[12] | V1 | SSTL135 |
| ddr_dq[13] | U1 | SSTL135 |
| ddr_dq[14] | V2 | SSTL135 |
| ddr_dq[15] | U2 | SSTL135 |
| ddr_dqs_n[0] | T9 | DIFF_SSTL135 |
| ddr_dqs_p[0] | T10 | DIFF_SSTL135 |
| ddr_dqs_n[1] | U4 | DIFF_SSTL135 |
| ddr_dqs_p[1] | U3 | DIFF_SSTL135 |
| ddr_dm[0] | N9 | SSTL135 |
| ddr_dm[1] | V6 | SSTL135 |
| ddr_ck_n[0] | N7 | DIFF_SSTL135 |
| ddr_ck_p[0] | P7 | DIFF_SSTL135 |
| ddr_ras_n | T6 | SSTL135 |
| ddr_cas_n | R1 | SSTL135 |
| ddr_we_n | R2 | SSTL135 |
| ddr_reset_n | P9 | SSTL135 |
| ddr_cke[0] | R8 | SSTL135 |
| ddr_cs_n[0] | R5 | SSTL135 |
| ddr_odt[0] | P1 | SSTL135 |
| ddr_addr[0] | T4 | SSTL135 |
| ddr_addr[1] | N4 | SSTL135 |
| ddr_addr[2] | R6 | SSTL135 |
| ddr_addr[3] | T3 | SSTL135 |
| ddr_addr[4] | N3 | SSTL135 |
| ddr_addr[5] | P5 | SSTL135 |
| ddr_addr[6] | N5 | SSTL135 |
| ddr_addr[7] | P8 | SSTL135 |
| ddr_addr[8] | M5 | SSTL135 |
| ddr_addr[9] | R7 | SSTL135 |
| ddr_addr[10] | P2 | SSTL135 |
| ddr_addr[11] | N6 | SSTL135 |
| ddr_addr[12] | P3 | SSTL135 |
| ddr_addr[13] | N8 | SSTL135 |
| ddr_ba[0] | T1 | SSTL135 |
| ddr_ba[1] | P4 | SSTL135 |
| ddr_ba[2] | R3 | SSTL135 |

<details>
<summary>原 ADC 引脚指令（保留全部属性）</summary>

```tcl
set_ippin_assignment { ddr_dq[0] } {LOCATION = U8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[1] } {LOCATION = T8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[2] } {LOCATION = U9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[3] } {LOCATION = U7; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[4] } {LOCATION = V10; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[5] } {LOCATION = P10; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[6] } {LOCATION = V9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[7] } {LOCATION = R10; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[8] } {LOCATION = U6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[9] } {LOCATION = V5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[10] } {LOCATION = T5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[11] } {LOCATION = V4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[12] } {LOCATION = V1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[13] } {LOCATION = U1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[14] } {LOCATION = V2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dq[15] } {LOCATION = U2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dqs_n[0] } {LOCATION = T9; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dqs_p[0] } {LOCATION = T10; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dqs_n[1] } {LOCATION = U4; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dqs_p[1] } {LOCATION = U3; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_dm[0] } {LOCATION = N9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_dm[1] } {LOCATION = V6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ck_n[0] } {LOCATION = N7; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_ck_p[0] } {LOCATION = P7; IOSTANDARD = DIFF_SSTL135; }
set_ippin_assignment { ddr_ras_n } {LOCATION = T6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_cas_n } {LOCATION = R1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_we_n } {LOCATION = R2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_reset_n } {LOCATION = P9; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_cke[0] } {LOCATION = R8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_cs_n[0] } {LOCATION = R5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_odt[0] } {LOCATION = P1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[0] } {LOCATION = T4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[1] } {LOCATION = N4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[2] } {LOCATION = R6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[3] } {LOCATION = T3; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[4] } {LOCATION = N3; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[5] } {LOCATION = P5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[6] } {LOCATION = N5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[7] } {LOCATION = P8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[8] } {LOCATION = M5; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[9] } {LOCATION = R7; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[10] } {LOCATION = P2; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[11] } {LOCATION = N6; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[12] } {LOCATION = P3; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_addr[13] } {LOCATION = N8; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ba[0] } {LOCATION = T1; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ba[1] } {LOCATION = P4; IOSTANDARD = SSTL135; }
set_ippin_assignment { ddr_ba[2] } {LOCATION = R3; IOSTANDARD = SSTL135; }
```

</details>

### uisrc/03_ip/dsi/constraint_source/pin.adc

IP/目录内约束；不是独立要求再添加一次。

| 信号 | LOCATION | IOSTANDARD |
|---|---|---|
| I_clk | T16 | LVCMOS18 |
| I_rst_n | U14 | LVCMOS18 |
| O_dsi_pwm | H17 | LVCMOS18 |
| O_clk_hs_p | C14 | LVDS18 |
| O_data_hs_p[0] | C17 | LVDS18 |
| O_data_hs_p[1] | A13 | LVDS18 |
| O_data_hs_p[2] | C15 | LVDS18 |
| O_data_hs_p[3] | A14 | LVDS18 |
| O_clk_lp_p | D14 | LVCMOS18 |
| O_clk_lp_n | E15 | LVCMOS18 |
| O_data_lp_p[0] | D18 | LVCMOS18 |
| O_data_lp_n[0] | E18 | LVCMOS18 |
| O_data_lp_p[1] | A18 | LVCMOS18 |
| O_data_lp_n[1] | B18 | LVCMOS18 |
| O_data_lp_p[2] | B16 | LVCMOS18 |
| O_data_lp_n[2] | C16 | LVCMOS18 |
| O_data_lp_p[3] | A15 | LVCMOS18 |
| O_data_lp_n[3] | A16 | LVCMOS18 |

<details>
<summary>原 ADC 引脚指令（保留全部属性）</summary>

```tcl
set_pin_assignment	{ I_clk }		{ LOCATION = T16; IOSTANDARD = LVCMOS18; PULLTYPE = NONE; }
set_pin_assignment	{ I_rst_n }		{ LOCATION = U14; IOSTANDARD = LVCMOS18; PULLTYPE = NONE; }
set_pin_assignment	{ O_dsi_pwm }	{ LOCATION = H17; IOSTANDARD = LVCMOS18; PULLTYPE = NONE; }
set_pin_assignment	{ O_clk_hs_p }	{ LOCATION = C14; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; VOCM = L2; VOD = 300M;}
set_pin_assignment	{ O_data_hs_p[0] }	{ LOCATION = C17; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; VOCM = L2; VOD = 300M;}
set_pin_assignment	{ O_data_hs_p[1] }	{ LOCATION = A13; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; VOCM = L2; VOD = 300M;}
set_pin_assignment	{ O_data_hs_p[2] }	{ LOCATION = C15; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; VOCM = L2; VOD = 300M;}
set_pin_assignment	{ O_data_hs_p[3] }	{ LOCATION = A14; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; VOCM = L2; VOD = 300M;}
set_pin_assignment	{ O_clk_lp_p }		{ LOCATION = D14; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = NONE; SLEWRATE = FAST; }
set_pin_assignment	{ O_clk_lp_n }		{ LOCATION = E15; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = NONE; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_p[0] }	{ LOCATION = D18; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_n[0] }	{ LOCATION = E18; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_p[1] }	{ LOCATION = A18; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_n[1] }	{ LOCATION = B18; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_p[2] }	{ LOCATION = B16; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_n[2] }	{ LOCATION = C16; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_p[3] }	{ LOCATION = A15; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_n[3] }	{ LOCATION = A16; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
```

</details>

### uisrc/04_pin/fpga_pin.adc

直接注册于 .al 的约束。

| 信号 | LOCATION | IOSTANDARD |
|---|---|---|
| I_sysclk_25m | T16 | LVCMOS18 |
| I_ddr_clk | T13 | LVDS18 |
| O_cam_scl | B14 | LVCMOS18 |
| IO_cam_sda | A14 | LVCMOS18 |
| O_clk_rst | B18 | LVCMOS18 |
| S_clk_25m | A18 | LVCMOS18 |
| I_clk_hs_p | E13 | LVDS18 |
| I_data_hs_p[0] | C14 | LVDS18 |
| I_data_hs_p[1] | D14 | LVDS18 |
| I_data_hs_p[2] | A15 | LVDS18 |
| I_data_hs_p[3] | G17 | LVDS18 |
| I_data_lp_p[0] | B16 | LVCMOS18 |
| I_data_lp_n[0] | C16 | LVCMOS18 |
| I_data_lp_p[1] | C15 | LVCMOS18 |
| I_data_lp_n[1] | D15 | LVCMOS18 |
| I_data_lp_p[2] | C17 | LVCMOS18 |
| I_data_lp_n[2] | B17 | LVCMOS18 |
| I_data_lp_p[3] | F15 | LVCMOS18 |
| I_data_lp_n[3] | F14 | LVCMOS18 |
| O_clk_hs_p | E16 | LVDS18 |
| O_clk_lp_n | B13 | LVCMOS18 |
| O_clk_lp_p | A13 | LVCMOS18 |
| O_data_hs_p[0] | F18 | LVDS18 |
| O_data_hs_p[1] | K16 | LVDS18 |
| O_data_hs_p[2] | D17 | LVDS18 |
| O_data_hs_p[3] | J17 | LVDS18 |
| O_data_lp_p[0] | G14 | LVCMOS18 |
| O_data_lp_n[0] | G13 | LVCMOS18 |
| O_data_lp_p[1] | H14 | LVCMOS18 |
| O_data_lp_n[1] | J14 | LVCMOS18 |
| O_data_lp_p[2] | D18 | LVCMOS18 |
| O_data_lp_n[2] | E18 | LVCMOS18 |
| O_data_lp_p[3] | J15 | LVCMOS18 |
| O_data_lp_n[3] | K15 | LVCMOS18 |

<details>
<summary>原 ADC 引脚指令（保留全部属性）</summary>

```tcl
set_pin_assignment	{ I_sysclk_25m }	{ LOCATION = T16; IOSTANDARD = LVCMOS18; PULLTYPE = PULLUP; }
set_pin_assignment	{ I_ddr_clk }		{ LOCATION = T13; IOSTANDARD = LVDS18; PULLTYPE = NONE; }
set_pin_assignment	{ O_cam_scl }		{ LOCATION = B14; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; }
set_pin_assignment	{ IO_cam_sda }		{ LOCATION = A14; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; }
set_pin_assignment	{ O_clk_rst }		{ LOCATION = B18; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = NONE; }
set_pin_assignment	{ S_clk_25m }		{ LOCATION = A18; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = NONE; }
set_pin_assignment	{ I_clk_hs_p }		{ LOCATION = E13; IOSTANDARD = LVDS18; PULLTYPE = NONE; }
set_pin_assignment	{ I_data_hs_p[0] }	{ LOCATION = C14; IOSTANDARD = LVDS18; PULLTYPE = NONE; INDEL = 20; }
set_pin_assignment	{ I_data_hs_p[1] }	{ LOCATION = D14; IOSTANDARD = LVDS18; PULLTYPE = NONE; INDEL = 20; }
set_pin_assignment	{ I_data_hs_p[2] }	{ LOCATION = A15; IOSTANDARD = LVDS18; PULLTYPE = NONE; INDEL = 20; }
set_pin_assignment	{ I_data_hs_p[3] }	{ LOCATION = G17; IOSTANDARD = LVDS18; PULLTYPE = NONE; INDEL = 20; }
set_pin_assignment	{ I_data_lp_p[0] }	{ LOCATION = B16; IOSTANDARD = LVCMOS18; PULLTYPE = PULLUP; }
set_pin_assignment	{ I_data_lp_n[0] }	{ LOCATION = C16; IOSTANDARD = LVCMOS18; PULLTYPE = PULLUP; }
set_pin_assignment	{ I_data_lp_p[1] }	{ LOCATION = C15; IOSTANDARD = LVCMOS18; PULLTYPE = PULLUP; }
set_pin_assignment	{ I_data_lp_n[1] }	{ LOCATION = D15; IOSTANDARD = LVCMOS18; PULLTYPE = PULLUP; }
set_pin_assignment	{ I_data_lp_p[2] }	{ LOCATION = C17; IOSTANDARD = LVCMOS18; PULLTYPE = PULLUP; }
set_pin_assignment	{ I_data_lp_n[2] }	{ LOCATION = B17; IOSTANDARD = LVCMOS18; PULLTYPE = PULLUP; }
set_pin_assignment	{ I_data_lp_p[3] }	{ LOCATION = F15; IOSTANDARD = LVCMOS18; PULLTYPE = PULLUP; }
set_pin_assignment	{ I_data_lp_n[3] }	{ LOCATION = F14; IOSTANDARD = LVCMOS18; PULLTYPE = PULLUP; }
set_pin_assignment	{ O_clk_hs_p }	{ LOCATION = E16; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; }
set_pin_assignment	{ O_clk_lp_n }	{ LOCATION = B13; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = NONE; SLEWRATE = FAST; }
set_pin_assignment	{ O_clk_lp_p }	{ LOCATION = A13; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = NONE; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_hs_p[0] }	{ LOCATION = F18; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; }
set_pin_assignment	{ O_data_hs_p[1] }	{ LOCATION = K16; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; }
set_pin_assignment	{ O_data_hs_p[2] }	{ LOCATION = D17; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; }
set_pin_assignment	{ O_data_hs_p[3] }	{ LOCATION = J17; IOSTANDARD = LVDS18; PULLTYPE = NONE; PRE_EMP = ON; }
set_pin_assignment	{ O_data_lp_p[0] }	{ LOCATION = G14; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_n[0] }	{ LOCATION = G13; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_p[1] }	{ LOCATION = H14; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_n[1] }	{ LOCATION = J14; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_p[2] }	{ LOCATION = D18; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_n[2] }	{ LOCATION = E18; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_p[3] }	{ LOCATION = J15; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
set_pin_assignment	{ O_data_lp_n[3] }	{ LOCATION = K15; IOSTANDARD = LVCMOS18; DRIVESTRENGTH = 8; PULLTYPE = PULLUP; SLEWRATE = FAST; }
```

</details>
