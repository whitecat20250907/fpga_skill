"""Extend verified PC receiver with explicit keys for the actual gaze window."""
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path

BASE_SHA = '42501345d1b4f29475c91fbe7f208c98b9ac6f4e1cb90653cb72cde2e5c9dd2e'
source = Path(__file__).with_name('receiver.py')
if hashlib.sha256(source.read_bytes()).hexdigest() != BASE_SHA:
    raise RuntimeError('Original PC receiver changed')
spec = importlib.util.spec_from_file_location('_pc_original_v2', source)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
KEYS = {'gaze_calibrate':'r','gaze_recalibrate':'r','gaze_validate':'v',
        'gaze_pointer':'F8','gaze_dwell':'F6','gaze_restore':'F9'}

class Receiver(base.Receiver):
    def socket_owner(self):
        # This RK kernel does not expose /proc/PID/task/PID/children.
        # Read the actual PPID from stat instead; retain endpoint/executable checks.
        inodes = {r.split()[9] for r in Path('/proc/net/udp').read_text().splitlines()[1:]
                  if r.split()[1] == '0100007F:7452'}
        launcher = self.cfg['launcher_pid']
        candidates = [launcher]
        for p in Path('/proc').iterdir():
            if not p.name.isdigit():
                continue
            try:
                fields = (p/'stat').read_text().rsplit(')',1)[1].split()
                if int(fields[1]) == launcher:
                    candidates.append(int(p.name))
            except (FileNotFoundError, ProcessLookupError):
                continue
        owners = []
        for pid in candidates:
            try:
                owned = set()
                for fd in Path(f'/proc/{pid}/fd').iterdir():
                    try:
                        target = os.readlink(fd)
                    except FileNotFoundError:
                        continue
                    if target.startswith('socket:['):
                        owned.add(target[8:-1])
                if len(inodes) != 1 or not inodes.issubset(owned):
                    continue
                if pid != launcher:
                    exe = Path(f'/proc/{pid}/exe')
                    meta = exe.stat()
                    stamp = (pid,base.start_ticks(pid),meta.st_dev,meta.st_ino,meta.st_size,meta.st_mtime_ns)
                    if stamp not in self.verified_clients:
                        if hashlib.sha256(exe.read_bytes()).hexdigest() != self.cfg['game_sha256']:
                            raise RuntimeError('Active game executable changed')
                        self.verified_clients.add(stamp)
                owners.append((pid,base.start_ticks(pid)))
            except (FileNotFoundError, ProcessLookupError):
                continue
        if len(owners) != 1:
            raise RuntimeError('No unique pinned game endpoint')
        self.endpoint = owners[0]

    def dispatch(self, req):
        action = req.get('action')
        if action not in KEYS:
            return super().dispatch(req)
        if not self.active:
            raise ValueError('First click computer takeover')
        binding = json.loads(Path(self.cfg['binding']).read_text())
        state = json.loads((Path(binding['root'])/'lifecycle/video_owner_state.json').read_text())
        if state['phase'] not in ('FEATURE_RUNNING','FEATURE_KEEP_RUNNING'):
            raise RuntimeError('采集/眼动程序已停止，无法标定；请先恢复图像输入')
        if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != binding['boot_id']:
            raise RuntimeError('Board rebooted')
        expected = [r for r in binding['runtime']['owners'] if 'run_gaze.py' in r['cmdline']]
        if len(expected) != 1 or expected[0] not in state['runtime']['owners']:
            raise RuntimeError('Gaze process binding changed')
        process = expected[0]
        if base.start_ticks(process['pid']) != process['start_ticks']:
            raise RuntimeError('Gaze process restarted')
        from gaze_window import restore_gaze_window
        restore_gaze_window(process['pid'],self.env)
        subprocess.run(['xdotool','key','--clearmodifiers',KEYS[action]],env=self.env,check=True,timeout=2)
        return {'input':action,'source':'PC_MANUAL','target':'gaze','key':KEYS[action]}

base.Receiver = Receiver
if __name__ == '__main__':
    raise SystemExit(base.main())
