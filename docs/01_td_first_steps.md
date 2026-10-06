# 第一课：TD工程、引脚和编译

无需连接开发板。依据本地《米联客-安路FPGA TD软件快速入门课程》第24–53页和UART源工程。

## Quartus对应关系

| Quartus | TD |
|---|---|
| .qpf/.qsf | .al工程，.adc物理约束 |
| Top-level entity | Top Module |
| Pin Planner | IO约束编辑界面、.adc |
| TimeQuest / .sdc | TD时序分析 / .sdc |
| Analysis & Synthesis | Read Design、综合 |
| Fitter | Physical Design、布局布线 |
| Assembler / .sof | Generate Bitstream / .bit（格式不通用） |
| Programmer | BitWrite |
| SignalTap | ChipWatcher |
| IP Catalog | IP Catalog、安路对应IP |

Intel PLL/RAM原语不能直接搬过来，但RTL与时序设计概念可以迁移。

## 1 打开工程

1. 启动 E:/qianrufpga/TD/bin/td.exe，Help/About记录实际版本；安装包名称不能代替实际版本。
2. 打开 E:/qianrufpga/fpga-lab/examples/01_uart_loop/fpga_prj.al。
3. 核对器件PH1A90SEG324，例程等级-2（实物等级后续核对）。XML族名PH1，教程界面写PH1A，以完整器件名为准。
4. Hierarchy顶层应为uart_top；读uart_top.v、uiuart_rx.v、uiuart_tx.v。接收模块的数据和有效信号送到发送模块，完成回环。
5. 核对约束集合已有uisrc/04_pin/fpga_pin.adc与timing.sdc。只在磁盘上存在不代表参与编译。

## 2 学习引脚调配

顺序：顶层端口 → 原理图网络 → FPGA焊球 → BANK供电 → IOStandard。
FMC连接器脚号、RK芯片脚号都不是FPGA封装焊球号。

原例程ADC：

```tcl
set_pin_assignment { I_sysclk } { LOCATION = T16; IOSTANDARD = LVCMOS18; }
set_pin_assignment { O_uart_tx } { LOCATION = U11; IOSTANDARD = LVCMOS18; }
set_pin_assignment { I_uart_rx } { LOCATION = V11; IOSTANDARD = LVCMOS18; }
```

T16为25MHz输入，U11发送，V11接收；与本地本板管脚资料对应。LVCMOS18是1.8V标准，不能随意改成3.3V。
GUI操作：先完成Read Design，再打开IO约束编辑界面，核对Name、Direction、Location、IOStandard，保存ADC。首次只核对，不换脚。
添加新文件：Hierarchy右键 → Add Sources → Constraint files → 选择ADC/SDC；新建约束保存后确认加入工程。
后续BANK13/J32选择必须核对原理图和实际供电，不能因为接相机就盲改跳帽。

## 3 学习时序约束

```tcl
create_clock -name sysclk -period 40.000 [get_ports {I_sysclk}]
```

单位ns，25MHz周期40ns。教程正文10ns是笔误。ADC负责物理连接；SDC告诉工具电路在多快节拍下必须工作。
后续PLL课学习derive_clocks/派生时钟，UART课学习异步输入同步器；不要把整个设计设false path来消除警告。

## 4 编译与检查

1. 保存并运行Read Design，排除语法、顶层、缺源文件错误。
2. 运行综合，确认模块层次与资源合理。
3. 运行布局布线，检查引脚冲突、电压冲突和时序。
4. 运行Generate Bitstream；也可以使用完整一键编译。
5. Log Tree先看首个Error；查看25MHz时钟是否识别、资源、时序裕量、未约束路径。生成bit不意味着所有时序都已正确约束。
6. 核对新生成bit的时间与路径，记录到records/progress.md。

本课验收：器件和顶层正确，三个IO正确约束，40ns时钟生效，完成位流生成并记录警告/时序。不接板也能完成。
若遇license错误，保存原文再处理；目前只确认TD程序存在，未验证许可证。

## 教材勘误

本板无FPGA用户LED和按键，PLL教材O_up_led不能照搬到实际设计，不能以板上LED证明该工程正常。
原工程含作者电脑ModelSim路径，仿真课再配置本机工具；不影响识别本课源文件。
压缩bit属于配置文件压缩，不等于赛题的JPEG/LZ77图像压缩。
