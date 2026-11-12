# P2 视觉服务
眼动调用原 run_gaze.App.process/advance、原人脸/眼动模型、标定、OneEuro、RegionDecider。包装替换摄像头为三槽读取，发布 face/gaze 消息并关闭自身点击出口。人脸几何取原结果；按状态在采集边界限速。新硬件 epoch、gaze 进程重启、标定者 track 变化使旧个人标定失效。

手部调用原 HandRecognizer；原 MultiTrajectory/Classifier 只在 WRITE 工作，离开 WRITE 清空录制器。真实 8 类 probabilities 保留，显示轨迹最多 48 点，显示采样不改分类器实际输入。

字节校验及三平面不变性测试通过。原始目录与整合目录在独立进程中运行同一确定性输入：390 条 258 维标定样本、96 条留出输入、600 帧 OneEuro/区域判定、7 组轨迹栅格，6 组输出逐字节相等、最大绝对误差 0，见 evidence/numerical_comparison.json。此检查覆盖 CPU 数值阶段；没有 RK3576，因此没有完成两个完整 RKNN 服务的真实输入 A/B、NPU 耗时与精度验证。

读者每轮检查发布路径所指 memfd 的设备号/inode，原 owner 退出或更换环时退出并由 systemd 重启，避免旧 mmap 继续存活造成假恢复。眼动包装停止写旧应用的 control_status.json 和旧人物 tmpfs 导出，界面提示替换为新手势规则。专用导入解析器固定项目模块到 vendor，历史绝对路径不能覆盖同名源码；第三方及标准库照常加载。两人同时登记/各自标定及身份恢复未实现，菜单明确保持单人。
