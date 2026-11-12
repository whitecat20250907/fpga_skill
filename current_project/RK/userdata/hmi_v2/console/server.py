"""Loopback management UI. All mutations are token authenticated and queued to engine."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import hmac,json,secrets,threading,time,mimetypes,errno
from queue import Queue,Empty
from urllib.parse import urlsplit
from core.config import ROOT,load
from core.clock import fresh
from core.hmibus import Subscriber,Publisher
from core.service import Service
from .medical import html as medical_html
from .comparison import Comparison
from core.targets import medical_spec,medical_view
from core.snapshot_file import SnapshotReader
from core.bindings import validate as validate_bindings,options,CONTEXTS,LABELS
from ui.live_preview import compact_status,compact_receipt
DEMO_COMMANDS=('demo_next','demo_previous','demo_focus','demo_snap','demo_reset','demo_rotate')

HTML='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>HMI 管理控制台</title>
<style>body{background:#0b121b;color:#e7eef4;font:18px system-ui;max-width:1000px;margin:40px auto}button{padding:14px;margin:8px;background:#61ddce;border:0;border-radius:8px}pre{white-space:pre-wrap}input{padding:12px}</style>
<h1>HMI · 眼神与手势交互</h1><p>✊ 握拳进入手势识别 → ☝ 伸食指切换轨迹识别</p>
<input id="token" type="password" placeholder="本机管理令牌"><button onclick="cmd('estop')">紧急待机</button><button onclick="cmd('resume')">恢复入座检测</button><button onclick="cmd('menu')">系统菜单</button>
<section><button onclick="cmd('single')">单人模式</button><button onclick="cmd('dual')">双人模式</button><button onclick="cmd('person1')">选择第一人</button><button onclick="cmd('person2')">选择第二人</button><button onclick="cmd('next')">下一候选 / 菜单项</button><button onclick="cmd('confirm')">确认</button><button onclick="cmd('cancel')">取消</button><button onclick="cmd('calibrate')">标定当前人</button><button onclick="cmd('use_calibration')">使用标定</button></section><a href="/demo">医学演示</a><pre id="state">正在连接…</pre><script>
async function cmd(command){await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+document.querySelector('#token').value},body:JSON.stringify({command})})}
setInterval(async()=>{try{document.querySelector('#state').textContent=JSON.stringify(await (await fetch('/api/state')).json(),null,2)}catch(e){}},250)</script></html>'''

def publish_commands(commands,state,pub,seq,clock=time.monotonic_ns):
    """Check age after dequeue: HTTP may enqueue after the polling timestamp."""
    while True:
        try:stamp,command=commands.get_nowait()
        except Empty:return seq
        now=clock()
        if not fresh(state.get('src_ns'),350,now) or not fresh(stamp,800,now):continue
        seq+=1;pub.publish(dict(src_ns=stamp,seq=seq,epoch=state['epoch'],**command))

def main():
    c=load();run=Path(c['paths']['run']);svc=Service('console',c);commands=Queue(maxsize=16)
    from core.console_auth import console_token
    token=console_token(run);snapshot={};lock=threading.Lock();comparison=Comparison();comparison_snapshot={};basic_values={}
    from .game_preview import GamePreview
    game_preview=GamePreview(c['paths']['game'])
    from .model_preview import ModelPreview
    model_preview=ModelPreview(run)
    from .basic_preview import BasicPreview
    from .process_preview import ProcessPreview
    preview_class=ProcessPreview if c.get('display',{}).get('preview_process',False) else BasicPreview
    basic_preview=preview_class(run,c.get('display',{}).get('preview_cpu'))
    preview_slots=threading.BoundedSemaphore(2)
    def preview_snapshot():
        with lock:return dict(basic_values),dict(comparison_snapshot)
    class Handler(BaseHTTPRequestHandler):
        # Frame polling reuses a connection across the SSH tunnel. Closing it
        # every image adds a channel/handshake delay larger than JPEG encoding.
        protocol_version='HTTP/1.1'
        disable_nagle_algorithm=True
        timeout=10
        def reply(self,status,data,kind='application/json',headers=None):
            raw=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            for k,v in (headers or {}).items():self.send_header(k,str(v))
            self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            route=urlsplit(self.path).path
            if route=='/':return self.reply(200,(ROOT/'console/index.html').read_bytes(),'text/html; charset=utf-8')
            if route=='/api/auth':
                ok=hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token)
                return self.reply(200 if ok else 403,{'paired':ok})
            if route=='/api/bindings':return self.reply(200,{'bindings':validate_bindings(load()['bindings']),'labels':LABELS,'options':{c:options(c) for c in CONTEXTS}})
            if route=='/api/medical/spec':return self.reply(200,medical_spec())
            if route.startswith('/assets/'):
                base=(ROOT/'console/assets').resolve();asset=(base/route[8:]).resolve()
                if base not in asset.parents:return self.reply(404,{'error':'asset not found'})
                if not asset.is_file() and asset.name in ('ct.i16','labels.u8'):
                    packed=asset.with_name(asset.name+'.gz')
                    if packed.is_file():return self.reply(200,packed.read_bytes(),'application/octet-stream',{'Content-Encoding':'gzip'})
                if not asset.is_file():return self.reply(404,{'error':'asset not found'})
                kind={'.js':'text/javascript','.glb':'model/gltf-binary','.css':'text/css'}.get(asset.suffix,mimetypes.guess_type(str(asset))[0] or 'application/octet-stream')
                return self.reply(200,asset.read_bytes(),kind)
            if route=='/basic':return self.reply(200,(ROOT/'console/basic.html').read_bytes(),'text/html; charset=utf-8')
            if route=='/api/basic/stream':
                if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):return self.reply(403,{'error':'token required'})
                from .preview_stream import serve
                return serve(self,basic_preview,preview_snapshot,lambda:svc.running,preview_slots)
            if route in ('/api/basic/frame','/api/basic/packet'):
                if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):return self.reply(403,{'error':'token required'})
                with lock:values=dict(basic_values);telemetry=dict(comparison_snapshot)
                try:
                    if route.endswith('/packet'):return self.reply(200,basic_preview.capture_packet(values,telemetry),'application/vnd.hmi.preview')
                    return self.reply(200,basic_preview.capture(values,telemetry))
                except Exception as exc:return self.reply(409,{'error':str(exc)})
            if route=='/demo':return self.reply(200,medical_html(),'text/html; charset=utf-8')
            if route=='/api/game/frame':
                if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):return self.reply(403,{'error':'token required'})
                try:
                    frame,jpeg=game_preview.capture()
                    return self.reply(200,jpeg,'image/jpeg',{'X-Frame-Id':frame['id']})
                except Exception as exc:return self.reply(409,{'error':str(exc)})
            if route=='/api/model/frame':
                if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):return self.reply(403,{'error':'token required'})
                try:return self.reply(200,model_preview.capture())
                except Exception as exc:return self.reply(409,{'error':str(exc)})
            if route=='/medical.jpg':
                f=ROOT/'vendor/web_demo/medical.jpg'
                return self.reply(200,f.read_bytes(),'image/jpeg') if f.exists() else self.reply(404,{'error':'Original image absent'})
            if route=='/api/comparison':
                with lock:data=dict(comparison_snapshot)
                return self.reply(200,data)
            if route=='/api/state':
                with lock:data=dict(snapshot)
                return self.reply(200,data)
            self.reply(404,{'error':'not found'})
        def do_POST(self):
            if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):return self.reply(403,{'error':'token required'})
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=4096:raise ValueError('length')
                data=json.loads(self.rfile.read(n));route=urlsplit(self.path).path
                request_id=secrets.token_hex(12)
                if route=='/api/medical/target':
                    target_id=data.get('target_id')
                    if not isinstance(target_id,str) or not target_id.startswith('demo:') or len(target_id)>120:raise ValueError('target id')
                    commands.put_nowait((time.monotonic_ns(),{'command':'medical_target','target_id':target_id,'request_id':request_id}))
                    return self.reply(202,{'queued':'medical_target','request_id':request_id})
                if route=='/api/game/input':
                    commands.put_nowait((time.monotonic_ns(),game_preview.command(data)))
                    return self.reply(202,{'queued':'game_input'})
                if route=='/api/bindings':
                    bindings=validate_bindings(data)
                    saved=ROOT/'config/bindings.json';temporary=saved.with_suffix('.pending')
                    with lock:
                        if commands.full():raise ValueError('queue full')
                        temporary.write_text(json.dumps(bindings,ensure_ascii=False,indent=2),'utf-8');temporary.replace(saved)
                        commands.put_nowait((time.monotonic_ns(),{'command':'bindings','bindings':bindings,'request_id':request_id}))
                    return self.reply(202,{'saved':True,'request_id':request_id,'detail':'映射已保存，等待引擎确认应用'})
                command=data.get('command') if route=='/api/command' else data.get('action')
                allowed=('estop','resume','menu','takeover','app_desktop','app_game','app_demo','app_basic','mode_next','calibrate_person1','calibrate_person2','pointer','eye_takeover','calibrate','validate','use_calibration','single','dual','person1','person2','next','confirm','cancel') if route=='/api/command' else DEMO_COMMANDS if route=='/api/action' else ()
                if command not in allowed:raise ValueError('command')
                with lock:engine_online=fresh(snapshot.get('hmi',{}).get('src_ns'),350)
                if not engine_online:return self.reply(503,{'error':'交互引擎暂未连接，请稍后再试'})
                commands.put_nowait((time.monotonic_ns(),{'command':command,'request_id':request_id}))
            except OSError as exc:
                if exc.errno in (errno.ENOSPC,errno.EDQUOT):return self.reply(507,{'error':'开发板存储空间不足，映射未保存；请清理运行记录后重试'})
                return self.reply(500,{'error':'开发板写入配置失败，映射未保存'})
            except Exception:return self.reply(400,{'error':'invalid/full command request'})
            self.reply(202,{'queued':command,'request_id':request_id})
        def log_message(self,*args):pass
    if c['console']['host'] not in ('127.0.0.1','::1'):raise ValueError('Management console must bind loopback')
    http=ThreadingHTTPServer((c['console']['host'],c['console']['port']),Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    sub=Subscriber(['hmi.state','frame.meta','sys.metrics','vision.face','vision.hands'],run=run);pub=Publisher('cmd.system',run=run);seq=0
    disk_snapshot=SnapshotReader(run/'demo.json')
    try:
        while svc.running:
            sub.poll(30);state=sub.latest('hmi.state') or {};now=time.monotonic_ns()
            try:data=disk_snapshot.read()
            except (OSError,ValueError):data={'hmi':state,'demo':{}}
            data['hmi']=state
            data['medical_view']=medical_view(data.get('demo',{}))
            data['display']={'status':compact_status(state),'receipt':compact_receipt(state.get('toast'))}
            data['hmi_fresh']=fresh(state.get('src_ns'),350,now)
            telemetry=comparison.sample(sub.values,now)
            with lock:
                snapshot.clear();snapshot.update(data)
                comparison_snapshot.clear();comparison_snapshot.update(telemetry)
                basic_values.clear();basic_values.update(sub.values)
            seq=publish_commands(commands,state,pub,seq)
            svc.heartbeat(state.get('epoch',0))
    finally:http.shutdown();http.server_close();game_preview.close();model_preview.close();basic_preview.close();sub.close();pub.close();svc.close()

if __name__=='__main__':main()
