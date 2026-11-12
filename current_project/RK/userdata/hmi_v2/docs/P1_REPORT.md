# P1 原生硬件所有者
完成：单 C 进程复用 capture_native/fpga_model_input 原包校验、twb_core 原事务接口；3 槽 memfd；旧 GZMDL002 导出；硬件锁；本地 SOCK_SEQPACKET 受限 UI01/STAT；UI 源年龄与 epoch 检查；CSR 忙拒绝；原 panel 四步与 ABI/时钟活动门禁；退出检查模型通道低三位空闲。

Windows 上用 Zig 构建 ARM64 Linux 可执行文件和 libring.so，所有 C 编译使用 -Werror。ring_test.dll 的双读者并发测试校验完整 850944 字节帧；panel_test.exe 只在寄存器模型上验证顺序和拒绝条件。证据见 evidence/native_build.json 与 local_check.json。

UI 提交包装调用原 twb_core 的真实校验/预留/提交函数，正确区分 prepared_ns 与 token；先核验输入 CRC，再按 C 侧硬件锚点向上更新 age_ms（不改源时间或几何），重新计算 CRC。硬件所有者分配单调传输序号，同时更新 HFT2 display_generation 与 CSR，UI 服务重启不会回放旧 FPGA 序号。CSR mailbox 在 HFT2 FIFO 数据前提交，按相同 generation 等待空白期锁存。ui_test.dll 的回归覆盖实际 C 路径：令牌、包龄、CRC、代号不匹配、未来源时间、忙拒绝、UI 重启和旧 ABI 无 CSR 路径。

唯一生成的原代码派生头为 native/fpga_io/fpga_model_input.h：调度 CPU6→CPU4、SCHED_RR1→SCHED_FIFO10，同时更新日志；解码及像素计算未改。vendor 原头字节不变，build.py 可重复生成。

未验证：真实 DMA 停机、PCIe 包率、独立时钟电气输出、面板光学显示、Linux IPC 共享映射一致性。AE/ISP 任意控制写口未开放，P6 实验功能不能通过改配置直接启用。
