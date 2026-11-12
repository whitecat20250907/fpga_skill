# v50：异构对比页面

2026-10-26。电脑控制台 http://127.0.0.1:8786/ 新增“异构对比”导航，已部署并通过实际浏览器检查。v49 眼控、映射、游戏、医学与昨天 MIPI 布局保持。本轮只重启 hmi-console。

## 页面

- 现用链路实时卡片：模型图像交付 Hz、FPGA MIPI 场景接收包率、全 CPU 归一负载、NPU 两核驱动忙碌率；最近 60 点交付速率趋势。
- 按 FPGA / NPU / CPU 展示实际分工，比较连续图像、实时性、灵活性与功耗测量状态。
- 历史 CPU 精确缩图中位 3.756 ms 来自 2026-10-23 的 120 次样本。独立 FPGA 仿真的约 518402 周期、125 MHz 假设换算 4.147 ms 单独标明，并注明当时完整时序未签核；工作范围不同，不提供伪加速比。
- 窄屏自动两列指标、单列说明；比较页隐藏应用切换条，紧急待机和导航仍保留。无外部 CDN。

## 口径与实现

console/comparison.py 只读既有 frame.meta、sys.metrics.fpga-io 以及 /proc/stat、/sys/kernel/debug/rknpu/load。原 console 的 Subscriber 增加观测主题，每秒采样，/api/comparison 返回缓存；浏览器仅在本页可见时请求，约 1.1 秒一次，折线最多 60 点。不直接打开设备、不请求新的 DMA、不加载模型、不发送动作。

共享环 serial 增量 / 所有者心跳时间差为模型交付率。FPGA accepted_packets 增量为显示协议接收包率，两者都不是屏幕刷新率或模型识别 FPS。frame.meta 的源时间年龄不是光子到响应的端到端延迟。显示错误仅统计 CRC/格式/序号的采样区间增量，不证明 DMA 长跑完全稳定。

CPU 所有在线核心归一到100%；NPU两个核心各自0–100%，不合成全板利用率。缺失文件、失联、计数回退、epoch/所有者实例变化不拼接或伪装零值。功耗、FPS/W及当前位流静态占用未测/未绑定正式报告，页面明确说明，不从忙碌率推算瓦数。

## 验证

本地和板端均9项回归通过（4项遥测边界、5项原console/game接口），浏览器脚本语法检查通过。实际浏览器导航进入新页，实时数值与趋势显示，窄屏无整页横向溢出；截图 console_comparison_v50.png。

板端6次接口采样：模型图像交付39.80–41.86帧/秒，显示29.85–29.94包/秒，CPU42.60–48.15%，NPU0为39–40%、NPU1为0–1%；显示协议错误增量均0。该短窗口不是单/双人资源矩阵，未据此宣称节能、延迟上界或长跑通过。

八项服务运行。原生owner PID2708、epoch13349717123306135891、native二进制SHA均保持；除console外服务PID不变。没有改动FPGA位流、采集、映射、眼控或应用适配器。

源码总表 V50_CURRENT_SOURCE_MANIFEST.json；部署原补丁 V50_SOURCE_MANIFEST.json 中HTML为布局修正前版本，最终HTML以CURRENT总表为准。备份 /home/linaro/pcie_fix_20261003/hmi_v50_previous，布局前HTML另存 console_index_v50_before_layout.html。回退本次只恢复console/server.py与index.html并重启hmi-console，新增comparison模块可保留不加载。

原项目未完成范围仍以v49交付和WORK_PLAN_v17为准，含确认手重复、真人/双人四手、P6、compat-up与DMA长期恢复等。本次页面完成不代表原项目全验收完成。
