# 启动登记失败与真实实例恢复

没有写FPGA、但驱动已重新探测的失败恢复须使用独立driver-only receipt，不能伪造JTAG重烧，也不能套用“驱动未变”的unchanged receipt。新增`restart_same51_after_reprobe_v2.py`保留原bridge的文件/环境、无owner/FD、cold模式、原owned Popen和新runtime检查，明确driver_reprobed=true/FPGA_programmed=false；10项纯测试覆盖错误CURRENT/bit/boot、缺reprobe、字符串布尔、已有owner及部分启动不二次重试。证据：模型项目`evidence/driver_only_recovery_v2_pure/result.json`。尚未实际执行生产reprobe/启停，不把该单元测试计为恢复通过。

跨多次SSH请求执行启停事务时，保留同一个远端Python进程和原Popen登记表；响应JSON只传结果，不能传回收权限。当前持久进程/file-RPC的RK实测已完成：同一PID77599连续status/read_current/status/finish，原模型72211与采集72264的出生时间/参数保持，零launch登记，read-only模式拒绝stop请求。证据：模型项目`evidence/selected51_persistent_supervisor_actual_v1/host_result.json`。这只验证只读传输和实际运行检查，未实现受控启停适配器，不等于生产恢复验收。纯事务核心的22项故障注入也只证明调用顺序、恢复门和不自动二次启动；需要实际JTAG/UART/恢复证据后才能验收硬件事务。

Popen返回后立即登记可能观察到尚未稳定的argv。若登记拒绝而主程序实际已启动，先核真实PID/出生时间/父子与会话、独有日志FD、原文件哈希及数据推进；不要把登记拒绝当作进程未启动再开一个模型。本次最初的瞬时argv未保存，后续真实argv与请求一致，不能据此断言唯一根因。

测试扩展`test_runtime_owned_launcher_v2.py`在原登记前增加有界只读就绪观察：逐字节argv相等且稳定至少10ms，再执行原OwnedLauncherReaper的完整检查；当前实现上限0.6秒。期间PID出生、父进程、PGID/SID变化、退出或持续不匹配均拒绝，保留原Popen，不poll/wait/发信号、不重试启动。回收权限仍只属于原Python父进程持有的已登记句柄，原完整session/FD守卫保持；JSON和live recovery不能伪造这一权限。

RK上11项纯检查、8项无设备集成（含真实runuser启动/退出）通过。`prepare_selected51_runtime_bridge_v2.py`已能按当前CURRENT生成并校验新capsule；实际RK导入和被动factory构造也通过，确认v2绑定、原Popen/完整守卫及零launch登记，原模型/采集实例保持。保留原v1及其失败，以上均不等于新扩展的真实主程序启停验收。实际使用前重新验证prepared引用与CURRENT，保持原模型、采集配置、驱动和权重。证据位于模型项目`evidence/owned_runtime_ready_v2_20261020`、`evidence/selected51_runtime_bridge_prepared_v2`及`evidence/ready_v2_capsule_import_actual_20261020`。

# 历史v179：app28与异常提交边界

当前CURRENT已实际发布app28，SRAM51/stage0/gate0及原RK3576 NPU保持，模型61305、采集61347。app26试验未留用：全1080表面再缩放有CPU开销，且发现writer死亡后旧valid头可能覆盖半写像素，已干净回退app25（60370/60412）。独立app27只修原子valid0→像素/元数据→release提交；app28在此基础仅改显示表面/960×540 widget，105源104继承同27。真实ARM三RGB/原模型oracle、跨进程锁、SIGSEGV后invalid拒收及GUI像素证明通过；同一原生采集提供独立processed RGB1080预览，模型仍是等3×3均值640×360。app28实际F10正常退出和重启通过，root已查看HDMI并留用，但无正脸窗口不能验收肤色、阴影、控制或整项画质。

writer-death语义：先aligned atomic valid0+全序fence，写payload和valid0元数据，最后release提交。跨进程record锁会在死亡时自动释放，不能用正常退出/旧header完整掩盖半写像素。恢复以CURRENT app28和显式app25 fallback为准。

