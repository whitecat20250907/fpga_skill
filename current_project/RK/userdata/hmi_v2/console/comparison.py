"""Read-only dashboard telemetry. No device access, inference or control calls."""
import re
from pathlib import Path


def cpu_percent(previous, current):
    if previous is None or len(previous) != 8 or len(current) != 8:
        return None
    delta = [b-a for a,b in zip(previous,current)]
    if min(delta) < 0 or sum(delta) <= 0:
        return None
    return 100 * (sum(delta)-delta[3]-delta[4]) / sum(delta)


class Comparison:
    def __init__(self):
        from .fpga_observation import OwnerRates,profile
        self.owner_rates=OwnerRates();self.fpga_profile=profile()
        self.cpu = None
        self.native = None
        self.last_ns = 0
        self.data = {}

    def sample(self, values, now, read=lambda p: Path(p).read_text()):
        if self.last_ns and now-self.last_ns < 1_000_000_000:
            return self.data
        self.last_ns = now
        cpu = None
        try:
            current = list(map(int,read('/proc/stat').splitlines()[0].split()[1:9]))
            cpu = cpu_percent(self.cpu,current)
            self.cpu = current
        except (OSError,ValueError,IndexError):
            self.cpu = None
        npu = {}
        try:
            npu = {k:float(v) for k,v in re.findall(r'Core(\d+):\s*(\d+)%',read('/sys/kernel/debug/rknpu/load')) if 0<=float(v)<=100}
        except OSError:
            pass
        heartbeat = values.get('sys.metrics.fpga-io',{})
        age = now-heartbeat.get('src_ns',0)
        online = bool(heartbeat.get('epoch')) and 0<=age<=2_000_000_000
        native = heartbeat.get('native',{}) if online else {}
        from .fpga_observation import link
        pcie=link(read)
        fpga_counters=self.owner_rates.sample(heartbeat,now) if online else self.owner_rates.sample({},now)
        display = native.get('display',{})
        row = (heartbeat.get('epoch'),heartbeat.get('instance'),heartbeat.get('src_ns',0),native.get('serial'),display.get('accepted_packets'))
        rates = [None,None]
        errors = None
        if online and self.native:
            old,old_errors = self.native
            dt = (row[2]-old[2])/1e9
            if row[:2]==old[:2] and 0<dt<=3:
                rates = [(b-a)/dt if isinstance(a,int) and isinstance(b,int) and b>=a else None for a,b in zip(old[3:],row[3:])]
                current_errors = [display.get(k) for k in ('crc_errors','format_errors','sequence_errors')]
                if all(isinstance(a,int) and isinstance(b,int) and b>=a for a,b in zip(old_errors,current_errors)):
                    errors = sum(b-a for a,b in zip(old_errors,current_errors))
        self.native = (row,[display.get(k) for k in ('crc_errors','format_errors','sequence_errors')]) if online else None
        frame = values.get('frame.meta',{})
        frame_age = (now-frame.get('src_ns',0))/1e6
        valid_frame = online and frame.get('epoch')==heartbeat.get('epoch') and 0<=frame_age<=2000
        self.data = dict(sample_ns=now,online=online,owner_ok=heartbeat.get('ok') if online else None,
                         cpu_percent=cpu,npu_percent=npu,model_hz=rates[0],display_packet_hz=rates[1],
                         display_error_delta=errors,frame_age_ms=frame_age if valid_frame else None,
                         epoch=str(heartbeat.get('epoch')) if online else None,
                         power_w=None,fpga_utilization=None,pcie=pcie,
                         fpga_static=self.fpga_profile,fpga_counters=fpga_counters)
        return self.data
