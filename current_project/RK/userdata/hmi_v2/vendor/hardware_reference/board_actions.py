"""Existing PCIe lifecycle plus actual DSI start; no model lifecycle here."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(value,message):
    if not value:raise RuntimeError(message)
def save(p,value):p.write_text(json.dumps(value,indent=2)+'\n')


def dispatch(action,cfg,out):
    out=Path(out);need(not out.exists(),'New action output required');out.mkdir()
    need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==cfg['boot_id'],'Boot changed')
    for row in cfg['files']:need(sha(row['path'])==row['sha256'],'Pinned input changed: '+row['path'])
    spec=importlib.util.spec_from_file_location('_video_existing_pcie_lifecycle',cfg['capture_actions_module'])
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    old.APP=Path(cfg['runtime']['app'])
    public=dict(boot_id=cfg['boot_id'],remote_files={r['path']:r['sha256'] for r in cfg['files']},capture_seconds_per_stage=6)
    old.environment(public)
    need(not any(old.owners().values()),'Main/capture must be normally closed before hardware change')
    old.camera_fds()
    if action=='quiesce':value=old.quiesce(public,out)
    elif action=='reprobe':
        value=old.reprobe(public,out)
        pci=Path('/sys/bus/pci/devices/0000:21:00.0')
        value.update(link_speed=(pci/'current_link_speed').read_text().strip(),link_width=(pci/'current_link_width').read_text().strip())
        need(value['link_speed'].startswith('5.0') and value['link_width']=='1','Unexpected PCIe link')
    elif action in ('start_panel','stop_panel'):
        requests=[('pad','quiet'),('clock','off')]
        if action=='start_panel':requests += [('pad','drive'),('clock','on')]
        rows=[]
        for kind,mode in requests:
            old.camera_fds();need(not any(old.owners().values()),'Runtime started during panel control')
            binary=cfg['dsi_drive_control' if kind=='pad' else 'dsi_clock_control']
            p=subprocess.run([binary,mode],capture_output=True,timeout=5)
            (out/(kind+'_'+mode+'.stdout')).write_bytes(p.stdout)
            (out/(kind+'_'+mode+'.stderr')).write_bytes(p.stderr)
            row=json.loads(p.stdout)
            need(p.returncode==0 and row['MMIO_writes']==1 and row['capture_CTRL']&1==0,'Panel control not accepted: '+repr(row))
            expected=(0x44534900 if kind=='pad' else 0x44534300) | int(mode in ('drive','on'))
            need(row['after']==expected,'Panel control readback mismatch')
            rows.append(dict(kind=kind,mode=mode,result=row))
            save(out/'partial.json',rows)
        value=dict(status='PANEL_DRIVEN_LP_BEFORE_PLL_START' if action=='start_panel' else 'PANEL_QUIET_AND_CLOCK_OFF',
            controls=rows,optical_pixels_accepted=False)
    else:raise ValueError('Unsupported video hardware action')
    result=dict(action=action,ok=True,value=value,boot_id=cfg['boot_id'])
    save(out/'result.json',result);print(json.dumps(result),flush=True)
    return value
