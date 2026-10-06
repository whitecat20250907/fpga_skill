from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'fpga'
p = root / 'deploy/v4l2_drv/milianke_v4l2_zerocopy.c'
b = p.read_bytes()
start = b.index(b'        /* Accept frames that are >= 99%')
end = b.index(b'        pr_info(DRIVER_NAME ": DMA thread started', start)
b = b[:start] + b'        u32 rejected_frames = 0;\n        u32 delivered_frames = 0;\n\n' + b[end:]
start = b.index(b'                if (xfer_len < fragment_max)')
end = b.index(b'                /* 3. Frame data is already', start)
b = b[:start] + b'''                /* Never expose unwritten buffer tails as valid RGB pixels.
                 * Supported widths have no line padding, so a good packet
                 * must contain exactly pixel_bytes bytes. */
                if (xfer_len != mdev->pixel_bytes) {
                        rejected_frames++;
                        pr_warn_ratelimited(DRIVER_NAME
                                ": rejecting packet bytes=%zd expected=%u rejected=%u\\n",
                                xfer_len, mdev->pixel_bytes, rejected_frames);
                        spin_lock_irqsave(&mdev->buf_lock, flags);
                        list_add(&mbuf->list, &mdev->buf_list);
                        spin_unlock_irqrestore(&mdev->buf_lock, flags);
                        continue;
                }
                delivered_frames++;

''' + b[end:]
b = b.replace(b'        pr_info(DRIVER_NAME ": DMA thread stopped\\n");',
              b'        pr_info(DRIVER_NAME ": DMA thread stopped: delivered=%u rejected=%u\\n",\n                delivered_frames, rejected_frames);')
p.write_bytes(b)
print('Driver: exact packet length required; rejection counts recorded')
