# v178 当前应用与限定证据

匹配2026-05-11 uisrc@ubuntu Linux6.1.99 #3/build-id3029de626e5b93ec060106f70b361766bd9a7132的源码仍未取得。新增Taishan公开kernel-6.1固定bf3e03f69e6a3b766dc6356a7475e8ad64a48a98及LubanCat固定7357e3e2c5f0114c07baa750f9949ec46f7ae320的6.1.99参考文件；三份ISP/CIF/IOMMU文件逐byte同SHA，但不同板/配置，不能当匹配SDK或内核修复。未克隆全树或下载26.9GB包。

固定参考入口：https://cnb.cool/TaishanPi-3-Rockchip-Linux/kernel-6.1 与 https://github.com/LubanCat/kernel/tree/7357e3e2c5f0114c07baa750f9949ec46f7ae320 。仍须取得匹配Image/build-id的厂商revision、dirty补丁、最终config/DTS及vmlinux/System.map；参考驱动中的早completion/DTE解引用顺序不能直接确诊旧Oops，继续隔离RK CSI/AIQ。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v178/actual_app25_T08_observation.json`。该版本保留83主项、12正式项及47 RK子检查和全部status，不增加验收。

# RK3576 CSI停流内核崩溃与匹配源码

当前板子为Linux 6.1.99，uisrc@ubuntu，GCC10.3.1，2026-05-11构建。2026-10-17读取运行内核GNU notes和boot分区FIT（全程只读），确认未压缩Image中的build-id和/proc/version均与运行内核相同：build-id `3029de626e5b93ec060106f70b361766bd9a7132`，Image SHA256 `dc87193455529b79f1487ad02790fd822f50c9cf5c3dcab7dcd98a1cf28ad592`。该证据不证明取得了匹配源树。

