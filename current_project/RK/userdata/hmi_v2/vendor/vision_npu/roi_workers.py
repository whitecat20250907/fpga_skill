"""Bounded ROI parallelism; each worker constructs/uses/closes its own models."""
import queue,threading
from concurrent.futures import Future,wait

class OwnerPool:
    def __init__(self,factory,cores):
        if not cores or len(cores)>2 or any(c not in (0,1,2) for c in cores):raise ValueError('RK3576 owner cores')
        self.queues=[];self.threads=[];self.closed=False;ready=[]
        for i,core in enumerate(cores):
            q=queue.Queue(1);r=Future();self.queues.append(q);ready.append(r)
            t=threading.Thread(target=self._owner,args=(factory,core,q,r),name=f'NPU-ROI-owner-{i}')
            self.threads.append(t);t.start()
        try:
            for r in ready:r.result()
        except BaseException:self.close();raise
    @staticmethod
    def _owner(factory,core,q,ready):
        model=None
        try:
            model=factory(core);ready.set_result(True)
        except BaseException as e:ready.set_exception(e);return
        try:
            while True:
                job=q.get()
                if job is None:break
                f,args=job
                try:f.set_result(model(*args))
                except BaseException as e:f.set_exception(e)
        finally:model.close()
    def map(self,args):
        if self.closed:raise RuntimeError('Owner pool closed')
        futures=[]
        for i,arg in enumerate(args):
            f=Future();futures.append(f);self.queues[i%len(self.queues)].put((f,arg))
        # Wait for every submitted ROI before propagating an error. No frame
        # buffer can be reused while another owner is still reading it.
        wait(futures)
        return [f.result() for f in futures]
    def close(self):
        if self.closed:return
        self.closed=True
        for q,t in zip(self.queues,self.threads):
            if t.is_alive():q.put(None)
        for t in self.threads:t.join()
