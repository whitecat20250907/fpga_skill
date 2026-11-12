"""Optional nonblocking screen-to-map adapter; call from existing inference.

Geometry is queried from the game's existing UDP event loop. There is no
camera, inference, global mouse injection, thread, timer or polling service.
"""
import json
import math
import secrets
import time
from input_bridge import FreecivInput


class FreecivScreenInput(FreecivInput):
    def __init__(self,port=29778):
        super().__init__(port)
        self.socket.setblocking(False)
        self.pending={}
        self.requested_at=-math.inf
        self.received_at=-math.inf
        self.state=None
        self.held_name=None
        self.held_sent=False
        self.gaze_active=False;self.last_source=-math.inf
        self.counts=dict(queries=0,replies=0,gaze=0,actions=0,unavailable=0)

    def update(self):
        now=time.monotonic()
        self.pending={k:t for k,t in self.pending.items() if now-t<=.25}
        if now-self.requested_at>=.1:
            nonce=secrets.token_hex(16)
            try:
                self.socket.sendto(f'query {nonce}'.encode('ascii'),self.address)
                self.pending[nonce]=now;self.requested_at=now;self.counts['queries']+=1
            except OSError:pass
        for _ in range(8):
            try:data,sender=self.socket.recvfrom(32768)
            except (BlockingIOError,OSError):break
            if sender!=self.address:continue
            try:
                prefix,nonce,body=data.decode('ascii').split(' ',2)
                if prefix!='state' or nonce not in self.pending:continue
                state=json.loads(body)
                rect=state['map']
                if state['version']!=1 or len(rect)!=4 or any(type(v)!=int for v in rect):continue
                if not all(abs(v)<=32768 for v in rect) or not all(0<v<=16384 for v in rect[2:]):continue
                # Age from request creation, not reply arrival: delayed responses
                # cannot make old window geometry appear fresh.
                requested=self.pending.pop(nonce)
                if requested<self.received_at:continue
                self.state=state;self.received_at=requested;self.counts['replies']+=1
            except (ValueError,KeyError,TypeError,UnicodeError):continue
        return self.state if now-self.received_at<=.25 else None

    def gaze_screen(self,x,y,sample_time):
        state=self.update()
        if state is None or not all(math.isfinite(v) for v in (x,y,sample_time)):
            self.counts['unavailable']+=1;self.invalidate_gaze();return False
        if not 0<=time.monotonic()-sample_time<=.25:self.invalidate_gaze();return False
        if sample_time<=self.last_source:return False
        left,top,width,height=state['map']
        nx,ny=(x-left)/width,(y-top)/height
        if not 0<=nx<=1 or not 0<=ny<=1:self.invalidate_gaze();return False
        try:super().gaze(nx,ny,sample_time)
        except OSError:return False
        self.last_source=sample_time;self.gaze_active=True
        self.counts['gaze']+=1;return True

    def invalidate_gaze(self):
        if self.gaze_active:
            try:super().gaze_lost()
            except OSError:return False
            self.gaze_active=False
        return True

    def action(self,name):
        if name not in ('wake','confirm','cancel','next','end'):raise ValueError(name)
        if self.update() is None:return False
        try:super().action(name)
        except OSError:return False
        self.counts['actions']+=1;return True

    def held_action(self,name):
        """An existing recognizer supplies its mapped action or None on release.

        No gesture labels, confidence threshold or inference task is defined
        here. A held logical action sends once; unavailable geometry retries.
        """
        if name is not None and name not in ('wake','confirm','cancel','next','end'):
            raise ValueError(name)
        if name!=self.held_name:
            self.held_name=name;self.held_sent=False
        if name is not None and not self.held_sent:
            self.held_sent=self.action(name)
            return self.held_sent
        return False
