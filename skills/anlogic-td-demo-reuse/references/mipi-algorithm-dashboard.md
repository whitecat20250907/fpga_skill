# MIPI屏算法仪表盘

2026-10-21 用户随后明确纠正：当前主界面必须是项目的手部、头部、双眼真实特征和实时三维孪生。
以下通用灰度/高斯/Sobel 首版仅保留作字体、DSI与完整构建的历史参考，不能再签当前 U01/U03。
新数据流、实际 RK 渲染和双人交互经验见 [project-feature-twin-and-campaign.md](project-feature-twin-and-campaign.md)。

用户于2026-10-21明确参赛项目包括完整个人项目：保留多屏、语音、多人及高阶交互；新增FPGA端MIPI屏算法内部展示，可适当数字孪生。I系列和K09退出任务，不等于删除UART基础设施或放开故障CSI链路。当前范围和状态读根PROJECT_SCOPE.md与GOAL_PROGRESS.json。

首版完整工程是 `projects/mipi_algorithm_dashboard_20261021`，独立派生05 DSI CRC，1024×600、50MHz像素时钟，保留原ADC/SDC/DSI封包和PHY。新renderer无额外CDC、CPU显示线程或帧缓存；同步与字体、RGB保持3周期延迟。

真实RTL预览由Icarus逐像素输出，不能用Python重新画的示意图代替。四窗口对同一合成图样分别显示原图、灰度、3×3高斯和Sobel；独立Python只核对选定像素的数值。全帧614400像素、同步、未知值、边界和中途reset均检查。中文字体仅分发渲染后位图，不复制字体二进制。

数字孪生必须标注合成输入、真实遥测未接入；移动ROI和动画不是相机检测或真实吞吐。显示源帧计数不是屏幕光学接收帧率。U02负责真实中间图和一致性快照；U04负责实屏/颜色及PCIe/NPU共存，独立05位流没有PCIe功能。

TD脚本参数使用正斜杠。TD在读脚本失败后仍可能以0退出，必须要求真实DIRECT_BUILD_COMPLETE、自己的输出、STA和源哈希，保留零退出但无构建的反例。

TD的readmemh相对路径首先以调用RTL文件目录为基准；Icarus通常以进程cwd为基准。ROM默认使用同目录basename参数，仿真显式覆盖为项目相对路径。必须检查HDL-5105与ROM undriven告警：正STA和bitgen成功不代表字体已加载。首次两个失败和修正位于工程evidence，不覆盖它们。

当前原生及位流验收读取本工程evidence/full_native_v3/result.json及后续审查；不得引用前两次构建的标量或未初始化位流作为当前成功。
