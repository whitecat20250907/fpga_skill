# P0 工程收敛
选择离线包中的 app_v51_native_export_20261024 和 combined_app_tdm_v2 为基线；未断言它们就是当前板上运行版本。

冻结来源共 322 个文件，逐文件路径、字节数、SHA256 见 vendor/PROVENANCE.json。副本内可用 `tools/hmi verify`，对原提取目录可用 `tools/hmi verify --originals <baseline>`。原 ZIP 和 baseline 未修改。

新的 tools/hmi 提供 up/down/status/logs/verify/install/check。compat-up 未实现独立拉起：旧 relay 依赖 owner RPC/binding 与运行代号，脱离现场无法可靠恢复；命令会明确报错。原完整归档随发布保留，实际恢复入口应使用归档内原 owner 对应的当前代配置，不能猜一个旧 start.sh 就直接运行。

沿用板上现有 Python venv，避免在无 RKNN 环境的 Windows 伪造运行验证。额外带上完整游戏源码和资源；省略游戏 .maintenance 实验目录的副本，原记录仍在完整 rollback 归档中。
