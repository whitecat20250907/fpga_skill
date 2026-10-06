"""Make V4L2 allocation and format changes honest in the isolated driver."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'fpga/deploy/v4l2_drv/milianke_v4l2_zerocopy.c'
b=p.read_bytes().replace(b'\r\n',b'\n')
def replace(a,c):
    global b
    a=a.encode();c=c.encode();assert b.count(a)==1,a;b=b.replace(a,c)
replace('#define MIN_BUFFERS             2 /* two 1080p buffers fit the board 16 MiB CMA */',
        '#define MIN_BUFFERS             4 /* requires the validated 64 MiB CMA boot */')
replace('if (vb2_is_streaming(&mdev->queue))\n                return milianke_g_fmt(file, priv, f);',
        'if (vb2_is_busy(&mdev->queue))\n                return -EBUSY; /* allocated buffers belong to the old format */')
a=b.index(b'        /* EOP-delimited mode:')
c=b.index(b'        if (mdev->width == 0',a)
b=b[:a]+b'''        /* One complete frame per EOP. Never accept a short packet as RGB. */
        ret = sgdma_engine_set_eop_flush(mdev->sgdev, 0, false, 1);
        if (ret) {
                pr_err(DRIVER_NAME ": cannot enable frame-delimited DMA: %d\\n", ret);
                goto fail_return_bufs;
        }

'''+b[c:]
replace('if (xfer_len < 0) {\n                        pr_warn(DRIVER_NAME ": DMA error %zd\\n", xfer_len);',
        'if (xfer_len < 0) {\n                        if (!kthread_should_stop() && mdev->streaming)\n                                pr_warn_ratelimited(DRIVER_NAME ": DMA error %zd\\n", xfer_len);')
p.write_bytes(b)
p=root/'tools/capture_verify.c'
b=p.read_bytes();assert b.count(b'.count=2,')==1
p.write_bytes(b.replace(b'.count=2,',b'.count=4,'))
print('V4L2: four buffers, reject busy S_FMT, require EOP, preserve exact packet check.')
