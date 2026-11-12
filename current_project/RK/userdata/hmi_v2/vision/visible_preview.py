"""Skip the presentation copy while the calibration window is minimized."""
class VisiblePreview:
    def __init__(self,selector,visible):
        self.selector=selector;self.visible=visible;self.was_visible=True

    def select(self,model_rgb,capture,now_ns=None):
        if not self.visible():
            if self.was_visible:
                self.selector.rgb=None;self.selector.metadata=None
            self.was_visible=False
            return None,''
        if not self.was_visible:self.selector.next_poll=0
        self.was_visible=True
        return self.selector.select(model_rgb,capture,now_ns)
