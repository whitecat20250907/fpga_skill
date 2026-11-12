# 眼部特征协议与app30兼容修正

已修复status为真但密集点尚未赋值时导出全零“有效脸”的问题。出口现在携带独立头部、左右眼及虹膜有效位，468点结果不会声称有虹膜；接收器拒绝退化点集、异常EAR、重放包和已退休源。

面部坐标契约明确为x/w、y/h、z/w。三维预览将Y乘h/w恢复等比例坐标，按独立有效位显示双眼。包装器透传RGB输入与capture_sequence；手部置信值保留旧confidence兼容字段，同时明确handedness_confidence含义。未增加任何模型或采集。

板端`/userdata/freeciv-rk3576-gaze-demo`对应支持文件已按原SHA256核对、备份并同步。Windows和ARM64各8项`test_project_features.py`通过。默认手势路径更新为当前`app_v30_eye_20261021`，仍可用`APP_DIR`覆盖。8类轨迹共享采样已在当前普通用户主进程旁读取56帧，没有新摄像头和动作输出。

当前主程序仍直接运行run_gaze.py；`tools/run_main_feature_export.py`是可选入口，未因为本次修正而启用。源码/协议测试不代替真人头眼跟踪和实际FPGA屏幕验收。

完整模型修正、数值一致性与正常停启证据在同工作区`fpga_skill/projects/gaze_eye_fix_20261021/README.md`。
