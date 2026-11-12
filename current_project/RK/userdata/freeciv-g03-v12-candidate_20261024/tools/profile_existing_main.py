"""Read an existing gaze process and its CSV; never start inference or capture."""
import argparse
import collections
import csv
import io
import json
import math
import os
from pathlib import Path
import statistics
import time


def process(pid):
    fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
    return dict(start_ticks=int(fields[19]),ticks=int(fields[11])+int(fields[12]),
                rss_bytes=int(fields[21])*os.sysconf('SC_PAGE_SIZE'))


def tail_csv(path):
    with path.open('rb') as stream:
        header=stream.readline()
        size=os.fstat(stream.fileno()).st_size
        stream.seek(max(len(header),size-2*1024*1024))
        if stream.tell()>len(header):stream.readline()
        body=stream.read()
    if not body.endswith(b'\n'):body=body.rsplit(b'\n',1)[0]+b'\n'
    return [row for row in csv.DictReader(io.StringIO((header+body).decode('utf8')))
            if None not in row.values()]


def summary(values):
    values=sorted(x for x in values if math.isfinite(x))
    if not values:return dict(count=0,median=None,p95=None)
    index=.95*(len(values)-1);lower=int(index);upper=min(lower+1,len(values)-1)
    return dict(count=len(values),median=statistics.median(values),
                p95=values[lower]+(values[upper]-values[lower])*(index-lower),
                minimum=values[0],maximum=values[-1])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid',type=int,required=True)
    ap.add_argument('--csv',type=Path,required=True)
    ap.add_argument('--seconds',type=float,default=30)
    ap.add_argument('--label',required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    if not 0<a.seconds<=60:ap.error('seconds must be in (0,60]')
    if a.output.exists():ap.error('Preserve prior measurement')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    before=process(a.pid);begin=time.monotonic_ns()
    time.sleep(a.seconds)
    end=time.monotonic_ns();after=process(a.pid)
    if before['start_ticks']!=after['start_ticks']:raise RuntimeError('Main process instance changed')
    rows=[r for r in tail_csv(a.csv) if begin<=int(r['timestamp_ns'])<=end]
    if len({r['timestamp_ns'] for r in rows})!=len(rows):raise RuntimeError('Duplicate source timestamps')
    elapsed=(end-begin)/1e9
    npu=[r for r in rows if r['npu_called'].lower() in ('true','1')]
    result=dict(label=a.label,elapsed_seconds=elapsed,boot_id=boot,
        process_identity=dict(pid=a.pid,start_ticks=before['start_ticks']),
        main_cpu_one_core_percent=100*(after['ticks']-before['ticks'])/os.sysconf('SC_CLK_TCK')/elapsed,
        main_rss_mib=after['rss_bytes']/2**20,
        source_samples=len(rows),source_updates_per_second=len(rows)/elapsed,
        valid_samples=sum(r['valid']=='1' for r in rows),npu_call_samples=len(npu),
        valid_updates_per_second=sum(r['valid']=='1' for r in rows)/elapsed,
        npu_calls_per_second=len(npu)/elapsed,
        phases=dict(collections.Counter(r['phase'] for r in rows)),
        reasons=dict(collections.Counter(r['reason'] for r in rows)),
        timings_ms={key:summary([float(r[key]) for r in (npu if key=='npu_ms' else rows)])
                    for key in ('inference_ms','sample_age_ms','input_age_ms','face_ms','prepare_ms','npu_ms','dequeue_to_input_ms')},
        measurement='Existing main /proc CPU and source-timestamp CSV window; no inference/camera process created.',
        real_NPU_latency_measured=bool(npu))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
