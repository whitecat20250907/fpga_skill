"""RK X11 display coordinates, global function keys and deliberate gaze clicks."""
import ctypes as C
import ctypes.util
import math
import os
import re
import subprocess


def display_geometry(name='HDMI-1'):
    output=subprocess.check_output(['xrandr','--current'],text=True)
    pattern=r'^'+re.escape(name)+r' connected (?:primary )?(\d+)x(\d+)\+(-?\d+)\+(-?\d+)\b'
    match=re.search(pattern,output,re.M)
    if not match:raise RuntimeError('Requested display is not active: '+name)
    w,h,x,y=map(int,match.groups())
    return {'name':name,'width':w,'height':h,'x':x,'y':y}


def chinese_font():
    path=subprocess.check_output(['fc-match',':lang=zh','-f','%{file}'],text=True).strip()
    if not path or not os.path.isfile(path):raise RuntimeError('Chinese UI font unavailable')
    return path


class X11Input:
    def __init__(self,geometry):
        self.geometry=geometry;self.display=None;self.key_states={}
        self.x=C.CDLL(ctypes_name('X11'));self.xt=C.CDLL(ctypes_name('Xtst'))
        def bind(lib,name,args,ret):
            f=getattr(lib,name);f.argtypes=args;f.restype=ret;return f
        P=C.c_void_p;U=C.c_ulong;I=C.c_int
        bind(self.x,'XOpenDisplay',[C.c_char_p],P);bind(self.x,'XCloseDisplay',[P],I)
        bind(self.x,'XDefaultRootWindow',[P],U);bind(self.x,'XFlush',[P],I)
        bind(self.x,'XQueryKeymap',[P,C.c_char_p],I);bind(self.x,'XKeysymToKeycode',[P,U],C.c_ubyte)
        bind(self.x,'XWarpPointer',[P,U,U,I,I,C.c_uint,C.c_uint,I,I],I)
        bind(self.x,'XMapRaised',[P,U],I);bind(self.x,'XSetInputFocus',[P,U,I,U],I)
        bind(self.x,'XQueryPointer',[P,U,C.POINTER(U),C.POINTER(U),C.POINTER(I),C.POINTER(I),C.POINTER(I),C.POINTER(I),C.POINTER(C.c_uint)],I)
        bind(self.xt,'XTestFakeButtonEvent',[P,C.c_uint,I,U],I)
        self.display=self.x.XOpenDisplay(None)
        if not self.display:raise RuntimeError('Cannot open DISPLAY for RK input')
        self.root=self.x.XDefaultRootWindow(self.display)

    def pressed(self,virtual_key):
        if not 0x74<=virtual_key<=0x79:return False
        key=self.x.XKeysymToKeycode(self.display,0xffbe+virtual_key-0x70)
        bits=C.create_string_buffer(32);self.x.XQueryKeymap(self.display,bits)
        down=bool(key and bits.raw[key//8]&(1<<(key%8)))
        edge=down and not self.key_states.get(virtual_key,False);self.key_states[virtual_key]=down
        return edge

    def move(self,x,y):
        if not math.isfinite(x) or not math.isfinite(y):raise ValueError('Nonfinite cursor position')
        g=self.geometry;x=max(0,min(g['width']-1,int(x)))+g['x'];y=max(0,min(g['height']-1,int(y)))+g['y']
        self.x.XWarpPointer(self.display,0,self.root,0,0,0,0,x,y);self.x.XFlush(self.display)

    def click(self,button=1):
        if button not in (1,3):raise ValueError('Only deliberate left/right clicks supported')
        if not self.xt.XTestFakeButtonEvent(self.display,button,1,0):raise RuntimeError('XTest press failed')
        try:self.x.XFlush(self.display)
        finally:
            self.xt.XTestFakeButtonEvent(self.display,button,0,0);self.x.XFlush(self.display)

    def restore(self,window):
        self.x.XMapRaised(self.display,int(window));self.x.XFlush(self.display)

    def position(self):
        root=C.c_ulong();child=C.c_ulong();rx=C.c_int();ry=C.c_int();wx=C.c_int();wy=C.c_int();mask=C.c_uint()
        if not self.x.XQueryPointer(self.display,self.root,C.byref(root),C.byref(child),C.byref(rx),C.byref(ry),C.byref(wx),C.byref(wy),C.byref(mask)):raise RuntimeError('Cannot query X pointer')
        return rx.value,ry.value

    def close(self):
        if self.display:self.x.XCloseDisplay(self.display);self.display=None


def ctypes_name(name):
    result=C.util.find_library(name)
    if not result:raise RuntimeError('Missing X11 runtime library '+name)
    return result


class DwellClick:
    """One click per fixation; leaving the radius or invalid input rearms."""
    def __init__(self,seconds=1.0,radius=35.0,max_gap=.25):
        self.seconds=float(seconds);self.radius=float(radius);self.max_gap=float(max_gap)
        if min(self.seconds,self.radius,self.max_gap)<=0:raise ValueError('Positive dwell parameters required')
        self.reset()

    def reset(self):self.anchor=None;self.start=None;self.last=None;self.fired=False

    def update(self,point,timestamp,enabled):
        if not enabled or point is None or not all(math.isfinite(x) for x in (*point,timestamp)):
            self.reset();return False
        if self.last is not None and (timestamp<=self.last or timestamp-self.last>self.max_gap):self.reset()
        if self.anchor is None or math.dist(point,self.anchor)>self.radius:
            self.anchor=tuple(point);self.start=timestamp;self.fired=False
        self.last=timestamp
        if not self.fired and timestamp-self.start>=self.seconds:
            self.fired=True;return True
        return False
