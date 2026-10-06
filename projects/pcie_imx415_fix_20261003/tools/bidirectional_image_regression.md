# 双向完整图像回归工具

原冻结07入口 `bidirectional_image_regression.py` SHA-256 `13f988ddcbde53890e1f1e8b8be4dc92457b27cb50dacd3be2b341dd771c2af9` 保持原字节。更新入口 `bidirectional_image_regression08.py` 支持实际BAR版本0x56440701及0x56440801，记录实际版本并拒绝运行中变更，默认结果目录带实际07/08编号。两个入口不能互相继承实测状态。

本地主机验证：Python py_compile及自检通过；没有运行开发板或Linux C编译。08自检27项，覆盖长度/rc/memcmp/hash、短echo/同inode/改字节/重复JSON拒绝、活动fd、真实普通文件mmap下的CAM_MODE0-before-insmod、BUSY1禁止恢复，以及07/08版本接受和运行中版本改变拒绝；标记HOST_SELF_TEST_PASS_NOT_BOARD。真实C和pattern脚本的编译/运行是板上入口首阶段，不能只看主机Python通过宣称板链路已验证。

```bash
sudo python3 tools/bidirectional_image_regression08.py \
  --task-root /path/to/deployed_project \
  --camera-rgb /path/to/actual_camera/last.rgb \
  --camera-origin-version 0x56440401 \
  --v4l2-ko /path/to/deployed_project/deploy/v4l2_drv/milianke_v4l2.ko
```

camera文件必须是现有实际采集的一幅720p或1080p紧密RGB24。该命令只把指定字节经H2C→FPGA loop FIFO→C2H回传，不采集新相机，不验颜色；示例旧04 source在新07/08回传不能标新相机通过。source/echo不允许同inode，输出新目录，保留原始source快照、echo、所有正常/失败日志和JSON。

动态唯一发现user/control/C2H0/H2C0、Milianke video及endpoint。需要已加载SGDMA和V4L2、无活动clients、CTRL/A4/app-command关闭、真实DMA RUN0/BUSY0、正确版本；拒绝缺失/歧义/忙设备。只卸载milianke_v4l2，SGDMA始终保留；finally等子程序退出并确认真实idle后，将BAR mode置0并读回，再恢复相同V4L2 ko/参数。若DMA卡BUSY或子程序不能退出，明确失败并拒绝强制unbind/SIGKILL，不假称恢复成功。

验收矩阵：known720p 20帧/64KiB；known1080p 3帧/4KiB、20帧/64KiB、50帧/1MiB；指定实际camera source 3帧/64KiB；每项须精确总字节、C逐字节比较0错误、完整echo单帧长度和source/echo SHA相同。C源码是实际image_roundtrip.c，用gcc -std=c11 -O2 -Wall -Wextra -Werror -pthread在新目录编译；实际make_rgb_patterns.py同字节复制到私有source目录，py_compile后生成坐标/通道编码图案，避免覆盖工程历史pattern。

SIGTERM项计划100000个1080p大帧，在子程序仍运行、mux打开且echo确有至少1MiB实际收回字节后发送真实SIGTERM；要求工具报告interrupted/failed、返回1、完成量介于0和计划总量之间且已收字节无内容错误。记录实际signal时engine状态、partial echo和返回日志。随后核对CTRL/A4关闭、RUN0/BUSY0，**从子程序已退出且cleanup/idle完成后观察完整12秒**，不重新开流或复位，kernel增量不能含残留poll timeout，再做新known首帧精确hash。

08工具把中断处理期间的kernel日志及poll消息另外完整保留/显式计数；12秒quiet判据只针对cleanup后的残留任务。若中断期间有超时，仍需人工审查是否为当前被停止的互等read，不能隐去或将该记录描述为全过程零超时。旧冻结07脚本以整个中断过程kernel增量为判据，两者范围不同，报告按实际入口区分。

AER endpoint/rootport状态与计数、CMA总量/空闲前后记录。endpoint AER不可读拒绝认证；rootport缺项明确不可用，不装作已检查；既存/新增AER flag或计数增加失败。CMA总量至少64MiB，默认允许空闲损失≤1024KiB（不是任意泄漏认可），可用--cma-leak-kb收紧。所有phase、版本、source/C/executable/ko hash和恢复结果进入summary.json；只最终全部完成才输出通过。
