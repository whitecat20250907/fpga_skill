"""Read-only receive diagnostics for issue1. A snapshot is not a PHY acceptance."""
import argparse, json, mmap, os, struct, time

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bar',default='/dev/ANLOGIC-PCI0_user')
p.add_argument('--seconds',type=float,default=15)
p.add_argument('--interval',type=float,default=.1)
a=p.parse_args()
if not (0<a.seconds<=7200 and .01<=a.interval<=1): p.error('Invalid duration/interval')
fd=os.open(a.bar,os.O_RDWR|os.O_SYNC)
with mmap.mmap(fd,4096) as m:
    def read(r): return struct.unpack_from('<I',m,r)[0]
    def snap(status, offsets):
        for _ in range(100):
            before=read(status)
            vals=[read(r) for r in offsets]
            after=read(status)
            if before>>1==after>>1: return after,vals
        raise RuntimeError('Coherent snapshot changed on every read')
    version=read(0x5c)
    if version!=0x56440901: raise SystemExit('Requires actual diagnostic09 FPGA')
    start=time.monotonic()
    while time.monotonic()-start<a.seconds:
        ctrl_before=read(0x60)
        cs,c=snap(0xa8,[0xac,0xb0,0xb4,0xb8,0xbc,0xc0,0xc4,0xc8])
        d0,v0=snap(0xe4,[0xe8,0xec,0xf0,0xf4,0xf8,0xfc])
        d1,v1=snap(0x100,[0x104,0x108,0x10c,0x110,0x114,0x118])
        for _ in range(100):
            w0=read(0xd0);edges=read(0xcc);clock_status=read(0xd4);w1=read(0xd0)
            if w0==w1: break
        else: raise RuntimeError('Clock measurement changed on every read')
        cam=read(0x84);flags=v0[5];control=(flags>>8)&0x7f
        row=dict(seconds=time.monotonic()-start,bit_version=hex(version),
            ctrl_before=hex(ctrl_before),ctrl_after=hex(read(0x60)),
            frame_count=read(0x50),camera_status=hex(cam),
            phy_calibration_done=bool(cam&16),phy_best_window=(cam>>6)&63,
            cam27_window=w1,cam27_edges_per_10ms=edges,cam27_status=hex(clock_status),
            csi_snapshot_seq=cs>>1,csi_snapshot_busy=bool(cs&1),
            hs_cycles=c[0],raw_packets=c[1],crc_errors=c[2],ecc_errors=c[3],
            wc_errors=c[4],timeout_errors=c[5],fifo_overflows=c[6],hs_cycles_per_100ms=c[7],
            diag0_seq=d0>>1,diag0_busy=bool(d0&1),lane_valid_cycles=v0[:4],
            raw_sample_bytes=hex(v0[4]),flags=hex(flags),
            sticky_observations=hex(flags&255),applied_control=hex(control),
            sampler_reset_released=bool(flags&(1<<15)),
            active_manual_override=bool(control&64),requested_tap=control&63,
            effective_delay=(flags>>16)&63,effective_manual=bool(flags&(1<<22)),
            dbg_mipi=hex(flags>>24),control_shadow=hex(read(0xe0)&127),
            diag1_seq=d1>>1,diag1_busy=bool(d1&1),frame_start_count=v1[0],
            previous_observed_payload_lines=v1[1],current_observed_payload_lines=v1[2],
            ungated_packet_errors=v1[3],word_valid_cycles=v1[4],payload_beats=v1[5],
            payload_line_counts_are_crc_good=False)
        if read(0x5c)!=version: raise RuntimeError('FPGA version changed during diagnostics')
        print(json.dumps(row),flush=True)
        time.sleep(a.interval)
os.close(fd)
