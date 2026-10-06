# IMX415 时钟审查与独立 PLL 配置试验（2026-10-04）

这是独立试验目录，不属于 TD 文件集。未改冻结 FPGA 源码，未执行 optimize/place/route/bitgen，未操作开发板。后续获主任务明确授权，仅对本目录 standalone 单模块执行 analyze/elaborate 和 PLL 参数更新 API 探针。`cam27_trial.ipc`、`cam27_25unity.ipc` 是从当前厂商 `ui_pll.ipc` 复制、修改的**待生成配置**；目前没有取得官方 wizard 生成的 27 MHz IP，不得把 shadow 配置或数值种子当作已验证 IP。

## 已确认与未确认

- 当前 `imx415_pcie_top.v` 的 `cam_24m` 为 24 MHz，posedge 触发器每拍翻转使 `cam_mclk` 为 12 MHz。源码注释“6–27 MHz 所以 12 MHz OK”不能作为 IMX415 当前配置的合法性证据。
- binning 的有效时钟字段 BCWAIT=0x05D、CPWAIT=0x042、SYS_MODE=5、INCKSEL1/2/3/4/5/6/7=00/23/00C6/00E7/23/0/1、TXCLKESC=0x06C0，匹配 Linux 主线 IMX415 的 **INCK 27 MHz、lane 891 Mbps** 表。300B 原写值 A0 含保留位，不把整个 16 bit 原始写值等同 Linux 的 CPWAIT 值；这里比较的是手册定义的有效位。
- VMAX=2283、HMAX=542，以 74.25 MHz 的该族行时序计算约 60.0055 fps。若 sensor 确实由当前 12 MHz 驱动，并且其内部频率同比缩放，则约 26.6691 fps，与旧 26.65 fps 观测接近。这是**待物理测量确认的推断**，不能排除采集/保存瓶颈。
- FPGA A18 对应 B13_L20P / FMC_HPC_LA02_P / FMC H7。核心板、底板 pinlist 能支持这一段路由；本地资料没有 VID005/CAM002 的 MCLK 到 sensor 接线或时钟选择图，未证明固定晶振是否覆盖 FPGA MCLK。
- 历史 06 的 PLL C1 为 25 MHz，直接送 `S_clk_25m`；其 binning 表仍是 27 MHz 族。DSI 刷新率或“画面显示成功”不足以证明 sensor 实际帧率、时钟来源正确。

## 数字范围合法的 PLL 候选

本地 DS900_1.6.9（2026.04），PDF 第 57 页 / 正文第 52 页，表 3-2-5：FIN 10–500 MHz，**FPFD 10–500 MHz**，FVCO 800–2000 MHz，FOUT 6.25–1000 MHz。

| 候选 | 输入 | REF | FB | C0 DIV | PFD | C0/外部反馈 | VCO | C1 DIV / 输出 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 本 shadow | 100 MHz | 10 | 27 | 4 | 10 MHz | 270 MHz | 1080 MHz | 40 / 27 MHz |
| 可另评估 | 25 MHz | 2 | 27 | 4 | 12.5 MHz | 337.5 MHz | 1350 MHz | 50 / 27 MHz |
| 较低反馈频率候选 | 25 MHz | 1 | 1 | 54 | 25 MHz | 25 MHz | 1350 MHz | 50 / 27 MHz |

25/5 或 100/25 的旧候选 PFD 只有 5/4 MHz，低于官方最小 10 MHz，不能仅因 VCO 合法就采用。

`cam27_trial.ipc` 保留 Normal 模式，C0 使用 BUFG 作外部反馈，C1 配为 27 MHz，不保留原 C2。`cam27_25unity.ipc` 为低频反馈候选，使用 parameters_setting 保留 1/1/54/50 数值。后续实际采用必须区分“官方 wizard 生成”与“按官方 primitive 默认值手动例化”，两者均还需要输出路由和 PLL 锁定、输出频率及 CRC 验证。不得把其他 PLL 的参数复制后称为本频率官方生成结果。

