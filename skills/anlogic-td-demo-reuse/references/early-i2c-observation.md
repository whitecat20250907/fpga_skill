# 早期I²C观测、SDA读值与启动窗口

配置器报事务/ACK错误而总线无START时，错误位不能证明外部传感器NACK。使用先于配置器释放的控制复位启动观测，将配置复位边沿、重新断言及armed_at_config作为事件保留；首次写入冻结后仍保留复位变化。分开采样实际SDA PAD输入、内部主机SCL和主机SDA释放意图，各走私有两级同步链。内部SCL和主机意图不等于外部引脚电压。

记录饱和边沿计数、首次START/STOP和配置释放tick，区分无活动、观测太晚、复位清空及主机意图与PAD输入不符。tick附参考时钟和复位代次；标称root25的40ns不等于电气沿或曝光时刻。遥测扩长使用新版本，严格绑定长度、CRC及序号；真实UART逐字段核对冻结值并保留旧格式保留位规则。

当前实证：[F10R2](../../../projects/hci06_early_wire_events_v2_20261018/VALIDATION_CURRENT.md)自己的完整174+9构建、正最终时序及位流通过限定复核；实板111包CRC/序号连续，armed_at_config真、config边沿1、主机低意图真、内部SCL上升37，但SDA边沿0且始终高、START/字节0、RAW/ISP0。它排除该次晚armed和配置复位清空，仍没有证明外部NACK、GTS、输出电气或具体根因。

[F12候选](../../../projects/hci06_startup_guard_20261018/README.md)只把top的XCLR低等待10us改100ms。注入首2ms PAD断开的数字模型下，旧等待复现同症状拒绝；新等待通过真实启动/core/table/外部ACK从机/UART109包36HCK、NACK2/4及复位后203写。这是有对照的假设实验，不能用来认证硅片全局启动延迟或硬件修好。其完整源必须重新做自己的门级、物理、STA、位流和实测。

物理并行复制网名不同时，探针来源可严格追同一实际顶层PAD、TSMUX、未寄存TS、数据0及首D共同终端；不得把终端连接证明扩大为PAD布尔、电气或时钟波形等价。所有试验结束均按实际精确47 JTAG→PCIe重绑→app20 STREAMON→运行时2档及完整2073600像素hist核对恢复，并更新CURRENT_CAMERA的新owner证据。原始失败保留，Flash37保持。
