# 06 CSI→DSI 独立修复副本验证

更新：2026-10-05。本副本已完成数字修复与三个实际 ModelSim 自检；当前没有新的完整 TD 时序/bit 验收，也没有重新上板的 DSI/DDR/相机电气证明。原六例程未改。

## 修复与兼容接口

- 保留原06的 PH1 加密 MIPI PHY、IP 注册、PLL、DDR、DSI、屏初始化 ROM 和 ADC 四 lane INDEL20；没有把 PCIe 的 PH1A 动态校准 PHY 半套替换进来。保留 PHY 与直接引脚文件的字节校验见 source_provenance.json。
- 新 csi_integrity/ui06_csi_frontend 将原 PHY 高字节优先的协议输出适配为低字节优先 parser；像素仍低10bit=P0，禁止额外反转像素。精确按 WC 接受载荷，仅尾部合法字节进入 reservoir，显式末组 TLAST，增加 CRC/ECC/WC/完整RAW包/FIFO溢出/解包计数。WAIT_VALID_LOW=1 针对旧 PHY 无 parser-done 反馈的包间 valid 下降；BODY 中合法空拍不会重置行。
- 接收 Gray/FIFO CDC 从突发 HS byte 域进入稳定75MHz视频域。top 的 S_clk_70m 名称历史保留，真实 PLL C0=75MHz。video reset 异步断言、两拍同步释放；CSI 不使用此复位阻断原 PHY 工作。
- crop 以真实 TLAST 更新坐标，不按 valid 洞猜行尾；保持原剪裁原点（跳过首原始行及每行首4像素组），输出1920×1080，因此输入需要至少1924像素、1081原始行。实际 IMX415 WC/行数/Bayer 尚待实机核对，不能从小尺寸仿真推出相机真实边界。
- 同源完整 ISP 修复成套迁移：BLC、matrix真实行缓存、四Bayer插值、AWB SOF帧锁、cut、gamma/contrast/brightness/saturation接受拍与背压一致。matrix实际2×2048×32同步CE RAM helper随 ui_ram_demosaic.v 搬入，不使用旧33bit RAM冒充。顶层接回 ready，demosaic/AWB/cut运行时尺寸绑定13'd1920/1080；原 ui_isp_top 的 O_tready 是输入、I_tready 是输出，保留此遗留接口方向，实际接线按方向处理。
- ISP低128bit四像素顺序：低32bit=P0，格式{0,R,G,B}。移除旧 cut 首四像素组的错误黑掩码，保留 gamma22/contrast140/brightness+5/saturation130算法参数。
- ui_dbuf 的写ready改为真实almost-full/复位就绪，只有接受拍保存valid/SOF/TLAST；跨域的FSM状态/empty改为源域2FF级别同步。启动时用外部SOF请求释放FIFO，但第一接受SOF仍进入FIFO。DDR AXI地址位数改为APP_ADDR27+log2(2bytes)=28，未修改DDR真实IP。
- AL退役旧 ui_csi_unpacket_4lane/ui_raw10_unpacket_4lane/ui_image_correction，资料文件仍保留；注册7个新接收文件，完整ISP文件路径保留原布局。audit 0 errors仅代表显式依赖/直接引脚检查。

## 时序约束修改

原C0/C1时钟名交换已纠正；保留同一PLL输出之间真实时序，不再把所有相关输出 mutual-exclusive 切掉。补 camera I2C内部scl_clk generated clock：CLK_DIV249→SCL_DIV124→每125输入周期翻转→divide250。03另为CLK_DIV250→divide252。04没有I2C fabric时钟，DDR自有SDC派生PLL时钟仍保留。

CSI输入以配置目标891Mbps/lane约束 HS445.5MHz(period2.244669ns)，不是实测相机MCLK/HS速率；PH1 LCLK实际/4 byteclock由derive_clocks处理。PLL、DDR、CSI独立家族仅通过实际FIFO或2FF的CDC处使用async时钟组。必须在完整TD审查时钟匹配、未覆盖/UNDEFINED路径、derived SCL setup/hold与例外；当前数字仿真不签核这些约束。

## 实际 ModelSim 数字证据

工具：ModelSim SE-64 10.5。在tb目录执行 vsim.exe -c -do 'do run_frontend.do'、'do run_isp.do'、'do run_dbuf.do'。各脚本编译/断言失败或超时返回1，test_done后才返回0。

| 测试 | 实际RTL/模型范围 | 结果 |
|---|---|---|
| frontend | 真实parser/RAW10/FIFO/RAM/Gray/crop；输入为协议word驱动，不仿加密PHY | 两帧RAW24×4→16×3共24四像素组；WC30尾2字节与CRC同拍、valid洞、1周期包间空隙、输出停顿保持、低10bit=P0、CRC/ECC错误计数，PASS，0 errors/0 warnings |
| ISP wrapper | 真实全ISP、原divider_gate门级网表、官方TD逻辑/加法/LUT primitive库及glbl | 两帧16×3，24个128bit输出组；黑/白所有像素及SOF/TLAST、洞和长背压精确，PASS/0 errors；冷展开vendor网表有未使用端口warnings，不能记作所有vendor warnings均消除 |
| DBUF | 真实ui_dbuf与异步sfifo/RAM；FDMA侧为事务消费者，未仿DDR/DSI PHY | 首SOF保留，48完整128bit字/6个8beat burst逐字精确，地址正确，almost-full产生85周期背压，无丢字/重复，PASS，0 errors；13个原FIFO unused-port warnings |

完整日志：[frontend.log](../evidence/frontend.log)、[isp_wrapper.log](../evidence/isp_wrapper.log)、[dbuf.log](../evidence/dbuf.log)。数字测试没有用空模块伪装DDR/DSI/MIPI电气核心。

ISP黑值独立金值：RAW32→BLC0→Gamma22 LUT[0]=240→归一化14→contrast3→brightness8→saturation7；RAW1023最终gray254。这是保留厂商定点参数的结果，不声称全视觉算法等于理想黑0白255，也不由灰色测试证明所有颜色正常。

## 独立完整构建

保留 managed build.tcl，新增独立 build_direct.tcl。命令：

```powershell
& 'E:/qianrufpga/TD/bin/td_commands_prompt.exe' 'E:/qianrufpga/fpga-lab/projects/demo_repair_20261004/06_csi_2_dsi_imx415_7cun/build_direct.tcl'
```

新schema2通用模板从当前AL配置列出所有注册源目录（含IP内部ROM），逐文件检查大小/mtime并复制后逐字节确认，复制AL只重定位staging目录；所有TD阶段同一新 reports/direct_build_时间_PID 工作目录，避免open_project与elaborate使用不同cwd造成IPC/XML或ROM缺失。03/06已实际执行Tcl文件staging smoke PASS，输入AL未变，未调用TD命令；STAGING_ONLY_NOT_TD_BUILD.txt 明确标记，不能当bit证据。源/config变化必须重跑skill audit --direct-config。

## 未验证范围和剩余风险

CRC在包尾才能判断，当前已流出的坏行不能撤回；计数可观测而不是坏帧自动剔除证明。有限FIFO可被持续背压填满，溢出被计数，未实现整帧缓存或无限承载；实机必须观察错误计数/帧完整性。06原PH1加密PHY固定tap的电气窗口未由本轮主项目PH1A校准测试覆盖。DSI屏时序、DDR板级读写、实际camera MCLK/WC/Bayer、所有色彩图案、长时无闪屏和资源落ERAM仍待完整TD及板测。

该副本解决了明确共享数字缺陷；原先六例的用户板测成功只保留为历史基线，不表示本修复06再次板测成功。