MCLK 必须按 27 MHz 同频转发到 IO（适当的官方 ODDR/clock forwarding 实现），不能继续每个 27 MHz posedge 翻转，否则会得到 13.5 MHz。不要因此修改已有 UI150/24 时钟和 24 MHz I2C/CDC 逻辑。若最终采用 27 MHz / 891 Mbps 族，CSI HS clock 为 445.5 MHz、byte clock 为 111.375 MHz；应同步核对真实 PHY 的时序约束，不以 400/100 MHz 旧标称代替实测。

## 官方命令入口探针结果

工具版本 TD Release_2026.1_SP2 / build 6.2.2.200067。

`IpTool.exe` 的本地 Usage 字符串确实给出 `TD_PATH -gen IP_PATH -device DEV_STR -export_to ... -comp ... [-use_value default]` 和 `-user USER_PATH ...`。其参数还含 `-app_path`、`-use_value copy`、`-use_params`、`-run_tcl`；本版本二进制中未发现 `-ipgen` / `-td` 字面选项。Usage 不能推导 legacy PH1 XML `.ipc` 能以新版 ipxact 参数文件方式自动生成。

`TD/ip/depot/Catalog.xml` 将 PH1A90SEG324 的 PLL 定义为 `Generic IP Lib / PLL 1.0`、`customTool=use_host`、`ipid=29`。`PLLF6F1D0P0_1.1` 只匹配 PH1P 系列；其模板不是 PH1A90 的合法替代。

| 日志前缀 | 实际结果 |
|---|---|
| help | IpTool 第一个 TD_PATH + -help 返回 1，无生成 |
| user_ipc | shadow .ipc 导入等待，20 s 后只清理该探针自己的进程树；无生成 |
| copy_ipc | 加 app_path、use_value copy、quiet 仍等待；同样清理，无生成 |
| gen_catalog | 返回 0，但 `log/ipgen.log` 是 File Identification Error 自动确认；无生成 |
| iptool_commands | `-run_tcl` 能运行并立即退出；它注册的是通用 GUI 控件命令，未提供直接 PLL 生成命令 |
| td_commands | 仅查询 readonly Tcl commands，返回 0；未执行任何 RTL 分析或编译；有 read_ipc_file/update_pll_param，后者需要已分析 module/inst |
| td_legacy_open | TD `-ip -open shadow.ipc ... -use_value copy -nolog` 返回 0，仅 `RUN-001 : GUI based run...`；无生成文件 |

每个探针的 exact argv、PID、returncode、timeout 和耗时保存在同名 JSON，stdout/stderr 为独立日志。所有进程通过 Windows hidden 启动且有 20 秒上限；最终未见本试验留下 IpTool/td 进程。未调用已打开的用户 TD 窗口。

## update_pll_param 阴性控制：不能用此 API 证明 PH1 参数是否合法

主任务后续授权 standalone elaborate/参数更新探针。实际 API 字面文法为 `update_pll_param -help -module <string> -inst <string> -debug`；输出 netlist 命令为 `write_verilog file_name`，本版本没有 `export_verilog` 命令。

全部候选均正常 elaborate 到 PH1_PHY_PLL，故种子数值被正确导入；模拟五项特意设 0，以便辨认是否真的被更新。没有 optimize 或 bitgen。

| 探针日志前缀 | update_pll_param 的结果 |
|---|---|
| update_trial_literal | REF=10 被报不在 `[1,2,4]` |
| update_trial25 | FB=27 被报不在 `[1,2,4]` |
| update_trial25unity | REF/FB=1/1 越过上项后，报缺少 `DPLL_FEED_TYPE` |
| update_control | **官方原 UI150/100/24 的完整参数不变**，仅 rename module；FB=3 同样被报不在 `[1,2,4]` |

这一阴性控制排除了该更新 API 在本调用方式下对 PH1_PHY_PLL 的适用性。UG910 对 PH1 的 REFCLK_DIV/FBCLK_DIV 明确列 1–128，原 wizard 的 FB=3 又是已成功完整构建所用配置；PH1 原语名是 `PLL_FEED_TYPE`，不是报错中的 `DPLL_FEED_TYPE`。因此**前两条 range 错误不得写进 skill 作为 PH1 的合法分频集合**，不得据此把 REF10/FB27 判定为器件本身非法，也不得伪造 DPLL 参数绕过检查。没有任何 after-update netlist/DB 成功产生。

