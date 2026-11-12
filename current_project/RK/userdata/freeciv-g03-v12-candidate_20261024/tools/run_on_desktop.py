"""Run an explicit command in an existing same-user graphical session.

Copies only display/session variables from the specified live process, never
guesses DISPLAY, reads authentication contents, or changes X access control.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess


def environment(pid):
    proc=Path('/proc')/str(pid)
    if proc.stat().st_uid!=os.geteuid():raise RuntimeError('Reference process must belong to this desktop user')
    fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
    initial=int(fields[19])
    data={}
    for item in (proc/'environ').read_bytes().split(b'\0'):
        if b'=' in item:
            key,value=item.split(b'=',1)
            data[key.decode()]=value.decode()
    if not data.get('DISPLAY') or not data.get('XAUTHORITY'):
        raise RuntimeError('Reference process lacks explicit X11 display/authentication path')
    auth=Path(data['XAUTHORITY'])
    if not auth.is_file():raise RuntimeError('The existing X authority file is unavailable')
    if int((proc/'stat').read_text().rsplit(')',1)[1].split()[19])!=initial:
        raise RuntimeError('Reference process changed')
    selected={k:data[k] for k in ('DISPLAY','XAUTHORITY','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS','LANG') if data.get(k)}
    return dict(os.environ,**selected),dict(reference_pid=pid,start_ticks=initial,display=selected['DISPLAY'])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference-pid',type=int,required=True)
    ap.add_argument('--inspect',action='store_true')
    ap.add_argument('command',nargs=argparse.REMAINDER)
    a=ap.parse_args();env,identity=environment(a.reference_pid)
    if a.inspect:
        print(json.dumps(identity));return 0
    argv=a.command[1:] if a.command[:1]==['--'] else a.command
    if not argv:ap.error('An explicit command is required')
    return subprocess.call(argv,env=env)


if __name__=='__main__':raise SystemExit(main())
