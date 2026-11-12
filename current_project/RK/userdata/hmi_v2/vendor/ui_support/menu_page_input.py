"""Non-grabbing Linux adc-keys MENU reader for the existing UI owner.

No GPIO, device-tree, FPGA access or model work. The caller owns this context
and sends page changes through its existing UI transport at a frame boundary.
"""
import os
import struct
from pathlib import Path

MENU = 139
EVENT = struct.Struct('<qqHHi')  # Linux little-endian AArch64 input_event
KEY_BYTES = 128
EVIOCGKEY = 0x80000000 | (KEY_BYTES << 16) | (ord('E') << 8) | 0x18


class PagePress:
    def __init__(self, page=0, *, initially_pressed=True):
        if type(page) is not int or page not in (0, 1):
            raise ValueError('Page must be 0 or 1')
        self.page = page
        self.armed = not initially_pressed
        self.desynced = False

    def resync(self, pressed):
        self.desynced = False
        self.armed = not pressed

    def event(self, kind, code, value):
        if kind == 0 and code == 3:  # SYN_DROPPED
            self.desynced = True
            self.armed = False
            return None
        if self.desynced or kind != 1 or code != MENU:
            return None
        if value == 0:
            self.armed = True
        elif value == 1 and self.armed:
            self.armed = False
            self.page ^= 1
            return self.page
        return None  # Includes autorepeat value 2.


class MenuPageInput:
    def __init__(self, page=0, *, sys_input='/sys/class/input', dev_input='/dev/input'):
        import fcntl
        if os.name != 'posix' or struct.calcsize('P') != 8:
            raise RuntimeError('This installed reader targets Linux AArch64/64-bit')
        matches = [p for p in sorted(Path(sys_input).glob('event*'))
                   if (p / 'device/name').read_text().strip() == 'adc-keys']
        if len(matches) != 1:
            raise RuntimeError('Require exactly one existing adc-keys input device')
        self.path = Path(dev_input) / matches[0].name
        self.fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        self.buffer = bytearray()
        self.state = PagePress(page)
        try:
            self.state.resync(self._pressed())
        except BaseException:
            self.close()
            raise

    def _pressed(self):
        import fcntl
        bits = bytearray(KEY_BYTES)
        fcntl.ioctl(self.fd, EVIOCGKEY, bits, True)
        return bool(bits[MENU // 8] & (1 << (MENU % 8)))

    def poll(self):
        """Drain available events and return page indices for fresh presses."""
        changed = []
        while True:
            try:
                block = os.read(self.fd, EVENT.size * 64)
            except BlockingIOError:
                break
            if not block:
                self.close()
                raise RuntimeError('adc-keys input disconnected')
            self.buffer.extend(block)
            while len(self.buffer) >= EVENT.size:
                _, _, kind, code, value = EVENT.unpack(self.buffer[:EVENT.size])
                del self.buffer[:EVENT.size]
                if self.state.desynced and kind == 0 and code == 0:
                    self.state.resync(self._pressed())
                    continue
                page = self.state.event(kind, code, value)
                if page is not None:
                    changed.append(page)
        return changed

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        self.state.armed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
