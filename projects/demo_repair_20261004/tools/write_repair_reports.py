from pathlib import Path
import hashlib
import json
import subprocess
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SKILL = Path('C:/Users/zjh13/.codex/skills/anlogic-td-demo-reuse')
HW = Path('E:/qianrufpga/03_MLK_AFH03_AFC03/02_hardware/HW_MLK_AFH03_20250402_AFC03_20250402_RK+AL/HW_MLK_AFH03_20250402_AFC03_20250402_RK+AL')
manual = HW / '01_硬件手册/MLK-AFC03核心板硬件使用手册.pdf'
baseline = subprocess.run(['python', str(SKILL/'scripts/td_reuse.py'), 'verify', '--examples', 'E:/qianrufpga/fpga-lab/examples'], capture_output=True, text=True, encoding='utf-8', errors='replace')
if baseline.returncode:
    raise RuntimeError('Original baseline verification failed: '+baseline.stdout+baseline.stderr)
(ROOT/'evidence').mkdir(exist_ok=True)
(ROOT/'evidence/baseline_verify.json').write_text(baseline.stdout, encoding='utf-8')

common = '''
## 复现命令与构建边界

以下 ModelSim 命令在各 clone 的 `tb` 目录执行；各脚本遇到编译错误、断言失败或超时返回1，只有 test_done 为1才返回0。没有把进程启动等同通过。

完整 TD 构建入口已从当前 .al 准备，但**本修复 clone 尚未执行 TD、未生成已验收 bit，也未上板**：

```powershell
& 'E:/qianrufpga/TD/bin/td_commands_prompt.exe' 'PROJECT/build_direct.tcl'
```

也保留 `build.tcl` 的原 managed run 流程。direct 全流程从当前源重新 elaborate，在 `reports/direct_build_时间_PID/` 输出独立新产物。不能复用原 examples 的旧 bit 当成此次修复 bit。01 通用模板的实际 TD 通过仅证明模板可执行，不等于03/04此次修复已编译。

源文件保持厂商原字节编码和版权；没有重新生成 IP、修改许可证、引脚或时序约束。`audit.json` 仅证明活动 source/IP/直接引脚检查通过，不证明 Verilog elaboration、IP 内约束、电气接口或时序签核。新 `tb` 未注册为可综合工程源。原六例程基线 verify 六项 missing/added/changed 全为空，证据在上级 evidence/baseline_verify.json。
'''

