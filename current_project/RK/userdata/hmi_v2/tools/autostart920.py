#!/usr/bin/env python3
"""Standalone board startup. No host PC, network, or JTAG dependency."""
from pathlib import Path
import json,os,subprocess,time,urllib.request

ROOT=Path('/userdata/hmi_v2')
PY='/userdata/gaze_model_migration_v1_20261014/app_venv/bin/python'
LOADER=Path('/home/linaro/pcie_fix_20261003/sgdma_wb_trial_20261024_v2/loader/pcie_setup.sh')
env=dict(os.environ,DISPLAY=':0',XAUTHORITY='/home/linaro/.Xauthority')
os.chdir(ROOT)
# The tested setup enumerates PCIe and loads the matching local modules.
# Never reload modules under an existing capture process.
active=subprocess.run(['systemctl','is-active','--quiet','hmi-fpga-io']).returncode==0
if not active:
    subprocess.run(['bash',str(LOADER)],check=True,timeout=75,env=env)
deadline=time.monotonic()+90
while True:
    probe=subprocess.run(['xdpyinfo'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)
    if probe.returncode==0:break
    if time.monotonic()>deadline:raise TimeoutError('Local HDMI X11 session unavailable')
    time.sleep(1)
subprocess.run([PY,'-B','tools/hmi','up'],check=True,timeout=130,env=env)
applications=[]
for command,context in [('app_game','GAME'),('app_demo','DEMO')]:
    deadline=time.monotonic()+30
    while True:
        try:
            token=Path('/run/hmi/console.token').read_text().strip()
            req=urllib.request.Request('http://127.0.0.1:8766/api/command',
                data=json.dumps({'command':command}).encode(),
                headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=4) as response:
                reply=json.loads(response.read())
            break
        except (OSError,ValueError):
            if time.monotonic()>deadline:raise
            time.sleep(1)
    while time.monotonic()<deadline:
        with urllib.request.urlopen('http://127.0.0.1:8766/api/state',timeout=4) as response:
            state=json.loads(response.read())
        app=state.get('application',{})
        if app.get('context')==context and app.get('status')=='active':
            applications.append(context);break
        time.sleep(.5)
    print('STANDALONE920_APPLICATION',context,'active' if context in applications else 'requested',flush=True)
Path('/run/hmi/standalone920.json').write_text(json.dumps({
    'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
    'started_ns':time.monotonic_ns(),'default_application':'DEMO','active_applications':applications,'host_pc_required':False}))
