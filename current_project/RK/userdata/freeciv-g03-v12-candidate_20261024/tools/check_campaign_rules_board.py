"""Bounded native server rules smoke test on a separate local port."""
import json,shlex,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'evidence/campaign_rules_v3';H=R.parent/'tmp/freeciv_rk.py'
BODY=r'''
import json,os,subprocess,time
from pathlib import Path
r=Path('/userdata/freeciv-rk3576-gaze-demo');o=r/'.maintenance/campaign_rules_v3';assert not o.exists();o.mkdir()
env=dict(os.environ,FREECIV_DATA_PATH=str(r/'upstream/freeciv-3.2.6/data'))
with (o/'server.log').open('wb') as log:
 p=subprocess.Popen(['taskset','-c','0-3','nice','-n','15',str(r/'build-arm64/freeciv-server'),'-p','5558','-b','127.0.0.1','-f',str(r/'scenario/border-keep.sav')],cwd=r,env=env,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,text=True)
 print('RULES_ORIGINAL_SERVER',p.pid,flush=True)
 try:
  time.sleep(1);p.stdin.write('set minplayers 0\nset timeout -1\nset endturn 12\nstart\n');p.stdin.flush()
  deadline=time.monotonic()+15
  while p.poll() is None and time.monotonic()<deadline:
   text=(o/'server.log').read_text(errors='replace')
   if 'CAMPAIGN_INIT_V2' in text and ('CAMPAIGN_REINFORCE' in text or 'Scenario victory' in text):break
   time.sleep(.1)
 finally:
  if p.poll() is None:
   p.stdin.write('quit\n'.replace('\\n','\n'));p.stdin.flush()
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
 text=(o/'server.log').read_text(errors='replace')
 result=dict(status='NATIVE_RULES_PROBE_SAVED',server_returncode=p.returncode,init='CAMPAIGN_INIT_V2' in text,
  income_lines=text.count('CAMPAIGN_INCOME'),reinforcement_lines=text.count('CAMPAIGN_REINFORCE'),
  lua_error=('Lua error' in text or 'Lua script error' in text or 'stack traceback' in text),
  actual_GUI_or_human_play_accepted=False,original_Popen_waited=True)
 (o/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
 print(text[-6000:],flush=True)
'''
def main():
    assert not O.exists();O.mkdir(parents=True);script=O/'board.py';script.write_text(BODY,encoding='utf8')
    subprocess.run([sys.executable,'-X','utf8','-B',str(H),'--put',str(script),'/home/linaro/pcie_fix_20261003/campaign_rules_v3.py'],check=True)
    with (O/'actual.stdout').open('xb') as log:
        subprocess.run([sys.executable,'-X','utf8','-B',str(H),'--command','python3 -B /home/linaro/pcie_fix_20261003/campaign_rules_v3.py','--timeout','40'],stdout=log,stderr=subprocess.STDOUT,check=True)
    print((O/'actual.stdout').read_text(encoding='utf8'),flush=True)
if __name__=='__main__':main()