reports = {
 '03_iic_rtc': ('03 RTC / UART 独立修复验证', ['uisrc/03_ip/uart_tx_block.v', 'uisrc/01_rtl/rtc_clock_ds1337.v'], '''
## 已修改的行为

- `uart_tx_block.v` 的旧条件 index<TX_BYTES 导致多发送一个索引越界字节；改成 index<TX_BYTES-1，并使用 max(1,clog2(TX_BYTES)) 索引宽度。请求接受时保存整个消息，发送过程中外部缓冲变化不改变本包。
- RTC 旧状态3在请求读之前保存 rd_data，而周期 t_en 同时启动UART，打印的是前次读值。现在必须先观察本次读 busy 上升，再等待其下降，保存完成的 rd_data 并产生报告脉冲。UART下一拍取到新时间的完整快照。
- 保留初始化12:00:00、每1000ms读取/报告、DS1337地址0xD0、起始寄存器0及原 I2C 实现（源码旧“500ms”注释与真实SYSCLKHZ-1计数不符，以参数/逻辑为准）。报告为 `HH-MM-SS\\r\\n`，精确10字节。UART核心本身和引脚未变。

## 数字测试：实际 ModelSim 10.5

```powershell
Push-Location 'PROJECT/tb'
try {
  & 'D:/Modelsim/soft/win64/vsim.exe' -c -do 'do run_uart.do'
  & 'D:/Modelsim/soft/win64/vsim.exe' -c -do 'do run_rtc.do'
} finally { Pop-Location }
```

两进程均 exit0，编译与仿真0 errors / 0 warnings：

| 测试 | 真实 RTL / 模型范围 | 判据与结果 |
|---|---|---|
| UART block | 真实 ui_uart_tx_block + ui_uart_tx；按串口起始位/8数据位/停止位解码 | TX_BYTES=1/10/16，各2包，共54字节；精确数量/顺序/内容，运行中外部buffer变化不改变包；发送后等待并断言无第N+1字节，全部PASS |
| RTC poll | 真实rtc_clock_ds1337 + 两个UART模块；仅 ui_i2c 为事务行为模型 | 核对地址/寄存器/5字节初始化/2写3读、20,000clk读busy；两次BCD123456/123457完成后收到精确20字节，无未完成读提前UART及旧值，PASS |

日志：`evidence/uart_block.log`、`evidence/rtc_poll.log`；脚本含1ms/10ms超时。RTC测试缩放SYSCLKHZ/baud和时间，验证顺序，不测晶振误差。I2C模型没有证明SCL/SDA物理时序、NACK/异常设备恢复或实际RTC走时。UART模块仍没有向用户导出busy；本例1000ms周期远长于10字节115200bps传输，但一般复用必须保证请求间隔/排队。

## 下次实机验收

TD完整编译/布局布线与约束覆盖；当前新bit串口115200、8N1，每报告10字节；上电初始化、连续时间递增和RTC真实完成读；不要因数字stub通过把I2C硬件标为通过。
'''),
 '04_ddr3_axi_fdma_test': ('04 DDR3 / FDMA 独立修复验证', ['uisrc/01_rtl/system_top.v', 'uisrc/01_rtl/fdma_test.v'], '''
## 已修改的行为与容量证据

- 核心板硬件使用手册PDF第12页写FPGA侧1片GigaDevice DDR3L、256MB、16bit（同时注明型号/大小随实物变化）。本例真实 ui_ddr.ipc 为2Gb/x16；ui_ddr.sv 为ROW14/COL10/BANK3/BG0/CS1、MC_DATA128。容量2^(14+10+3)×2=268435456字节=256MiB。
- DDR IP 的 AXI_ADDR_WIDTH=MC_ADDR_WIDTH+clog2(MC_DATA_WIDTH/8)-3=27+4-3=28，是**字节地址**。旧top写APP_ADDR_WIDTH+3=30并请求2GiB，使地址截断/物理alias发生；现 top 为APP_ADDR_WIDTH+clog2(DRAM_BYTE_NUM)=28，测试范围256MiB、offset0。IP/颗粒时序参数未改变。换板/BOM须重新核实，不能把本容量写死用于任意板。
- 每FDMA长度1024个128bit beat，地址步长16KiB；相对地址从0到256MiB-16KiB，完成最后一次读后回0，不再多测一burst。一般范围若非整burst会向下取完整burst；offset+请求范围超容量/地址跨度、零有效范围等报config_error并禁止请求。
- 旧数据各16bit lane重复并仅比低16bit。现在全128bit比较；模式含beat序号、burst字节地址折叠tag、每lane不同常数，能够检测lane交换及高位错误。比较数据与期望在同一接受拍锁存；错误粘滞至复位，累计错误、完成burst、完成轮数。
- 保留现有CWC13探针：probe5仍低16bit示例值，probe12现在粘滞test_error。新增三个32bit计数与config_error接口暂在顶层明确空连接，不宣称它们在最终硬件可见；需观察计数时更新CWC并重编译。

## 数字测试：实际 ModelSim 10.5

```powershell
Push-Location 'PROJECT/tb'
try { & 'D:/Modelsim/soft/win64/vsim.exe' -c -do 'do run_fdma.do' }
finally { Pop-Location }
```

进程exit0；编译与仿真0 errors / 0 warnings。真实 `ui_fdma_test`，ChipWatcher仅空接口壳；FDMA用户接口以事务driver+scoreboard内存模型驱动，**没有例化真实uiFDMA、DDR控制器/PHY或物理DDR**。

- 128bit、4beat/burst，测试容量256字节、offset16、请求200字节：只发地址16/80/144并回16，覆盖非整burst尾部与相对offset。
- 首6burst干净通过；后续分别注入bit0、15、16、63、127单bit错误；12burst/4轮，错误计数精确5，后续干净数据不清除粘滞错误。
- 有效信号间插入空拍，读写请求握手/连续完成；范围越容量的第二实例config_error=1、绝不产生流量。
- 复位后错误/计数全清、地址重新从offset开始；1ms超时保证不能假通过。

日志 `evidence/fdma_checker.log`；容量来源摘录 `evidence/ddr_capacity_sources.txt`。小范围数字测试证明地址管理和checker逻辑，**不证明真实256MiB全部硬件读写、DDR校准、电气时序或真实AXI wrapper的错误响应处理**。本pattern+顺序写后读也不是完整March/保留/刷新压力测试，不能称DDR全面诊断。

## 下次实机验收

TD检查真实IP 28bit地址连接、无截断、setup/hold和DDR约束；新bit观察init_done，probe12始终0且读写计数实际推进；至少一整轮256MiB、跨高地址和重新复位。新计数若需硬件验收，接入新的CWC/可读寄存器并匹配新debugbit。错误为0但未观测读写进度，不能认定DDR通过。
''')
}
for name,(title,changed,body) in reports.items():
 project=ROOT/name
 proc=subprocess.run(['python',str(SKILL/'scripts/td_reuse.py'),'audit','--project',str(project/'fpga_prj.al')],capture_output=True,text=True,encoding='utf-8',errors='replace')
 if proc.returncode: raise RuntimeError(proc.stdout+proc.stderr)
 audit=json.loads(proc.stdout)
 (project/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
 (project/'reports').mkdir(exist_ok=True)
 hashes={rel:hashlib.sha256((project/rel).read_bytes()).hexdigest() for rel in changed}
 manifest_path=project/'clone_manifest.json'
 manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
 manifest['repair_date']='2026-10-04'
 manifest['repair_source_hashes']=hashes
 manifest['repair_status']='Self-checking ModelSim tests passed; target TD build and board verification pending'
 manifest['changes'] += [f'Repaired {rel}' for rel in changed if f'Repaired {rel}' not in manifest['changes']]
 manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 table='\n'.join(f'| `{rel}` | `{sha}` |' for rel,sha in hashes.items())
 content=(f'# {title}\n\n2026-10-04；PH1A90SEG324-2。原例程历史上板成功不替代本修复验收。\n'+body+common+'\n## 修复源 SHA-256\n\n| 文件 | SHA-256 |\n|---|---|\n'+table+'\n').replace('PROJECT',project.as_posix())
 (project/'reports/validation.md').write_text(content,encoding='utf-8')
 (project/'README.md').write_text(f'# {title}\n\n独立修复工程，数字自检已通过，TD/上板待验证。完整修改、命令、模型边界及哈希见 [验证报告]({project.as_posix()}/reports/validation.md)。\n',encoding='utf-8')

ddr=ROOT/'04_ddr3_axi_fdma_test'
capacity='Hardware manual: '+manual.as_posix()+'; PDF page12\n'+(PdfReader(manual).pages[11].extract_text() or '')+'\n\nIPC: '+(ddr/'uisrc/03_ip/ui_ddr/ui_ddr.ipc').read_text(encoding='utf-8')
(ddr/'evidence/ddr_capacity_sources.txt').write_text(capacity,encoding='utf-8')
index='''# 原03/04例程独立修复

2026-10-04：基于skill正式baseline校验后clone，原六examples哈希均不变。03修精确UART包长/快照和RTC读完成后报告；04修128bit检查、28bit字节地址和256MiB边界。三项ModelSim实际自检通过；两目标未TD构建、未新上板，不能写成“所有例程已修好”。

| 工程 | 数字证据 | 下一关 |
|---|---|---|
| [03 RTC](03_iic_rtc/reports/validation.md) | UART54字节、RTC20字节，无额外/旧值 | TD、新bit、实际I2C/RTC走时 |
| [04 DDR](04_ddr3_axi_fdma_test/reports/validation.md) | 12burst/4轮，5个全宽单bit故障、边界/复位/非法配置 | TD、新bit、真实DDR至少完整一轮 |

保留原约束/IP和managed build.tcl；提供独立build_direct.tcl，模板实际TD能力已在UART01验证，不能冒充03/04编译证据。06 CSI→DSI需完整receiver/ISP/ready/constraint迁移，见PCIe工程 reports/demo_reuse_impact.md；此次没有半搬06 PHY。
'''
(ROOT/'README.md').write_text(index,encoding='utf-8')
print('Reports and repaired manifests written. Original baseline unchanged. TD/board pending.')
