# 后续电脑复验 prompt：第10项MTBF与动态SDF

2026-10-10：用户确认当前电脑没有ModelSim/Questa，并明确授权当前先计第10项验收通过、保留以后复验入口。这里的“通过”属于用户暂时豁免工具检查。正式37的完整STA已实际通过；MTBF原生崩溃、最小例异常和动态SDF未执行的原记录仍保留，不是工具成功报告。

TD自带器件模型及外部仿真工程入口，不能用综合、ChipWatcher或STA替代事件驱动时序仿真。[安路官方FAQ](https://tech.anlogic.com/Cn/Index/index/cate/32/tp/1/p/2.html)说明TD没有嵌入仿真工具；当前SDK的SWUG107给出ModelSim/Questa模型库编译流程。release_note.pdf另列UVS模型支持，但当前安装目录没有对应仿真引擎，未将“支持模型”当成“已经执行仿真”。

将下面整段复制给以后有合法许可、可运行ModelSim或Questa及TD的电脑：

```text
请接续检查安路PH1A90SEG324 -2工程的第10项，只把真实执行且证据符合范围的检查标为技术通过。2026-10-10当前验收由用户暂时豁免了MTBF/动态SDF，不能将豁免记录当成工具曾通过。读取仓库skills/anlogic-td-demo-reuse/SKILL.md、references/engineering-rules.md、references/workflow.md以及当前验收/交付索引。先定位本机仓库根、合法可用的ModelSim/Questa安装路径与版本、TD版本，不沿用C盘路径假定。

正式生产组合为projects/pcie_imx415_bar_contract37_20261010（FPGA37，硬件版本0x56442501），SGDMA36及V4L2_37。正式bit SHA256 391fe012ea487c18e450bf3ba4f6c23cbb7752dbce2d3747be39b521236c3b0a；SGDMA SHA256 0eae16450705a87f58e055875a8878b3d8a0a01c9adae9535dc3d9f2147a8ef2；V4L2 SHA256 1e8cfa968ecd51acd3df7c1fec4a0c6e8b8ae409d6d216edcca9f224e903cebb。不要用其他候选或旧09b结果替代这个组合。

1. 核对当前源/ADC/SDC/完整IP/ROM、正式prDB/bit、构建和STA原始日志。正式37 native setup +0.148ns、hold +0.019ns、TNS0、STA覆盖99.97%；这些是旧已完成结果，换工具/改源/重新路由后必须产生新源哈希及新检查结果。当前六例程选择以deliverables/current_delivery_index_v1/index.json为准，不能仅按目录名选旧失败bit。

2. MTBF：生产37 report_mtbf曾原生0xC0000005崩溃。projects/td_mtbf_minimal_20261010_retry01有两FF最小例；projects/td_mtbf_opposite_edge_20261010有负沿/正沿100MHz、两个独立PH1物理单元、5ns半周期对照。后者真实报告settling 2147487.694ns = INT32_MAX ps换算 + 4.047ns，MTBF 8.218407e307years；最小例settling 2147492.892ns = INT32_MAX ps换算 + 9.245ns，均被数值审核拒绝。去掉async clock group对照仍异常，同单元打包不是必要条件；不能认定SDK根因已证明。

   用新目录保留原始DB/约束/bit/日志，先审查当前TD官方修复或可用新版工具，再用完整源重建实际控制例验证。遵照SWUG105：在insert_debugger后、optimize_rtl前，以及place前重新启用rtl directive:async_reg与place async_reg；核对实际gate连接、属性和布局，不使用字符串属性或setter伪造同步器。只读导入matching routed DB运行report_mtbf并核对前后SHA。评估settling是否符合真实接收周期/级数/路由，活动率是否有依据，报告是否存在UNDEFINED、饱和值或sentinel。有效控制例通过后才尝试生产37。不得手工减去INT32_MAX偏置、改报告、删约束、改license/SDK二进制或用未有器件特性数据的解析公式假称native MTBF通过。若新工具仍异常，完整保留复现和结论，继续标技术失败/待修。

3. 动态SDF：生产37完整matching材料在evidence/current37_sdf_export_v2与deliverables/current37_matched_sdf_materials_v1。prDB SHA e3e43eaa01e6de675d7156a767ad16453ca88107457fb87a83572157c5911200；物理网表SHA ad0f72630bd76fd00884f0ef97d961c5debcd99d2e3dbb3f5e8a56c4c1a46652；SDF SHA 5ed297fda1564a0854c289ef2a4ca66a36776fe46c5deffa015c9dd93c11571d。旧09b的网表/DB/SDF缺失，原10.5 time0崩溃日志仅是历史材料，不能算37仿真。

   当前导出含28632非top SDF CELL、180063 INTERCONNECT（360126端点）静态匹配；119个没有CELL时序记录的物理单元清单保留。这只是结构审核，不是动态注入覆盖。完整模型库实际101文件、18原语类型，模型路径/SHA及4个加密模块声明的位置已列入simulator_materials_v1.json，不能将加密声明误判为缺失模型。

   在实际许可仿真器中按SWUG107编译当前TD完整common+PH1/SALPHOENIX1A原始模型库，保留版权，处理实际PCIe配置文件/库依赖。不要解密或用空模块、理想时钟/PHY/DDR替代生产原语。旧工具10.5的失败不证明新版本一定成功，须实际记录版本、库编译和运行结果。

   先阅读完整production top和相机启动/使能接口，编写真正full-top的动态TB；当前材料尚没有经过执行验证的完整37动态TB。用外部引脚驱动真实系统/DDR/PCIe参考时钟、摄像头I2C ACK/初始化与四路CSI输入；正确例化实际PH1 GSR及glbl。满足真实相机初始化与cam_enable条件再发送包，不force内部时钟、reset、使能或数据以绕过设计。独立生成具有明确lane顺序的四路非零golden数据、短/长包、WC/ECC/CRC、RAW10像素与正确frame/line标记；记录采样数据和原字节比对结果。

   网表自带一次$sdf_annotate及glbl，勿重复例化/注入。其注入文件路径为旧电脑绝对路径。换根目录优先用tools/export_current37_sdf.py新attempt从同一匹配DB重新导出，使注入路径有效；保护全部原native文件，update_timing中的SDC诊断输出须重定向新目录，317源及原643文件前后SHA相同。native write_verilog会写默认<top>_out.v，指定文件名可能被忽略，立即复制实际默认产物。不要修改网表/SDF中的逻辑、时序或负检查值来消除故障。

   实际执行SDF所支持且含义明确的时序角、lane skew/采样相位、异步reset释放相位、LP↔HS启动和时钟停止/恢复场景。确认所有应注入的CELL/端口/IOPATH/RECREM/SETUPHOLD覆盖及错误/警告；对119个无CELL单元逐类说明模型依据，不用全局豁免。不得用nospecify、notimingchecks、负时序值手工钳位、抑制SDF/时序警告或禁用时序检查得到绿灯。遇到负检查值/工具不支持须记录并按原模型正确选项解决，不能静默改变语义。

4. 给出真实命令、工具版本、库源SHA、TB与golden哈希、所有角/相位的原始日志、注入覆盖、逐lane/逐byte预期与实际、检查失败/超时、源/DB/bit前后同一性。区分RTL数字、STA、静态SDF匹配、动态时序、MTBF和物理实测，不以某一项推断其他项。给出独立复核脚本和可重跑入口。

5. 不重测已通过且源/bit未变的1–8/13或01–04外设来替代缺失的第10项。需要SRAM板测时沿用现有quiesce/finally恢复：停止所有client、解绑/卸载配套模块、下载准确候选，结束后恢复正式37和配套两个ko、boot SHA/参数/控制/DMA idle，并抓新的完整帧复核。禁止刷Flash或修改boot。第9项为用户硬件豁免，不恢复其USB测试要求。

6. 将技术复验结果写入新证据目录并并入skill/当前交付索引，原用户豁免记录和原失败日志保留。只有真实全部技术门通过后才将技术状态由deferred改为pass；不要删除“当前先计通过”的来源历史。
```
