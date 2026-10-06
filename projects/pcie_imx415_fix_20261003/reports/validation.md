# PCIe / IMX415 修复验证记录

更新日期：2026-10-05。这是持续更新的实测记录，最终组合的连续图像与双向验收尚未完成。

## 当前结论

- 历史六个 examples 文件哈希全部一致，未覆盖原材料。用户原六例程上板成功只作历史基线，修复模块复用应读独立维护副本及各自新证据，不能继承旧通过标签。
- RK已恢复串口访问，PCIe1模式启动、64MiB CMA保留。板载USB1 hub/Wi-Fi与PCIe1的总线互斥是硬件限制，不能仅改boot.img让同一hub共存；独立OTG0尚未接外设验证。
- build03的生成RGB双向回环通过，但相机仍有紫绿异常帧，**该位流不是相机修复交付版**。历史1080p 50帧零差异只证明生成图回环，不证明1080p相机。
- build04完成数字自检，矩阵双bank实映8ERAM；同源high-hold修复后Setup +0.253ns、Hold +0.020ns、TNS=0，bit已下载（SHA256 `700b625fdb94f84820c836d0479cb34e814827e94a8ccf7d6127b75915126c58`）。两轮各120帧720p长度/序号正常、采集期有效CSI快照RAW最高128664包，CRC/ECC/WC/timeout/overflow均0；这些**不证明颜色正确**。用户确认实体橙卡在`evidence/quick04_scene_last.png`显示绿色，颜色明确失败；另有首帧20.8%紫。26.669fps及实测49.5001MHz byteclock与当前12MHz MCLK驱动27MHz寄存器表的比例相符，sensor最终INCK连线仍须实测。后续HDMI九色图实拍已保存，尚无patch量化通过结论。
- FPGA5已完成route而非仍在集成：最终Setup −1.960ns、TNS −7.222ns、Hold +0.020ns；四条负路径为byte reset→四个HS IDDR异步reset recovery。CRC/header/payload并非该报告负路径，不允许false-path相关域。gate196/物理83个ASYNC_REG是不同映射表示；OOC参数恢复已独立TD验证，但`report_mtbf -cdc_sink_pin`发生native crash，**无新bit，STA/CDC未通过，不可交付**。证据`evidence/build05_direct_staged.log`及`evidence/direct_build_20261005_002919_8820/final_timing.rpt`。
- 驱动05存在STREAMOFF十秒后残留poll timeout。06取消generation/worker lease/物理STOP guard完成模型及RK编译；实际加载确认后的`driver_negative06_loaded.jsonl`为8/8，初次setup权限不足时旧05的同名测试已改为`_NOT_LOADED_old05`，不能混用。07再修probe真实错误回滚，RK编译/加载RC0，实际SGDMA ko SHA256 `b2caa435b33822410872189cf010881628f34ae2cb5d0fbab12984556457baef`；V4L2 ko SHA256 `b7d6d24f51419ef9e748c002445ff1e80a7f894afe248d670fb44072e700b588`，新增取消符号存在。07实际负测也8/8，**未通过20轮循环**：cycle0获8帧720p，cycle1的1080p在15.022秒获0/8帧，6197776+16字节短包共792次拒收、DMA errors0；停止后RUN0/BUSY0、CmaFree61516KiB恢复。原文在`evidence/rk_serial.log`，不能把编译/8项负测或一次回收写成所有恢复通过。
- 上述首次真实1080p失败已有尺寸证据：binning输入1097行，旧裁切首行20至1099越界；矩阵前看后1076行×5760字节+flush16=6197776，吻合物理包长。**不是仅模式切换问题**。root已中止FPGA6 fullTD（保留`evidence/build06_direct_staged.log`），改准备07首行16至1095的1080p裁切，4K首行16至2175在2192输入内，720p不变，均保持偶数Bayer相位；新的真实源尺寸golden/fullTD/两档相机验收待完成。
- FPGA6版本0x56440601曾集成27MHz手工PH1 PLL、startup/snapshot/快速计数、D8 shadow/DC裁切SOF锁帧Bayer与连续PH1采样候选，源manifest为`evidence/colour06_integration.json`。GBRG有官方驱动依据且本地偶数裁切保持相位，仍须实拍标定；PLL不是新Wizard生成，数字模型及独立elaborate不证明模拟lock/频率或电气采样。06已停构建、没有最终route/bit；后续07必须新源/bit清单，不能复用06hash或build04短采集标签。

