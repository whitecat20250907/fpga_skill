from pathlib import Path
import json,logging,logging.handlers,signal,time,uuid
from .hmibus import Publisher
from .metrics import Metrics

class Service:
    def __init__(self,name,config):
        self.name=name;self.config=config;self.running=True;self.last_heartbeat=0;self.instance=uuid.uuid4().hex
        self.measurements=Metrics()
        self.metrics=Publisher('sys.metrics',run=config['paths']['run'],producer=name)
        signal.signal(signal.SIGTERM,self.stop);signal.signal(signal.SIGINT,self.stop)
        directory=Path(config['paths']['logs']);directory.mkdir(parents=True,exist_ok=True)
        self.logger=logging.getLogger(name);self.logger.setLevel(logging.INFO)
        handler=logging.handlers.RotatingFileHandler(directory/(name+'.jsonl'),maxBytes=2*1024*1024,backupCount=2,encoding='utf-8')
        self.logger.addHandler(handler)
    def stop(self,*_):self.running=False
    def heartbeat(self,epoch,ok=True,**values):
        now=time.monotonic_ns()
        if epoch and now-self.last_heartbeat>=500_000_000:
            self.metrics.publish(dict(epoch=epoch,seq=0,src_ns=now,producer=self.name,instance=self.instance,ok=ok,measurements=self.measurements.snapshot(now),**values));self.last_heartbeat=now
    def log(self,event,**values):self.logger.info(json.dumps(dict(event=event,ns=time.monotonic_ns(),**values),ensure_ascii=False))
    def close(self):self.metrics.close()
