#!/bin/bash
set -euo pipefail
python3 - <<'PY'
import json,os,subprocess
from pathlib import Path
out={}
for key,cmd in [
 ('ip',['hostname','-I']),('kernel',['uname','-r']),
 ('source_format_before',['v4l2-ctl','-d','/dev/v4l-subdev4','--get-subdev-fmt=pad=0']),
 ('source_try_only_720x128',['v4l2-ctl','-d','/dev/v4l-subdev4','--try-subdev-fmt=pad=0,width=720,height=128,code=0x2008']),
 ('source_format_after',['v4l2-ctl','-d','/dev/v4l-subdev4','--get-subdev-fmt=pad=0']),
 ('source_sizes',['v4l2-ctl','-d','/dev/v4l-subdev4','--list-subdev-framesizes=pad=0,code=0x2008'])]:
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=10);out[key]={'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
driver=Path('/sys/bus/i2c/devices/9-001a/driver')
out['driver']=str(driver.resolve())
mod=driver/'module';out['driver_module']=str(mod.resolve()) if mod.exists() else 'BUILTIN_OR_NO_MODULE_LINK'
if mod.exists():
 root=mod.resolve();pars=root/'parameters';out['module_parameters']={q.name:q.read_text().strip() for q in pars.iterdir()} if pars.exists() else {}
base=Path('/home/linaro/t3_basic6');out['test_project_entries']=sorted(q.name for q in base.iterdir()) if base.exists() else []
for q in [Path('/lib/modules')/os.uname().release/'build',Path('/usr/src')]:
 out[str(q)]=str(q.resolve()) if q.exists() else 'MISSING'
out['scope']='READONLY: GET/ENUM/TRY subdevice state; no ACTIVE format, GPIO/boot/kernel module or board programming changed.'
print(json.dumps(out,indent=2))
PY
