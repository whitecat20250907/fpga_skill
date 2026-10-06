"""Actual RK STREAMON/OFF regression; no bit/boot/driver mutations."""
import json,mmap,os,re,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence'/('driver_cycles_'+str(time.monotonic_ns()))
OUT.mkdir()
names=[p.parent.name for p in Path('/sys/class/video4linux').glob('video*/name')
       if p.read_text().strip()=='Milianke PCIe Capture']
if len(names)!=1:raise SystemExit('Expected one capture node')
video='/dev/'+names[0]
def cma():
    return {k:int(v) for k,v in re.findall(r'^(Cma\w+):\s+(\d+)',Path('/proc/meminfo').read_text(),re.M)}
def idle():
    f=os.open('/dev/ANLOGIC-PCI0_control',os.O_RDWR|os.O_SYNC)
    try:
        with mmap.mmap(f,65536) as m:
            r={hex(o):int.from_bytes(m[o:o+4],'little') for o in (4,64,4100,4160)}
    finally:os.close(f)
    if any(r[hex(o)]&1 for o in (4,64,4100,4160)):raise RuntimeError(f'engine not idle: {r}')
    return r
start_uptime=float(Path('/proc/uptime').read_text().split()[0])
before=cma();results=[]
try:
    idle()
    for index in range(20):
        width,height=(1280,720) if index%2==0 else (1920,1080)
        prefix=OUT/f'cycle{index:02d}'
        env=dict(os.environ,CAPTURE_SAVE_MODE='none')
        t=time.monotonic()
        with prefix.with_suffix('.jsonl').open('w') as out,prefix.with_suffix('.stderr').open('w') as err:
            r=subprocess.run([str(ROOT/'capture_verify'),video,str(width),str(height),'8',str(prefix),'15'],
                             stdout=out,stderr=err,env=env,timeout=25)
        rows=[json.loads(line) for line in prefix.with_suffix('.jsonl').read_text().splitlines() if line.startswith('{')]
        frames=[r for r in rows if 'frame' in r]
        if r.returncode or len(frames)!=8 or any(row['error'] or row['bytesused']!=width*height*3 for row in frames):
            raise RuntimeError(f'cycle{index} rc{r.returncode} frames{len(frames)}')
        if any(b['sequence']!=a['sequence']+1 for a,b in zip(frames,frames[1:])):
            raise RuntimeError(f'cycle{index} sequence gap')
        row=dict(cycle=index,width=width,height=height,frames=8,seconds=time.monotonic()-t,
                 engines=idle(),cma=cma())
        results.append(row);print(json.dumps(row),flush=True)
    # The former cancelled WB worker timed out after ten seconds.
    time.sleep(12)
    log=subprocess.check_output(['dmesg'],text=True)
    new=[]
    for line in log.splitlines():
        m=re.match(r'^\[\s*([0-9.]+)\]',line)
        if m and float(m.group(1))>=start_uptime:new.append(line)
    (OUT/'kernel.log').write_text('\n'.join(new)+'\n')
    errors=[line for line in new if re.search(r'Polling timeout|not get comp desc|retaining DMA|dma_errors=[1-9]|rejected=[1-9]|DMA transfer failed',line,re.I)]
    if errors:raise RuntimeError(f'kernel faults: {errors[:6]}')
    after=cma()
    if before['CmaFree']-after['CmaFree']>1024:raise RuntimeError(f'CMA retention {before} -> {after}')
    result=dict(status='PASS',cycles=results,before=before,after=after,engines=idle(),
                observation='12s after stop without residual timeout',output=str(OUT))
except Exception as e:
    result=dict(status='FAIL',error=str(e),cycles=results,output=str(OUT))
(OUT/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
raise SystemExit(result['status']!='PASS')
