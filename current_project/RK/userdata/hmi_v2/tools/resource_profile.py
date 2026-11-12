"""Read-only whole-system measurement. Percentages keep their own denominators."""
import argparse,json,os,re,sys,time
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.config import load
from core.hmibus import Subscriber
from core.resource_audit import ResourceAudit


def cpu_ticks():
    return {row.split()[0]:list(map(int,row.split()[1:9]))
            for row in Path('/proc/stat').read_text().splitlines() if row.startswith('cpu')}


def services():
    rows={}
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if int(p.name)==os.getpid():continue
            args=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            cwd=(p/'cwd').resolve()
            if '/userdata/hmi_v2' not in args and str(cwd)!='/userdata/hmi_v2':continue
            stat=(p/'stat').read_text().split(') ',1)[1].split()
            module=re.search(r' -m ([\w.]+)',args)
            rows[p.name]={'name':module.group(1) if module else (p/'comm').read_text().strip(),'ticks':int(stat[11])+int(stat[12]),
                          'start':int(stat[19]),'rss':int(stat[21])*os.sysconf('SC_PAGE_SIZE'),
                          'affinity':sorted(os.sched_getaffinity(int(p.name)))}
        except (OSError,ValueError,IndexError):continue
    return rows


def summarize(values):
    if not values:return None
    values=sorted(values)
    return {'mean':sum(values)/len(values),'p95':values[int((len(values)-1)*.95)],'peak':values[-1],'samples':len(values)}


def main():
    p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=60)
    p.add_argument('--scenario',choices=['empty','single','dual_four_hands'],required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not 5<=a.seconds<=3600:p.error('seconds must be 5..3600')
    c=load();sub=Subscriber(['frame.meta','vision.face','vision.gaze','vision.hands','hmi.state','sys.metrics'],run=c['paths']['run'])
    counts=Counter();faces=Counter();hands=Counter();states=Counter();ages=defaultdict(list);loads=defaultdict(list);processes={};epochs=set();stages={}
    start=last=time.monotonic();ticks=cpu_ticks();procs=services();hz=os.sysconf('SC_CLK_TCK')
    audit=ResourceAudit(a.scenario,time.monotonic_ns());next_window=time.monotonic_ns()
    metrics={};thermal=defaultdict(list);frequencies=defaultdict(list)
    online_cpus=os.cpu_count()
    try:
        while time.monotonic()-start<a.seconds:
            for topic,msg in sub.poll(30).items():
                now_ns=time.monotonic_ns();epochs.add(msg.get('epoch'));counts[topic]+=1
                audit.observe(topic,msg,now_ns)
                age=(now_ns-msg.get('src_ns',now_ns))/1e6
                if len(ages[topic])<10000:ages[topic].append(age)
                if topic=='vision.face':faces[sum(bool(f.get('valid')) for f in msg.get('faces',[]))]+=1
                if topic=='vision.hands':hands[len(msg.get('hands',[]))]+=1
                if topic=='vision.gaze' and msg.get('valid'):counts['valid_calibrated_gaze']+=1
                if topic=='vision.gaze' and msg.get('timings',{}).get('npu_called'):counts['gaze_npu_called']+=1
                if topic=='hmi.state':states[msg.get('state','UNKNOWN')]+=1
                if topic.startswith('sys.metrics'):
                    producer=msg.get('producer',topic);stages[producer]=msg.get('measurements',{})
                    metrics.setdefault(producer,[]).append(stages[producer])
            now_ns=time.monotonic_ns()
            if now_ns>=next_window:
                audit.sample(now_ns);next_window=now_ns+100_000_000
            now=time.monotonic()
            if now-last<1:continue
            current=cpu_ticks();dt=now-last
            for core,values in current.items():
                prev=ticks.get(core,values);delta=[v-b for v,b in zip(values,prev)];total=sum(delta)
                if total>0:loads[core].append(100*(total-delta[3]-delta[4])/total)
            current_procs=services()
            for pid,row in current_procs.items():
                previous=procs.get(pid)
                if previous and previous['start']==row['start']:
                    process=processes.setdefault(pid,dict(name=row['name'],start=row['start'],affinity=row['affinity'],cpu_percent_one_core=[],rss_bytes=[]))
                    process['cpu_percent_one_core'].append(100*(row['ticks']-previous['ticks'])/hz/dt)
                    process['rss_bytes'].append(row['rss'])
            try:
                for core,value in re.findall(r'Core(\d+):\s*(\d+)%',Path('/sys/kernel/debug/rknpu/load').read_text()):loads['npu'+core].append(float(value))
            except OSError:pass
            for zone in Path('/sys/class/thermal').glob('thermal_zone*'):
                try:thermal[(zone/'type').read_text().strip()].append(float((zone/'temp').read_text())/1000)
                except (OSError,ValueError):pass
            for policy in Path('/sys/devices/system/cpu/cpufreq').glob('policy*'):
                try:frequencies[policy.name].append(float((policy/'scaling_cur_freq').read_text())/1000)
                except (OSError,ValueError):pass
            ticks=current;procs=current_procs;last=now
    finally:sub.close()
    duration=time.monotonic()-start
    for row in processes.values():
        row['cpu_percent_one_core']=summarize(row['cpu_percent_one_core']);row['rss_bytes']=summarize(row['rss_bytes'])
    quality=audit.finish(time.monotonic_ns());coverage=quality['scenario_coverage']
    missing_loads=[key for key in ('cpu','npu0','npu1') if not loads.get(key)]
    measurement_complete=not missing_loads
    result={'scenario_requested':a.scenario,'duration_s':duration,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'cpu_npu_percent':{k:summarize(v) for k,v in loads.items()},'processes':processes,
            'online_cpu_count':online_cpus,'temperature_celsius':{k:summarize(v) for k,v in thermal.items()},'cpu_frequency_mhz':{k:summarize(v) for k,v in frequencies.items()},
            'rate_hz':{k:v/duration for k,v in counts.items()},'ring_publish_rate_hz':quality['ring_publish_rate_hz'],'rate_semantics':'rate_hz is subscriber-observed, possibly conflated. ring_publish_rate_hz uses monotonic ring serial delta; producer metrics use producer observations.',
            'producer_metrics':metrics,'age_ms':{k:summarize(v) for k,v in ages.items()},
            'face_count_histogram':dict(faces),'hand_count_histogram':dict(hands),'state_histogram':dict(states),'epochs':list(epochs),
            'scenario_coverage':coverage,'quality':quality,'measurement_complete':measurement_complete,'missing_loads':missing_loads,
            'stable':quality['stable'],
            'denominators':'cpu=all online cores normalized to 100%; cpuN=one CPU core; npu0/1=driver per-core busy%; process CPU=one core 100%, may exceed 100%; no combined FPGA/CPU percentage',
            'limits':'NPU busy is not attribution to individual models; valid calibrated gaze is separate from inference calls. Human accuracy/false actions require separate trials.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({'output':str(a.output),'stable':result['stable'],'scenario_coverage':coverage,'measurement_complete':measurement_complete,'rates':result['rate_hz']},ensure_ascii=False))
    return 0 if result['stable'] and coverage and measurement_complete else 1


if __name__=='__main__':raise SystemExit(main())
