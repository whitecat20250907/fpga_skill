# P3 交互引擎
实现 BOOT/STANDBY/PRESENT/ONBOARD/CALIBRATING/IDLE/POINTING/MENU/WRITING/DEGRADED、统一手势保持/释放、跨手冲突、过期/重复帧拒绝、上下文映射、动作 id 去重及不重发。

关键测试覆盖入座→标定→唤醒→确认、过期眼动、服务故障和 epoch 变化、10 万随机事件不变量、WRITE 手势所有权、紧急待机粘滞、重复管理命令、gaze 快速重启、个人 track 改变。详见 tests 与 evidence/local_check.json。

按附件的“最小惊讶”原则：菜单的双人项暂只显示说明，不猜测人与手的归属。当前 AFC03 顶层明确 `debug_button` 无物理输入，未编造 K4 引脚；使用全局 F10/F5 和认证控制台。
