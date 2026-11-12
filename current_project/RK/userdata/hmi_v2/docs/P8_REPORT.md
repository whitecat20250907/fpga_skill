# P8 验收清单
本地自动结果：evidence/local_check.json、native_build.json、bus_load.json、numerical_comparison.json、web_render.json；FPGA 仿真结果在工程 validation/hmi_sim/results.json。发布包会逐文件验 hash 并 testzip，体积以最终发布清单为准。

待上板实际记录，不得填造结果：
1. preflight；正常停止旧链路；新 owner 唯一持有设备，首帧 epoch 和三平面 CRC 正确。
2. 连续 10 分钟模型包率、源年龄、温度；停机后 0x19C 空闲，无残留设备 FD。
3. 摄像头画面和 MIPI 真实像素；新 CSR ABI、generation、flush 恢复。
4. 相同人/坐姿的原标定与 20 点留出评测 A/B；模型与算法同输入数值比较。
5. 三应用各完成 20 次唤醒/确认/取消/下一项，记录误触、漏触、延迟；过期帧不得确认。
6. kill/restart 每个服务、相机断流、桌面焦点切换、游戏 nonce 超时、进程 epoch 变化；所有路径不重发动作。
7. HUD 穿透与 F10 紧急待机；实体 K4 仅在板卡引脚查证后另行实现。
8. WRITE 八类结果、低置信度、双手冲突；游戏 WRITE 不触发动作。

当前不可写成“全部 P0–P8 完成”：compat-up 独立旧链路、双人登记、完整新 MIPI 布局及 P6 预处理功能未实现，实际部署/真人验收未执行。当前交付是可复查的本地整合候选版。
