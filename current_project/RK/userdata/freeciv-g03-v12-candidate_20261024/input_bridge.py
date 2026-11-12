"""Small optional adapter for an existing gaze/gesture inference loop.

No inference, camera access, mouse injection, or third-party dependencies.
"""
import socket
import time
import math

class FreecivInput:
    def __init__(self, port=29778):
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.address=('127.0.0.1',port)
        self.sequence=time.time_ns()//1000
        self.previous_gesture=None
        self.since=0.
        self.fired=False

    def gaze(self,x,y,sample_time=None):
        """Normalized coordinates relative to the game's map canvas."""
        if math.isfinite(x) and math.isfinite(y) and 0<=x<=1 and 0<=y<=1:
            if sample_time is None:body=f'gaze {x:.6f} {y:.6f}'
            else:
                if not math.isfinite(sample_time) or not 0<=time.monotonic()-sample_time<=.25:return
                body=f'gaze2 {int(sample_time*1e6)} {x:.6f} {y:.6f}'
            self.socket.sendto(body.encode(),self.address)

    def gaze_lost(self):self.socket.sendto(b'gaze_lost',self.address)

    def action(self,name):
        if name not in ('wake','confirm','cancel','next','end','mouse'):
            raise ValueError(name)
        self.sequence+=1
        self.socket.sendto(f'event {self.sequence} {name}'.encode(),self.address)

    def gesture(self,name,confidence=1.):
        """An example five-gesture binding. Trigger once per held pose.

        Open_Palm=wake, Closed_Fist=confirm, Thumb_Down=cancel,
        Victory=next, Thumb_Up=end. Change the mapping for your model.
        """
        mapping={'Open_Palm':'wake','Closed_Fist':'confirm','Thumb_Down':'cancel',
                 'Victory':'next','Thumb_Up':'end'}
        now=time.monotonic()
        if confidence<.7 or name not in mapping: name=None
        if name!=self.previous_gesture:
            self.previous_gesture=name; self.since=now;self.fired=False
        if name and not self.fired and now-self.since>=.18:
            self.action(mapping[name]);self.fired=True

    def close(self): self.socket.close()
