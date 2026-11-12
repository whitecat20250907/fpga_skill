"""On-demand, at most 2 Hz preview; never captures the camera or runs models."""
import io,secrets,time,threading
from core.manual_game import validate

class GamePreview:
    def __init__(self,root):
        from .rga_display import DisplayResize
        self.root=root;self.lock=threading.Lock();self.frame=None;self.jpeg=None;self.resize=DisplayResize()
    def close(self):
        with self.lock:self.resize.close()
    def capture(self):
        with self.lock:
            now=time.monotonic_ns()
            if self.frame and 0<=now-self.frame['frame_ns']<500_000_000:return self.frame,self.jpeg
            from Xlib import display,X
            from PIL import Image
            from adapters.game_window import active_game_window
            d=display.Display(':0')
            try:
                win,rect=active_game_window(d,self.root);root=d.screen().root;geo=root.get_geometry()
                x,y,w,h=rect
                if x<0 or y<0 or x+w>geo.width or y+h>geo.height:raise ValueError('游戏窗口超出屏幕，请最大化后重试')
                # XFCE composites windows: the root backing pixmap can contain
                # only wallpaper. Read the verified game drawable itself.
                raw=win.get_image(0,0,w,h,X.ZPixmap,0xffffffff)
                img,executor=self.resize.image(raw.data,w,h)
                output=io.BytesIO();img.save(output,'JPEG',quality=75)
                self.frame=dict(id=secrets.token_hex(12),window=win.id,rect=rect,frame_ns=now,resize_executor=executor)
                self.jpeg=output.getvalue();return dict(self.frame),self.jpeg
            finally:d.close()
    def command(self,data):
        with self.lock:
            if not self.frame or data.get('frame_id')!=self.frame['id'] or not 0<=time.monotonic_ns()-self.frame['frame_ns']<=2_000_000_000:raise ValueError('游戏画面过期，请刷新')
            args={k:self.frame[k] for k in ('window','rect','frame_ns')}
            args.update({k:data[k] for k in ('kind','x','y','button','key') if k in data})
            return dict(command='game_input',args=validate(args))