## 工程与工具

工程：`E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/fpga/imx415_pcie_4k.al`，PH1A90SEG324 -2，TD 6.2.2.200067 Release_2026.1_SP2，ModelSim 10.5。RK 运行 Linux 6.1.99，内核头位于 `/usr/src/linux-headers-6.1-rockchip`；系统 `/lib/modules/6.1.99/build` 不存在，编译必须传正确 KDIR。RK RTC 时间不正确，make 使用 `-B` 并核对实际 CC/LD 与产物哈希，不能把旧模块当成新编译结果。

原始厂商工程位于开发材料的 AFC03_IMX415_PCIE_X1/IMX415_PCIE_X1。修改均在独立副本；保存 `clone_manifest.json`、修前源、每轮源快照和构建日志。

## 已取得证据

| 验证 | 结果与边界 | 本地证据 |
|---|---|---|
| build03 布线 | Setup +0.586 ns、Hold +0.020 ns；0 TNS；99.84%覆盖，仅证明当时约束 | evidence/build03_awb_loopback/phy_1/final_timing.rpt |
| build03 已知 RGB 720p 回环 | 20 帧、每方向 55,296,000 字节、0 字节差异，源/echo SHA 相同 | evidence/roundtrip01_720.json |
| build03 已知 RGB 1080p 回环 | 50 帧、每方向 311,040,000 字节、0 字节差异，源/echo SHA 相同 | evidence/roundtrip02_1080.json |
| build03 相机 720p | 1000 帧长度正确，3 紫/2 绿可疑；1500 帧长度正确，17 紫/3 绿可疑；查看异常原图确认，未通过 | evidence/check05_720.summary.json、check06_720.summary.json、check05_720_frame0054.png |
| RAW10/CSI 数字协议 | 1944/WC2430、3888/WC4860、CRC共拍/跨拍、valid洞、随机ready、错误注入及FIFO溢出恢复 | evidence/csi_integrity_sim.log |
| PHY 校准控制 | 32tap全PASS/窗口/全FAIL、64长度不溢出、手动31→0，IO为行为壳，非电气眼图证明 | evidence/csi_calibration_sim.log |
| 校准图像gate | parser持续供反馈，校准后等待新FS才放行；仅数字模型 | evidence/csi_capture_gate_sim.log |
| 时钟检测 / 计数CDC | 注册Gray、短消隐容忍、失钟/恢复；原子诊断快照/停钟busy | evidence/csi_clock_sim04.log、csi_snapshot_sim.log |
| ISP 矩阵/插值 | 四种Bayer，720p/1080p、边界、valid洞、背靠背帧与背压逐像素golden | evidence/isp_golden.log |
| ISP 接口/后处理/参数 | 裁切、行RAM、BLC dest、弹性后处理；Gamma0.8与奇数contrast定向golden | evidence/isp_interfaces.log、isp_elastic.log、isp_parameters.log |
| AWB | 行/帧marker、SOF增益、stall、黑帧/饱和；除法器是行为模型 | evidence/awb_sim.log |
| RGB24 打包 | 短行及720p/1080p全部字节golden，最后真实beat EOF、随机stall | evidence/packer_sim03.log |
| RK 新驱动 | SGDMA与V4L2实际CC/LD；模块哈希见下 | RK evidence/driver_sgdma04_build.log、driver_v4l2_04_build.log，待回收 |
| RK 新驱动负测 | 8/8通过，cleanup_errno=0、mode0、CTRLoff；本轮基于build03硬件，未代替新位流图像测评 | evidence/driver_negative04.jsonl |
| build04实际颜色 | 用户确认实体橙卡在接收图中为绿；120帧长度正常仍颜色失败；HDMI图案实拍尚待patch量化 | evidence/quick04_scene_last.png、rk_serial.log（colour_baseline04/colour_chart04_full） |
| FPGA5最终route/无bit | WNS −1.960/TNS −7.222/Hold +0.020ns；四条IDDR reset recovery负路径；随后native MTBF crash，无新bit | evidence/direct_build_20261005_002919_8820/final_timing.rpt、build05_direct_staged.log、tools/csi_fast6/timing_audit.json |
| TD OOC属性机制 | tiny TD六轮，place-only不恢复，rtl directive重开恢复原3属性；196 gate→83物理不是直接丢链证明，MTBF未过 | reports/td_async_ooc_attribute_review.md、evidence/td_async_ooc_review_manifest.json |
| 06 PHY/runtime候选数字测试 | 真TD primitive连续采样/不同相位reset/停钟，3828拍/844有效lane-byte；runtime四模式32帧全像素golden。06 fullTD主动中止，无新bit | tools/csi_fast6/evidence_sampler6.log、tools/bayer_runtime6/README.md、evidence/colour06_integration.json、build06_direct_staged.log |
| 驱动06实际加载负测 | 新取消符号存在，8/8，不能使用首次加载失败的旧05结果；未完成持续循环/双向验收 | evidence/rk_serial.log（driver_negative06_loaded.jsonl） |
| 驱动07实际编译/加载与负测 | BUILD07_RC=0/SETUP07_RC=0、准确ko hash见当前结论，负测8/8；probe OOM回滚仍只有主机故障注入 | evidence/rk_serial.log、driver_probe_error07_manifest.json、reports/driver_probe_error07.md |
| 07驱动+04bit首次真实1080p | 20轮计划FAIL：cycle0 720p八帧通过、cycle1 1080p0/8，6197776+16包、792拒收；1097输入裁切越界与长度吻合；STOP后idle/CMA恢复，非循环验收通过 | evidence/rk_serial.log（driver_cycles07_run.log/cycle1、CMA），07修裁切golden/新bit待验证 |

