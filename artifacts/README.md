# 选定产物与验收边界

逐文件 SHA256、大小、来源与状态在 [manifest.json](manifest.json)。名称已经标明不能继承的实机状态。

| 文件 | 状态 |
|---|---|
| `rtc03_sta_pass_not_board_tested.bit` | 当前RTC修订约束下完整TD通过，setup+32.845ns/hold+0.036ns；未新上板 |
| `ddr04_sta_pass_not_board_tested.bit` | DDR修订完整TD通过，setup+0.745ns/hold+0.020ns；未新上板 |
| `pcie09_static_pass_BAR_precheck_failed.bit` | setup+0.067ns/hold+0.020ns；实际下载但视频BAR前置失败、未采集，不能当相机修复交付版 |
| `boot_pcie_cma64.img.gz` | 原镜像已刷写读回/重启确认CMA64；PCIe1模式下USB1 hub/Wi-Fi互斥，未恢复共存 |

本轮10候选没有完整bit；未放置失败时序候选bit作为通过产物。原六例程使用源码重编或明确的历史位流，不能将以上文件混用到另一工程。

boot使用gzip仅为发布压缩，解压后必须核对67108864字节及SHA256：

```text
acd036d8de113cfd4166a5e34a71e7222429297dc1ed13de7db51828b35cd247
```

刷写属于独立板卡操作；仅下载本文件不等于硬件访问、图像或所有USB已通过。原boot备份与失败USB2共存镜像留在本机，详情见交接和boot审查。

## 历史基线产物

`historical_six/`只归档与skill冻结清单逐文件hash一致的压缩bit。原demo用户成功是历史事实，但源/位流清单不证明该实测恰对应这一份bit，也不代表新修订验收。`t3_s4b_75m_historical_stage_compress.bit`是早期75MHz阶段本机产物；其阶段10帧CRC证据与尚缺验收见t3 README，发布时未新增板测。
