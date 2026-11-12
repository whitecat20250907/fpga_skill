# F5资源分账（当前实板版本）

ERAM采用物理网表逐单元计数，下面顶层集合互斥，相加为264；总容量272。

| 顶层实例 | ERAM | 占器件ERAM |
|---|---:|---:|
| `u_cam_video_source` | 88 | 32.35% |
| `u_sgdma_subsys` | 66 | 24.26% |
| `u_c2h_fifo` | 52 | 19.12% |
| `u_twin_pcie_ui` | 46 | 16.91% |
| `u_image_loop35_fifo` | 4 | 1.47% |
| `u_raw_trace` | 4 | 1.47% |
| `u_twin_dsi` | 2 | 0.74% |
| `auto_created_cwc1` | 1 | 0.37% |
| `auto_created_cwc2` | 1 | 0.37% |

子实例明细在 resource_f5_breakdown.json 中；子项已经包含在父项内，不重复相加。

| 用户进程 | CPU均值（单核100%） | 折合整颗八核容量 |
|---|---:|---:|
| vision.gaze_app | 30.50% | 3.81% |
| adapters.run | 16.12% | 2.01% |
| vision.hand_service | 13.05% | 1.63% |
| core.interaction.run | 12.17% | 1.52% |
| console.server | 10.38% | 1.30% |
| fpga_io | 9.44% | 1.18% |
| core.io_service | 6.92% | 0.86% |
| ui.hdmi_hud | 4.57% | 0.57% |
| ui.mipi_composer | 3.75% | 0.47% |
| bash | 0.00% | 0.00% |

测量为F5空场景十分钟。CPU2/CPU3的内核SGDMA轮询不在这些用户进程内，不能用进程合计替代整机CPU。NPU0/NPU1均值12.23%/0.80%，只能代表该空场景；固定输入并发模型见 RESOURCE_AND_DEPLOYMENT_v20.md，真人单人/双人四手还需独立采样。

当前可解释的下一步是回收CNR过配行存储；F6未通过最终时序和实板验证前，不把其239块中间值计入当前结果。FIFO两分钟峰值1字不是压力余量签核，也没有通过牺牲1080P预览来减少占用。
