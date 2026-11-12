# TD 自身 checkpoint 续跑的实际边界

续跑要区分原完整源码构建、自己的checkpoint派生结果和新完整构建。保存原失败，绑定原源码清单与checkpoint SHA，复制到独立工作目录；最终STA/位流仍须在本次结果上复核。

Windows向TD传Tcl入口时使用`Path.as_posix()`。TD会解释反斜杠，实际出现过入口路径被吞、`resume.tcl`未读到而进程返回0。成功判据包含本次明确完成标记和所需产物/时序结果，不能只看returncode。

导入RTL DB重新执行`optimize_gate`仍依赖原工作目录相对路径中的MIF/DAT/DATH等ROM文件。只复制DB会在Map Macro时报Unable to open RAM init file。复制并核对实际staged清单及它引用的本地依赖，保留项目文件被原生工具重写前后两种SHA的明确映射。导出mapped网表和gate DB放在覆盖守护之前，便于真实失败诊断；成功导出不等于守护通过。

快照约束的实际路径数不能由源寄存器总数推定。F15 held的高32位目标snapshot未被消费而可裁掉，源高32位仍驱动previous_cycles/clock_delta；因此source寄存器901与snapshot路径869都不能直接作为覆盖签核数。由本次mapped图沿源Q和buffer alias到目标时钟的首个D端点推导集合，检查所有实际消费者，再逐端点核活动约束及预算。额外clock/SR/CE或意外时钟域须显式调查。

同样，debugger reset的两个逻辑FF可能同slice共用一个ASR，也可能分开成两个实际ASR。按本次physical图推导端点，固定原预算并核精确source/endpoint/path type；不把期望1放宽为任意1–2来掩盖遗漏。报告命令日志中集合参数显示为空不代表结果文件无路径，应以集合大小守护和实际报告完整端点为证。

证据入口：`projects/hci03_clock_query_rebase_20261019/evidence/debug_reset_guard_v2/result.json`、`own_place_resume_v2/result.json`、`own_place_resume_v3/plan.json`；F15对应`projects/hci06_csi_observe2_20261019/evidence/full_build_v1/result.json`、`mapped_diagnostic_v1/result.json`、`mapped_diagnostic_v2_ready/plan.json`。这些记录包含失败和准备状态，不可整体标为PASS。
