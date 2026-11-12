"""RK-local console and gesture dispatcher. No camera, NPU or FPGA descriptor."""
import argparse,hashlib,hmac,importlib.util,json,os,queue,secrets,sys,threading,time,shutil,subprocess,math
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
from gesture_actions import GestureActions,DEFAULTS,ACTIONS,validate_bindings,action_context

HERE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def save(p,v):
    p=Path(p);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(v,ensure_ascii=False),encoding='utf8');os.replace(tmp,p)
def ticks(pid):return int(Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19])

class Console:
    def __init__(self,config):
        self.cfg=config;self.token=secrets.token_urlsafe(32);self.jobs=queue.Queue(8);self.events=[];self.lock=threading.RLock()
        self.mapping_path=Path(config['state_directory'])/'gesture_bindings.json';self.mapping_path.parent.mkdir(parents=True,exist_ok=True)
        self.bindings=validate_bindings(read(self.mapping_path)) if self.mapping_path.exists() else dict(DEFAULTS)
        self.enabled=True;self.router=GestureActions();self.receiver=None;self.stopped=threading.Event()
        self.demo=dict(slide=0,zoom=1.,focus=False,snap=True,revision=0)
        self.action_serial=0;self.browser=None
    def health(self):
        try:
            b=read(self.cfg['binding']);s=read(Path(b['root'])/'lifecycle/video_owner_state.json')
            if b['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():raise ValueError('board_rebooted')
            if s['phase'] not in ('FEATURE_RUNNING','FEATURE_KEEP_RUNNING'):raise ValueError('model_not_running: '+s['phase'])
            h=read(self.cfg['telemetry']);pid=h['relay_identity']
            if ticks(pid['pid'])!=pid['start_ticks'] or h['boot_id']!=b['boot_id']:raise ValueError('relay_identity_changed')
            if h['controller']!={k:b['owner'][k] for k in ('pid','start_ticks')}:raise ValueError('owner_changed')
            if not 0<=time.monotonic_ns()-h['timestamp_ns']<=500_000_000:raise ValueError('telemetry_stale')
            return h
        except (OSError,KeyError,TypeError,ValueError) as e:return dict(error=str(e),interaction_ui=None,registrations=[])
    def get_receiver(self):
        if self.receiver is None:
            p=Path(self.cfg['receiver']);sys.path.insert(0,str(p.parent))
            spec=importlib.util.spec_from_file_location('_html_receiver',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
            receiver_cfg=read(self.cfg['receiver_config']);receiver_cfg['_config_path']=self.cfg['receiver_config']
            self.receiver=m.Receiver(receiver_cfg);self.receiver.active=True
        return self.receiver
    def owner(self,body):
        cfg=read(self.cfg['receiver_config']);p=Path(cfg['application_client_source']['path'])
        if hashlib.sha256(p.read_bytes()).hexdigest()!=cfg['application_client_source']['sha256']:raise ValueError('client_source_changed')
        argv=[sys.executable,'-B',str(HERE/'web_owner_command.py'),'--binding',self.cfg['binding']]
        if cfg.get('control_sudo'):argv=['sudo','-n',*argv]
        done=subprocess.run(argv,input=json.dumps(body),capture_output=True,text=True,timeout=55.)
        if done.returncode:raise ValueError(done.stderr[-600:] or done.stdout[-600:])
        result=json.loads(done.stdout)
        # Propagate nested rejection; transport acknowledgement is not success.
        node=result
        for _ in range(8):
            if not isinstance(node,dict):break
            if node.get('ok') is False or node.get('accepted') is False:raise ValueError(str(node.get('error') or node.get('reason') or node))
            node=node.get('result',node.get('value'))
        return result
    def dispatch(self,job):
        action=job['action']
        if action in ('pointer','click','key'):
            # Explicit PC control targets the HDMI desktop, including the
            # medical viewer. The X root may also contain a taller DSI monitor.
            receiver=self.get_receiver();receiver.identity()
            if action=='key':
                key=job.get('key')
                if key not in ('Return','Escape','Tab','space','Up','Down','Left','Right','F1',*map(str,range(10))):raise ValueError('unsupported key')
                subprocess.run(['xdotool','key','--clearmodifiers',key],env=receiver.env,check=True,timeout=2)
            else:
                xy=[job.get(k) for k in ('x','y')]
                if any(type(v) not in (float,int) or not math.isfinite(v) or not 0<=v<=1 for v in xy):raise ValueError('normalized HDMI point required')
                if action=='click' and (type(job.get('button')) is not int or job['button'] not in (1,3)):raise ValueError('left/right click only')
                proof=read(self.cfg['desktop_proof']);size=proof['screen_size'];origin=proof['screen_origin']
                if proof['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():raise ValueError('desktop boot changed')
                subprocess.run(['xdotool','mousemove',*[str(o+round(v*(s-1))) for o,v,s in zip(origin,xy,size)]],env=receiver.env,check=True,timeout=2)
                if action=='click':
                    subprocess.run(['xdotool','click',str(job['button'])],env=receiver.env,check=True,timeout=2)
            return dict(input=action,target='HDMI_active_window',source='PC_MANUAL')
        if action=='demo_open':
            receiver=self.get_receiver()
            if self.browser is not None and self.browser.poll() is None:
                ids=subprocess.check_output(['xdotool','search','--onlyvisible','--pid',str(self.browser.pid)],env=receiver.env,text=True,timeout=2).split()
                if ids:subprocess.run(['xdotool','windowactivate','--sync',ids[-1]],env=receiver.env,check=True,timeout=2)
                return dict(open=True,pid=self.browser.pid)
            binary=shutil.which('chromium') or shutil.which('chromium-browser')
            if not binary:raise RuntimeError('Chromium unavailable on RK')
            url=f"http://127.0.0.1:{self.cfg.get('port',8765)}/demo#"+self.token
            self.browser=subprocess.Popen([binary,'--no-first-run','--kiosk','--disable-session-crashed-bubble',
                '--user-data-dir='+str(Path(self.cfg['state_directory'])/'browser'),url],env=receiver.env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            return dict(open=True,pid=self.browser.pid)
        if action.startswith('demo_'):
            with self.lock:
                d=self.demo
                if action=='demo_next':d['slide']=(d['slide']+1)%3;d['zoom']=1.
                elif action=='demo_previous':d['slide']=(d['slide']-1)%3;d['zoom']=1.
                elif action=='demo_zoom_in':d['zoom']=min(5.,d['zoom']*1.25)
                elif action=='demo_zoom_out':d['zoom']=max(1.,d['zoom']/1.25)
                elif action=='demo_focus':d['focus']=not d['focus']
                elif action=='demo_snap':d['snap']=not d['snap']
                elif action=='demo_reset':d.update(zoom=1.,focus=False,snap=True)
                d['revision']+=1
                return dict(d)
        if action in ('single','dual'):return self.owner(dict(command='people_mode',mode=action))
        for prefix in ('page','register','unregister'):
            if action in (prefix+'1',prefix+'2'):return self.owner(dict(command=prefix,slot=int(action[-1])))
        return self.get_receiver().dispatch(job)
    def submit(self,job):
        if job.get('action') not in ACTIONS+('pointer','click','key','takeover','release','unregister1','unregister2','visual','trajectory'):raise ValueError('unsupported action')
        with self.lock:self.action_serial+=1;job=dict(job,id=self.action_serial)
        self.jobs.put_nowait(job);return dict(queued=True,id=job['id'])
    def worker(self):
        while not self.stopped.is_set():
            try:job=self.jobs.get(timeout=.2)
            except queue.Empty:continue
            result=dict(id=job['id'],action=job['action'],source=job.get('source','PC'),time=time.time())
            try:
                if job.get('source')=='gesture':
                    h=self.health();ctx=action_context(h)
                    if not self.enabled or h.get('error') or ctx!=tuple(job['context']) or time.monotonic_ns()-job['timestamp_ns']>500_000_000:raise ValueError('gesture_expired_before_action')
                    if (h.get('filtered_gaze') or {}).get('mode') in ('CALIBRATE','VALIDATE'):
                        raise ValueError('标定/验证期间暂停手势快捷动作，避免重复标定或切走窗口')
                result.update(ok=True,result=self.dispatch(job))
            except Exception as e:result.update(ok=False,error=str(e)[:600])
            with self.lock:self.events=(self.events+[result])[-12:]
            self.jobs.task_done()
    def gesture_loop(self):
        while not self.stopped.wait(.05):
            with self.lock:enabled=self.enabled;bindings=dict(self.bindings)
            if not enabled:self.router=GestureActions();continue
            h=self.health()
            try:
                event=self.router.update(h,time.monotonic_ns(),bindings)
                if event:self.submit(dict(event,source='gesture'))
            except (ValueError,KeyError,TypeError,queue.Full):pass
    def snapshot(self):
        with self.lock:
            return dict(health=self.health(),bindings=dict(self.bindings),enabled=self.enabled,events=list(self.events),demo=dict(self.demo),actions=ACTIONS)

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);args=p.parse_args();cfg=read(args.config);c=Console(cfg)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,status,value,ctype='application/json'):
            raw=json.dumps(value,ensure_ascii=False).encode() if ctype=='application/json' else value
            self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def authenticated(self):return hmac.compare_digest(self.headers.get('X-Console-Token',''),c.token)
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/api/state':
                if not self.authenticated():return self.respond(403,dict(error='token_required'))
                return self.respond(200,c.snapshot())
            files={'/':('index.html','text/html; charset=utf-8'),'/demo':('medical.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8'),'/medical.jpg':('medical.jpg','image/jpeg'),'/slides.pptx':('slides.pptx','application/vnd.openxmlformats-officedocument.presentationml.presentation'),'/medical_source.json':('medical_source.json','application/json; charset=utf-8')}
            if path not in files:return self.respond(404,dict(error='not_found'))
            name,ctype=files[path]
            try:return self.respond(200,(HERE/name).read_bytes(),ctype)
            except OSError:return self.respond(404,dict(error='asset_missing'))
        def do_POST(self):
            if not self.authenticated():return self.respond(403,dict(error='token_required'))
            try:
                n=int(self.headers.get('Content-Length',0))
                if not 0<n<=8192:raise ValueError('bounded JSON required')
                body=json.loads(self.rfile.read(n));path=urlsplit(self.path).path
                if path=='/api/action':return self.respond(202,c.submit(body))
                if path=='/api/bindings':
                    value=validate_bindings(body['bindings'])
                    if type(body['enabled']) is not bool:raise ValueError('boolean enabled required')
                    with c.lock:save(c.mapping_path,value);c.bindings=value;c.enabled=body['enabled'];c.router=GestureActions()
                    return self.respond(200,dict(saved=True))
                return self.respond(404,dict(error='not_found'))
            except (ValueError,KeyError,TypeError,queue.Full) as e:return self.respond(400,dict(error=str(e)))
    server=ThreadingHTTPServer(('127.0.0.1',int(cfg.get('port',8765))),Handler)
    save(Path(cfg['state_directory'])/'console_connection.json',dict(port=server.server_port,token=c.token,pid=os.getpid(),start_ticks=ticks(os.getpid())))
    os.chmod(Path(cfg['state_directory'])/'console_connection.json',0o600)
    for fn in (c.worker,c.gesture_loop):threading.Thread(target=fn,daemon=True).start()
    try:server.serve_forever()
    finally:c.stopped.set();server.server_close()
if __name__=='__main__':main()
