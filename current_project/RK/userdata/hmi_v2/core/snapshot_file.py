"""Bound observation I/O without throttling actions or their acknowledgements."""
import json,os
from pathlib import Path


class SnapshotWriter:
    def __init__(self, path, interval_ns=50_000_000):
        self.path = Path(path)
        self.interval_ns = interval_ns
        self.last_ns = None
        self.signature = None

    def due(self, now, signature):
        return (self.last_ns is None or now < self.last_ns or
                now-self.last_ns >= self.interval_ns or signature != self.signature)

    def publish(self, now, signature, value):
        temporary = self.path.with_suffix(self.path.suffix+'.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        temporary.replace(self.path)
        self.last_ns, self.signature = now, signature


class SnapshotReader:
    def __init__(self, path):
        self.path = Path(path)
        self.identity = None
        self.value = {}

    def read(self):
        # Atomic replace changes the inode; mtime alone is not an identity.
        stat = self.path.stat()
        identity = (stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_size)
        if identity != self.identity:
            with self.path.open(encoding='utf-8') as stream:
                actual = os.fstat(stream.fileno())
                value = json.load(stream)
            self.identity = (actual.st_dev, actual.st_ino, actual.st_mtime_ns, actual.st_size)
            self.value = value
        # Callers can replace top-level fields without corrupting the cache.
        return dict(self.value)
