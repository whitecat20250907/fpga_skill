# VS Code + TD 全过程（以本仓库UART为例）

## 0. 已验证状态

2026-09-22：现有TD phy_1日志完成位流生成，fpga_prj.bit和fpga_prj_compress.bit已存在。现有约束下最终Setup WNS=33.003ns、Hold WNS=0.061ns，TNS均为0；这不代表所有异步接口都已被时序约束覆盖。
本轮新增verified仿真，在本机ModelSim SE-64 10.5运行通过：25MHz、115200波特率、6字节55/AA/00/FF/31/95逐个回传，检查数据与起止位；不覆盖连续满速、噪声、所有波特率偏差。
用户说明环境和BitWriter已配置；尚无本轮UART实机回环证据。没有自动执行下载或Flash固化。

## 1. 目录习惯

仓库根E:/qianrufpga/fpga-lab，VS Code打开整个仓库。原始资料仍在03_MLK_AFH03_AFC03；TD与license不进入仓库。

```text
fpga-lab/
  fpga-lab.code-workspace    VS Code工作区
  docs/                     分课教程
  records/                  实测记录和来源清单
  examples/01_uart_loop/
    fpga_prj.al              TD工程入口，交给TD管理
    uisrc/
      01_rtl/uart_top.v      可综合顶层和用户逻辑
      02_sim/               原厂仿真文件，原样保留
        verified/           新增自检仿真入口
          uart_loop_tb.sv
          run.do
      03_ip/                可复用模块/厂商生成IP
        uiuart_rx.v
        uiuart_tx.v
      04_pin/
        fpga_pin.adc        物理引脚/IO电平
        timing.sdc          时钟与时序
      05_boot/              后续留存通过验证的发布位流
      06_doc/               单个例程说明
    fpga_prj_Runs/           TD自动生成，不能在里面改设计代码
      syn_1/                综合产物
      phy_1/                布局布线、时序、位流
    log/                    工具日志
```

每个例程独立工程。项目阶段另建projects/task1_camera（规划，尚未创建），保留已通过的例程基线。
RTL放01_rtl；仿真激励放02_sim，不能作为可综合顶层加入；IP参数由TD生成器维护，保留ipc与生成源码/约束，避免手改生成文件。ADC与SDC进入版本管理；Runs、work、日志、许可不进Git。
05_boot只有板上验收通过后才建立对应版本快照，记录Git提交、TD版本、bit哈希和测试结果，不靠文件名猜来源。

## 2. VS Code看代码

1. VS Code菜单File→Open Workspace from File…，选择根目录fpga-lab.code-workspace。
2. 左侧Explorer展开examples→01_uart_loop→uisrc→01_rtl，打开uart_top.v。
3. 再打开03_ip/uiuart_rx.v和uiuart_tx.v。先读顶层端口、SYSCLKHZ、复位计数、接收/发送连线，再读子模块。
4. Ctrl+P快速找文件；Ctrl+Shift+F全仓库搜索uart_rvalid；Ctrl+S保存。已设置Verilog/SystemVerilog/Tcl文件关联；跳转定义功能是否可用取决于安装的语言扩展。
5. 工作区默认隐藏Runs/log/work，减少误改；查看输出用Windows资源管理器或临时关闭files.exclude。
6. 已有文件改完保存即可回TD重新编译。新建文件需要在TD Hierarchy右键Add Sources→Design files加入；只创建文件并不会自动加入TD。
7. 新顶层在TD中右键模块→Set As Top。当前顶层uart_top，不要把uart_loop_tb设成硬件顶层。
8. 注释乱码先用VS Code右下角编码→Reopen with Encoding，尝试原文件编码，不要直接乱码另存破坏原文。

## 3. 仿真先于上板

原厂cmd.do写死C:/modeltech64_10.6d/anlogic/PH1，且原testbench把25MHz算成10ns、仅跑1000ns，因此本课程用独立verified版本。
UART全为普通RTL，不依赖安路PLL/DDR原语库。之后PLL/DDR/IP仿真需要对应器件库和IP仿真模型，不能照抄UART最小脚本。

1. 启动本机D:/Modelsim/soft/win64/vsim.exe。
2. 找到Transcript命令窗口，输入：

```tcl
cd E:/qianrufpga/fpga-lab/examples/01_uart_loop/uisrc/02_sim/verified
do run.do
```

3. 脚本编译RTL和testbench、加载设计、添加波形、运行2ms。预期看到6行RX和PASS，Errors:0。
4. 若波形窗未显示，用View→Wave；缩放到完整时间范围，再放大单字节。
5. clk周期40ns；rx空闲高、起始低、8位LSB优先、停止高；单比特约8.68us。uart_rvalid表示收完一字节；uart_rdata应与输入一致；tx随后回传。
6. 内部复位在约82us后释放，脚本100us后才发送。test_done=1表示全部比对完成。脚本自动检查超时，不能只看波形是否变化。

批量运行PowerShell：

```powershell
Set-Location 'E:/qianrufpga/fpga-lab/examples/01_uart_loop/uisrc/02_sim/verified'
& 'D:/Modelsim/soft/win64/vsim.exe' -c -do 'do run.do; quit -f'
```

改变RTL后重新do run.do；换输入测试在testbench中改，不能通过修改接收结果来让测试通过。

## 4. TD工程与约束

