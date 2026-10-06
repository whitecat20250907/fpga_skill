"""Coherent BAR snapshots; no control writes. Intended for build04+ only."""
import argparse,json,mmap,os,struct,time
from pathlib import Path
arg=argparse.ArgumentParser()
arg.add_argument('--bar',default='/dev/ANLOGIC-PCI0_user')
arg.add_argument('--seconds',type=float,default=65)
arg.add_argument('--interval',type=float,default=.1)
a=arg.parse_args()
regs={'hs_cycles':0xac,'raw_packets':0xb0,'crc_errors':0xb4,
      'ecc_errors':0xb8,'wc_errors':0xbc,'timeout_errors':0xc0,
      'fifo_overflows':0xc4,'hs_cycles_per_100ms':0xc8}
fd=os.open(a.bar,os.O_RDWR|os.O_SYNC)
with mmap.mmap(fd,4096) as mem:
    def read(reg):return struct.unpack_from('<I',mem,reg)[0]
    version=read(0x5c)
    if version not in (0x56440401,0x56440501,0x56440601,0x56440701):
        raise SystemExit('Expected repaired diagnostic bit version 04 through 07')
    start=time.monotonic();previous=None;changed=start
    while time.monotonic()-start<a.seconds:
        for attempt in range(100):
            before=read(0xa8)
            row={name:read(reg) for name,reg in regs.items()}
            after=read(0xa8)
            if before>>1==after>>1:break
        else:raise RuntimeError('Snapshot changes too quickly')
        now=time.monotonic();seq=after>>1
        if seq!=previous:changed=now;previous=seq
        row.update(seconds=now-start,snapshot_seq=seq,busy=bool(after&1),
                   snapshot_age=now-changed,bit_version=hex(version))
        if version in (0x56440501,0x56440601,0x56440701):
            for attempt in range(100):
                clock_before=read(0xd0)
                clock_edges=read(0xcc);clock_status=read(0xd4)
                clock_after=read(0xd0)
                if clock_before==clock_after:break
            else:raise RuntimeError('Clock measurement changed during every read')
            row.update(cam27_window=clock_after,cam27_edges_per_10ms=clock_edges,
                cam27_status=hex(clock_status),cam27_locked=bool(clock_status&1),
                cam27_frequency_ok=bool(clock_status&2),
                cam_xclr=bool(clock_status&8),cam_config_ready=bool(clock_status&16))
        if version in (0x56440601,0x56440701):
            row.update(bayer_shadow=read(0xd8)&3,bayer_crop_frame_active=read(0xdc)&3)
        camera_status=read(0x84)
        row.update(camera_status=hex(camera_status),
                   phy_calibration_done=bool(camera_status&16),
                   phy_best_window=(camera_status>>6)&63)
        print(json.dumps(row),flush=True)
        time.sleep(a.interval)
os.close(fd)
