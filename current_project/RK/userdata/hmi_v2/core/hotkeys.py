"""Read-only global keyboard polling; never grabs focus or injects events."""
class Hotkeys:
    def __init__(self):
        from Xlib import display,XK
        self.display=display.Display();self.held=set()
        self.codes={self.display.keysym_to_keycode(XK.string_to_keysym(k)):v for k,v in [('F10','estop'),('F5','menu')]}
    def poll(self):
        keys=self.display.query_keymap()
        down={code for code in self.codes if keys[code//8] & (1<<(code%8))}
        events=[self.codes[code] for code in down-self.held];self.held=down
        return events
    def close(self):self.display.close()
