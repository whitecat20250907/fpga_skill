#!/usr/bin/env bash
# RK regression only: never patches/flashes boot or downloads FPGA.
# Run after loading the repaired bit and running deploy/pcie_setup.sh.
# CAPTURE_SAVE_MODE=none (default) or bounded; all is deliberately refused.
set -euo pipefail
TASK_ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
if [[ $# -gt 2 ]]; then
    echo "usage: $0 [task_root] [new_output_dir]" >&2
    exit 2
fi
[[ $# -lt 1 ]] || TASK_ROOT=$1
TASK_OUTPUT=''
[[ $# -lt 2 ]] || TASK_OUTPUT=$2
exec python3 - "$TASK_ROOT" "$TASK_OUTPUT" <<'PY_REGRESSION'
import hashlib,json,math,mmap,os,re,signal,struct,subprocess,sys,time,traceback
from pathlib import Path

ROOT=Path(sys.argv[1]).resolve()
OUT=Path(sys.argv[2]).resolve() if sys.argv[2] else ROOT/'evidence'/('hardware_regression_'+str(time.monotonic_ns()))
OUT.mkdir(parents=True,exist_ok=False)
BIN=OUT/'bin';BIN.mkdir()
PHASES=[]
SCRATCH=[o for o in range(0x300,0x400,4) if o!=0x328]
ERROR_KEYS=('crc_errors','ecc_errors','wc_errors','timeout_errors','fifo_overflows')
SUPPORTED_VERSIONS=(0x56440401,0x56440501,0x56440601,0x56440701)
CLOCK27_VERSIONS=SUPPORTED_VERSIONS[1:]
CAM27_EXPECTED_EDGES=270000
CAM27_TOLERANCE_EDGES=544 # 0.2% plus four CDC edge counts, 10ms window
HS_EXPECTED_EDGES=11137500 # 111.375MHz byte clock, 100ms snapshot period
HS_TOLERANCE_EDGES=22275 # 0.2%, not the old build04's 49.5MHz clock
MAX_SNAPSHOT_AGE_S=.25
MAX_COLLECTOR_GAP_S=.35
class Failure(RuntimeError): pass
def dump(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
def event(name,**fields):
    row=dict(event=name,**fields)
    with (OUT/'progress.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    print(json.dumps(row),flush=True)
def integer(name,default,minimum):
    v=int(os.environ.get(name,str(default)))
    if v<minimum:raise Failure(f'{name} must be >= {minimum}, got {v}')
    return v
def json_lines(path):
    rows=[]
    for line in Path(path).read_text(errors='replace').splitlines():
        if line.startswith('{'):rows.append(json.loads(line))
    return rows
def run(args,path,timeout=30):
    with Path(path).open('w') as f:
        r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
    if r.returncode:raise Failure(f'command failed rc={r.returncode}: {args}; log={path}')
def text_cmd(args):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=20)
    if p.returncode:raise Failure(f'{args}: {p.stderr.strip()}')
    return p.stdout
def meminfo():
    text=Path('/proc/meminfo').read_text()
    data={}
    for key in ('CmaTotal','CmaFree'):
        m=re.search(r'^'+key+r':\s+(\d+)\s+kB$',text,re.M)
        if not m:raise Failure(f'missing {key} in /proc/meminfo')
        data[key+'_kB']=int(m.group(1))
    return data,text
def endpoint():
    candidates=[]
    for d in Path('/sys/bus/pci/devices').glob('*'):
        if not (d/'vendor').exists() or not (d/'device').exists():continue
        if (d/'vendor').read_text().strip()=='0x1edb' and (d/'device').read_text().strip()=='0xabcd':
            candidates.append(d)
    if len(candidates)!=1:raise Failure(f'expected one 1edb:abcd endpoint, found {len(candidates)}')
    return candidates[0]
def video_node():
    candidates=[]
    for name in Path('/sys/class/video4linux').glob('video*/name'):
        if name.read_text().strip()=='Milianke PCIe Capture':
            candidates.append(Path('/dev')/name.parent.name)
    if len(candidates)!=1:raise Failure(f'expected one Milianke video node, found {len(candidates)}')
    return candidates[0]
def bar_read(offsets):
    fd=os.open(str(BAR),os.O_RDWR|os.O_SYNC)
    try:
        with mmap.mmap(fd,4096) as m:return {o:struct.unpack_from('<I',m,o)[0] for o in offsets}
    finally:os.close(fd)
def scratch_restore(values):
    # Only tested register RAM; excludes every low-byte 0x28 IRQ alias.
    fd=os.open(str(BAR),os.O_RDWR|os.O_SYNC)
    try:
        with mmap.mmap(fd,4096) as m:
            for offset,value in values.items():struct.pack_into('<I',m,offset,value)
            struct.unpack_from('<I',m,SCRATCH[0])
    finally:os.close(fd)
def aer_snapshot(dev,directory,label,required):
    bdf=dev.name
    text=text_cmd(['lspci','-vv','-s',bdf])
    (directory/(label+'_lspci_'+bdf.replace(':','_')+'.txt')).write_text(text)
    lines=[s.strip() for s in text.splitlines() if re.search(r'\b(?:UESta|CESta):',s)]
    flags=[flag for line in lines for flag in re.findall(r'\b[A-Za-z][A-Za-z0-9_]*\+',line)]
    counters={}
    for p in dev.glob('aer_dev_*'):
        value=p.read_text()
        (directory/(label+'_'+bdf.replace(':','_')+'_'+p.name+'.txt')).write_text(value)
        for line in value.splitlines():
            fields=line.rsplit(None,1)
            if len(fields)==2 and fields[1].isdigit():counters[p.name+':'+fields[0]]=int(fields[1])
    available=any('UESta:' in s for s in lines) and any('CESta:' in s for s in lines)
    if required and not available:raise Failure(f'AER UESta/CESta unavailable for {bdf}; cannot mark checked')
    return dict(bdf=bdf,status_available=available,status_lines=lines,asserted_flags=flags,counters=counters)
def snapshot(directory,label):
    cma,text=meminfo()
    (directory/(label+'_meminfo.txt')).write_text(text)
    kernel=text_cmd(['dmesg','--color=never'])
    (directory/(label+'_dmesg.txt')).write_text(kernel)
    state=dict(cma=cma,aer_endpoint=aer_snapshot(EP,directory,label,True))
    if ROOTPORT:state['aer_rootport']=aer_snapshot(ROOTPORT,directory,label,False)
    dump(directory/(label+'_state.json'),state)
    return state,kernel
def check_state(before,after):
    reasons=[]
    if after['cma']['CmaTotal_kB']<65536:reasons.append('CMA total below 64 MiB')
    loss=before['cma']['CmaFree_kB']-after['cma']['CmaFree_kB']
    if loss>LEAK_KB:reasons.append(f'CMA free loss {loss}kB exceeds allowed {LEAK_KB}kB')
    aer_checks={}
    for key in ('aer_endpoint','aer_rootport'):
        if key not in before:continue
        b,a=before[key],after[key]
        increased={k:a['counters'].get(k,0)-v for k,v in b['counters'].items() if a['counters'].get(k,0)>v}
        if b['asserted_flags'] or a['asserted_flags']:reasons.append(f'{key} has asserted AER status flags')
        if increased:reasons.append(f'{key} counters increased: {increased}')
        aer_checks[key]=dict(status_available=a['status_available'],counter_increases=increased,
                              before_flags=b['asserted_flags'],after_flags=a['asserted_flags'])
    return dict(cma_free_loss_kB=loss,allowed_loss_kB=LEAK_KB,aer=aer_checks,reasons=reasons)
def stop_child(p,timeout=15):
    if p is None:return None
    if p.poll() is None:
        p.terminate()
        try:return p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:raise Failure('child did not exit even after SIGKILL; kernel/device may be stuck')
            return -signal.SIGKILL
    return p.returncode
def csi_once(directory,label):
    run([sys.executable,str(ROOT/'tools/read_csi_stats.py'),'--bar',str(BAR),
         '--seconds','1.2','--interval','.1'],directory/(label+'_csi.jsonl'),timeout=10)
    rows=json_lines(directory/(label+'_csi.jsonl'))
    if not rows:raise Failure(f'{label} CSI snapshot file has no rows')
    return rows
def validate_camera_status(status):
    # These are quasi-static/qualified states, not instantaneous RAW valid or SOF.
    best_len=(status>>6)&0x3f
    if not status&1:raise Failure('active camera I2C configuration is not done')
    if not status&2:raise Failure('active camera HS byte clock presence is not qualified')
    if status&8:raise Failure('active camera I2C bus error is asserted')
    if not status&16:raise Failure('active camera calibration is not done')
    if best_len==0:raise Failure('active camera calibration has no passing eye window (best_len=0)')
    return dict(status=hex(status),calibration_done=True,best_len=best_len)
def active_calibration_sample():
    # STREAMOFF may occur while capture_verify is closing. Bookend with CTRL so
    # a reset/stopped camera is never required to retain calibration diagnostics.
    before=bar_read([0x60,0x84])
    after=bar_read([0x60])
    if not before[0x60]&1 or not after[0x60]&1:return None
    return validate_camera_status(before[0x84])
def validate_capture(rows,count,width,height):
    if len(rows)!=count:raise Failure(f'capture rows={len(rows)}, expected={count}')
    if [r['frame'] for r in rows]!=list(range(count)):raise Failure('capture frame indices are not complete')
    if any(r['bytesused']!=width*height*3 or r['expected']!=width*height*3 or r['error'] for r in rows):
        raise Failure('capture byte length or V4L2 ERROR flag mismatch')
    if any(b['sequence']!=a['sequence']+1 for a,b in zip(rows,rows[1:])):raise Failure('V4L2 sequence gap')
    duration=rows[-1]['seconds']-rows[0]['seconds']
    if duration<=0:raise Failure('capture duration is not positive')
    return dict(frames=len(rows),frame_bytes=width*height*3,
                measured_fps=(len(rows)-1)/duration,
                worst_green_fraction=max(r['green_fraction'] for r in rows),
                worst_purple_fraction=max(r['purple_fraction'] for r in rows),
                color_acceptance='requires_visual_or_golden_reference_review')
def validate_csi(rows,first_frame_s,last_frame_s,collector_lead_s,bit_version=0x56440401):
    if bit_version not in SUPPORTED_VERSIONS:raise Failure(f'unsupported CSI validation version {bit_version:08x}')
    if len(rows)<2:raise Failure('continuous CSI collector has fewer than two samples')
    for r in rows:
        try:version=int(r['bit_version'],0)
        except (KeyError,TypeError,ValueError):raise Failure('CSI sample lacks a valid bit_version')
        if version!=bit_version:raise Failure('CSI collector bit version differs from suite manifest')
        if not math.isfinite(r['seconds']):raise Failure('CSI collector timestamp is not finite')
    if any(b['seconds']<=a['seconds'] for a,b in zip(rows,rows[1:])):
        raise Failure('CSI collector timestamps did not strictly advance')
    # STREAMON soft-reset legitimately starts a new snapshot/counter epoch.
    # Retain the last reset before first valid captured data; reject later resets.
    boundary=first_frame_s+collector_lead_s+.05
    end_boundary=last_frame_s+collector_lead_s
    cut=0;resets=[]
    for i,(a,b) in enumerate(zip(rows,rows[1:]),1):
        if b['seconds']<=end_boundary and b['snapshot_seq']<a['snapshot_seq']:
            resets.append(dict(index=i,seconds=b['seconds']))
            if b['seconds']<=boundary:cut=i
            else:raise Failure(f'unexpected CSI snapshot reset after captured data: {resets[-1]}')
    epoch=rows[cut:]
    # Require measured progress only before the last delivered-frame timestamp.
    # A small startup allowance avoids the first in-flight snapshot. The reader
    # continues after STREAMOFF for evidence, but stopped/reset counters and
    # their ages/errors/frequencies are never active-capture acceptance inputs.
    active=[r for r in epoch if boundary<=r['seconds']<=end_boundary and r['snapshot_seq']>0]
    if len({r['snapshot_seq'] for r in active})<2:raise Failure('CSI snapshot never progressed during capture')
    if any(not math.isfinite(r['snapshot_age']) or not 0<=r['snapshot_age']<=MAX_SNAPSHOT_AGE_S for r in active):
        raise Failure('CSI coherent snapshot became stale during active capture')
    if any(b['seconds']-a['seconds']>MAX_COLLECTOR_GAP_S for a,b in zip(active,active[1:])):
        raise Failure('CSI collector has a coverage gap during active capture')
    raw=max(r['raw_packets'] for r in active)
    if raw<=0:raise Failure('CSI raw-good packet count stayed zero despite V4L2 output')
    if any(b['raw_packets']<a['raw_packets'] for a,b in zip(active,active[1:])):
        raise Failure('CSI RAW counter decreased within the active capture window')
    raw_delta=active[-1]['raw_packets']-active[0]['raw_packets']
    if raw_delta<=0:raise Failure('CSI RAW counter did not increase during delivered capture frames')
    hs=[r['hs_cycles_per_100ms'] for r in active]
    if any(v<=0 for v in hs):raise Failure('HS byte clock sampling stayed zero in an active snapshot')
    errors={k:max(r[k] for r in active) for k in ERROR_KEYS}
    if any(errors.values()):raise Failure(f'CSI errors in active capture window: {errors}')
    result=dict(samples=len(rows),epoch_start_index=cut,expected_start_resets=resets,
                raw_good_packets=raw,raw_good_packets_in_active_window=raw_delta,errors=errors,
                distinct_active_snapshots=len({r['snapshot_seq'] for r in active}),
                max_snapshot_age_s=max(r['snapshot_age'] for r in active),
                min_hs_cycles_per_100ms=min(hs),max_hs_cycles_per_100ms=max(hs),
                bit_version=hex(bit_version))
    if bit_version in CLOCK27_VERSIONS:
        if any(abs(v-HS_EXPECTED_EDGES)>HS_TOLERANCE_EDGES for v in hs):
            raise Failure(f'HS byte clock is outside 111.375MHz +/-0.2%: {min(hs)}..{max(hs)} edges/100ms')
        for r in active:
            required=('cam27_window','cam27_edges_per_10ms','cam27_status','cam27_locked',
                      'cam27_frequency_ok','cam_xclr','cam_config_ready')
            if any(k not in r for k in required):raise Failure('27MHz diagnostic fields missing from active CSI sample')
            try:status=int(r['cam27_status'],0)
            except (TypeError,ValueError):raise Failure('invalid 27MHz diagnostic status')
            if status&0x1f!=0x1f or not all(r[k] is True for k in
                    ('cam27_locked','cam27_frequency_ok','cam_xclr','cam_config_ready')):
                raise Failure('active camera 27MHz lock/frequency/window/XCLR/config-ready is not qualified')
            if not 1<=r['cam27_window']<=0xffffffff:raise Failure('27MHz measurement window is not valid')
            if abs(r['cam27_edges_per_10ms']-CAM27_EXPECTED_EDGES)>CAM27_TOLERANCE_EDGES:
                raise Failure(f'27MHz edges outside 270000 +/-544: {r["cam27_edges_per_10ms"]}')
        # A cached good edge count and status do not prove the clock is alive.
        # The window counter must progress at the reference's real 10ms rate.
        # Two windows cover quantisation/read skew; 0.2% covers ref tolerance.
        def window_delta(a,b):
            dt=b['seconds']-a['seconds'];expected=dt*100;tolerance=2+expected*.002
            delta=(b['cam27_window']-a['cam27_window'])&0xffffffff
            if delta==0 or not max(1,math.floor(expected-tolerance))<=delta<=math.ceil(expected+tolerance):
                raise Failure(f'27MHz window did not progress at 10ms rate: delta={delta}, elapsed={dt:.6f}s')
            return delta
        for a,b in zip(active,active[1:]):window_delta(a,b)
        span_windows=window_delta(active[0],active[-1])
        edges=[r['cam27_edges_per_10ms'] for r in active]
        result['camera_clock27']=dict(active_samples=len(active),window_delta=span_windows,
            min_edges_per_10ms=min(edges),max_edges_per_10ms=max(edges),
            expected_edges_per_10ms=CAM27_EXPECTED_EDGES,tolerance_edges=CAM27_TOLERANCE_EDGES,
            expected_hs_edges_per_100ms=HS_EXPECTED_EDGES,hs_tolerance_edges=HS_TOLERANCE_EDGES,
            lock_frequency_xclr_config_ready=True)
    else:
        result['camera_clock27']=dict(required=False,reason='build04 has no 27MHz monitor registers; legacy HS nonzero check only')
    return result
def validate_driver(before,after,count):
    old=set(before.splitlines())
    new=[line for line in after.splitlines() if line not in old]
    fatal=[line for line in new if re.search(r'BUG:|Oops:|WARNING:|Unable to handle kernel|Call trace:',line)]
    if fatal:raise Failure('new kernel warning/fault during capture: '+ '; '.join(fatal))
    stops=[]
    for line in new:
        m=re.search(r'DMA thread stopped: delivered=(\d+) rejected=(\d+) dma_errors=(\d+)',line)
        if m:stops.append(tuple(map(int,m.groups())))
    if not stops:raise Failure('no fresh driver delivered/rejected/dma_errors stop record')
    delivered,rejected,errors=stops[-1]
    if delivered<count or rejected or errors:
        raise Failure(f'driver delivered={delivered} rejected={rejected} dma_errors={errors}')
    return dict(delivered=delivered,rejected=rejected,dma_errors=errors)
def phase(name,width,height,count,save_mode,pressure):
    directory=OUT/name;directory.mkdir()
    summary=dict(name=name,width=width,height=height,requested_frames=count,save_mode=save_mode,
                 result='running',rgb_visual_status='not_automatically_accepted')
    PHASES.append(summary)
    dump(directory/'summary.json',summary)
    event('phase_start',**{k:summary[k] for k in ('name','width','height','requested_frames','save_mode')})
    cap=diag=bar=None
    handles=[]
    pressure_saved=None
    before=kernel_before=None
    collector_lead=0
    try:
        before,kernel_before=snapshot(directory,'before')
        csi_once(directory,'before')
        diag_out=(directory/'during_csi.jsonl').open('w');diag_err=(directory/'during_csi.err').open('w')
        handles.extend([diag_out,diag_err])
        diag_started=time.monotonic()
        diag=subprocess.Popen([sys.executable,str(ROOT/'tools/read_csi_stats.py'),'--bar',str(BAR),
                               '--seconds',str(TIMEOUT+20),'--interval','.1'],stdout=diag_out,stderr=diag_err)
        cap_out=(directory/'capture.jsonl').open('w');cap_err=(directory/'capture.err').open('w')
        handles.extend([cap_out,cap_err])
        environment=os.environ.copy();environment['CAPTURE_SAVE_MODE']=save_mode
        cap_started=time.monotonic();collector_lead=cap_started-diag_started
        cap=subprocess.Popen([str(BIN/'capture_verify'),str(VIDEO),str(width),str(height),str(count),
                              str(directory/'camera'),str(TIMEOUT)],stdout=cap_out,stderr=cap_err,env=environment)
        pressure_started=False;seen=0;last_progress=0;active_registers_checked=False;pressure_finished_during_capture=False
        while cap.poll() is None:
            elapsed=time.monotonic()-cap_started
            if elapsed>TIMEOUT+15:raise Failure('capture process exceeded its own deadline plus cleanup grace')
            seen=sum(1 for line in (directory/'capture.jsonl').read_text(errors='replace').splitlines() if line.startswith('{'))
            if seen and not active_registers_checked:
                active=bar_read([0x44,0x48,0x60,0x64,0x84,0x90,0xa4])
                expected_mode=2 if height==720 else 0
                if (active[0x90]&3)!=expected_mode or active[0x44]!=width or active[0x48]!=height or active[0x64]!=width*height*3:
                    raise Failure(f'S_FMT and FPGA active mode/geometry disagree: {active}')
                if not active[0x60]&1 or active[0xa4]&1:
                    raise Failure(f'camera/mux not active in expected camera mode: {active}')
                summary['active_calibration_first']=validate_camera_status(active[0x84])
                summary['active_registers']={hex(k):hex(v) for k,v in active.items()}
                active_registers_checked=True
            if seen and active_registers_checked:
                calibration=active_calibration_sample()
                if calibration is not None:
                    calibration['capture_elapsed_s']=elapsed
                    with (directory/'active_calibration.jsonl').open('a') as f:
                        f.write(json.dumps(calibration)+'\n')
                    summary['active_calibration_samples']=summary.get('active_calibration_samples',0)+1
                    summary['minimum_best_len']=min(summary.get('minimum_best_len',63),calibration['best_len'])
            if pressure and not pressure_started and seen>=10:
                pressure_saved=bar_read(SCRATCH)
                pressure_started=True
                summary['pressure_started_after_frames']=seen
                summary['pressure_started_capture_elapsed_s']=elapsed
                bar_out=(directory/'bar_pressure.json').open('w');bar_err=(directory/'bar_pressure.err').open('w')
                handles.extend([bar_out,bar_err])
                bar=subprocess.Popen([str(BIN/'bar_roundtrip'),str(BAR),str(BAR_ROUNDS)],stdout=bar_out,stderr=bar_err)
            if bar is not None and not pressure_finished_during_capture and bar.poll() is not None:
                pressure_finished_during_capture=True
                summary['pressure_finished_capture_elapsed_s']=elapsed
                summary['pressure_finished_after_frames']=seen
            if elapsed-last_progress>=10:
                event('capture_progress',phase=name,frames_seen=seen,elapsed_s=round(elapsed,2));last_progress=elapsed
            time.sleep(.1)
        cap_rc=cap.returncode;cap_out.close();cap_err.close()
        if not active_registers_checked:raise Failure('no capture overlapped an active mode/geometry register check')
        if pressure and not pressure_started:raise Failure('BAR pressure never overlapped a capture with >=10 real frames')
        if pressure and not pressure_finished_during_capture:
            raise Failure('the full BAR pressure run was not observed to finish while camera capture was active')
        if bar is not None:
            try:bar_rc=bar.wait(timeout=60)
            except subprocess.TimeoutExpired:raise Failure('BAR pressure did not finish')
            bar_out.close();bar_err.close()
            if bar_rc:raise Failure(f'BAR pressure rc={bar_rc}')
            result=json_lines(directory/'bar_pressure.json')
            if len(result)!=1 or result[0].get('rounds')!=BAR_ROUNDS or result[0].get('words')!=BAR_ROUNDS*63 or result[0].get('errors')!=0:
                raise Failure(f'incomplete/failed BAR pressure result: {result}')
            if bar_read(SCRATCH)!=pressure_saved:raise Failure('BAR pressure did not restore the tested scratch contents')
            summary['bar_pressure']=result[0]
        time.sleep(.4) # allow the final coherent snapshot to cross before stopping collector
        stopped_by_runner=diag.poll() is None
        diag_rc=stop_child(diag,3)
        diag_out.close();diag_err.close()
        if diag_rc not in (0,-signal.SIGTERM) or (diag_rc==-signal.SIGTERM and not stopped_by_runner):
            raise Failure(f'CSI collector exited unexpectedly rc={diag_rc}')
        summary['capture_exit_code']=cap_rc
        summary['collector_exit_code']=diag_rc
        if cap_rc:raise Failure(f'capture executable rc={cap_rc}; see capture.err')
        capture_rows=json_lines(directory/'capture.jsonl')
        summary['capture']=validate_capture(capture_rows,count,width,height)
        summary['csi']=validate_csi(json_lines(directory/'during_csi.jsonl'),capture_rows[0]['seconds'],capture_rows[-1]['seconds'],collector_lead,BIT_VERSION)
        csi_once(directory,'after')
        after,kernel_after=snapshot(directory,'after')
        idle=bar_read([0x60,0x90,0xa4])
        if idle[0x60]&1 or idle[0xa4]&1 or (idle[0x90]&3)!=(2 if height==720 else 0):
            raise Failure(f'STREAMOFF/mode idle state is inconsistent: {idle}')
        summary['idle_registers']={hex(k):hex(v) for k,v in idle.items()}
        summary['driver']=validate_driver(kernel_before,kernel_after,count)
        summary['state']=check_state(before,after)
        if summary['state']['reasons']:raise Failure('; '.join(summary['state']['reasons']))
        summary['result']='transport_and_csi_pass'
        summary['collector_lead_s']=collector_lead
    except BaseException as e:
        summary['result']='fail';summary['reason']=str(e)
        (directory/'failure.txt').write_text(traceback.format_exc())
        raise
    finally:
        cleanup_reasons=[]
        for child in (cap,diag):
            try:stop_child(child,3 if child is diag else 15)
            except BaseException as e:cleanup_reasons.append(str(e))
        if bar is not None and bar.poll() is None:
            try:bar.wait(timeout=60)
            except subprocess.TimeoutExpired:
                try:stop_child(bar)
                except BaseException as e:cleanup_reasons.append(str(e))
        if pressure_saved is not None:
            try:
                if bar_read(SCRATCH)!=pressure_saved:
                    scratch_restore(pressure_saved)
                    summary['scratch_recovery_performed']=True
                summary['scratch_restored']=bar_read(SCRATCH)==pressure_saved
                if not summary['scratch_restored']:cleanup_reasons.append('scratch restore verification failed')
            except BaseException as e:
                summary['scratch_restored']=False;cleanup_reasons.append('scratch recovery: '+str(e))
        for h in handles:h.close()
        try:
            if not (directory/'after_state.json').exists():snapshot(directory,'after_failure')
        except BaseException as e:cleanup_reasons.append('after failure snapshot: '+str(e))
        if cleanup_reasons:
            summary['cleanup_errors']=cleanup_reasons;summary['result']='fail'
        dump(directory/'summary.json',summary)
        event('phase_result',phase=name,result=summary['result'],reason=summary.get('reason'))
    if summary['result']!='transport_and_csi_pass':raise Failure(f'{name} cleanup/recovery did not complete')

def interrupted(signo,frame):
    raise InterruptedError(f'regression interrupted by signal {signo}')
signal.signal(signal.SIGTERM,interrupted)
signal.signal(signal.SIGINT,interrupted)
overall=dict(result='running',task_root=str(ROOT),output=str(OUT),
             bidirectional_image_status='not_covered_use_image_roundtrip',
             rgb_visual_status='requires_separate_visual_or_golden_reference_acceptance')
exit_code=1
try:
    FRAMES=integer('REGRESSION_FRAMES',1000,1000)
    CYCLES=integer('REGRESSION_CYCLES',4,2)
    CYCLE_FRAMES=integer('REGRESSION_CYCLE_FRAMES',32,16)
    TIMEOUT=integer('REGRESSION_TIMEOUT_S',180,20)
    BAR_ROUNDS=integer('REGRESSION_BAR_ROUNDS',1000,1000)
    LEAK_KB=integer('REGRESSION_CMA_LEAK_KB',1024,0)
    SAVE_MODE=os.environ.get('CAPTURE_SAVE_MODE','none')
    if SAVE_MODE not in ('none','bounded'):raise Failure('CAPTURE_SAVE_MODE must be none or bounded for regression')
    if os.geteuid()!=0:raise Failure('run as root')
    compatible=Path('/proc/device-tree/compatible').read_bytes()
    if b'rk3576' not in compatible:raise Failure('this suite targets the tested RK3576')
    dt=Path('/sys/firmware/devicetree/base')
    for node,status in [('pcie@2a210000','okay'),('usb@23400000','disabled')]:
        if (dt/node/'status').read_bytes().rstrip(b'\0').decode()!=status:
            raise Failure(f'{node} must be {status}; install verified boot separately, this suite never flashes boot')
    for mod in ('anlogic_pci','milianke_v4l2'):
        if not (Path('/sys/module')/mod).exists():raise Failure(f'{mod} not loaded; run bash deploy/pcie_setup.sh first')
    params=Path('/sys/module/anlogic_pci/parameters')
    for key,value in [('poll_mode','1'),('enable_st_c2h_credit','1'),('desc_blen_max','1048576')]:
        if (params/key).read_text().strip()!=value:raise Failure(f'SGDMA {key} must be {value}')
    EP=endpoint();BAR=EP/'resource0';VIDEO=video_node()
    parent=EP.resolve().parent
    ROOTPORT=Path('/sys/bus/pci/devices')/parent.name if re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]',parent.name) else None
    current=bar_read([0x5c,0x60,0x90,0xa4])
    BIT_VERSION=current[0x5c]
    if BIT_VERSION not in SUPPORTED_VERSIONS:raise Failure(f'unsupported diagnostic bit version: {BIT_VERSION:08x}')
    if current[0x60]&1 or current[0xa4]&1:raise Failure('camera/loopback already active; stop applications before regression')
    cma,_=meminfo()
    if cma['CmaTotal_kB']<65536 or cma['CmaFree_kB']<24576:raise Failure(f'insufficient CMA for four 1080p buffers: {cma}')
    free=__import__('shutil').disk_usage(OUT).free
    required_free=(512 if SAVE_MODE=='bounded' else 64)*1024*1024
    if free<required_free:raise Failure(f'insufficient output free space: {free} bytes')
    tools=('capture_verify.c','bar_roundtrip.c','read_csi_stats.py')
    source_hashes={p:hashlib.sha256((ROOT/'tools'/p).read_bytes()).hexdigest() for p in tools}
    if 'CAPTURE_SAVE_MODE' not in (ROOT/'tools/capture_verify.c').read_text():
        raise Failure('capture_verify does not support bounded/none saving')
    for tool in ('capture_verify','bar_roundtrip'):
        run(['gcc','-std=gnu11','-O2','-Wall','-Wextra','-o',str(BIN/tool),str(ROOT/'tools'/(tool+'.c'))],
            OUT/(tool+'_compile.log'),timeout=60)
    module_hashes={}
    for module in ('sgdma_drv/anlogic_pci.ko','v4l2_drv/milianke_v4l2.ko'):
        p=ROOT/'deploy'/module
        if p.exists():module_hashes[module]=hashlib.sha256(p.read_bytes()).hexdigest()
    overall.update(endpoint=EP.name,video=str(VIDEO),bar=str(BAR),rootport=ROOTPORT.name if ROOTPORT else None,
                   frames_per_long_mode=FRAMES,cycles=CYCLES,cycle_frames=CYCLE_FRAMES,
                   long_save_mode=SAVE_MODE,source_hashes=source_hashes,module_file_hashes=module_hashes,
                   initial_registers={hex(k):hex(v) for k,v in current.items()},cma=cma)
    dump(OUT/'manifest.json',overall)
    suite_before,_=snapshot(OUT,'suite_before')
    phase('long_720',1280,720,FRAMES,SAVE_MODE,True)
    phase('long_1080',1920,1080,FRAMES,SAVE_MODE,True)
    for i in range(CYCLES):
        phase(f'cycle_{i+1:02}_720',1280,720,CYCLE_FRAMES,'none',False)
        phase(f'cycle_{i+1:02}_1080',1920,1080,CYCLE_FRAMES,'none',False)
    if len(PHASES)!=2+2*CYCLES or any(p['result']!='transport_and_csi_pass' for p in PHASES):
        raise Failure('required phases did not all complete successfully')
    final=bar_read([0x60,0x90,0xa4])
    if final[0x60]&1 or final[0xa4]&1 or final[0x90]&3:raise Failure('pipeline/mux not idle in final 1080p mode after capture close')
    suite_after,_=snapshot(OUT,'suite_after')
    overall['suite_state']=check_state(suite_before,suite_after)
    if overall['suite_state']['reasons']:raise Failure('; '.join(overall['suite_state']['reasons']))
    overall['final_registers']={hex(k):hex(v) for k,v in final.items()}
    overall['result']='transport_and_csi_pass'
    exit_code=0
except BaseException as e:
    overall['result']='fail';overall['reason']=str(e)
    (OUT/'suite_failure.txt').write_text(traceback.format_exc())
finally:
    overall['phases']=PHASES
    dump(OUT/'summary.json',overall)
    event('suite_result',result=overall['result'],reason=overall.get('reason'),output=str(OUT),
          rgb_visual_status=overall['rgb_visual_status'],bidirectional_image_status=overall['bidirectional_image_status'])
raise SystemExit(exit_code)
PY_REGRESSION
