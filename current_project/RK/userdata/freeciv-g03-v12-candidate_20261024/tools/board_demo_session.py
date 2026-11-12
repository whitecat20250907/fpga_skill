"""Own one native game launcher; keep its Popen until normal exit and reap it.

Start only after the separately identified old game has exited. No inference,
camera, driver or FPGA operations are performed here.
"""
import argparse,ctypes as C,json,os,subprocess,time
from pathlib import Path
from run_on_desktop import environment
from test_live_input import Link,need
ROOT=Path(__file__).resolve().parents[1]
def identity(pid):
    p=Path('/proc')/str(pid);f=(p/'stat').read_text().rsplit(')',1)[1].split()
    return dict(pid=pid,birth=int(f[19]),ppid=int(f[1]),cwd=os.readlink(p/'cwd'),argv=[x.decode() for x in (p/'cmdline').read_bytes().split(b'\0') if x])
def close_window(window):
    class Data(C.Union):_fields_=[('l',C.c_long*5),('b',C.c_char*20)]
    class Message(C.Structure):_fields_=[('type',C.c_int),('serial',C.c_ulong),('send_event',C.c_int),('display',C.c_void_p),('window',C.c_ulong),('message_type',C.c_ulong),('format',C.c_int),('data',Data)]
    class Event(C.Union):_fields_=[('message',Message),('pad',C.c_long*24)]
    x=C.CDLL('libX11.so.6');x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=C.c_void_p
    x.XInternAtom.argtypes=[C.c_void_p,C.c_char_p,C.c_int];x.XInternAtom.restype=C.c_ulong
    x.XSendEvent.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_long,C.POINTER(Event)];x.XFlush.argtypes=[C.c_void_p];x.XCloseDisplay.argtypes=[C.c_void_p]
    display=x.XOpenDisplay(None);need(display,'X11 unavailable');event=Event();m=event.message
    m.type=33;m.display=display;m.window=int(window);m.format=32;m.message_type=x.XInternAtom(display,b'WM_PROTOCOLS',0)
    m.data.l[0]=x.XInternAtom(display,b'WM_DELETE_WINDOW',0);x.XSendEvent(display,int(window),0,0,C.byref(event));x.XFlush(display);x.XCloseDisplay(display)
def close_client(pid,birth):
    before=identity(pid);need(before['birth']==birth and before['argv'][0]==str(ROOT/'build-arm64/freeciv-gtk3.22'),'Wrong native game identity')
    windows=subprocess.check_output(['xdotool','search','--onlyvisible','--pid',str(pid)],text=True).split()
    need(windows,'Owned game has no visible window')
    roles={w:subprocess.check_output(['xprop','-id',w,'WM_WINDOW_ROLE'],text=True) for w in windows}
    main=next((w for w in windows if '"toplevel"' in roles[w]),None)
    need(main,'Owned native main window not identified')
    # A technology-help child is not the quit confirmation. Close only this
    # exact known native browser before asking the main window to quit.
    for w in windows:
        if subprocess.check_output(['xdotool','getwindowname',w],text=True).strip()=='Freeciv Help Browser':close_window(w)
    time.sleep(.15)
    previous=set(subprocess.check_output(['xdotool','search','--onlyvisible','--pid',str(pid)],text=True).split())
    close_window(main);time.sleep(.3)
    if not Path('/proc',str(pid)).exists():return
    new=subprocess.check_output(['xdotool','search','--onlyvisible','--pid',str(pid)],text=True).split()
    dialogs=[w for w in new if w not in previous]
    need(dialogs,'Native quit confirmation not found')
    for dialog in dialogs:
        # This client's actual GTK dialog orders No, Yes. Focus No first and
        # move right to Yes; its labels do not provide an Alt+Y mnemonic.
        subprocess.run(['xdotool','windowactivate','--sync',dialog],check=True,timeout=3)
        subprocess.run(['xdotool','key','Left','Right','Return'],check=True)
    end=time.monotonic()+6
    while Path('/proc',str(pid)).exists() and time.monotonic()<end:time.sleep(.1)
    need(not Path('/proc',str(pid)).exists(),'Native game did not accept quit confirmation')
def wait_state(predicate,seconds=25):
    link=Link();end=time.monotonic()+seconds
    try:
        while time.monotonic()<end:
            try:s=link.state(.8)
            except RuntimeError:continue
            if predicate(s):return s
        raise RuntimeError('Game state transition timed out')
    finally:link.socket.close()
def menu_exit():
    s=wait_state(lambda s:s.get('phase')=='menu');link=Link();link.sequence=int(s['last_event'])
    try:
        s=link.event('wake');target=next(t for t in s['targets'] if t['id']==3);link.point(target,s,.45)
        link.sequence+=1;link.raw(f'event {link.sequence} confirm')
    finally:link.socket.close()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--session',required=True);ap.add_argument('--replace-old',action='store_true');a=ap.parse_args()
    need(a.session.replace('_','').isalnum(),'Session name');out=ROOT/'.maintenance'/a.session;out.mkdir(exist_ok=False)
    env,display=environment(1721);os.environ.update(env)
    if a.replace_old:
        old=identity(136747);need(old['birth']==51386602,'Old client identity changed')
        (out/'old_game.json').write_text(json.dumps(dict(client=old,launcher=identity(136742),owner=identity(136732)),indent=2))
        close_client(136747,51386602);wait_state(lambda s:s.get('phase')=='menu');menu_exit()
        end=time.monotonic()+10
        while Path('/proc/136742').exists() and time.monotonic()<end:time.sleep(.1)
        need(not Path('/proc/136742').exists(),'Old launcher did not exit through its menu')
        (out/'old_exit.json').write_text(json.dumps(dict(client_exited=True,launcher_exited=True,original_owner_responsible_for_reap=True)))
    with (out/'launcher.log').open('wb') as stream:
        child=subprocess.Popen(['taskset','-c','0-3','nice','-n','10','ionice','-c','3','python3','-B','launch.py','--build','build-arm64'],cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
    (out/'owner.json').write_text(json.dumps(dict(supervisor=identity(os.getpid()),launcher=identity(child.pid),display=display),indent=2))
    try:
        s=wait_state(lambda s:s.get('phase')=='menu');(out/'ready.json').write_text(json.dumps(dict(status='OWNED_START_PAGE_READY',state=s),indent=2));print('OWNED_START_PAGE_READY',child.pid,flush=True)
        while child.poll() is None and not (out/'stop.request').exists():time.sleep(.2)
        if child.poll() is None:
            s=Link().state();
            if s.get('phase')!='menu':
                clients=[]
                for p in Path('/proc').glob('[0-9]*/stat'):
                    try:
                        row=identity(int(p.parent.name))
                        if row['ppid']==child.pid and row['argv'][0]==str(ROOT/'build-arm64/freeciv-gtk3.22'):clients.append(row)
                    except (OSError,IndexError):pass
                need(len(clients)==1,'Exact owned client required');close_client(clients[0]['pid'],clients[0]['birth'])
            menu_exit()
        code=child.wait(timeout=15)
        (out/'terminal.json').write_text(json.dumps(dict(status='OWNED_LAUNCHER_REAPED',returncode=code,original_Popen_waited=True),indent=2))
    except BaseException as e:
        (out/'error.json').write_text(json.dumps(dict(error=repr(e),launcher_still_running=child.poll() is None),indent=2));raise
if __name__=='__main__':main()
