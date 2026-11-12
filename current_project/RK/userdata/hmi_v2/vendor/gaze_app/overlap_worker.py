"""Two resource owners with one replaceable pending item between stages."""
import threading
import traceback


class LatestSlot:
    def __init__(self):
        self.condition = threading.Condition()
        self.item = None
        self.closed = False
        self.replaced = 0

    def put(self, item):
        if item is None:
            raise ValueError('None is reserved for a closed/empty slot')
        with self.condition:
            if self.closed:
                return False
            if self.item is not None:
                self.replaced += 1
            self.item = item
            self.condition.notify()
            return True

    def get(self):
        with self.condition:
            while self.item is None and not self.closed:
                self.condition.wait()
            item, self.item = self.item, None
            self.condition.notify_all()
            return item

    def wait_for_space(self):
        # Read the newest camera frame only after pending work was consumed.
        # close() wakes this wait as well, preserving normal shutdown.
        with self.condition:
            while self.item is not None and not self.closed:
                self.condition.wait()
            return not self.closed

    def close(self, discard=False):
        with self.condition:
            self.closed = True
            if discard:
                self.item = None
            self.condition.notify_all()


class OverlapRunner:
    """Create/use/close each model on its owner; interrupt only wakes input."""
    def __init__(self, source_factory, target_factory, publish, ready, error, stop_event):
        self.source_factory, self.target_factory = source_factory, target_factory
        self.publish, self.ready, self.error = publish, ready, error
        self.stop_event = stop_event
        self.slot = LatestSlot()
        self.source = None
        self.source_lock = threading.Lock()
        self.target_thread = None
        self.started = False

    def request_stop(self):
        self.stop_event.set()
        self.slot.close(discard=True)
        with self.source_lock:
            source = self.source
        if source is not None:
            # This is a non-owning wakeup, never a cross-thread close/release.
            source.interrupt()

    def _failed(self):
        detail = traceback.format_exc()
        try:
            self.request_stop()
        finally:
            self.error(detail)

    def _consume(self):
        target = None
        try:
            if self.stop_event.is_set():
                return
            target = self.target_factory()
            if not self.stop_event.is_set():
                self.ready()
            while not self.stop_event.is_set():
                packet = self.slot.get()
                if packet is None or self.stop_event.is_set():
                    break
                result = target.process(packet)
                if not self.stop_event.is_set():
                    self.publish(result)
        except BaseException:
            self._failed()
        finally:
            if target is not None:
                try:
                    target.close()
                except BaseException:
                    self._failed()

    def run(self):
        if self.started:
            raise RuntimeError('Runner may be started only once')
        self.started = True
        source = None
        try:
            if self.stop_event.is_set():
                return
            # Camera first-frame/DMA barrier is part of source_factory.
            # The target NPU is not constructed until that factory succeeds.
            source = self.source_factory()
            with self.source_lock:
                self.source = source
            if not self.stop_event.is_set():
                self.target_thread = threading.Thread(target=self._consume, name='gaze-NPU-owner', daemon=True)
                self.target_thread.start()
            while not self.stop_event.is_set():
                if not self.slot.wait_for_space():
                    break
                try:
                    packet = source.next()
                except StopIteration:
                    break
                if packet is None:
                    self.stop_event.wait(.01)
                elif not self.slot.put(packet):
                    break
        except BaseException:
            self._failed()
        finally:
            self.slot.close(discard=self.stop_event.is_set())
            if source is not None:
                try:
                    source.close()
                except BaseException:
                    self._failed()
            if self.target_thread is not None:
                self.target_thread.join()
            self.stop_event.set()
