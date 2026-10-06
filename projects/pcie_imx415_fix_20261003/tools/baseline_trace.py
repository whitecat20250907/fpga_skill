from pathlib import Path

root=Path(__file__).resolve().parent
p=root/'deploy/v4l2_drv/milianke_v4l2_zerocopy.c'
b=p.read_bytes()
backup=root/'evidence/v4l2_baseline_before_trace.c'
if not backup.exists():
    backup.write_bytes(b)
needle=b'                if (xfer_len < fragment_max) {'
assert b.count(needle)==1
b=b.replace(needle,b'                pr_info(DRIVER_NAME ": BASELINE_PACKET bytes=%zd expected=%u\\n", xfer_len, mdev->pixel_bytes);\n'+needle)
p.write_bytes(b)
print('BASELINE_PACKET_TRACE_ADDED')
