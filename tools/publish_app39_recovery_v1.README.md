# app39 恢复状态发布器

本工具仅由根会话执行。编写阶段没有执行发布、SSH、owner RPC、模型启动/停止或 Git 暂存。入口为 `publish_app39_recovery_v1.py running` 和 `publish_app39_recovery_v1.py kept`。

`running` 只接受根 CURRENT 仍指向 WBv2 本轮失败、冻结的新 binding SHA `1bbaa07a…`、config SHA `bdc62741…`、844 源 pins、新 owner233963/start66678019，以及原实际退役、全静默、同9e82/f9保留、驱动恢复、面板、三组张量和六幅整帧逐字节通过记录。它通过原完整 control 再读一次实机 status、全部文件 SHA、新 d740 游戏 factory 和已加载 WBv2 build-id/原参数；不会发 RPC。新 selection 保留旧控制字段及历史 selection。

`kept` 必须先有本工具的 running 指针；本代 `longrun_35min_v3/result.json` 必须完整通过至少2100秒且 binding/boot/capture一致，原 `keep_feature_running` RPC 必须真正成功，新的只读核验必须仍为 `FEATURE_KEEP_RUNNING`。工具不隐式 keep，也不修改冻结 binding。

发布前比较 GOAL、CURRENT、调度表和估时表的原 bytes，按最新完整账本增量生成下一版。每个共享文件以再次比较后的原子替换发布；若并发变动则保留新账本及 `publication_prepared.json`/`applied_N.json` 日志并拒绝继续，不覆盖另一发布者。四文件不是文件系统级的联合原子事务；发生中途冲突时由根会话根据日志处理，不能重复运行同阶段覆盖证据。最后运行 `refresh_pending_tasks.py` 同步两份待办视图。

T02/U04仍列开发：新启动或35分钟通过不能解释此前5小时51分钟 DMA 故障。U01/U02/U03/U05保留真人待实测。首次 running 将实际友城目标被 DEMO_CITY 覆盖的问题移回 G03 开发；kept 保留之后可能已发布的游戏修复进度，不重复重开 G03。两阶段均不改 G02 的尚未冻结实测状态。

新 d740 原生单人/双人战斗收据与五动作 factory 接线成立，`newbridge_bound=true`；`new_game_revision_acceptance=false` 保持为整体联动尚未验收的兼容字段，独立原生战斗另用 `game_independent_battle_accepted=true`。真人游戏控制、光学、标定、有效NPU时延及完整 goal 全部保持未验收。旧 cleanup110、观察缺口和错误原件不覆盖。

此工具的编译和本机保存 RPC/schema 检查不能代替根会话执行时的实机核验；不要把“工具写完”计为新运行态已发布。
