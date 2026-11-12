# P5 FPGA 显示
新增 0xC80–0xCF8 影子组与 0xCFC 提交；busy 时拒绝写。跨域使用稳定 mailbox + toggle/ack，只有 HFT2 前台 generation 与 CSR generation 匹配且处于垂直消隐时才发布。0xCF0 返回 UI10 ABI，0xCF4 返回拒绝计数。传输 flush 同时清除 CSR 状态。

保留原五个 HFT2 视口/ERAM 和光栅路径，在同样三周期视频延迟下叠加状态、上下文、服务流水线、手势进度、菜单和 8 类概率条。未把原视口强改为附件的新大舞台布局：当前 ERAM 接近满额，布局调整需要与 P6 存储回收一起评估。流水线卡片当前表达服务健康，不冒充各 NPU 层精确耗时。

实际 RTL 验证：独立 CSR 异步时钟测试；原五帧光栅回归（3072000 像素）；整合顶层 BAR→FIFO→HFT2→光栅→叠加九帧（5529600 像素），检查无未知有效像素、三周期同步、消隐发布、有效帧内代号一致。字体 ROM 在仿真中使用相同数据的一周期行为模型。图像全部来自显式 synthetic fixture，不是真机识别画面。

完整 TD 布局布线与时序结果见 FPGA_BUILD_STATUS.md。未执行 SRAM 下载。csr_enabled 默认 false，避免新 host 对旧 bitstream 写未知寄存器。
