# app39实际keep发布 v3

本轮实际发布入口是 `publish_app39_recovery_v3.py kept`，已生成账本v269。它只读原source-bound状态、核844文件、实际loaded driver/八参数、新游戏factory与当前keep，不发送owner RPC。

35分钟观察实际2114.880秒/142采样通过，原keep seq9仅发一次，原RPC成功；发布v1误读value.keep_feature失败，v2将原keep更新的csv_bytes当不可变身份失败，二者均未发布。原文件/失败stderr/实际响应保留。v3使用实际RPC返回的runtime/owner_event_loop_active/automatic_restart，仍强制核当前state.keep_feature=True；runtime仅csv_bytes允许原正常增长，其余键精确相等，实际CSV文件必须不少于该字节数。3项RPC重放与5项实际runtime反例见Y/evidence/application_recovery_actual_v4的两个schema_replay JSON。

既有绑定及主程序、原Popen/EX、模型/native未修改或重启。35分钟、空场景有限量测、真人光学与旧5h51分钟故障根因是不同验收范围。全goal未完成。不要重复执行这个已消费的发布脚本或原keep RPC。
