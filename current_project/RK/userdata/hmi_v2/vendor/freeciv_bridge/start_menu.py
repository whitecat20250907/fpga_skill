"""Native GTK start page using the same five-action local input protocol.

No cameras, inference, game server, browser or background service is started
until the player explicitly confirms Start. GTK is imported only on demand.
"""
import json,math,re,socket,time
from semantic_selection import Selection

class MenuModel:
    def __init__(self,mode='campaign'):
        self.mode=mode;self.awake=False;self.pick=-1;self.last_event=0
        self.stamp=0.;self.pick_stamp=0.;self.margin=0.;self.x=self.y=0.;self.result=None
        self.selection=Selection();self.last_source=0.
    def invalidate(self):self.selection.reset();self.pick=-1;self.stamp=0.
    def sleep(self):self.awake=False;self.invalidate()
    def sample(self,x,y,targets,now=None,source=None,filtered=False):
        now=time.monotonic() if now is None else now
        if not self.awake:return
        self.selection.sample(x,y,targets,now if source is None else source,now,filtered)
        s=self.selection;self.stamp=s.stamp or 0.;self.x,self.y=s.x,s.y;self.margin=s.margin
        self.pick=s.targets[s.pick]['id'] if s.pick>=0 else -1
    def event(self,name,now=None):
        now=time.monotonic() if now is None else now
        if name=='wake':self.awake=True;self.invalidate()
        elif name in ('cancel','next'):self.sleep()
        elif name=='confirm' and self.awake and self.pick>=0 and self.selection.confirmable(now):
            picked=self.pick;self.sleep()
            if picked in (0,1):self.mode=('campaign','hotseat')[picked]
            elif picked==2:self.result=self.mode
            elif picked==3:self.result='exit'
    def datagram(self,body,targets,width,height,now=None):
        now=time.monotonic() if now is None else now
        try:text=body.decode('ascii')
        except UnicodeError:return
        m=re.fullmatch(r'event ([0-9]{1,20}) (wake|confirm|cancel|next|end|mouse)',text)
        if m:
            sequence=int(m[1])
            if sequence<=self.last_event or sequence>2**64-1:return
            self.last_event=sequence;self.selection.sync(targets);self.event(m[2],now);return
        if text.startswith('gaze'):
            try:
                if text=='gaze_lost':self.invalidate();return
                parts=text.split();source=None
                if parts[0]=='gaze2':
                    assert len(parts)==4 and re.fullmatch('[0-9]{1,19}',parts[1])
                    source=int(parts[1])/1e6;assert source>0 and 0<=now-source<=.25
                    if source<=self.last_source:return
                    x,y=map(float,parts[2:])
                else:
                    assert len(parts)==3 and parts[0]=='gaze';x,y=map(float,parts[1:])
                assert math.isfinite(x) and math.isfinite(y) and 0<=x<=1 and 0<=y<=1
                if source is not None:self.last_source=source
            except (ValueError,AssertionError):self.invalidate();return
            self.sample(x*width,y*height,targets,now,source,source is not None)