证据：`projects/pcie_imx415_bar_contract37_20261010/evidence/goal_task_ledger_v179/actual_app28_T08_observation.json`。全部83+12+47及status保持，未扩大画质/光学/整机验收。

# 当前真人原RGB反例与app24（v172）

实际真人测试已取得：完整105帧1080p原RGB、三张RGB/PNG逐像素一致，绿点在模型缩放前存在。47运行时门限2严重吞掉面部阴影，2→1→0预览反例已归档，门限2不再作为人脸修复。当前保留诊断门限0，原app24/NHWC/CPU4/并行/原RK3576 NPU及六项关键哈希恢复，唯一PID53502/53544。恢复后8秒窗口115/115样本有效并实际调用NPU，源时间跨度内约15.51次/秒，样本年龄中位145.18ms/P95 192.27ms；非曝光FPS、个人精度或操控验收。后续窗18/151调用说明可见性变化，不能算持续真人FPS。原始CSV布尔True/False曾被观察器误按1统计，已独立纠正。 按CURRENT_CAMERA恢复诊断门限0，拒绝历史gate2。

# 原生采集重复停止、MCF1半包与实际回退

用于PCIe采集退出EOF、F10失败、native end缺失，以及推理源线程/调用者同时请求停止的场景。当前运行版本从根CURRENT_CAMERA选择，不能沿用旧脚本写死的app20。

glibc的`signal()`语义会受feature宏影响；需要持久处理时用明确的`sigaction()`。[Linux signal手册](https://man7.org/linux/man-pages/man2/signal.2.html)说明了这一区别。本机原采集源定义_POSIX_C_SOURCE，实际已部署ARM二进制的动态符号为`__sysv_signal`。app21新增唤醒路径和owner释放均可发送SIGTERM；实际默认F10退出出现MCF1不完整EOF、无end记录，必须拒绝默认验收并恢复原20，不能算正常退出或直接判内核崩溃。

app22采用两层修复：

- 原生程序用持久sigaction注册INT/TERM/HUP，并显式忽略PIPE；安装失败返回错误。handler只设置sig_atomic_t，保留原poll/ioctl/输出线程和清理规则。
- 适配器用锁保护stop_requested，调用者和资源owner最多向自己的子进程发送一次停止信号。读线程继续验证并接收完整MCF1/end；资源仍由owner释放。EOF、错误end、强杀均不得因为“正在停止”而豁免。

实际RK源码对照不打开摄像头：将完整新旧采集源码包含进独立辅助翻译单元，调用实际注册逻辑。旧版首次后恢复SIG_DFL、第二次退出码−15；新持久处理存活并正常返回0。新ARM二进制动态符号使用sigaction，不再导入__sysv_signal。此辅助测试不算V4L2板测。

适配器10项用例覆盖20个并发停止请求、原版20次信号对照、新版一次、RGB字节、正常end、半header、半payload、缺end、错误清理和强制停止。随后实际完整GUI通过照片158个原NPU有效样本、PCIe154个无人脸样本，两者均经真实X11全局F10正常退出；实际默认启动→F10→再次启动及47运行时2档完整直方图通过。

当前app22完整103文件与ARM程序已实际安装，原模型SHA保持9eeeaedd…；编译native为6e1d118f…，不是旧cda81d48…二进制。已保留app20目录和`bin/gaze_app20.sh`。恢复现用版本时核对CURRENT_CAMERA的app/native/adapter/model/launcher SHA、实际cwd/FD绑定的NPU会话、新PID与门限2；历史app20专用恢复器只能作模板，不能据它签核app22。

证据位于模型项目：`evidence/app21_default_job_v1/failure_and_recovery_review.json`、`app22_stop_frozen_v1/result.json`、`app22_GUI_job_v1/independent_review.json`、`app22_default_job_v1/independent_review.json`。复用runner保留了first21/default21_selected等旧字段名；用实际安装清单、cwd、启动文件与模型字节判断版本，不能按标签猜测。

GPU DRI回退、静态RKNN动态范围查询及NCHW→NHWC转换日志保留。照片容量、真实无人脸采集、个人标定/颜色/帧率、CSI内核修复各自验收，不互相补签。此修复属于用户态采集停止，不代表RK ISP/IOMMU内核问题已解决。
