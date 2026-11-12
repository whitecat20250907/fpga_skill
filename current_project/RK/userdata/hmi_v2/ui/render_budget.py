"""Admission for presentation only; inference and event handling never wait here."""
class RenderBudget:
    def __init__(self):
        self.key=None;self.next_at=0.;self.visible=False
    def due(self,now,key,visible=True):
        if not visible:
            self.visible=False
            return False
        changed=not self.visible or key!=self.key
        self.visible=True
        if not changed and now<self.next_at:return False
        self.key=key
        self.next_at=now+1/(30 if key[0] in ('CALIBRATE','VALIDATE') else 15)
        return True