## 已记录哈希

- build03 压缩 bit：`12b059d18b1f1c71b228852d29744e08d0ff3e27ee34bf8f83c4ab2df6fa890f`。
- build04 high hold 压缩bit：`700b625fdb94f84820c836d0479cb34e814827e94a8ccf7d6127b75915126c58`；当前板上使用，证据 `evidence/resume_hold04.log`、`program04.log`。
- 驱动05 SGDMA：`45bf443714de7cd82e5680f3e003bb61e418353c8fdae99ea2473a0eb85e76260`；V4L2：`b7d6d24f51419ef9e748c002445ff1e80a7f894afe248d670fb44072e700b588`。这组存在已发现的取消poll问题，非最终交付。
- 当前板上 boot_pcie_cma64.img：`acd036d8de113cfd4166a5e34a71e7222429297dc1ed13de7db51828b35cd247`，此前刷写读回一致；本次重新供电实际 CmaTotal=65536 kB。
- 原 boot 备份：`faebf16428deb61867f57f17f79b7d27ba0faf9503853284a697aa83e882abec`。
- 新 SGDMA .ko：`3688d14688161b717b31a990cf76a46d9cee948d61fa0780f2b050e5a3350900b`。
- 新 V4L2 .ko：`f33e843f58161f684651ed6e0234ce5bac149b15cddb63c5d53f6ed67ac6c112`。

## 必须继续完成

1. 行缓存映射修复并完整 TD 布线，核对本轮产物、Setup/Hold、I2C生成时钟、动态PCIe PLL告警与实际HS速率。
2. 新位流下载后，720p/1080p长测与原图检查，记录CSI CRC/ECC/WC/超时/溢出诊断。CRC现为诊断，不能声称坏载荷自动撤回。
3. 新位流/新驱动组合的已知图与真实相机帧双向逐字节回环、不同分块、主动中断后恢复。
4. 多次开关流、模式切换、软件重启/重新枚举、AER前后、CMA回收及持续控制访问。
5. 按最终结果更新本文、README与skill的验证状态；未接的外设和物理互斥必须明确保留边界。

源码细节见 `isp_review.md`、`boot_driver_audit.md` 与 `../tools/csi_integrity_notes.md`。不能以这份中间记录宣称项目全部完成。
