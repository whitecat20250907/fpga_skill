"""Render the real medical canvas against synthetic HMI state, locally only."""
import argparse,json,re,subprocess,sys,tempfile,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from console.medical import html
from console.server import HTML

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--browser',required=True);p.add_argument('--node',required=True);a=p.parse_args()
    evidence=ROOT/'docs/evidence';checks=[];page=[0];requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path.startswith('/api/state'):
                body=json.dumps({'hmi_fresh':page[0]!=3,'demo':{'page':page[0]%3,'zoom':1.25,'focus':page[0]==1,'snap':True,'anchor':[.62,.5]},'hmi':{'state':'POINTING','cursor':{'xy':[800,360],'screen_size':[1280,720],'valid':True,'frozen':False}}}).encode();kind='application/json'
            elif self.path=='/medical.jpg':body=(ROOT/'vendor/web_demo/medical.jpg').read_bytes();kind='image/jpeg'
            else:
                capture=b'<script>window.addEventListener("error",e=>document.documentElement.setAttribute("data-js-error",e.message));</script>'
                body=html().replace(b'<script>',capture+b'<script>',1);kind='text/html; charset=utf-8'
            self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*_):pass
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='hmi_web_') as tmp:
            tmp=Path(tmp)
            for label,text in [('medical',html().decode()),('console',HTML)]:
                for i,code in enumerate(re.findall(r'<script>(.*?)</script>',text,re.S)):
                    script=tmp/f'{label}{i}.js';script.write_text(code,encoding='utf-8')
                    r=subprocess.run([a.node,'--check',str(script)],capture_output=True,text=True,check=True)
                    checks.append({'name':label+' JS syntax','ok':r.returncode==0})
            for index in range(4):
                page[0]=index;requests.clear();shot=evidence/f'medical_synthetic_{index}.png'
                cmd=[a.browser,'--headless','--disable-gpu','--no-first-run','--disable-extensions','--hide-scrollbars',
                     '--user-data-dir='+str(tmp/f'profile{index}'),'--window-size=1280,720','--virtual-time-budget=2500',
                     '--run-all-compositor-stages-before-draw','--screenshot='+str(shot),'--dump-dom',f'http://127.0.0.1:{http.server_port}/demo']
                r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45,
                                 creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                (evidence/f'medical_synthetic_{index}.log').write_text(r.stderr,encoding='utf-8')
                error=re.search(r'data-js-error="([^"]*)"',r.stdout)
                status=re.search(r'<div id="status">([^<]*)</div>',r.stdout)
                expected='实时眼动' if index<3 else '等待当前人物完成标定'
                ok=r.returncode==0 and shot.exists() and not error and '/api/state' in requests and '/medical.jpg' in requests and status is not None and status[1].startswith(expected)
                checks.append({'name':f'medical page {index}' if index<3 else 'stale engine state disables live gaze','ok':ok,'status_text':status[1] if status else None,'runtime_error':error.group(1) if error else None,'requests':list(requests)})
    finally:http.shutdown();http.server_close()
    report={'status':'PASS' if all(c['ok'] for c in checks) else 'FAIL','scope':'Windows headless browser with synthetic state; no live gaze or X11 validation','checks':checks}
    (evidence/'web_render.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
