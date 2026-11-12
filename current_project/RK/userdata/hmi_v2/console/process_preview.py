"""One persistent read-only image worker, outside the console's Python GIL."""
import multiprocessing
import threading
from concurrent.futures import ProcessPoolExecutor
from .basic_preview import BasicPreview

_preview=None


def start_worker(run,cpus):
    global _preview
    from pathlib import Path
    from multiprocessing.util import Finalize
    BasicPreview._start_worker(cpus)
    _preview=BasicPreview(Path(run))
    # Only this child creates/uses/destroys its read mappings and RGA buffers.
    Finalize(None,_preview.close,exitpriority=10)


def capture(values,telemetry):
    return _preview._capture(values,telemetry)


class ProcessPreview(BasicPreview):
    def __init__(self,run,worker_cpus=None):
        if worker_cpus is not None and (not isinstance(worker_cpus,list) or not worker_cpus or
                any(type(v) is not int or not 0<=v<8 for v in worker_cpus) or len(set(worker_cpus))!=len(worker_cpus)):
            raise ValueError('Preview worker CPU affinity must contain unique RK CPU indices 0..7')
        self.dispatch_lock=threading.Lock();self.pending=None
        self.worker=ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn'),
            initializer=start_worker,initargs=(str(run),worker_cpus))

    def _dispatch(self,values,telemetry):
        with self.dispatch_lock:
            if self.pending is None or self.pending.done():
                self.pending=self.worker.submit(capture,values,telemetry)
            pending=self.pending
        return pending.result(timeout=3)

    def close(self):
        self.worker.shutdown(wait=True,cancel_futures=True)