真实 before netlist、DB、四组 stdout 日志与 exact argv JSON 保留。首轮使用 Tcl `[file join ...]` 传给本 API 时文件名被解析成 null，之后改用相对 literal 路径才正确导出；首轮在 update 前已退出，不能当参数计算测试结果。

## 官方默认值与模拟参数边界

UG910_1.6，PDF78 / 正文66，第27.3节给出了明确 Default 列：

| 参数 | Allowed | Default | 文档说明 |
|---|---|---:|---|
| GMC_GAIN | 0–7 | 2 | 带宽设置相关参数 |
| ICP_CUR | 0–31 | 12 | 带宽设置相关参数 |
| LPF_CAP | 0–3 | 2 | 带宽设置相关参数 |
| LPF_RES | 0–7 | 2 | 带宽设置相关参数 |
| INTPI | 0–3 | 0 | VCO 等级（PDF81 / 正文69） |

这是**文档默认值**，不是已找到的频率选型算法；文档没有写它们必定适配上述 tuple，没有给出 Medium 档与这组数值的等价关系，也没有给 INTPI 的 VCO 分段边界。

本地真正的官方生成样本（`pll_generated_profiles.txt`）证明参数并非单一 Medium 常量：PFD25 MHz 的 VCO900/1000/1200 使用 1/11/2/3；PFD50和62.5 MHz 使用 2/12/2/2；PFD125 MHz 使用 3/13/2/1。INTPI 的样本为 VCO900/1000→0、1200→1，没有 VCO1350 样本。当前 `al_ip/sgdma_pll.v` 实际为 1/11/2/3、INTPI0；`al_ip/ui_pll.v` 为 2/12/2/2、INTPI1，不能说两者相同。

**结论：数字参数候选及官方 primitive 默认列已审查，新的 legacy wizard 模拟参数未取得。后续可以按官方文档默认值制作明确标注为手动原语候选的 PLL，再以真正完整构建、PLL lock/输出频率/CSI CRC 实测验收；不需要无限等待此不适用 API，也不能把未知默认设置冒充工具重算结果。**

## 已交付的独立可验证候选

`cam_pll27.v` 按主任务明确指定制作，尚未加入冻结 fpga：

- FIN25、REF1、FB1、C0DIV54、C1DIV50；PFD25、反馈25、VCO1350、输出27 MHz；两路 duty 均为50%。C0 外部反馈经过 BUFG，C1 输出另用 BUFG，输出端口为 `clk25_feedback` 和 `clk27_out`。输入应接已有 `sys_clk_g` 的25 MHz，不能接24 MHz。
- GMC/ICP/CAP/RES=1/11/2/3 来自本地真正生成的 PFD25 样本；INTPI1 由 VCO1200 样本推断到1350。它**不是新的 wizard 输出，也不是官方1350档位已验证推荐**。所有动态相移、DRP操作、SSC、分数分频及其它输出关闭；原厂 PH1 原语模板及版权保留。wakeup tie0 按当前已生成模板保持；旧 UG910 的端口表另写需 tie1，这是模板与文档版本差异，不能声称二者完全一致。
- `cam27_candidate_elaborate.tcl` 仅 analyze/elaborate/export：TD build6.2.2.200067 返回0，日志实际识别 C0DIV54、C1DIV50、GMC1、ICP11、CAP2、RES3、INTPI1；没有HDL错误/警告。`cam27_candidate_elaborated.v/.db` 为导出后的独立候选，**导出没有重新计算模拟参数**，仅证实原语接口与手写数值可被当前工具正确导入。没有执行 optimize、物理布局或 bitgen。
- SHA256：`cam_pll27.v` = `A9376AF99E56343B66EAA1BFEFDC1E99565276B33254C24643E381A224F6F753`。

`cam_clock27_monitor.v` 是可选内部诊断：源时钟端先注册 binary-next 的 Gray 值，再经过3级同步到25 MHz基准；每10 ms期待270000边沿，允许±544边沿（0.2%+4边沿CDC计数裕量），同时输出同步后的 PLL lock、窗口序号和单拍 valid。两个复位输入必须分别在各自时钟域同步解除；不能直接把多位二进制计数器跨域。使用32bit modulo差值，10 ms窗口远小于其绕回时间。

