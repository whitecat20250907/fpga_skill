# TD逐步操作：先处理许可证，再学工程和IP

2026-09-21实查：TD Release_2026.1_SP2，6.2.2.200067。
当前UART工程器件PH1A90SEG324、等级-2、顶层uart_top均已确认。三个源文件读入成功，ADC/SDC已读入。
原报错为缺少 E:/qianrufpga/TD/license/Anlogic.lic。已从外部license目录复制，保留原件；重跑综合后报 License expired!。尚未通过综合，无新bit。

## A. 更新许可证

1. 浏览器打开 https://www.anlogic.com/support/tools-downloads 。
2. 找到软件工具分类，再找TD License。若要求登录，用自己的安路账号登录。
3. 下载当前有效、支持所用TD与PH1A器件的许可证；下载压缩包需先解压。
4. 将新文件提供给助手核对路径；最终应放在 E:/qianrufpga/TD/license/Anlogic.lic。
5. 保存工程，关闭重开TD，再重新运行综合。不要反复重装驱动、改变器件或修改HDL来解决license错误。

## B. 在本机确认器件，完全不用猜菜单

1. 按Windows键+E打开资源管理器。
2. 点击地址栏，粘贴 E:/qianrufpga/fpga-lab/examples/01_uart_loop，再按Enter。
3. 找到fpga_prj.al，右键→打开方式→记事本。只查看，不改内容。
4. 按Ctrl+F，搜索PH1A90SEG324。应看到<Device>PH1A90SEG324</Device>；附近有<Speed>-2</Speed>。
5. 关闭记事本。工程已经选对，不需要重新选择。

以后从零新建时：TD顶栏Project→New Project…；Project Name填项目名，Project Path填单独英文目录；Device Family选择提供PH1A器件的族，Device Name明确选PH1A90SEG324。不要选择相似封装名。现有工程不必重建。

## C. 区分模块和IP

UART例程的uiuart_rx.v/uiuart_tx.v是已经提供的Verilog模块，不需要通过IP Catalog重新生成。目录叫03_ip不代表里面每个文件都要图形化配置。
厂商PLL、RAM、FIFO等IP通常用Tools→IP Catalog生成。基本流程：选功能→命名/保存→参数→生成→例化连接→约束→编译→验证。

## D. 第一项IP练习：PLL（在独立练习工程中）

先完成许可证处理和UART基线，再做此练习。不要把实验IP直接混入UART基线。
本练习按板卡教材第33–35页，25MHz输入、200MHz输出；用于学习/仿真，本板没有FPGA用户LED。

1. TD点击Project→New Project…，新工程名pll_practice，路径E:/qianrufpga/fpga-lab/practice/pll_practice，器件PH1A90SEG324。
2. 点击Tools→IP Catalog。展开Primitive IP→Clock，双击PLL。
3. Setup Exporting Options窗口：Export Path选择本练习工程下uisrc/03_ip，Component Name填ui_pll，点OK。
4. 输入参数页：Input frequency填25，单位MHz；Feedback mode选Normal；勾选PLL lock；Standby和动态配置保持关闭。点Next。
5. 输出页：选Clock frequency；启用Use C0 clock；Frequency填200MHz；Phase Shift为0；其余C1–C4不启用。检查Actual Frequency为200MHz。点Next。
6. Bandwidth setting保持Medium，其余高级参数不改。点Next。
7. 后续生成页按教材选择Verilog .v输出；核对参数摘要后完成生成。若页面不同，停在该页发截图，不猜未知选项。
8. 检查工程源列表是否加入生成的IP；如未加入，Hierarchy右键Add Sources→IP files选择生成的ipc文件。
9. 选生成模块的.v，右键Show Instantiation Template，复制模板。模板中的模块名与端口是连接依据。
10. 在自己的顶层中例化：refclk接25MHz输入；reset为高有效复位输入，教材简单实验接0；clk0_out接内部时钟线；lock接内部锁定指示线。生成的实际模板优先。
11. clk0_out和lock是内部信号，无需分配封装引脚；只有顶层对外端口才做IO约束。SDC输入时钟40ns，PLL派生时钟后续按生成结果核对。

生成IP不等于已使用IP。必须实例化且输出参与有效逻辑，综合才会保留；本练习后续添加计数器、仿真和ChipWatcher观察，不照抄教材LED引脚上板。

## E. 如何读当前错误

syn_1是综合任务；opt_rtl是RTL优化阶段；phy_1是后续布局布线任务。综合失败时phy_1 not start正常，50%不是完成一半功能。
完整错误位于 examples/01_uart_loop/fpga_prj_Runs/syn_1/run.log；用记事本打开，Ctrl+F搜索ERROR，从首条开始判断。当前明确错误是许可证过期。

中文界面：本地用户手册未列语言切换选项，尚未核实官方中文版GUI。中文手册已自带：E:/qianrufpga/TD/doc/TD_User_Guide_V6.2.pdf。界面保留英文按钮，用本教程中文解释。