本地三份厂家教程指向`mlk-sdk-3576-v1.1.0.tar.gz`和`mlk_afh03_rk3576_defconfig`；厂商[下载页](https://www.uisrc.com/forum.php?mobile=no&mod=viewthread&page=1&tid=6245)的[SDK分享](https://pan.baidu.com/s/1lSdUu25wTTRFq4F1pvnTaw?pwd=32bg)提取码为32bg。匿名公开提取码验证成功，实际列出26912405818字节的文件；公开页面正常下载分支要求登录。未读取浏览器凭据、执行远程JS或尝试绕过登录/验证码；目前包仍未取得，等待用户提供本机已下载目录。包名相符、Linux release相符都不能单独证明与May11镜像匹配。

2026-10-17再次检查用户GitHub仓库的完整远端文件树（4251项，树SHA `682164dd30206566092f5332b4769884a733874f`，未截断），未发现文件名包含SDK/kernel/defconfig的新增源码。公开GitHub仓库检索`"mlk_afh03_rk3576"`、`"mlk-sdk-3576"`和`rk3576 uisrc`均返回0项；这不证明不存在其他镜像，也不代表已取得源码。实际HTTP响应和检索范围保存在`projects/hci05_dual_csi_sync_20261011/evidence/vendor_sdk_github_recheck_v4/result.json`，厂商下载页仍列上述SDK。

故障分开追踪：先有ISP capture/subdev停流超时，随后ISP IOMMU页错误，再有虚拟地址`ffffffffc0000fc0`的Oops。旧故障日志缺完整PC/LR/调用栈，不能把相似公开报告当成本机确诊。参考树`77168c8d5ab82399f65a80e9f807b50ba37cf483`为2026-07-29版本，不是本机源版本。

自己的Image按PE .text原始偏移与同一boot的_stext符号绑定后，已反汇编实际CIF/ISP/IOMMU函数。CIF IRQ内一处completion之后存在继续进入裁切/缓冲区更新的控制流候选，优先对照官方提交[d4adc9ef8376](https://github.com/rockchip-linux/kernel/commit/d4adc9ef8376ae8279884c23e7dee2a0b44f9441)。这是静态CFG候选，未证明条件可达性、completion字段归属、补丁缺失或本次崩溃归因。另查[暂停状态与停流超时](https://github.com/rockchip-linux/kernel/commit/84ed4c72d78a2a4c28609bb7b64f2f61c78df0aa)；one2multi补丁只有实际模式相符才考虑。

实际rk_pagefault_done中，页表基址转换、加DTE索引、转线性映射后读取DTE的指令已保留，检查DTE有效位在读取之后。与零页表基址诊断崩溃假设相容，但缺旧PC仍不能确诊。给诊断打印增加地址有效性保护，也不能代替修复DMA停机/IRQ完成/缓冲区归还/解绑的原始生命周期问题。

取得SDK后先运行`projects/hci05_dual_csi_sync_20261011/tools/check_vendor_sdk_source_v1.py --sdk-root <目录> --output <新的JSON>`。脚本只读版本、config差异、板配置、DTS、驱动源码与相关顺序，未经真实SDK运行验证；它不会构建或改内核。继续核对厂商revision、运行config、符号与构建对应关系，再在独立源树准备补丁和回退镜像。

当前RK CSI/realAIQ继续隔离，USB摄像头已退出。不能为验证候选补丁重复6.25秒阻塞读端或任意kill/重启CSI，不能盲换官方内核覆盖板配置。PCIe模型仍使用47 SRAM与运行时门限2，Flash37保留。真人测试按用户要求暂缓，不反复要求其入镜。

证据：HCI05的`evidence/vendor_sdk_acquisition_v3`、`kernel_binary_review_v2`、`kernel_stop_order_v1`及`upstream_stop_history_v1/candidate_diffs`。这些是源码取得与静态定位进展，不是内核修复/双摄长稳验收。

## Oops 后自动重启配置（已应用，实际故障重启未测）

2026-10-17同一boot `80995559-80cb-448c-a1bb-f4c35b1b5915`实际读取panic=0、panic_on_oops=0；运行内核没有soft/hard lockup检测接口，设备树`watchdog@2ace0000`为disabled，虽注册DW WDT驱动但没有设备节点，systemd RuntimeWatchdogUSec=0。不能把已编译CONFIG_DW_WATCHDOG=y当作实际硬件看门狗已启用。

已在`/etc/sysctl.d/91-fpga-lab-oops-recovery.conf`配置并实际应用`kernel.panic=10`、`kernel.panic_on_oops=1`，第二次独立SSH回读和文件SHA通过，panic_on_warn/sysrq保持0。[Linux 6.1原厂文档](https://www.kernel.org/doc/html/v6.1/admin-guide/sysctl/kernel.html#panic-on-oops)规定：Oops/BUG可进入panic，正panic值为重启等待秒数。本轮只验配置应用，没有诱发Oops/重启，没有验证下一次启动加载或完全硬锁恢复；CSI/AIQ仍隔离，根因修复仍需匹配SDK。

板端原值在`/userdata/fpga_lab_oops_recovery_v1_20261017/before.json`；回滚入口为`sudo bash /userdata/fpga_lab_oops_recovery_v1_20261017/rollback.sh`，只接受未被改写的本任务配置SHA和当前10/1，再还原0/0并删除自己的文件，保留回滚记录。脚本已按SHA实际安装，尚未执行回滚。主机源为HCI05的`rk/{inspect,apply,rollback}_kernel_recovery_v1.sh`，应用/第二次只读回验/板端备份和回滚SHA见`evidence/kernel_recovery_policy_v1/result.json`。FPGA/Flash、内核二进制、设备树与模型没有操作，不能据此补签双摄、内核稳定性或自动模型恢复。

## 用户态停流错误路径v9b（独立、未部署）

复查已编译的v8采集C发现：STREAMOFF报错后仍继续munmap、REQBUFS(0)、恢复格式及close；SIGTERM已置stopped时，旧ioctl包装器也不再重试EINTR。旧父进程虽然保留AIQ，采集子进程却已经释放映射，不能把父进程守护通过当成资源生命周期已完整修复。

独立完整软件副本为`projects/hci05_dual_csi_sync_20261011/rk/retained_cleanup_v9b`。STREAMOFF清理单独重试EINTR；其他失败输出`capture retained pid=... cleanup=... stage=streamoff_failed_retained mappings_and_fd_retained=1`，保留原V4L2映射、fd和进程，不执行后续释放或自行退出。现有AIQ manager据活子进程和未通过的cleanup证据继续保留其AIQ。私有stdout复制队列可结束，不等同释放DMA映射。

第一次v9模拟测试还发现POSIX编译条件下的signal()处理会被复位，第二次SIGTERM能终止保留进程；v9b改用sigaction持续处理INT/TERM/HUP。不要只观察第一条retained日志就签核重复停止信号下的资源保留。

RK本机编译和完整C的12个memfd模拟设备试验、10个父进程假进程案例已通过并逐源码/ZIP/板端输出SHA核对：4项旧版EIO/停止信号+EINTR反例确实在模拟流未停时解除8/16个映射；4项新版EIO/ETIMEDOUT保持映射/fd/进程且重复SIGTERM不退出，实际manager也不停止其假AIQ；2项EINTR重试成功，2项正常清理顺序通过。未包装的真实采集C仅编译，AArch64 ELF和SHA已核实，没有执行。证据：`evidence/retained_cleanup_v9b/review.json`。

模拟设备只允许`/dev/video-mock-only`，由memfd供数据。测试中的SIGKILL仅销毁已确认的模拟子进程，不能复制到真实相机/AIQ恢复流程。真实失败保留状态的PID在stderr，AIQ PID/未通过原因在父进程result；不能因SSH观察超时就强杀这些进程。

这只修复用户态收到失败后的错误释放与信号处理。STREAMOFF返回0但驱动内部已timeout、DMA未停，或ioctl本身挂死时，此守护不证明安全，也不解决原始内核问题。真实CSI/AIQ继续隔离；没有实际停流/双摄恢复验收，也没有切换当前PCIe模型。
