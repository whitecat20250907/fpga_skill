# 实际物理行数与裁切/ISP/打包边界自检

2026-10-05，ModelSim SE-64 10.5 实际进程 exit0，0 errors / 0 warnings，仿真时间75,121,464ns、运行2m55。证据：[physical_crop.log](physical_crop.log)。这不是新位流上板验收。

## 根因与条件

[Rockchip 官方 IMX415 驱动](https://raw.githubusercontent.com/rockchip-linux/kernel/develop-5.10/drivers/media/i2c/imx415.c)包含1944×1097的GBRG binning模式；[Linux主线驱动](https://raw.githubusercontent.com/torvalds/linux/master/drivers/media/i2c/imx415.c)采用RAW10 GBRG并定义2192行阵列。本地厂商寄存器表的时钟、bit depth并非与Rockchip整表完全相同。完整1944×1097/3888×2192 RAW10输入在本测试中是明确的物理尺寸假设，最终需要本板CSI每帧RAW包数/WC确认，不能将Linux表当实测。

主工程历史1080p `v_start=19,v_end=1100`，实际选中 `y>start && y<end`，即y20..1099。1097行输入只有y0..1096，因此只进入1077行。矩阵按声明height1080，需要输入第1079逻辑行才启动真正末行DRAIN；少行时只完成正常前看输出1076行。1076×1920×3=6,197,760字节。本次完整CSI仿真精确复现这个长度和EOF=0。

现场旧bit报告6,197,776字节后又16字节：其主要图像长度与仿真一致，但额外16字节的completer/flush残留来源没有在此TB例化或证明。不能声称本测试复现整个PCIe包化过程，也不能把驱动改为接收短帧。

## 真实测试对象与模型边界

`src/`为当轮真实RTL字节快照，见[source_manifest.json](source_manifest.json)，不改主源：CSI header ECC、packet handler CRC/WC、RAW10解包、image_correction、真实BLC（四lane偏移均设置0）、真实demosaic矩阵/两2048×32同步CE RAM/bilinear、真实RGB24→128bit packer。runtime Bayer实现与已提交root候选相同；参数GBRG且输入端口显式驱动3。

TB产生每行完整CSI-2 RAW10包、FS/FE短包、低lane-first字节、正确header ECC及CRC16。1944px的WC2430末载荷2byte与CRC2byte共享最后32bit拍；3888px的WC4860载荷整拍、CRC单独尾拍。每个RAW像素的低2bit随坐标变化，逐像素检查全部解包位与物理行坐标。发送拍间留空，验证有效洞不充当行末；输入速度刻意低于消费者，并断言任何RAW拍背压即失败，没有隐含丢弃或假FIFO。

未例化电气PHY、自动校准、跨时钟FIFO、AWB/后处理、frame_gate、frame_completer、PCIe核或驱动。输出ready保持1，本TB验证精确裁切及尺寸边界；背压/四Bayer/帧内修改另有runtime golden证据，不能写为同一测试覆盖。

## 自检结果

| 用例 | 输入CSI RAW像素/行 | 裁切原点与范围 | crop输入行 | RGB输出行 | 紧密RGB字节 | EOF |
|---|---|---|---:|---:|---:|---:|
|720p控制|1944×1097|x4，y36..755|720|720|2,764,800|1|
|新1080p|1944×1097|x4，y16..1095|1080|1080|6,220,800|1|
|新4K|3888×2192|x4，y16..2175|2160|2160|24,883,200|1|
|旧1080p复现|1944×1097|x4，要求y20..1099，实际至1096|1077|1076|6,197,760|0|

720p→新1080p→新4K在完整FE与排空后改变模式，未复位，输出均逐像素对独立坐标bilinear golden。旧短帧用单独复位隔离，以确认缺失末行时没有伪EOF。每个用例核对全部RAW/crop坐标、四lane顺序、精确SOF/EOL、RGB全部像素及首末镜像边界、全部packed字节顺序、帧计数和EOF同最后数据。RGB来自GBRG物理坐标编码，mid-frame将shadow写0但活动Bayer保持3；首行16/20/36为偶数，首列4亦偶数，因此相位保持GBRG。

4K只在数字域验证当前裁切和边界，不能由此声称Gen2 x1支持4K60、CMA够用或本板4K实拍通过。任意帧中改尺寸不在此测试范围；实际模式切换仍须STREAMOFF、停pipeline/flush、释放缓冲、修改/核对尺寸、重新分配后STREAMON。

## 复现

```powershell
Push-Location 'E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/tools/crop_height07'
try { & 'D:/Modelsim/soft/win64/vsim.exe' -c -do 'do run.do' } finally { Pop-Location }
```

脚本只在done=1时退出0；包含800ms仿真超时。测试文件没有注册为主工程综合源。新版本07的TD/新bit/CSI计数与720/1080实拍、正确原色、双向回环及停止恢复仍由对应当轮记录验收。
