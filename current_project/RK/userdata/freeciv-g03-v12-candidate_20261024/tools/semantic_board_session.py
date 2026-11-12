"""Own the new game launcher, test actual semantic UDP, retain it at start page.
No camera/model lifecycle or driver operations. The old idle page exits via its
own documented Exit target, and its original parent remains responsible for reaping.
"""
import ctypes as C,itertools,json,os,struct,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path('/userdata/freeciv-rk3576-gaze-demo');sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from test_live_input import Link,need
from run_on_desktop import environment
OUT=ROOT/'.maintenance/semantic_selection_session_v1'
def identity(pid):
    p=Path('/proc')/str(pid)
    return dict(pid=pid,birth=int((p/'stat').read_text().rsplit(')',1)[1].split()[19]),cwd=str((p/'cwd').resolve()))
def save(name,row):(OUT/name).write_text(json.dumps(row,indent=2)+'\n')
def screenshot(path):
    from PIL import Image
    rawpath=path.with_suffix('.xwd');subprocess.run(['xwd','-root','-silent','-out',str(rawpath)],check=True,timeout=6)
    raw=rawpath.read_bytes();h=struct.unpack_from('>25I',raw)
    need(h[11] in (24,32) and h[7]==0 and tuple(h[14:17])==(0xff0000,0xff00,0xff),'Unsupported XWD')
    Image.frombytes('RGB',(h[4],h[5]),raw[h[0]+h[19]*12:],'raw','BGR' if h[11]==24 else 'BGRX',h[12],1).save(path)
def close_window(window):
    class Data(C.Union):_fields_=[('l',C.c_long*5),('b',C.c_char*20)]
    class Message(C.Structure):
        _fields_=[('type',C.c_int),('serial',C.c_ulong),('send_event',C.c_int),('display',C.c_void_p),('window',C.c_ulong),('message_type',C.c_ulong),('format',C.c_int),('data',Data)]
    class Event(C.Union):_fields_=[('message',Message),('pad',C.c_long*24)]
    x=C.CDLL('libX11.so.6');x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=C.c_void_p
    x.XInternAtom.argtypes=[C.c_void_p,C.c_char_p,C.c_int];x.XInternAtom.restype=C.c_ulong
    x.XSendEvent.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_long,C.POINTER(Event)]
    x.XFlush.argtypes=[C.c_void_p];x.XCloseDisplay.argtypes=[C.c_void_p]
    display=x.XOpenDisplay(None);need(display,'Current desktop unavailable')
    event=Event();m=event.message;m.type=33;m.display=display;m.window=int(window);m.format=32
    m.message_type=x.XInternAtom(display,b'WM_PROTOCOLS',0);m.data.l[0]=x.XInternAtom(display,b'WM_DELETE_WINDOW',0)
    x.XSendEvent(display,int(window),0,0,C.byref(event));x.XFlush(display);x.XCloseDisplay(display)
