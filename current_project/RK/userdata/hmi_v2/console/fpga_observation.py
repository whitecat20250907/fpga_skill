"""Linux PCIe negotiation and owner counters; never open another BAR/DMA owner."""
from pathlib import Path
import json,re


def profile():
    path=Path(__file__).with_name('assets')/'fpga-deployed.json'
    try:
        value=json.loads(path.read_text('utf-8'))
        value['active_verified']=value.get('boot_id')==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and bool(value.get('programming_receipt_sha256'))
        receipt=path.with_name('fpga-flash-receipt.json')
        value['flash_verified']=False
        if receipt.exists():
            import hashlib
            raw=receipt.read_bytes();flash=json.loads(raw)
            value['flash_verified']=(flash.get('state')=='FLASH_VERIFIED_RESTORE_PENDING'
                and flash.get('bit_sha256')==value.get('bit_sha256')
                and hashlib.sha256(raw).hexdigest()==value.get('flash_receipt_sha256'))
        return value
    except (OSError,ValueError):return None


def link(read=lambda p:Path(p).read_text(),devices=None):
    paths=devices if devices is not None else Path('/sys/bus/pci/devices').glob('*')
    for path in paths:
        p=Path(path)
        try:
            if read(p/'vendor').strip()!='0x1edb' or read(p/'device').strip()!='0xabcd':continue
            speed=read(p/'current_link_speed').strip();width=int(read(p/'current_link_width').strip())
            match=re.match(r'(\d+(?:\.\d+)?) GT/s',speed)
            if not match or not 1<=width<=16:return None
            gt=float(match[1]);efficiency=.8 if gt<=5 else 128/130
            return dict(bdf=p.name,speed_gt_s=gt,lanes=width,encoded_capacity_MB_s=gt*1000/8*efficiency*width)
        except (OSError,ValueError):continue
    return None


class OwnerRates:
    def __init__(self):self.previous=None;self.values={}
    def sample(self,heartbeat,now):
        stamp=heartbeat.get('src_ns',0)
        if not 0<=now-stamp<=2_000_000_000:self.previous=None;self.values={};return {}
        capture=heartbeat.get('native',{}).get('capture',{})
        identity=(heartbeat.get('epoch'),heartbeat.get('instance'))
        counters={k:capture.get(k) for k in ('model_source_frames','model_complete_frames','model_abort_frames','model_overflows','model_packet_aborts','model_drops','preview_blocked_valid_cycles')}
        old=self.previous
        if old and old[0]==identity and old[1]==stamp:return self.values
        values={}
        if old and old[0]==identity and 0<stamp-old[1]<=3_000_000_000:
            for key,value in counters.items():
                before=old[2].get(key)
                if isinstance(value,int) and isinstance(before,int) and value>=before:values[key+'_hz']=(value-before)*1e9/(stamp-old[1])
        values['preview_fifo_highwater_words']=capture.get('preview_fifo_highwater_words')
        self.previous=(identity,stamp,counters);self.values=values;return values
