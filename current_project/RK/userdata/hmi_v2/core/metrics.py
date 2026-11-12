"""Bounded measured process/stage metrics; no inferred NPU utilization."""
from collections import deque
import math,os,time
from pathlib import Path

class Metrics:
    def __init__(self):
        self.samples=deque(maxlen=256);self.cpu=time.process_time();self.wall=time.monotonic()
    def observe(self,now,**timings_ms):
        values={k:float(v) for k,v in timings_ms.items() if type(v) in (int,float) and math.isfinite(v) and v>=0}
        self.samples.append((now,values))
    def snapshot(self,now):
        rows=[r for r in self.samples if 0<=now-r[0]<=5_000_000_000]
        fields={k for _,values in rows for k in values};stages={}
        for key in fields:
            values=sorted(v[key] for _,v in rows if key in v)
            stages[key]={'p50_ms':values[int((len(values)-1)*.5)],'p95_ms':values[int((len(values)-1)*.95)],'max_ms':values[-1],'samples':len(values)}
        rate=(len(rows)-1)*1e9/(rows[-1][0]-rows[0][0]) if len(rows)>1 and rows[-1][0]>rows[0][0] else 0.
        wall=time.monotonic();cpu=time.process_time();percent=100*(cpu-self.cpu)/max(1e-6,wall-self.wall);self.cpu=cpu;self.wall=wall
        rss=None
        try:rss=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        except (OSError,ValueError,IndexError,AttributeError):pass
        temperatures={}
        for path in Path('/sys/class/thermal').glob('thermal_zone*/temp'):
            try:temperatures[(path.parent/'type').read_text().strip()]=int(path.read_text())/1000
            except (OSError,ValueError):pass
        return {'observed_hz':rate,'stages':stages,'process_cpu_percent':percent,'process_rss_bytes':rss,
                'temperature_c':temperatures,'npu_utilization':None,'scope':'measured observations and this process only; NPU utilization unavailable'}