ModelSim10.5 自检 `run_clock27_monitor.do` 用100 µs窗口覆盖27 MHz、失锁但时钟继续、12 MHz、停钟和恢复，共29窗口，返回0、0errors/0warnings，证据 `monitor_golden.log`。**测试只验证计数/CDC数字逻辑，不能证明模拟PLL锁定、MCLK输出引脚、电缆/VID005或 sensor 真正收到的频率。** monitor SHA256 = `8CC39D6A3A8AC16A83B3BC510B76015301D314728139C76F7E205DE3EE25C000`。

## 下一轮 top 整合建议（未实施）

1. 保持原 UI150/100/24 PLL 及24 MHz I2C/CDC不动；另例化上述候选。不要把27 MHz再用posedge触发器翻转。使用官方 clock forwarding / ODDR同频输出27 MHz，任何启停使用该单元合法的CE/复位方式及其时钟域同步，不直接 `clk27 & lock` 组合门控。
2. PLL lock异步状态分别同步到控制所用25/24 MHz域。由sensor复位/时序状态机控制XCLR和cfg复位：发生锁丢失或全局复位立即保持sensor清除，锁恢复后经过同步及稳定窗口重新初始化。`cam_xclr`不应再恒1；I2C cfg的 `I_rst_n`不能只接原UIPLL lock。
3. Sony power-on sequence（PDF84 / 正文84）要求：全部供电完成后XCLR低≥500 ns；XCLR升高到INCK首个上升≥1 µs；到I2C通信开始≥20 µs。可以用独立稳定控制时钟计时，留出更长裕量，分别启动同频MCLK转发及cfg。PLL lock不等于确认sensor三路电源时序，必须结合子卡实际电路。频率切换/窄脉冲风险应在XCLR低期间处理，再完整初始化。既有寄存器初始化和standby/regulator等待继续保留。
4. 采集允许条件需同时包含新MCLK稳定、sensor已清除/初始化完成和现有I2C cfg_done；失锁后不得继续把缓存的旧图像误当新帧。监测放在原始内部 `clk27_out`，不依赖被禁用的相机输出，方便区分PLL源与转发状态。
5. 测频Gray CDC需保留async_reg、按项目现有TD选项启用布局识别，并对Gray总线作合理的跨域走线/skew约束；别用全域false_path掩盖错误。27 MHz生成时钟、891 Mbps链路所需445.5 MHz HS/111.375 MHz byte时钟应与真正使用的实例和实测频率核对。
6. 最终验收必须是新fresh bit的物理PLLlock稳定、内部计数及实际MCLK/HS周期符合预期、无保存瓶颈的FS帧率、CSI WC/CRC/溢出计数，以及完整正向/反向RGB逐字节比较。不能把本次elaborate或旧26.65 fps/旧双向图片的结果移作新候选上板结论。

## 来源

- [Linux 主线 IMX415 时钟参数](https://github.com/torvalds/linux/blob/master/drivers/media/i2c/imx415.c)，891000000/27000000 对应项及 24 MHz 的独立 720/1440 Mbps 参数项。
- [Sony IMX415 数据手册（Khadas 镜像）](https://dl.khadas.com/products/add-ons/cameras/imx415/datasheet/imx415-datasheet.pdf)，正文第 77 页 INCK selection：24、27、37.125、72、74.25 MHz；正文第 16 页输入时钟脉冲/duty/频率变化影响帧率。作者为 Sony，托管站为 Khadas。
- 本地 `DS900_PH1A_Datasheet.pdf` 表 3-2-5、`TD/doc/UG910_PH1A_Libraries_Guide_for_HDL_Designs.pdf` PLL 章节。
- 当前 top、IMX415 register LUT、原 06 的 top/PLL/约束，核心板/底板 FMC 与 B2B pinlist。

下一轮验证应测 sensor MCLK 或明确子卡时钟选择、读取 FPGA HS-period diagnostic、测无需图像保存的 FS 计数，并用 fresh bit/驱动哈希重复完整双向图像验收；本目录不宣称任何上板修复结果。