1. Project→Open Project打开examples/01_uart_loop/fpga_prj.al；保留器件PH1A90SEG324，顶层uart_top。
2. 确认Design files有三个RTL文件，Constraints有ADC和SDC。
3. FPGA Flow→Syn Opt→Read Design，双击；应能识别所有模块，无缺模块/语法错误。
4. Tools→IO Constraint，核对I_sysclk=T16、O_uart_tx=U11、I_uart_rx=V11，均为LVCMOS18。第一次保持原约束。
5. timing.sdc中应为create_clock -name sysclk -period 40.000 [get_ports {I_sysclk}]。
6. 修改IO必须核对原理图的网络、FPGA焊球和BANK电压；内部wire不分配引脚。25MHz是40ns，不是教程笔误的10ns。
7. SDC说明时序要求，不会把物理时钟改成所填频率。IO Constraint中物理InDelay/OutDelay也不能代替SDC接口时序预算。

## 5. 综合、布局、布线、位流

第一次逐项做；熟悉后可双击Syn Opt、再双击Phy Opt运行各自完整流程。每步双击或右键Run；若提示前置步骤过期，运行对应前置流程。

| 菜单项 | 工作内容 | 重点检查 |
|---|---|---|
| Read Design | 读源码/展开模块 | 顶层正确、没有缺模块 |
| Optimize RTL | RTL级优化 | 无Error，原先license错误在此 |
| Optimize Gate | 映射器件逻辑 | 资源合理、无异常大量删除 |
| Optimize Placement | 为逻辑分配物理位置 | 无引脚/BANK冲突 |
| Optimize Routing | 连接物理布线 | 最终时序和布线完成 |
| Generate Bitstream | 生成配置文件 | 新bit时间与本次运行一致 |

前三步在Syn Opt；后三步在Phy Opt。Flow Runs里的syn_1和phy_1就是这两组运行。
出错看首条ERROR，入口是该次Runs下run.log；不要用最后一条Run failed代替根因。
完成Routing后打开对应Run，在Design Summary查看Utilization Summary、Timing Summary。Setup/Hold裕量应非负；TNS为0，另看时钟是否完整、未约束路径与CDC，不能只盯一个绿色数字。
当前普通位流：E:/qianrufpga/fpga-lab/examples/01_uart_loop/fpga_prj_Runs/phy_1/fpga_prj.bit。
compress.bit表示FPGA配置位流压缩，不是JPEG/LZ77视频压缩。
改RTL/IP/ADC/SDC后都要重跑受影响步骤；改ChipWatcher探针也要重新生成与下载bit。仿真testbench变化不需要硬件重编译。

## 6. SRAM下载与UART实机验证

1. 接线与电源按本板手册，FMC/CSI/JTAG端子调整在断电时进行。
2. 打开TD的BitWriter下载工具（资料也称BitWrite）；既然你已配置环境，保留已识别成功的Cable设置。
3. 扫描到正确FPGA。点击Add选上面本次生成的fpga_prj.bit。
4. 本轮选择写FPGA配置SRAM的模式，确保不是PROGRAM_FLASH；核对目标器件/文件后点Run，等成功状态。
5. 打开FPGA对应COM，115200、8N1、无流控，关闭本地回显；RK调试COM的1500000不能混用。
6. 发送hello123，应收到同样内容。串口工具的发送显示不算接收结果；查看接收区/计数，避免本地回显假象。
7. 分次测试数个短字符串；原例程没有完整发送队列，满速连续压力测试另做。
8. SRAM配置断电丢失，重上电可能加载Flash旧程序，这是正常现象。

## 7. ChipWatcher在线调试

类似Quartus SignalTap，观测的是板上真实信号。先保留已通过UART版本，在副本/分支中加调试。

1. Tools→IP Catalog→Debug→ChipWatcher，双击。
2. Export Path选本工程uisrc/03_ip，Component Name如uart_cw。
3. Number of Probes设4；Sample Data Depth选4096；输入/输出流水级数先0。
4. 4个Probe Width依次1、8、1、1，分别接uart_rvalid、uart_rdata、I_uart_rx、O_uart_tx。开启Data Enable；至少uart_rvalid开启Trigger Enable。
5. 生成后用Show Instantiation Template，按实际模板端口例化；采样时钟接I_sysclk（25MHz）。不要猜生成端口名。
6. 完整编译并下载含该IP的新bit。调试描述必须与当前bit对应。
7. 打开ChipWatcher→Watch；Add Signals加入探针，Add Triggers加入uart_rvalid。
8. 条件选rising edge；一个窗口，4096深度，触发位置可取1024。
9. 先启动捕获，看到Wait for trigger，再从电脑发送单个字节。完成后查看rvalid、rdata与TX。
10. 4096点/25MHz=163.84us，触发前1024点仅40.96us；足以重点看收完字节后的回传，不一定看到完整接收帧。若要完整收发可改用更深缓存并重新生成/编译。

持续等待：确认发送到正确COM、触发信号有效、采样时钟运行、bit与调试描述一致。增加探针/深度会占用资源且可能改变时序，需要重查报告。

## 8. Flash固化

UART上板与调试通过后才进入。与SRAM下载不同，这一步会覆盖FPGA启动Flash内原有配置；先明确现有内容及对应恢复位流。

1. 保存已验证源码版本、bit、器件/Flash型号、工具版本与实测记录。
2. 在BitWriter选择PROGRAM_FLASH。按实物Flash型号与本板教程选择器件和配置方式，不按容量相似随意选择。
3. 添加同一份已通过SRAM验证的位流；核对地址和工具配置，执行编程及可用的校验。
4. 完成后正常断电再上电，不经JTAG重新下载，UART仍回环才算固化通过。
5. TD位流设置里boot_mode等选项按本板核对；不要随意改变启动模式。它与RK eMMC刷机是两件事。

## 9. 每次实验的完成条件

源码保存/版本明确 → 仿真有检查结果 → 综合布线无Error → 时序及约束覆盖检查 → bit路径/时间明确 → SRAM实测 → 必要时ChipWatcher → 可选Flash冷启动复验。
只完成哪一步就记录哪一步，不把“生成bit”写成“功能通过”。
