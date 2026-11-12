"""Build target ARM64 artifacts using an explicitly installed Zig compiler."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,subprocess,sys,time,shutil
R=Path(__file__).resolve().parents[1];N=R/'native/fpga_io';V=R/'vendor';E=R/'docs/evidence'
def main():
 p=argparse.ArgumentParser();p.add_argument('--zig',required=True);a=p.parse_args();E.mkdir(parents=True,exist_ok=True)
 spec=importlib.util.spec_from_file_location('native_build',N/'build.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);source=m.generate()
 # This cross target is the RK3576 release, whose CRC32 HWCAP is verified.
 common=[a.zig,'cc','-target','aarch64-linux-gnu','-march=armv8-a+crc','-O2','-std=c11','-Wall','-Wextra','-Werror','-pthread','-I'+str(V/'gaze_app'),'-I'+str(V/'twb_native'),'-I'+str(N)]
 commands=[common+[str(source),str(V/'gaze_app/async_output.c'),str(N/'ui_transaction.c'),str(N/'ring.c'),'-o',str(N/'fpga_io.aarch64')],
  [a.zig,'cc','-target','aarch64-linux-gnu','-march=armv8-a+crc','-O2','-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC',str(N/'ring.c'),'-o',str(N/'libring.aarch64.so')],
  [a.zig,'cc','-target','x86_64-windows-gnu','-O2','-std=c11','-Wall','-Wextra','-Werror','-shared',str(N/'ring.c'),'-o',str(N/'ring_test.dll')],
  [a.zig,'cc','-target','x86_64-windows-gnu','-O2','-std=c11','-Wall','-Wextra','-Werror',str(N/'test_panel.c'),'-o',str(N/'panel_test.exe')],
  [a.zig,'cc','-target','x86_64-windows-gnu','-O2','-std=c11','-Wall','-Wextra','-Werror','-shared','-I'+str(V/'twb_native'),str(N/'ui_transaction.c'),'-o',str(N/'ui_test.dll')]]
 rows=[]
 for i,cmd in enumerate(commands):
  start=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True);(E/f'native_build_{i}.log').write_text(r.stdout+r.stderr,encoding='utf-8')
  rows.append({'command':cmd,'returncode':r.returncode,'seconds':time.monotonic()-start});print(f'native build {i}: {r.returncode}',flush=True)
  if r.returncode:print(r.stderr);break
 if all(r['returncode']==0 for r in rows) and len(rows)==len(commands):
  shutil.copy2(N/'fpga_io.aarch64',N/'fpga_io');shutil.copy2(N/'libring.aarch64.so',N/'libring.so')
 files={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in [N/'fpga_io.aarch64',N/'libring.aarch64.so',N/'ring_test.dll',N/'ui_test.dll',N/'panel_test.exe'] if f.exists()}
 (E/'native_build.json').write_text(json.dumps({'commands':rows,'sha256':files,'executed_on_ARM64':False},indent=2),encoding='utf-8')
 return int(any(r['returncode'] for r in rows))
if __name__=='__main__':raise SystemExit(main())
