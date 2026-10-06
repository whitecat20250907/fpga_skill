# PH1A CSI 时钟、复位与 BAR 接收前置

适用于本次 PH1A90SEG324 / AFC03 PCIe 相机副本。状态依据2026-10-05实测，发布整理2026-10-06；这些经验不能无条件推广到原06的PH1加密PHY。

## 状态先分开

- 07有27MHz MCLK和111.375MHz byte clock，但auto done=1/best_window=0、RAW包0，无帧；SYN-6024四条PAD常量复位警告不能因一般setup/hold为正而忽略。
- 08恢复共同PAD复位，完整STA仍有recovery/removal负余量，未下载。
- 09 local/global时钟分支与active-high共同reset通过原语数字黄金、完整STA（setup+0.067ns/hold+0.020ns，TNS0，覆盖99.96%）。实际下载后Gen2x1，但视频只读BAR寄存器0，未采集，不能称接收已修好。
- 10相对09只改读地址guard和版本0x56440a01，数字地址自检268项通过；完整构建中断在place，交接时没有10最终bit/板测。
- 最近下载09不保证SRAM现在仍有09。2026-10-05交接电脑仅枚举蓝牙COM3/4，RK串口/AL-LINK未枚举；恢复访问后重新确认。

详细证据在仓库 `projects/pcie_imx415_fix_20261003/reports/` 和 `evidence/`；当前修复顺序及操作在 `docs/09_开发板修复_新对话完整交接_20261005.md`。这些是带时间的状态，不替代新会话读取最新日志。

## PAD本地时钟不能被fabric用户的全局分支代替

实际PH1A布线中，给fabric寄存器的PCLK经GCLK/SCLK分支，比本地SCLK晚约1.7ns。缩短reset数据只改善recovery却恶化removal，不能盲加寄存器或cut相关检查。

按官方UG910 §19，09使用D0 LCLK DIV2/DIV2TO8：clkout→local PAD PCLK，clkdivout→global fabric PCLK；D1 DIV4/BYPASS：clkout→HS sampler SCLK，clkdivout→byte clock。约222.75/222.75/445.5/111.375MHz，实际约束和实例以该完整工程为准，不在运行期mux时钟。

global n0采PAD nibble，n1采n0，byte由n0/n1组成；不能混用local本拍与global上一拍。共同3级reset改active-high存储而保持异步断言、释放边沿，使PAD.rst得到Q直连并去掉反相LUT。完整恢复/保持和nibble/byte路径仍受STA约束，不能靠独立小工程或数字仿真替代整机。

## BAR偏移与不可变版本是接收前置

实测BAR0 0x21200000..0x212fffff，1MiB对齐。CQ转发请求地址，SGDMA内部加密，不能假定ARADDR高16位为零。

10按本工程1MiB BAR0契约检查低20位offset：高offset nibble[19:16]为0、低16位0x0040..0x011c。兼容0起始、完整BAR地址和CQ26位残余地址，排除64KiB/0x80000高offset及0x128 IRQ别名。不要将这个契约推广到不同BAR大小。

setup写0x98后回读100可以来自原app RAM回显，不证明video read mux正常。先读取immutable 0x5c实际版本、0x44/48尺寸、0x4c格式1及bytes/padded，正确才采集。setup返回0、PCIe Gen2x1或可写RAM都不是通过结论。

CHAR_USER旧pread/pwrite加0x80000，而mmap不加；10只验证当前V4L2/setup/诊断所用mmap/直接BAR路径，不认证旧fops全部兼容。继承写地址别名、WSTRB忽略和RREADY stall时RDATA稳定性另列问题#13，不与当前接收定位同时大改。

## 诊断不能把无数据判健康

- 0x50低24位是frame count，高8位是pipeline sticky。当前read_csi_diag10.py仍整32位标frame_count，此观察工具修正待完成；一次读出再分别报告raw32/count/sticky，不能两次读形成不一致。
- E4为diag0 bookend，100为diag1，A8为CSI；11C属于diag0。SEQ应持续增加，busy可短暂置位。
- RAW previous/current payload行数不等于CRC-good或最终裁切高度；previous在下一FS锁定。binning输入1097行可以输出720/1080。
- manual override时auto scanner仍运行但tap被固定，best_window甚至32也不证明真正眼窗扫描。关闭override不会重跑scanner；自动验收需override关闭的fresh reset/完整扫描。
- 真实DMA运行后、tap稳定/auto done/新FS后的稳态比较CRC/ECC/WC/timeout/overflow增量。扫描启动ungated错误另记；无RAW包、无帧且错误0不是健康。不要开启CTRL却不准备DMA，把无消费者的overflow误判为PHY。
- 用实际完整帧bytes/序号/错误buffer验证；WC错误计数仅检查非零/整除5，不证明实际WC2430/4860。#1接收通过不包含色彩正确或双向通过。

## 保留工具限制

09b匹配SDF/网表已真实注入timingcheck，但ModelSim10.5在time0两次native SIGSEGV，无一个字节验收；没有关闭检查绕过。MTBF隔离入口亦native crash，无合格报告。数字原语黄金、完整STA、实机三个证据分开。

TD OOC/debugger关闭async_reg全局directive时，重新打开RTL/PLACE参数可恢复原准确集合；不能晚补属性伪装优化掉的链。逻辑232属性与物理104cell是不同映射粒度。99.96%覆盖及外部delay、PLL/IO/动态Gen1→Gen2警告仍需逐项记录，不写零警告全面合格。