def main():
    OUT.mkdir(exist_ok=False);env,display=environment(126531);os.environ.update(env)
    model=identity(126531);capture=identity(126613)
    need(model['birth']==45582633 and capture['birth']==45583116,'Current main identities changed')
    link=Link();old=link.state();need(old['phase']=='menu','Only an idle old start page may be replaced')
    link.sequence=int(old['last_event']);state=link.event('wake');target=next(t for t in state['targets'] if t['id']==3)
    link.point(target,state,.4);link.sequence+=1;link.raw(f'event {link.sequence} confirm')
    deadline=time.monotonic()+10
    while Path('/proc/122927').exists() and time.monotonic()<deadline:time.sleep(.1)
    need(not Path('/proc/122927').exists(),'Original start page did not exit')
    terminal=ROOT/'.maintenance/campaign_GUI_v8/terminal.json'
    need(terminal.exists() and json.loads(terminal.read_text())['original_Popen_waited'],'Original parent reap not recorded')
    link.socket.close();cases=[];report=dict(human_test=False,camera_or_model_restarted=False,cases=cases)
    with (OUT/'launch.log').open('wb') as log:
        child=subprocess.Popen(['taskset','-c','0-3','nice','-n','10','ionice','-c','3','python3','-B','launch.py','--build','build-arm64'],
            cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    save('owner.json',dict(supervisor=identity(os.getpid()),launcher=identity(child.pid),model=model,capture=capture,display=display))
    link=Link()
    def wait(predicate,seconds=25):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            need(child.poll() is None,'Owned game exited')
            try:s=link.state(.6)
            except RuntimeError:continue
            if predicate(s):return s
            time.sleep(.05)
        raise RuntimeError('State transition timed out')
    def point(target,state,seconds=.4,frozen=False,age=0.):
        stop=time.monotonic()+seconds;stamp=time.monotonic()-age
        while time.monotonic()<stop:
            if not frozen:stamp=time.monotonic()-age
            link.raw(f"gaze2 {int(stamp*1e6)} {target['x']/state['map'][2]:.8f} {target['y']/state['map'][3]:.8f}")
            time.sleep(.03)
    def record(name):cases.append(dict(name=name,passed=True))
    def no_order(state):
        s=link.event('confirm');need(s['awake'] and s['moves']==state['moves'] and s['unit']==state['unit'],'Unstable input executed an order');return s
    try:
        menu=wait(lambda s:s.get('phase')=='menu' and s.get('gaze_protocol')==2)
        link.sequence=int(menu['last_event']);s=link.event('wake');point(next(t for t in s['targets'] if t['id']==0),s)
        s=link.event('confirm');need(s['mode']=='campaign' and not s['awake'],'Mode confirmation failed')
        s=link.event('wake');point(next(t for t in s['targets'] if t['id']==2),s)
        link.sequence+=1;link.raw(f'event {link.sequence} confirm')
        s=wait(lambda s:s.get('phase')!='menu' and s.get('gaze_protocol')==2)
        link.sequence=int(s['last_event']);record('new_menu_source_time_selection_and_native_launch')
        s=link.event('wake');target=max((t for t in s['targets'] if t['kind']==0),key=lambda t:t['x'])
        point(target,s,.18,True);no_order(s);record('duplicate_source_frame_never_accumulates_confirmation')
        point(target,s);link.raw(f"gaze2 {int((time.monotonic()-.4)*1e6)} .5 .5");time.sleep(.08);no_order(s)
        record('delayed_source_invalidates_ready_selection')
        point(target,s);link.raw('gaze_lost');time.sleep(.08);no_order(s);record('loss_immediately_blocks_confirmation')
        link.event('cancel');s=link.event('wake')
        a,b=min(itertools.combinations(s['targets'],2),key=lambda p:(p[0]['x']-p[1]['x'])**2+(p[0]['y']-p[1]['y'])**2)
        point(dict(x=(a['x']+b['x'])/2,y=(a['y']+b['y'])/2),s);no_order(s);record('ambiguous_actual_target_boundary_rejected')
        link.event('cancel');s=link.event('wake');target=max((t for t in s['targets'] if t['kind']==0),key=lambda t:t['x'])
        point(target,s);ready=link.state();need(ready['selection_ready'],'Stable target did not become ready')
        other=next(t for t in s['targets'] if (t['kind'],t['id'],t['arg'])!=(target['kind'],target['id'],target['arg']))
        point(other,s,.01);no_order(s);record('single_target_jump_blocks_old_target_confirmation')
        link.event('cancel');s=link.event('wake');target=max((t for t in s['targets'] if t['kind']==0),key=lambda t:t['x'])
        point(target,s);screenshot(OUT/'stable_target.png')
        after=link.event('confirm');need(not after['awake'] and after['moves']<s['moves'],'Stable source did not move native unit and sleep')
        link.raw(f'event {link.sequence} confirm');time.sleep(.1);need(link.state()['moves']==after['moves'],'Duplicate command executed')
        record('stable_semantic_target_moves_once_then_sleeps')
        need(identity(126531)==model and identity(126613)==capture,'Main model/capture changed')
        report.update(status='PASS_REAL_NATIVE_SEMANTIC_SELECTION',final=after)
        save('result.json',report)
        # Close just this owned client's X window, returning its launcher to menu.
        descendants=[]
        for p in Path('/proc').glob('[0-9]*/stat'):
            try:
                fields=p.read_text().rsplit(')',1)[1].split();cmd=(p.parent/'cmdline').read_bytes().split(b'\0')
                if int(fields[1])==child.pid and cmd[0]==str(ROOT/'build-arm64/freeciv-gtk3.22').encode():descendants.append(int(p.parent.name))
            except (OSError,IndexError):pass
        need(len(descendants)==1,'Expected exact owned native client')
        windows=subprocess.check_output(['xdotool','search','--pid',str(descendants[0]),'--name','Freeciv'],env=env,text=True).split()
        need(windows,'Owned client window not found')
        for window in windows:close_window(window)
        menu=wait(lambda s:s.get('phase')=='menu' and s.get('gaze_protocol')==2)
        save('ready.json',dict(status='NEW_START_PAGE_RUNNING',launcher=identity(child.pid),supervisor=identity(os.getpid()),menu=menu,model=model,capture=capture))
        print(json.dumps(report),flush=True)
    except BaseException as error:
        report.update(status='FAILED_PRESERVED',error=repr(error),traceback=traceback.format_exc());save('result.json',report);print(json.dumps(report),flush=True)
    finally:link.socket.close()
    # Retain and reap our real launcher; do not adopt or kill unrelated owners.
    code=child.wait();save('terminal.json',dict(original_Popen_waited=True,returncode=code,launcher_pid=child.pid))
if __name__=='__main__':main()
