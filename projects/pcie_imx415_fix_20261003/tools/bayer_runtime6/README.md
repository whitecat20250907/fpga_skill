# Runtime Bayer candidate for build6（未修改main/06）

工具目录三RTL候选：cam_video_source.v、ui_top_demosaic.v、ui_bilinear_interpolation.v。SHA见manifest.json，输入SHA可用于确认主源码未变。编码：0RGGB、1BGGR、2GRBG、3GBRG。

## root最小集成

1. 替换主对应三RTL为这些候选（除此目录本任务未编辑任何FPGA源）；top user_clk域新增2bit影子cfg（拟BAR D8），复位3；cam_source例化新增 `.cfg_bayer_mode(reg_bayer_mode)`。cam source BAYER_MODE参数可设GBRG作为复位/仿真未知输入fallback；不能留端口悬空。
2. 影子写入可以在帧内任意时刻，但cam_source仅crop_tvalid&&crop_tready&&crop_tuser接受时锁定frame_bayer_mode，位于BLC弹性级之前；top_demosaic在自己的真实RAW接受SOF再次锁定，bilinear在矩阵接受SOF锁定并首拍使用本次requested选择，避免NBA前的旧mode。所有环节user_clk同域，无新增CDC。
3. 如果绕过cam_source直接例化ui_top_demosaic，I_bayer_mode必须与该模块的RAW接受SOF关联。前级若有BLC/队列，应在前级接受SOF锁定mode并随帧传来，不能让cfg shadow直接穿过一个不保存metadata的队列。
4. 当前主黄金TB唯一ui_top_demosaic例化在tb_isp_golden.sv；本目录tb_isp_golden_explicit_ports.sv提供按MODE显式驱动0/1/2/3的版本供root替换，不依赖X/HiZ fallback。runtime TB全部数值驱动。

## 实际数字验证

`vsim.exe -c -do 'do run_runtime.do'` 在此目录执行，真实BLC、矩阵、同步RAM和候选top/bilinear，无PHY/DDR/DSI行为替代。run_runtime.do编译或断言/超时失败返回1，done为1才返回0。

2026-10-05实际ModelSim exit0、0 errors/0 warnings：4×1、8×2、16×6、20×7、1280×720、1920×1080，共32帧，全部像素/首末行/SOF/TLAST精确。四mode按帧0→1→2→3循环；首接受SOF之前驱动正确mode，帧中影子换成其它mode，被帧锁忽略；输出背压与valid洞保留数据和标记。日志runtime_golden.log。TB的source SOF mode锁与cam_source候选一致，仿真上游BLC真实存在。未完整展开cam_source及MIPI/PCIe硬件块，也未新TD/板测。

第一次TB故意把影子mode直接穿过BLC导致SOF/配置错一拍，已纠正为实际候选cam_source的接受SOF模式锁；这说明mode也属于帧metadata，不能只在后端加裸cfg线。最终以上PASS对应修正后的TB和三RTL候选。

## readonly源码/官方证据

- 主top固定RGGB：fpga/uisrc/01_rtl/imx415_pcie_top.v:546。1080 crop start19→首行20；720/4K start35→首行36：同文件426/433/440。
- image_correction.v:36选择(y>start)&&(x>0)，首xgroup1即像素4；所有当前首行、首列偶数，保留输入Bayer相位。
- ui_imx415_reg.v:70 sensor3030=0，未启mirror/flip；PIX_HST/VST=0；3020/3021/3022=1用于binning。不能按无证据的RGGB注释认传感器起点。
- 官方主线imx415_enum_mbus_code/set_format为SGBRG10：[Linux源码](https://raw.githubusercontent.com/torvalds/linux/master/drivers/media/i2c/imx415.c)。Rockchip官方相同2×2 binning控制寄存器的1944×1097模式仍为SGBRG12：[Rockchip源码](https://raw.githubusercontent.com/rockchip-linux/kernel/develop-5.10/drivers/media/i2c/imx415.c)。其时钟/位深/行起点与本工程不是逐寄存器同配置，GBRG因此是强候选而不是实机已认证结论。
- RAW10 csi_rx_10bit_unpack.v:37–40：协议byte0高8位和byte4[1:0]组成P0低10；matrix ui_raw_matrix_3x3_buffer.v:75–76把低10位P0高8提到内部RAW8高字节；bilinear输出低32bit=P0 `{0,R,G,B}`；packer pack4_rgb24_to_128.v:16–20构造p0={B,G,R}整数位序，little-endian内存低字节实际R,G,B，匹配驱动RGB24。preview_rgb.py:15仅为cv2保存转换RGB→BGR，未再改变原rgb证据。

## 现场判据

屏幕放六个等亮度原色/补色大块，保留白/灰参考，镜头对准屏、先等待gain稳态，每种Bayer各收稳定帧并统计每块中心RGB（避开边缘、饱和与黑掩码）。正解应红块R主导、绿块G主导、蓝块B主导；橙块R>G>B。若真GBRG误用RGGB/BGGR，前AWB平场会红→G、蓝→G、绿→R+B，不能用简单RGB排列救回；真GBRG误用GRBG则主要R/B交换。所有四种在同一bit上比较，直到有物理图表证据才改默认并认证，不调WB掩盖排列。

不能用灰阶黑白或生成RAW与解码MODE一致的数字黄金来证明sensor的实际颜色排列；它们证明数字映射/时序正确，现场primarychart证明真实配置。
