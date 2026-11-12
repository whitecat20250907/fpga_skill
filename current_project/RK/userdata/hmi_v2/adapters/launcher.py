"""Launch/focus the selected local application; no camera/model/driver access."""
import os,shutil,subprocess,time
from pathlib import Path
from core.config import ROOT

def owned_game_menu(win,game_root,atom):
    """GTK's start page inherits launch.py WM_CLASS, unlike the native client."""
    try:
        classes=' '.join(win.get_wm_class() or ()).lower()
        if 'launch.py' not in classes:return False
        pid=win.get_full_property(atom('_NET_WM_PID'),0)
        if pid is None or not len(pid.value) or any(pid.value[1:]):return False
        return (Path('/proc')/str(int(pid.value[0]))/'cwd').resolve()==Path(game_root).resolve()
    except (OSError,ValueError,TypeError):return False

def presentation_kind(classes):
    # Chromium app windows retain their URL instance even when sharing one
    # browser process whose class comes from the first launched application.
    if '127.0.0.1__basic' in classes:return 'BASIC'
    if '127.0.0.1__demo' in classes:return 'DEMO'
    if 'hmibasic' in classes:return 'BASIC'
    if 'hmimedical' in classes:return 'DEMO'
    return None


class Launcher:
    def __init__(self,config,display):
        self.c=config;self.d=display;self.processes={};self.context=None;self.error='';self.logs=[];self.last_request=None
        self.attempt=0;self.launched_attempt={}
        self.status={};self.pending=False;self.deadline=0;self.focus_after=0;self.window_id=None
    def _selected(self):
        if self.d is None:return True  # Test display stub.
        from Xlib import X
        root=self.d.screen().root
        name='_NET_SHOWING_DESKTOP' if self.context=='DESKTOP' else '_NET_ACTIVE_WINDOW'
        p=root.get_full_property(self.d.intern_atom(name),X.AnyPropertyType)
        if not p or not len(p.value):return False
        if self.context=='DESKTOP':return int(p.value[0])==1
        if int(p.value[0])!=self.window_id:return False
        win=self.d.create_resource_object('window',self.window_id)
        p=win.get_full_property(self.d.intern_atom('_NET_WM_STATE'),X.AnyPropertyType)
        return p is not None and self.d.intern_atom('_NET_WM_STATE_FULLSCREEN') in p.value
    def _focus(self,context):
        from Xlib import X,protocol
        root=self.d.screen().root
        if context=='DESKTOP':
            clients=root.get_full_property(self.d.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
            for wid in ([] if clients is None else clients.value):
                win=self.d.create_resource_object('window',int(wid))
                try:kind=presentation_kind(' '.join(win.get_wm_class() or ()).lower())
                except Exception:continue
                if kind:root.send_event(protocol.event.ClientMessage(window=win,client_type=self.d.intern_atom('_NET_CLOSE_WINDOW'),data=(32,[X.CurrentTime,2,0,0,0])),event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask)
            root.send_event(protocol.event.ClientMessage(window=root,client_type=self.d.intern_atom('_NET_SHOWING_DESKTOP'),data=(32,[1,0,0,0,0])),event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask);self.d.flush();return True
        root.send_event(protocol.event.ClientMessage(window=root,client_type=self.d.intern_atom('_NET_SHOWING_DESKTOP'),data=(32,[0,0,0,0,0])),event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask)
        self.d.flush()
        prop=root.get_full_property(self.d.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
        # Only the selected presentation occupies the screen. Keep the other
        # native game alive and minimized; browser application state lives in the backend.
        for wid in ([] if prop is None else prop.value):
            win=self.d.create_resource_object('window',int(wid))
            try:classes=' '.join(win.get_wm_class() or ()).lower()
            except Exception:continue
            kind=presentation_kind(classes) or ('GAME' if 'freeciv' in classes or owned_game_menu(win,self.c['paths']['game'],self.d.intern_atom) else None)
            other=kind is not None and kind!=context
            if other and kind in ('DEMO','BASIC'):
                # 2GB board: keep application state in the backend, not hidden
                # browser windows with decoded images and WebGL allocations.
                root.send_event(protocol.event.ClientMessage(window=win,client_type=self.d.intern_atom('_NET_CLOSE_WINDOW'),data=(32,[X.CurrentTime,2,0,0,0])),event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask)
            elif other:
                root.send_event(protocol.event.ClientMessage(window=win,client_type=self.d.intern_atom('WM_CHANGE_STATE'),data=(32,[3,0,0,0,0])),event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask)
        for wid in ([] if prop is None else prop.value):
            win=self.d.create_resource_object('window',int(wid))
            try:classes=' '.join(win.get_wm_class() or ()).lower()
            except Exception:continue
            if (presentation_kind(classes)==context if context in ('DEMO','BASIC') else 'freeciv' in classes or owned_game_menu(win,self.c['paths']['game'],self.d.intern_atom)):
                self.window_id=int(wid)
                root.send_event(protocol.event.ClientMessage(window=win,client_type=self.d.intern_atom('_NET_WM_STATE'),data=(32,[1,self.d.intern_atom('_NET_WM_STATE_FULLSCREEN'),0,2,0])),event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask)
                root.send_event(protocol.event.ClientMessage(window=win,client_type=self.d.intern_atom('_NET_ACTIVE_WINDOW'),data=(32,[2,X.CurrentTime,0,0,0])),event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask);self.d.flush();return True
        return False
    def select(self,state):
        if state.get('estop') or state.get('health',{}).get('broken'):return
        req=state.get('application_request') or {}
        explicit=(bool(req.get('id')) and req['id']!=self.last_request
                  and req.get('context')==state.get('context')
                  and 0<=time.monotonic_ns()-req.get('src_ns',0)<=8_000_000_000
                  and state.get('state') not in ('BOOT','DEGRADED','CALIBRATING'))
        if self.pending and not explicit:
            if state.get('state')=='CALIBRATING' or state.get('context')!=self.context:
                self.pending=False;self.status['status']='cancelled';return
            if self._selected():
                self.pending=False;self.status.update(status='active',window_id=self.window_id);return
            if time.monotonic()>self.deadline:
                self.pending=False;self.error='应用窗口未能切换，请再次点击';self.status.update(status='failed',detail=self.error);return
        if not explicit and not self.pending and (state.get('state') not in ('IDLE','POINTING','WRITING') or not state.get('calibrated')):return
        context=state['context']
        if context=='DESKTOP' and state.get('layer')=='WRITE':context='DEMO'
        if context==self.context and not explicit and not self.pending:return
        if explicit or context!=self.context:
            self.attempt+=1
            self.last_request=req.get('id');self.pending=True;self.deadline=time.monotonic()+8;self.focus_after=0;self.window_id=None
            self.status=dict(request_id=req.get('id'),context=context,status='opening')
        self.context=context;self.error=''
        if time.monotonic()<self.focus_after:return
        self.focus_after=time.monotonic()+.2
        if self._focus(context):return
        proc=self.processes.get(context)
        if context in ('DEMO','BASIC'):
            if self.launched_attempt.get(context)==self.attempt:return
        elif proc and proc.poll() is None:return
        try:
            cpu_mask=','.join(map(str,self.c.get('applications',{}).get('cpu_affinity',[0,1])))
            cwd=ROOT
            if context in ('DEMO','BASIC'):
                browser=shutil.which('chromium') or shutil.which('chromium-browser')
                if not browser:raise RuntimeError('Chromium is not installed')
                cmd=['taskset','-c',cpu_mask,browser,'--class='+('HmiMedical' if context=='DEMO' else 'HmiBasic'),'--app=http://127.0.0.1:'+str(self.c['console']['port'])+('/demo#' if context=='DEMO' else '/basic#')+((Path(self.c['paths']['run'])/'console.token').read_text().strip() if (Path(self.c['paths']['run'])/'console.token').exists() else ''),'--start-fullscreen','--no-first-run']
                if os.geteuid()==0:cmd=['taskset','-c',cpu_mask,'runuser','-u','linaro','--','env','DISPLAY='+os.environ.get('DISPLAY',':0'),'XAUTHORITY=/home/linaro/.Xauthority',*cmd]
            elif context=='GAME':
                game=Path(self.c['paths']['game'])
                if not (game/'build-arm64/freeciv-gtk3.22').exists():raise RuntimeError('Build the included native Freeciv project first: build-rk3576.sh')
                # Same launch.py, native game and nice/I/O policy as the
                # standalone shell entry; HMI reserves CPU2/3 for DMA polling.
                # The shell entry hardcodes 0-3, so do not nest it under taskset.
                cwd=game
                cmd=['taskset','-c',cpu_mask,'nice','-n','10','ionice','-c','3','python3',str(game/'launch.py'),'--build','build-arm64']
                if os.geteuid()==0:cmd=['taskset','-c',cpu_mask,'runuser','-u','linaro','--','env','DISPLAY='+os.environ.get('DISPLAY',':0'),'XAUTHORITY=/home/linaro/.Xauthority',*cmd]
            else:return
            log=open(Path(self.c['paths']['logs'])/(context.lower()+'_launcher.log'),'ab');self.logs.append(log)
            self.processes[context]=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=cwd)
            self.launched_attempt[context]=self.attempt
            # Cold Chromium/GTK startup can exceed the focus-only deadline.
            # Do not re-launch or re-send actions while waiting for its real window.
            self.deadline=time.monotonic()+25
        except (OSError,RuntimeError) as exc:
            self.error=str(exc);self.pending=False;self.status.update(status='failed',detail=self.error)
    def close(self):
        # Application processes are in the systemd service cgroup. They receive
        # SIGTERM with their owner; no external browser or game is killed here.
        for log in self.logs:log.close()
