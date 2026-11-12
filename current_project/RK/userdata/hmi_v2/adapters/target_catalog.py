"""Application geometry snapshots; no camera access or input injection."""
import json,os,subprocess,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from core.config import ROOT
from core.targets import demo_targets,valid_target

class TargetCatalog:
    def __init__(self,display,geometry):
        self.d=display;self.geo=geometry;self.pool=ThreadPoolExecutor(max_workers=1)
        self.job=None;self.rows=[];self.pid=None;self.stamp=0;self.started=0;self.error=''
    def active_pid(self):
        from Xlib import X
        root=self.d.screen().root
        p=root.get_full_property(self.d.intern_atom('_NET_SHOWING_DESKTOP'),X.AnyPropertyType)
        if p and p.value[0]:
            for proc in Path('/proc').iterdir():
                try:
                    if (proc/'comm').read_text().strip()=='xfdesktop':return int(proc.name)
                except (OSError,ValueError):pass
        p=root.get_full_property(self.d.intern_atom('_NET_ACTIVE_WINDOW'),X.AnyPropertyType)
        if not p or not p.value[0]:return None
        win=self.d.create_resource_object('window',int(p.value[0]));p=win.get_full_property(self.d.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
        return int(p.value[0]) if p and p.value[0] else None
    @staticmethod
    def read_desktop(pid):
        env={}
        for proc in Path('/proc').iterdir():
            try:
                if (proc/'comm').read_text().strip()!='xfce4-session':continue
                values=dict(v.split('=',1) for v in (proc/'environ').read_bytes().decode().split('\0') if '=' in v)
                env={k:values[k] for k in ('DISPLAY','XAUTHORITY','DBUS_SESSION_BUS_ADDRESS') if k in values};break
            except (OSError,ValueError):continue
        if 'DBUS_SESSION_BUS_ADDRESS' not in env:raise RuntimeError('桌面辅助功能会话未连接')
        command=['/usr/bin/python3',str(ROOT/'adapters/accessible_targets.py'),str(pid)]
        if os.geteuid()==0:command=['runuser','-u','linaro','--','env']+[k+'='+v for k,v in env.items()]+command
        result=subprocess.run(command,capture_output=True,timeout=3,env={**os.environ,**env})
        if result.returncode:raise RuntimeError('当前窗口未提供辅助功能目标')
        return json.loads(result.stdout)
    def snapshot(self,context,demo,game,enabled):
        geo=self.geo;size=[geo['width'],geo['height']];origin=[geo['x'],geo['y']];rows=[];detail=''
        if context=='DEMO':rows=demo_targets(demo,size)
        elif context=='GAME' and game:
            rect=game['map']
            for t in game.get('targets',[]):
                key=f"game:{t['kind']}:{t['id']}:{t['arg']}";x=rect[0]+t['x']-origin[0];y=rect[1]+t['y']-origin[1]
                labels={10:'战役模式',11:'开始战役',12:'退出游戏'}
                rows.append(dict(id=key,label=t.get('label') or labels.get(t['kind'],'游戏目标 '+str(t['id'])),
                                 rect=[x-float(t.get('width',40))/2,y-float(t.get('height',40))/2,float(t.get('width',40)),float(t.get('height',40))],confidence=1.,action='game.click',native={k:t[k] for k in ('kind','id','arg')}))
        elif context=='DESKTOP' and enabled:
            try:pid=self.active_pid()
            except Exception:pid=None
            now=time.monotonic()
            if pid!=self.pid:self.pid=pid;self.rows=[];self.stamp=0
            if self.job and self.job.done():
                try:
                    got=self.job.result()
                    if self.job_pid==pid:self.rows=got;self.stamp=now;self.error=''
                except Exception as exc:self.rows=[];self.error=str(exc)
                self.job=None
            if pid and self.job is None and now-self.started>=.4:
                self.started=now;self.job_pid=pid;self.job=self.pool.submit(self.read_desktop,pid)
            if now-self.stamp<2:
                for row in self.rows:
                    row=dict(row);x,y,w,h=row['rect'];row['rect']=[x-origin[0],y-origin[1],w,h];rows.append(row)
            detail=self.error or ('正在读取桌面控件' if not rows else '')
        rows=[r for r in rows if valid_target(r,size)]
        return dict(context=context,targets=rows,screen_size=size,screen_origin=origin,detail=detail or ('当前应用没有可操作目标' if not rows else ''))
    def close(self):self.pool.shutdown(wait=False,cancel_futures=True)
