from pathlib import Path
import compileall,json,subprocess,sys,time,os
ROOT=Path(__file__).resolve().parents[1]
def main():
    start=time.monotonic();checks=[]
    (ROOT/'docs/evidence').mkdir(parents=True,exist_ok=True)
    for command in [[sys.executable,str(ROOT/'tools/hmi'),'verify'],[sys.executable,'-m','pytest','-q','tests']]:
        p=subprocess.run(command,cwd=ROOT,text=True,encoding='utf-8',errors='replace',env=dict(os.environ,PYTHONUTF8='1'),capture_output=True);print(p.stdout);print(p.stderr)
        checks.append({'command':command,'exit_code':p.returncode,'output':p.stdout+p.stderr})
    for folder in ['core','vision','adapters','ui','console','tools']:
        checks.append({'syntax':folder,'ok':compileall.compile_dir(ROOT/folder,quiet=1)})
    ok=all(c.get('exit_code',0)==0 and c.get('ok',True) for c in checks)
    report={'status':'PASS' if ok else 'FAIL','scope':'LOCAL_ONLY; no RKNN inference, hardware or human validation','seconds':time.monotonic()-start,'checks':checks}
    (ROOT/'docs/evidence/local_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
