"""Read-only game delivery inventory; no camera/model lifecycle actions."""
import json,os,platform,shutil,socket
from pathlib import Path
root=Path('/userdata/freeciv-rk3576-gaze-demo')
processes=[];desktop=[]
for p in Path('/proc').glob('[0-9]*'):
    try:
        argv=[x.decode(errors='replace') for x in (p/'cmdline').read_bytes().split(b'\0') if x]
        if not argv:continue
        stat=(p/'stat').read_text().rsplit(')',1)[1].split();name=(p/'comm').read_text().strip()
        if name in ('xfce4-session','xfdesktop','xfwm4'):
            desktop.append(dict(pid=int(p.name),birth=int(stat[19]),name=name))
        if any('freeciv' in x for x in argv[:2]) or (argv[0].endswith('python3') and 'launch.py' in argv):
            processes.append(dict(pid=int(p.name),birth=int(stat[19]),ppid=int(stat[1]),argv=argv,cwd=os.readlink(p/'cwd'),uid=p.stat().st_uid))
    except (OSError,ValueError):pass
state=None
try:
    import sys;sys.path.insert(0,str(root/'tools'))
    from test_live_input import Link
    link=Link();state=link.state(2);link.socket.close()
except Exception as e:state=dict(unavailable=type(e).__name__)
print(json.dumps(dict(machine=platform.machine(),kernel=platform.release(),uid=os.geteuid(),root_exists=root.is_dir(),
    disk=shutil.disk_usage(root)._asdict(),memory={k:v.strip() for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines()) if k in ('MemTotal','MemAvailable','SwapTotal')},
    processes=processes,desktop=desktop,state=state),ensure_ascii=False))