def show_start_menu(default='campaign'):
    import gi
    gi.require_version('Gtk','3.0')
    gi.require_version('PangoCairo','1.0')
    from gi.repository import Gtk,Gdk,GLib,Pango,PangoCairo
    model=MenuModel(default);external=False;closed=False
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:sock.bind(('127.0.0.1',29778))
    except OSError as error:
        sock.close();raise RuntimeError('游戏输入端口正在使用，请先退出已有游戏') from error
    sock.setblocking(False)
    window=Gtk.Window(title='Freeciv · 边境战役 · 开始');window.set_default_size(1152,720)
    area=Gtk.DrawingArea();window.add(area)
    area.set_can_focus(True);area.add_events(Gdk.EventMask.POINTER_MOTION_MASK|Gdk.EventMask.BUTTON_PRESS_MASK)
    def rectangles():
        w,h=area.get_allocated_width(),area.get_allocated_height();sx=w/1024;sy=h/600
        return [(56*sx,216*sy,435*sx,150*sy),(533*sx,216*sy,435*sx,150*sy),
                (280*sx,414*sy,464*sx,64*sy),(844*sx,522*sy,124*sx,40*sy)]
    def targets():
        return [dict(kind=10 if i<2 else 11+i-2,id=i,arg=i,x=round(x+w/2),y=round(y+h/2))
                for i,(x,y,w,h) in enumerate(rectangles())]
    def geometry():
        origin=area.get_window().get_origin();x,y=origin[-2:]
        return dict(version=1,map=[x,y,area.get_allocated_width(),area.get_allocated_height()],phase='menu',
            awake=model.awake,pick=model.pick,last_event=str(model.last_event),mode=model.mode,
            turn=0,city=-1,unit=-1,hp=0,moves=0,gold=0,targets=targets() if model.awake else [],
            gaze_protocol=2,selection_ready=model.selection.confirmable(time.monotonic()),selection_confidence=model.selection.confidence,
            hover=model.selection.preview(time.monotonic()))
    def draw(widget,cr):
        w,h=widget.get_allocated_width(),widget.get_allocated_height();cr.scale(w/1024,h/600)
        cr.set_source_rgb(.035,.065,.085);cr.paint()
        def text(x,y,value,size=18,color=(.87,.90,.87)):
            layout=PangoCairo.create_layout(cr);layout.set_font_description(Pango.FontDescription('Sans '+str(size)))
            layout.set_text(value,-1);cr.set_source_rgb(*color);cr.move_to(x,y);PangoCairo.show_layout(cr,layout)
        text(56,36,'FREECIV  /  RK3576',14,(.67,.77,.74))
        text(56,76,'边境战役',42,(.94,.82,.53))
        text(58,148,'占点经营  →  招兵扩军  →  攻防决胜',20)
        for i,(x,y,bw,bh) in enumerate(((56,216,435,150),(533,216,435,150),(280,414,464,64),(844,522,124,40))):
            selected=i<2 and model.mode==('campaign','hotseat')[i]
            cr.set_source_rgb(*((.11,.29,.25) if selected or i==2 else (.09,.14,.17)))
            cr.rectangle(x,y,bw,bh);cr.fill_preserve();cr.set_line_width(2)
            cr.set_source_rgb(*((.85,.72,.43) if selected else (.23,.32,.33)));cr.stroke()
            if model.awake and model.selection.preview(time.monotonic())==i:
                ready=model.selection.confirmable(time.monotonic()) and model.pick==i
                cr.set_source_rgb(*((1,.86,.45) if ready else (.55,.85,.98)))
                cr.set_line_width(3);cr.rectangle(x-5,y-5,bw+10,bh+10);cr.stroke()
                text(x+8,y+bh-24,'可确认' if ready else '定位中',12)
        text(80,234,'单人战役',26);text(80,282,'侦察扩张、争夺矿点与村庄',16);text(80,313,'招募四类兵种，抵御增援并攻城',16)
        text(557,234,'双人轮战',26);text(557,282,'两位玩家共享屏幕与摄像头',16);text(557,313,'各自军队与国库，确认交接再行动',16)
        text(412,427,'开始战役' if model.mode=='campaign' else '开始双人轮战',23)
        text(871,530,'退出',16)
        text(56,503,'F1 唤起  ·  指向目标  ·  Space 确认  ·  Esc 取消',16)
        text(56,542,'确认后休眠；普通注视不启动游戏。',14,(.64,.75,.74))
        text(56,574,'本机双人轮流操作 · 交接后重新唤起并确认',11,(.59,.68,.69))
        return False
    def close():
        nonlocal closed
        if not closed:closed=True;sock.close();Gtk.main_quit()
    def tick():
        nonlocal external
        if not area.get_realized():return True
        for _ in range(32):
            try:body,sender=sock.recvfrom(160)
            except BlockingIOError:break
            match=re.fullmatch(rb'query ([0-9a-f]{32})',body)
            if match:
                response=b'state '+match[1]+b' '+json.dumps(geometry(),separators=(',',':')).encode()
                try:sock.sendto(response,sender)
                except OSError:pass
                continue
            if body.startswith(b'gaze'):external=True
            if body.endswith(b' mouse'):external=False
            model.datagram(body,targets(),area.get_allocated_width(),area.get_allocated_height())
        if model.awake and not external:
            x,y=area.get_pointer()
            if 0<=x<=area.get_allocated_width() and 0<=y<=area.get_allocated_height():model.sample(x,y,targets())
            else:model.invalidate()
        if model.stamp and time.monotonic()-model.stamp>.25:model.invalidate()
        if model.result is not None:close();return False
        area.queue_draw();return True
    def key(widget,event):
        actions={Gdk.KEY_F1:'wake',Gdk.KEY_space:'confirm',Gdk.KEY_Escape:'cancel',Gdk.KEY_Tab:'next',Gdk.KEY_Return:'end'}
        if event.keyval in actions:model.selection.sync(targets());model.event(actions[event.keyval]);area.queue_draw();return True
        return False
    def motion(widget,event):
        if not external:model.sample(event.x,event.y,targets())
        return True
    window.connect('destroy',lambda *_:close());window.connect('key-press-event',key)
    area.connect('draw',draw);area.connect('motion-notify-event',motion)
    area.connect('button-press-event',lambda *_:area.grab_focus())
    timer=GLib.timeout_add(40,tick);window.show_all();area.grab_focus()
    try:Gtk.main()
    finally:
        sock.close()
        if model.result is None:GLib.source_remove(timer)
        window.destroy()
    return None if model.result=='exit' else model.result
