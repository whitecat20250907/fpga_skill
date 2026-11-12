"""One same-camera raw RGB slot, independent of inference and the MCF1 pipe.

Only this object owns the parent's memfd descriptor. Do not dup/reopen it:
closing any descriptor for the same inode releases that process's POSIX locks.
Python threads additionally serialize lock/unlock/close with a thread lock.
"""
import errno
import fcntl
import mmap
import os
import struct
import threading
import time

import numpy as np

MAGIC = b'GZPRV001'
HEADER = struct.Struct('<8s6I4Q')
WIDTH, HEIGHT, STRIDE = 1920, 1080, 5760
PAYLOAD = STRIDE * HEIGHT
TOTAL = HEADER.size + PAYLOAD
STALE_NS = 500_000_000


class SharedPreview:
    def __init__(self, fps=0):
        if type(fps) is not int or not 0<=fps<=120:
            raise ValueError('Shared preview fps: 0 uncapped or 1..120')
        self.fps = fps
        self.lock = threading.Lock()
        self.closed = False
        self.last_serial = 0
        self.last_stamp = 0
        self.last_error = None
        self.fd = os.memfd_create('gaze-preview-rgb1080', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        self.map = None
        try:
            os.ftruncate(self.fd, TOTAL)
            self.map = mmap.mmap(self.fd, TOTAL, flags=mmap.MAP_SHARED,
                                 prot=mmap.PROT_READ | mmap.PROT_WRITE)
            self.map[:HEADER.size] = HEADER.pack(MAGIC, 1, WIDTH, HEIGHT, STRIDE, 0, 0, 0, 0, 0, 0)
            fcntl.fcntl(self.fd, fcntl.F_ADD_SEALS,
                        fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SEAL)
        except BaseException:
            if self.map is not None:
                self.map.close()
            os.close(self.fd)
            raise

    def read_latest(self, now_ns=None):
        """Return a new private RGB copy or None; never wait for either lock."""
        if not self.lock.acquire(blocking=False):
            return None
        locked = False
        try:
            if self.closed:
                return None
            try:
                fcntl.lockf(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB, 1, 0, os.SEEK_SET)
                locked = True
            except OSError as error:
                if error.errno in (errno.EACCES, errno.EAGAIN, errno.EINTR):
                    return None
                raise
            fields = HEADER.unpack(self.map[:HEADER.size])
            magic, version, width, height, stride, valid, sequence, stamp, dequeue, serial, published = fields
            if (magic, version, width, height, stride) != (MAGIC, 1, WIDTH, HEIGHT, STRIDE):
                raise ValueError('Preview header/size contract changed')
            if valid == 0 and serial == 0:
                return None
            if valid != PAYLOAD:
                raise ValueError('Incomplete preview payload')
            now = time.monotonic_ns() if now_ns is None else now_ns
            if not (0 < stamp <= dequeue <= published <= now and serial > 0):
                raise ValueError('Invalid preview timestamps/publication')
            if now - stamp > STALE_NS or now - published > STALE_NS:
                return None
            if serial == self.last_serial:
                return None
            if serial < self.last_serial or stamp <= self.last_stamp:
                raise ValueError('Preview publication/timestamp moved backwards')
            # bytes slice is a private copy; no ndarray/memoryview escapes the lock.
            payload = self.map[HEADER.size:]
            self.last_serial, self.last_stamp = serial, stamp
            metadata = dict(sequence=sequence, timestamp_ns=stamp, dequeue_ns=dequeue,
                            publication_serial=serial, published_ns=published,
                            width=width, height=height, stride=stride)
        except (OSError, ValueError) as error:
            self.last_error = str(error)
            return None
        finally:
            try:
                if locked:
                    fcntl.lockf(self.fd, fcntl.LOCK_UN, 1, 0, os.SEEK_SET)
            finally:
                self.lock.release()
        return np.frombuffer(payload, np.uint8).reshape(HEIGHT, WIDTH, 3), metadata

    def close(self):
        # App stops polling before worker shutdown. This short local lock also
        # protects close if a final UI copy overlaps the capture owner's cleanup.
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.map.close()
            os.close(self.fd)


class PreviewSelector:
    """UI clock owns this cache; model publication never gates raw preview."""
    def __init__(self, fps=20):
        if fps not in (10, 15, 20):
            raise ValueError('Preview fps must be 10, 15 or 20')
        self.interval_ns = (1_000_000_000 + fps - 1) // fps
        self.next_poll = 0
        self.rgb = None
        self.metadata = None

    def select(self, model_rgb, capture, now_ns=None):
        now = time.monotonic_ns() if now_ns is None else now_ns
        if now >= self.next_poll:
            self.next_poll = now + self.interval_ns
            item = capture.read_hdmi_preview(now) if capture is not None else None
            if item is not None:
                self.rgb, self.metadata = item
        meta = self.metadata
        if (meta is not None and 0 <= now - meta['timestamp_ns'] <= STALE_NS
                and 0 <= now - meta['published_ns'] <= STALE_NS):
            return self.rgb, '原始1080p预览（不叠加模型框）；模型640×360'
        # Never display the old high-resolution image as a current frame.
        return model_rgb, '高清预览等待或已过期：回退模型640×360预览'
