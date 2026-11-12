"""Bounded PUB/SUB. One publisher per endpoint; metrics have producer endpoints.

IPC on Linux, explicit TCP endpoints in Windows tests. A single multipart-free
message makes CONFLATE safe for observation topics. Events are never replayed.
"""
from collections import defaultdict, deque
from pathlib import Path
import time
import msgpack
import zmq
from .schema import validate, EVENTS

PRODUCERS = ('fpga-io','gaze','hand','engine','ui','hud','adapters','console')

def endpoint(topic, run='/run/hmi', producer=None):
    if topic == 'sys.metrics':
        if producer not in PRODUCERS: raise ValueError('Metrics require producer')
        topic += '.'+producer
    return 'ipc://'+str(Path(run)/(topic+'.ipc')).replace('\\','/')

class Publisher:
    def __init__(self, topic, address=None, *, run='/run/hmi', producer=None, context=None):
        self.topic=topic; self.context=context or zmq.Context.instance()
        self.socket=self.context.socket(zmq.PUB)
        self.socket.setsockopt(zmq.LINGER,0)
        self.socket.setsockopt(zmq.SNDHWM,64 if topic in EVENTS else 2)
        if topic not in EVENTS: self.socket.setsockopt(zmq.CONFLATE,1)
        address=address or endpoint(topic,run,producer)
        if address.startswith('ipc://'): Path(address[6:]).parent.mkdir(parents=True,exist_ok=True)
        self.socket.bind(address)
    def publish(self, message):
        message=dict(message,v=1,pub_ns=time.monotonic_ns())
        validate(self.topic,message)
        try: self.socket.send(msgpack.packb(message,use_bin_type=True),zmq.NOBLOCK)
        except zmq.Again: return False
        return True
    def close(self): self.socket.close(0)

class Subscriber:
    def __init__(self, topics, *, run='/run/hmi', addresses=None, context=None):
        self.context=context or zmq.Context.instance();self.poller=zmq.Poller()
        self.sockets={};self.values={};self.queues=defaultdict(lambda:deque(maxlen=64))
        self.invalid=0;self.overflows=0
        for topic in topics:
            targets = [(topic,addresses[topic])] if addresses and topic in addresses else (
                [('sys.metrics.'+p,endpoint(topic,run,p)) for p in PRODUCERS] if topic=='sys.metrics' else [(topic,endpoint(topic,run))])
            for key,address in targets:
                s=self.context.socket(zmq.SUB);s.setsockopt(zmq.SUBSCRIBE,b'');s.setsockopt(zmq.LINGER,0)
                s.setsockopt(zmq.RCVHWM,64 if topic in EVENTS else 2)
                if topic not in EVENTS:s.setsockopt(zmq.CONFLATE,1)
                s.connect(address);self.poller.register(s,zmq.POLLIN);self.sockets[s]=(topic,key)
    def poll(self, timeout=0):
        changed={}
        for s,_ in self.poller.poll(timeout):
            topic,key=self.sockets[s]
            for _ in range(64):
                try:raw=s.recv(zmq.NOBLOCK)
                except zmq.Again:break
                try:
                    if len(raw)>1_000_000:raise ValueError('Oversize bus message')
                    m=validate(topic,msgpack.unpackb(raw,raw=False,strict_map_key=False))
                except (ValueError,TypeError,msgpack.UnpackException):self.invalid+=1;continue
                self.values[key]=m;changed[key]=m
                if topic in EVENTS:
                    q=self.queues[topic]
                    if len(q)==q.maxlen:self.overflows+=1
                    q.append(m)
        return changed
    def latest(self,topic):return self.values.get(topic)
    def events(self,topic):
        q=self.queues[topic];result=list(q);q.clear();return result
    def close(self):
        for s in self.sockets:s.close(0)
