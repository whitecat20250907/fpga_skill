# 打包LUT驱动寄存器与真实时序端点

用于TD把I²C被动观测的第一级FF打包进LUT单元，或合并时序查询遗漏输入的场景。保留原RTL/约束/数据库，扩展检查器对实际映射的识别；不要为了适配检查器更改功能路径或放宽时序例外。

F14实际映射为同一LSLICE的B寄存器接内部LUT（`LUTMODE=DLUT5, REGB_SD=LUT6`），A寄存器接IMA作为第二级。外部SDA驱动PAD的TS由另一个LUT产生。不能要求两者一定同网、INIT字面值相同，或把内部D虚拟名称传给`get_pins`。

本机`tools/packed_drive_configuration_v1.py`绑定实际gate LUT4的4个源、PAD TS及内部LUT的参数/选择器/输入。根据厂商公开tri1声明处理省略输入，按实际输入排列比较全部16个源组合；17项分类器测试含INIT/输入/选择器/寄存输出/模式/PAD错误拒绝，以及正确的输入排列与无关常量余因子。此为导出配置比较，不执行或解密受保护原语，也不证明模拟电气、毛刺、眼窗或ACK。

TD的`report_timing_path -path_num 1`按时序终点报告最差路径。把一个寄存器的4个LUT输入合并查询，本轮只得到最差setup与hold，其余输入未覆盖；原严格检查正确拒绝。改为逐输入单独报告，继续要求8个真实输入各自setup/hold共16项，另有SDA外部输入setup1项、复位recovery/removal6项，总23项，并核对实际源FF时钟端点。不能减少预期集合来迎合截断报告。

实际证据位于`projects/hci06_capture_clock_reset_20261019`：

- `evidence/packed_drive_configuration_v1/result.json`：当前配置及17个分类器用例。
- `evidence/wire_physical_route_v2/native_query_v1/result.json`：合并查询真实失败，保留原报告。
- `evidence/wire_physical_route_v2/native_query_v2/result.json`及父目录`independent_review.json`：隔离自己路由DB副本逐输入查询，全部23项通过；原构建文件逐SHA不变、最终标量仍+0.158/+0.020ns，原33组1266用户约束保持。
- v5静态结果保留一个v4旧字段名`physical_drive_same_net_or_identical_sibling_configuration_only_not_protected_behavior`。实际证明并非同网或相同INIT；以`source_terminal_proof.same_physical_net=False`和最终独立复核的明确纠正为准，不根据旧标签补签。

完整174+9构建及上述检查通过后，F14实板仍失败：PHY窗口0、RAW0，ECC16→25；仅首个常量配置被接收，因无帧界尚未应用。不能把正STA、配置ACK或CRC0当图像通过。实际已恢复47 SRAM、app24原NPU及运行时2档完整直方图；Flash37未改。

后续源比较还确认：word-align与稳定47相同，gearbox仅模块名/显式input wire/空白注释差异；9个相机控制/HS引脚属性相同，cam_pll27源字节相同。47 ADC的“12MHz toggle”注释已过时，实际top使用27MHz PLL转发，不能靠该注释修改时钟。这些源事实仍不证明实际相位/电气或训练根因。
