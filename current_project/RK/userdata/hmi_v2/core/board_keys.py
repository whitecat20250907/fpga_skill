"""AFH03 SARADC keys via the existing Linux driver, no invented FPGA pins.

Hardware manual p38 and schematic p20 connect MENU/VOL+/VOL-/ESC to
RK3576 SARADC_VIN1 (1A22). Live device tree reports codes 139/115/114/158.
"""
import os
import struct
import time
from pathlib import Path

KEY_LABELS={'MENU':'短按基础展示 / 长按2秒暂停','VOL+':'医学展示',
            'VOL-':'游戏','ESC':'短按单人 / 长按1.2秒双人'}

class ButtonLogic:
    LONG={139:(2.,'estop'),158:(1.2,'dual')}
    def __init__(self):
        self.down = {}
        self.long_sent = set()

    def event(self, code, value, stamp, now):
        if not 0 <= now-stamp <= .35:
            self.down.clear();self.long_sent.clear()
            return []
        if value == 1 and code not in self.down:
            self.down[code] = stamp
            self.long_sent.discard(code)
        if value == 0 and code in self.down:
            start = self.down.pop(code)
            if now-start < .03:return []
            if code in self.long_sent:self.long_sent.discard(code);return []
            limit,command=self.LONG.get(code,(float('inf'),''))
            if now-start>=limit:return [command]
            return {139:['app_basic'],115:['app_demo'],114:['app_game'],158:['single']}.get(code, [])
        return []

    def tick(self, now):
        out=[]
        for code,(limit,command) in self.LONG.items():
            if code in self.down and now-self.down[code]>=limit and code not in self.long_sent:
                self.long_sent.add(code);out.append(command)
        return ['estop'] if 'estop' in out else out[:1]


class BoardKeys:
    def __init__(self):
        self.fd=None;self.logic=ButtonLogic();self.last_probe=0;self.error=''

    def poll(self):
        import fcntl
        now=time.monotonic()
        if self.fd is None and now-self.last_probe>2:
            self.last_probe=now
            for entry in Path('/sys/class/input').glob('event*'):
                try:
                    if (entry/'device/name').read_text().strip()!='adc-keys':continue
                    fd=os.open('/dev/input/'+entry.name,os.O_RDONLY|os.O_NONBLOCK|os.O_CLOEXEC)
                    try:
                        fcntl.ioctl(fd,0x400445a0,struct.pack('i',1))  # EVIOCSCLOCKID MONOTONIC
                        fcntl.ioctl(fd,0x40044590,1)  # EVIOCGRAB only board ADC keys
                    except OSError:os.close(fd);raise
                    self.fd=fd;self.error='';break
                except OSError as exc:self.error=str(exc)
        result=[]
        if self.fd is not None:
            try:
                while True:
                    raw=os.read(self.fd,24*32)
                    if not raw:raise OSError('board keys disconnected')
                    for offset in range(0,len(raw),24):
                        sec,usec,kind,code,value=struct.unpack_from('=qqHHi',raw,offset)
                        if kind==0 and code==3:self.logic=ButtonLogic()
                        elif kind==1:result.extend(self.logic.event(code,value,sec+usec/1e6,time.monotonic()))
            except BlockingIOError:pass
            except OSError as exc:self.error=str(exc);self.close()
        return result+self.logic.tick(time.monotonic())

    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None
        self.logic=ButtonLogic()
