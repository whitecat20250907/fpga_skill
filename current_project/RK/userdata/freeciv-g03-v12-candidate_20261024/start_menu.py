"""Native GTK start page using the same five-action local input protocol.

No cameras, inference, game server, browser or background service is started
until the player explicitly confirms Start. GTK is imported only on demand.
"""
import json,math,re,socket,time
from semantic_selection import Selection

MENU_RECTS=((64,180,360,115),(620,180,340,115),(64,420,360,85),(720,420,240,85))

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
            self.activate(self.pick)
    def activate(self,picked):
        self.sleep()
        if picked in (0,1):self.mode=('campaign','hotseat')[picked]
        elif picked==2:self.result=self.mode
        elif picked==3:self.result='exit'
    def click(self,x,y,targets):
        # A real pointer click has an explicit target and needs no gaze dwell.
        if not all(math.isfinite(v) for v in (x,y)):return False
        for target in targets:
            if abs(x-target['x'])<=target['width']/2 and abs(y-target['y'])<=target['height']/2:
                self.activate(target['id']);return True
        return False
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
        return [(x*sx,y*sy,rw*sx,rh*sy) for x,y,rw,rh in MENU_RECTS]
    def targets():
        return [dict(kind=10 if i<2 else 11+i-2,id=i,arg=i,x=round(x+w/2),y=round(y+h/2),width=round(w),height=round(h),label=('单人战役','双人轮战','开始战役','退出游戏')[i])
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
        cr.set_source_rgb(.063,.075,.094);cr.paint()
        def text(x,y,value,size=18,color=(.929,.941,.953)):
            layout=PangoCairo.create_layout(cr);layout.set_font_description(Pango.FontDescription('Sans '+str(size)))
            layout.set_text(value,-1);cr.set_source_rgb(*color);cr.move_to(x,y);PangoCairo.show_layout(cr,layout)
        text(64,36,'FREECIV  /  FRONTIER',14,(.678,.718,.761))
        text(64,76,'边境战役',42,(.898,.722,.471))
        text(66,148,'选择你的战场，部署军队，夺取要塞',20)
        for i,(x,y,bw,bh) in enumerate(MENU_RECTS):
            selected=i<2 and model.mode==('campaign','hotseat')[i]
            cr.set_source_rgb(*((.125,.235,.263) if selected or i==2 else (.094,.114,.141)))
            cr.rectangle(x,y,bw,bh);cr.fill_preserve();cr.set_line_width(2)
            cr.set_source_rgb(*((.486,.788,.824) if selected else (.204,.243,.286)));cr.stroke()
            if model.awake and model.selection.preview(time.monotonic())==i:
                ready=model.selection.confirmable(time.monotonic()) and model.pick==i
                cr.set_source_rgb(*((.898,.722,.471) if ready else (.486,.788,.824)))
                cr.set_line_width(3);cr.rectangle(x-5,y-5,bw+10,bh+10);cr.stroke()
                text(x+8,y+bh-24,'可确认' if ready else '定位中',12)
        text(88,195,'单人战役',26);text(88,248,'侦察 · 扩张 · 攻城',16)
        text(88,316,'四类兵种，争夺矿点与村庄',15,(.678,.718,.761))
        text(644,195,'双人轮战',26);text(644,248,'共享屏幕 · 轮流指挥',16)
        text(644,316,'独立军队与国库，交接后行动',15,(.678,.718,.761))
        text(112,440,'开始战役' if model.mode=='campaign' else '开始双人轮战',23)
        text(786,442,'退出游戏',22)
        text(64,371,'眼控接管选择目标 → 握拳锁定 → 手势确认',17,(.486,.788,.824))
        text(64,540,'F1 唤起 / Space 确认 / Esc 返回',14,(.678,.718,.761))
        text(64,578,'本机双人轮流操作 · 交接后重新唤起并确认',11,(.557,.608,.659))
        return False
    def close():
        nonlocal closed
        if not closed:closed=True;sock.close();Gtk.main_quit()
    draw_state=None
    def tick():
        nonlocal external,draw_state
        if closed:return False
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
        # Static menu needs repaint only when visible state changes. Expose
        # and resize events still repaint through GTK itself.
        visual=(model.mode,model.awake,model.pick,model.selection.preview(time.monotonic()),
                model.selection.confirmable(time.monotonic()),area.get_allocated_width(),area.get_allocated_height())
        if visual!=draw_state:draw_state=visual;area.queue_draw()
        return True
    def key(widget,event):
        actions={Gdk.KEY_F1:'wake',Gdk.KEY_space:'confirm',Gdk.KEY_Escape:'cancel',Gdk.KEY_Tab:'next',Gdk.KEY_Return:'end'}
        if event.keyval in actions:model.selection.sync(targets());model.event(actions[event.keyval]);area.queue_draw();return True
        return False
    def motion(widget,event):
        if not external:model.sample(event.x,event.y,targets())
        return True
    window.connect('destroy',lambda *_:close());window.connect('key-press-event',key)
    area.connect('draw',draw);area.connect('motion-notify-event',motion)
    def click(widget,event):
        area.grab_focus()
        if event.button!=1:return False
        handled=model.click(event.x,event.y,targets())
        if model.result is not None:close()
        elif handled:area.queue_draw()
        return handled
    area.connect('button-press-event',click)
    timer=GLib.timeout_add(40,tick);window.show_all();area.grab_focus()
    try:Gtk.main()
    finally:
        # A pointer click may finish before tick removes itself. Always
        # release this menu's source before entering the application's loop.
        source=GLib.MainContext.default().find_source_by_id(timer)
        if source is not None:source.destroy()
        sock.close()
        window.destroy()
    return None if model.result=='exit' else model.result
