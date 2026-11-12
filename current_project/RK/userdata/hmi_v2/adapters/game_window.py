"""Read and operate only an active Freeciv window belonging to this project."""
import time
from .launcher import owned_game_menu
from core.manual_game import validate

def active_game_window(d,game_root):
    root=d.screen().root;atom=d.intern_atom
    active=root.get_full_property(atom('_NET_ACTIVE_WINDOW'),0)
    if active is None or not len(active.value) or any(active.value[1:]):raise ValueError('请先切换到游戏')
    win=d.create_resource_object('window',int(active.value[0]))
    if win.get_attributes().map_state!=2:raise ValueError('游戏窗口当前不可见')
    classes=' '.join(win.get_wm_class() or ()).lower()
    if 'freeciv' not in classes and not owned_game_menu(win,game_root,atom):raise ValueError('游戏窗口不在前台，请点击切换到游戏')
    geo=win.get_geometry();origin=root.translate_coords(win,0,0)
    return win,[origin.x,origin.y,geo.width,geo.height]

def apply(d,game_root,args,now=None):
    from Xlib import X,XK
    from Xlib.ext import xtest
    validate(args);now=time.monotonic_ns() if now is None else now
    if not 0<=now-args['frame_ns']<=2_000_000_000:raise ValueError('游戏画面已过期，请刷新后操作')
    win,rect=active_game_window(d,game_root)
    if win.id!=args['window'] or rect!=args['rect']:raise ValueError('游戏窗口已变化，请刷新后操作')
    if args['kind']=='click':
        x=rect[0]+round(args['x']*(rect[2]-1));y=rect[1]+round(args['y']*(rect[3]-1))
        xtest.fake_input(d,X.MotionNotify,x=x,y=y)
        xtest.fake_input(d,X.ButtonPress,args['button']);xtest.fake_input(d,X.ButtonRelease,args['button'])
    else:
        key=d.keysym_to_keycode(XK.string_to_keysym(args['key']))
        xtest.fake_input(d,X.KeyPress,key);xtest.fake_input(d,X.KeyRelease,key)
    d.sync()
    return '已向当前游戏窗口发送输入'
