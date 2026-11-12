// SPDX-License-Identifier: GPL-2.0
/*
 * milianke_v4l2.c - V4L2 capture wrapper for Milianke SGDMA PCIe FPGA
 *
 * Zero-copy optimized version:
 *   - DMA directly into vb2 buffer (no staging buffer, no memcpy)
 *   - Per-buffer SG table built once in buf_init
 *   - No frame_go trigger (freerun architecture)
 *   - Minimal gap between DMA completions
 *
 * DMA flow: sgdma_xfer_submit -> C2H -> directly into vb2 buffer
 *
 * Copyright (c) 2026 - Milianke PCIe Video Capture
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/pci.h>
#include <linux/kthread.h>
#include <linux/delay.h>
#include <linux/vmalloc.h>
#include <linux/scatterlist.h>

#include <media/v4l2-device.h>
#include <media/v4l2-dev.h>
#include <media/v4l2-ioctl.h>
#include <media/v4l2-ctrls.h>

#include <media/videobuf2-v4l2.h>
#include <media/videobuf2-dma-contig.h>

/* ------------------------------------------------------------------ */
/* Constants                                                          */
/* ------------------------------------------------------------------ */

#define DRIVER_NAME             "milianke-v4l2"
#define CARD_NAME               "Milianke PCIe Capture"

/* PCI IDs - same device as SGDMA driver */
#define PCI_VENDOR_MILIANKE     0x1edb
#define PCI_DEVICE_MILIANKE     0xabcd

/* User BAR register offsets */
#define REG_TPG_STATUS          0x40
#define REG_WIDTH               0x44
#define REG_HEIGHT              0x48
#define REG_FRAME_COUNT         0x50
#define REG_CTRL                0x60    /* bit[0]=reg_enable, bit[1]=soft_reset */
#define REG_PADDED_BYTES        0x64
#define REG_SOURCE_SEL          0x80    /* legacy: always 1 (camera) */
#define REG_CAM_MODE            0x90    /* bit[1:0]: 0=1080p, 1=4K, 2=720p */
#define REG_VERSION             0x5c
#define FRAME_CREDIT_VERSION    0x56442501
#define REG_FRAME_CREDIT        0x134
#define REG_AE_GAIN             0x98    /* IMX415 analog gain (0~1023, 0.3dB/step) */

/* Frame format - Phase 11: raw pixel data, no header */
#define BPP                     3               /* RGB24 bytes per pixel */
#define DMA_TIMEOUT_MS          100             /* steady-state frame timeout */
#define DMA_STARTUP_TIMEOUT_MS  1000            /* calibration + first complete frame */
#define MIN_BUFFERS             4 /* requires the validated 64 MiB CMA boot */
#define MAX_BUFFERS             8

/* Resolution mode table
 * 4K (mode 1) is BLOCKED due to PCIe x1 Gen2 bandwidth limit (747 MB/s > 350 MB/s).
 * FPGA FIFO (32KB) overflows mid-frame with 4K, causing ~45% data loss.
 * deploy v0.3: max resolution capped at 1080p. */
struct milianke_mode {
        u32 width;
        u32 height;
        u32 fps;
        bool allowed;   /* false = blocked by bandwidth cap */
};

static const struct milianke_mode milianke_modes[] = {
        [0] = { 1920, 1080, 60, true  },   /* 1080p binning */
        [1] = { 3840, 2160, 30, false },   /* 4K all-pixel — BLOCKED: bandwidth */
        [2] = { 1280,  720, 60, true  },   /* 720p */
};
#define NUM_MODES ARRAY_SIZE(milianke_modes)
#define DEFAULT_MODE 0              /* 1080p (was 4K, now capped) */
#define FALLBACK_MODE 0             /* fallback when blocked mode requested */

/* ------------------------------------------------------------------ */
/* Imported symbols from anlogic_pci.ko (RK3576 SGDMA exports)       */
/* ------------------------------------------------------------------ */

extern void *anlogic_get_sgdev(struct pci_dev *pdev);
extern void __iomem *anlogic_get_user_bar(struct pci_dev *pdev);
extern ssize_t sgdma_xfer_submit(void *dev_hndl, int channel, bool write,
                                 u64 ep_addr, struct sg_table *sgt,
                                 bool dma_mapped, int timeout_ms,
                                 u32 *controls);
extern int sgdma_engine_claim(void *dev_hndl, int channel, bool write,
                              int eop_flush);
extern void sgdma_engine_release(void *dev_hndl, int channel, bool write);

/* ------------------------------------------------------------------ */
/* Structures                                                         */
/* ------------------------------------------------------------------ */

struct milianke_v4l2_buffer {
        struct vb2_v4l2_buffer  vb;
        struct list_head        list;
        struct sg_table         sgt;            /* per-buffer SG table */
        bool                    sgt_valid;      /* SG table initialized */
};

struct milianke_v4l2_dev {
        struct v4l2_device      v4l2_dev;
        struct video_device     vdev;
        struct vb2_queue        queue;
        struct v4l2_ctrl_handler ctrl_handler;
        struct mutex            lock;           /* serialize ioctl */

        /* Hardware references */
        struct pci_dev          *pdev;
        void                    *sgdev;         /* SGDMA dev_hndl */
        void __iomem            *user_bar;

        /* Video format (read from FPGA) */
        u32                     width;
        u32                     height;
        u32                     pixel_bytes;    /* W * H * BPP */
        u32                     padded_frame_bytes;
        u32                     read_size;      /* DMA transfer size */
        u32                     cam_mode;       /* current resolution mode index */

        /* Streaming control */
        struct task_struct      *dma_thread;
        bool                    streaming;
        bool                    pipeline_enabled; /* FPGA reg_enable written */
        bool                    dma_claimed;      /* exclusive C2H ownership */
        u32                     sequence;

        /* vb2 buffer queue */
        struct list_head        buf_list;
        spinlock_t              buf_lock;
};

static inline struct milianke_v4l2_buffer *
to_milianke_buf(struct vb2_v4l2_buffer *vbuf)
{
        return container_of(vbuf, struct milianke_v4l2_buffer, vb);
}

/* Helper: clamp mode to allowed set */
static u32 milianke_clamp_mode(u32 mode)
{
        if (mode < NUM_MODES && milianke_modes[mode].allowed)
                return mode;
        pr_info(DRIVER_NAME ": mode %u blocked (PCIe bandwidth), using mode %u (%ux%u)\n",
                mode, FALLBACK_MODE,
                milianke_modes[FALLBACK_MODE].width,
                milianke_modes[FALLBACK_MODE].height);
        return FALLBACK_MODE;
}

/* ------------------------------------------------------------------ */
/* V4L2 control operations                                            */
/* ------------------------------------------------------------------ */

static int milianke_s_ctrl(struct v4l2_ctrl *ctrl)
{
        struct milianke_v4l2_dev *mdev =
                container_of(ctrl->handler, struct milianke_v4l2_dev,
                             ctrl_handler);

        switch (ctrl->id) {
        case V4L2_CID_GAIN:
                iowrite32(ctrl->val, mdev->user_bar + REG_AE_GAIN);
                return 0;
        default:
                return -EINVAL;
        }
}

static const struct v4l2_ctrl_ops milianke_ctrl_ops = {
        .s_ctrl = milianke_s_ctrl,
};

/* ------------------------------------------------------------------ */
/* V4L2 ioctl operations                                              */
/* ------------------------------------------------------------------ */

static int milianke_querycap(struct file *file, void *priv,
                             struct v4l2_capability *cap)
{
        struct milianke_v4l2_dev *mdev = video_drvdata(file);

        strscpy(cap->driver, DRIVER_NAME, sizeof(cap->driver));
        strscpy(cap->card, CARD_NAME, sizeof(cap->card));
        snprintf(cap->bus_info, sizeof(cap->bus_info), "PCI:%s",
                 pci_name(mdev->pdev));
        return 0;
}

static int milianke_enum_fmt(struct file *file, void *priv,
                             struct v4l2_fmtdesc *f)
{
        if (f->index > 0)
                return -EINVAL;
        f->pixelformat = V4L2_PIX_FMT_RGB24;
        return 0;
}

static int milianke_g_fmt(struct file *file, void *priv,
                          struct v4l2_format *f)
{
        struct milianke_v4l2_dev *mdev = video_drvdata(file);
        struct v4l2_pix_format *pix = &f->fmt.pix;

        pix->width = mdev->width;
        pix->height = mdev->height;
        pix->pixelformat = V4L2_PIX_FMT_RGB24;
        pix->field = V4L2_FIELD_NONE;
        pix->bytesperline = mdev->width * BPP;
        pix->sizeimage = mdev->pixel_bytes;
        pix->colorspace = V4L2_COLORSPACE_SRGB;
        return 0;
}

static int milianke_s_fmt(struct file *file, void *priv,
                          struct v4l2_format *f)
{
        struct milianke_v4l2_dev *mdev = video_drvdata(file);
        u32 i, best = DEFAULT_MODE;
        u32 req_w = f->fmt.pix.width;
        u32 req_h = f->fmt.pix.height;

        /* streaming 期间不允许切换分辨率 */
        if (vb2_is_busy(&mdev->queue))
                return -EBUSY; /* allocated buffers belong to the old format */

        /* 找最接近的模式 */
        for (i = 0; i < NUM_MODES; i++) {
                if (milianke_modes[i].width == req_w &&
                    milianke_modes[i].height == req_h) {
                        best = i;
                        break;
                }
        }

        /* Enforce bandwidth cap */
        best = milianke_clamp_mode(best);

        /* 写 REG_CAM_MODE 到 FPGA */
        if (best != mdev->cam_mode ||
            (ioread32(mdev->user_bar + REG_CAM_MODE) & 0x3) != best) {
                u32 line_bytes, beats;

                iowrite32(best, mdev->user_bar + REG_CAM_MODE);
                mdev->cam_mode = best;
                mdev->width  = milianke_modes[best].width;
                mdev->height = milianke_modes[best].height;
                mdev->pixel_bytes = mdev->width * mdev->height * BPP;

                /* 同步更新 padded_frame_bytes / read_size，
                   否则 queue_setup 仍按旧分辨率分配 buffer */
                line_bytes = mdev->width * BPP;
                beats = (line_bytes + 63) / 64;
                mdev->padded_frame_bytes = beats * mdev->height * 64;
                mdev->read_size = mdev->padded_frame_bytes;

                pr_info(DRIVER_NAME ": mode switched to %ux%u@%u (cam_mode=%u, read_size=%u)\n",
                        mdev->width, mdev->height,
                        milianke_modes[best].fps, best, mdev->read_size);
        }

        return milianke_g_fmt(file, priv, f);
}

static int milianke_try_fmt(struct file *file, void *priv,
                            struct v4l2_format *f)
{
        struct v4l2_pix_format *pix = &f->fmt.pix;
        u32 i, best = DEFAULT_MODE;
        u32 req_w = pix->width;
        u32 req_h = pix->height;

        /* 找最接近的模式 */
        for (i = 0; i < NUM_MODES; i++) {
                if (milianke_modes[i].width == req_w &&
                    milianke_modes[i].height == req_h) {
                        best = i;
                        break;
                }
        }

        /* Enforce bandwidth cap */
        best = milianke_clamp_mode(best);

        pix->width = milianke_modes[best].width;
        pix->height = milianke_modes[best].height;
        pix->pixelformat = V4L2_PIX_FMT_RGB24;
        pix->field = V4L2_FIELD_NONE;
        pix->bytesperline = pix->width * BPP;
        pix->sizeimage = pix->width * pix->height * BPP;
        pix->colorspace = V4L2_COLORSPACE_SRGB;
        return 0;
}

static int milianke_enum_input(struct file *file, void *priv,
                               struct v4l2_input *inp)
{
        if (inp->index > 0)
                return -EINVAL;
        strscpy(inp->name, "FPGA Video", sizeof(inp->name));
        inp->type = V4L2_INPUT_TYPE_CAMERA;
        inp->status = 0;
        return 0;
}

static int milianke_g_input(struct file *file, void *priv, unsigned int *i)
{
        *i = 0;
        return 0;
}

static int milianke_s_input(struct file *file, void *priv, unsigned int i)
{
        return (i == 0) ? 0 : -EINVAL;
}

static int milianke_g_parm(struct file *file, void *priv,
                           struct v4l2_streamparm *sp)
{
        struct milianke_v4l2_dev *mdev = video_drvdata(file);
        struct v4l2_captureparm *cp = &sp->parm.capture;
        u32 fps = milianke_modes[mdev->cam_mode].fps;

        if (sp->type != V4L2_BUF_TYPE_VIDEO_CAPTURE)
                return -EINVAL;

        memset(cp, 0, sizeof(*cp));
        cp->capability = V4L2_CAP_TIMEPERFRAME;
        cp->timeperframe.numerator = 1;
        cp->timeperframe.denominator = fps;
        cp->readbuffers = MIN_BUFFERS;
        return 0;
}

static int milianke_s_parm(struct file *file, void *priv,
                           struct v4l2_streamparm *sp)
{
        return milianke_g_parm(file, priv, sp);
}

static int milianke_enum_framesizes(struct file *file, void *priv,
                                    struct v4l2_frmsizeenum *fsize)
{
        u32 i, count = 0;

        if (fsize->pixel_format != V4L2_PIX_FMT_RGB24)
                return -EINVAL;

        /* Only enumerate allowed modes */
        for (i = 0; i < NUM_MODES; i++) {
                if (!milianke_modes[i].allowed)
                        continue;
                if (count == fsize->index) {
                        fsize->type = V4L2_FRMSIZE_TYPE_DISCRETE;
                        fsize->discrete.width = milianke_modes[i].width;
                        fsize->discrete.height = milianke_modes[i].height;
                        return 0;
                }
                count++;
        }
        return -EINVAL;
}

static int milianke_enum_frameintervals(struct file *file, void *priv,
                                        struct v4l2_frmivalenum *fival)
{
        u32 i;

        if (fival->index > 0)
                return -EINVAL;
        if (fival->pixel_format != V4L2_PIX_FMT_RGB24)
                return -EINVAL;

        /* 找到匹配分辨率的帧率（仅限 allowed 模式） */
        for (i = 0; i < NUM_MODES; i++) {
                if (!milianke_modes[i].allowed)
                        continue;
                if (milianke_modes[i].width == fival->width &&
                    milianke_modes[i].height == fival->height) {
                        fival->type = V4L2_FRMIVAL_TYPE_DISCRETE;
                        fival->discrete.numerator = 1;
                        fival->discrete.denominator = milianke_modes[i].fps;
                        return 0;
                }
        }
        return -EINVAL;
}

static const struct v4l2_ioctl_ops milianke_ioctl_ops = {
        .vidioc_querycap        = milianke_querycap,
        .vidioc_enum_fmt_vid_cap = milianke_enum_fmt,
        .vidioc_g_fmt_vid_cap   = milianke_g_fmt,
        .vidioc_s_fmt_vid_cap   = milianke_s_fmt,
        .vidioc_try_fmt_vid_cap = milianke_try_fmt,
        .vidioc_enum_input      = milianke_enum_input,
        .vidioc_g_input         = milianke_g_input,
        .vidioc_s_input         = milianke_s_input,
        .vidioc_g_parm          = milianke_g_parm,
        .vidioc_s_parm          = milianke_s_parm,
        .vidioc_enum_framesizes         = milianke_enum_framesizes,
        .vidioc_enum_frameintervals     = milianke_enum_frameintervals,

        /* vb2 helpers */
        .vidioc_reqbufs         = vb2_ioctl_reqbufs,
        .vidioc_querybuf        = vb2_ioctl_querybuf,
        .vidioc_qbuf            = vb2_ioctl_qbuf,
        .vidioc_dqbuf           = vb2_ioctl_dqbuf,
        .vidioc_streamon        = vb2_ioctl_streamon,
        .vidioc_streamoff       = vb2_ioctl_streamoff,
        .vidioc_create_bufs     = vb2_ioctl_create_bufs,
        .vidioc_prepare_buf     = vb2_ioctl_prepare_buf,
        .vidioc_expbuf          = vb2_ioctl_expbuf,
};

/* ------------------------------------------------------------------ */
/* DMA worker thread - zero-copy version                              */
/* ------------------------------------------------------------------ */

static int milianke_dma_thread(void *data)
{
        struct milianke_v4l2_dev *mdev = data;
        struct milianke_v4l2_buffer *mbuf;
        ssize_t xfer_len;
        unsigned long flags;
        u32 rejected_frames = 0;
        u32 delivered_frames = 0;
        u32 dma_errors = 0;
        u32 consecutive_errors = 0;

        pr_info(DRIVER_NAME ": DMA thread started (zero-copy)\n");

        while (!kthread_should_stop() && READ_ONCE(mdev->streaming)) {
                /* Enable FPGA video pipeline on first DMA iteration,
                 * right before the first xfer_submit so that tready
                 * goes high almost simultaneously with TPG starting.
                 * This prevents FIFO overflow and partial frames. */
                if (!mdev->pipeline_enabled) {
                        iowrite32(1, mdev->user_bar + REG_CTRL);
                        mdev->pipeline_enabled = true;
                }

                /* 1. Get next queued vb2 buffer */
                spin_lock_irqsave(&mdev->buf_lock, flags);
                if (list_empty(&mdev->buf_list)) {
                        spin_unlock_irqrestore(&mdev->buf_lock, flags);
                        usleep_range(500, 1000);
                        continue;
                }
                mbuf = list_first_entry(&mdev->buf_list,
                                        struct milianke_v4l2_buffer, list);
                list_del(&mbuf->list);
                spin_unlock_irqrestore(&mdev->buf_lock, flags);

                /* One queued buffer reserves exactly one complete FPGA frame.
                 * Readback flushes the posted BAR write before DMA submission.
                 * Hardware waits for DMA ready and retires at output TLAST. */
                iowrite32(1, mdev->user_bar + REG_FRAME_CREDIT);
                ioread32(mdev->user_bar + REG_FRAME_CREDIT);

                /* 2. DMA directly into vb2 buffer - no staging, no memcpy */
                xfer_len = sgdma_xfer_submit(mdev->sgdev, 0, false, 0,
                                             &mbuf->sgt, true,
                                             delivered_frames ? DMA_TIMEOUT_MS :
                                             DMA_STARTUP_TIMEOUT_MS, NULL);

                if (xfer_len < 0) {
                        /* A cancelled/timed-out request cannot leave a credit
                         * or a partial packet for the next DMA descriptor. */
                        iowrite32(0x02, mdev->user_bar + REG_CTRL);
                        ioread32(mdev->user_bar + REG_CTRL);
                        mdev->pipeline_enabled = false;
                        bool stopping = kthread_should_stop() ||
                                        !READ_ONCE(mdev->streaming);
                        if (!stopping) {
                                dma_errors++;
                                consecutive_errors++;
                                pr_warn_ratelimited(DRIVER_NAME
                                        ": DMA error %zd errors=%u consecutive=%u\n",
                                        xfer_len, dma_errors, consecutive_errors);
                        }
                        spin_lock_irqsave(&mdev->buf_lock, flags);
                        list_add(&mbuf->list, &mdev->buf_list);
                        spin_unlock_irqrestore(&mdev->buf_lock, flags);
                        /* Signal a persistent link failure to poll/DQBUF.
                         * STREAMOFF returns all queued buffers and releases
                         * ownership after the worker has exited. */
                        if (!stopping && consecutive_errors >= 3) {
                                iowrite32(0, mdev->user_bar + REG_CTRL);
                                WRITE_ONCE(mdev->streaming, false);
                                vb2_queue_error(&mdev->queue);
                                break;
                        }
                        continue;
                }
                consecutive_errors = 0;

                /* Never expose unwritten buffer tails as valid RGB pixels.
                 * Supported widths have no line padding, so a good packet
                 * must contain exactly pixel_bytes bytes. */
                if (xfer_len != mdev->pixel_bytes) {
                        rejected_frames++;
                        pr_warn_ratelimited(DRIVER_NAME
                                ": rejecting packet bytes=%zd expected=%u rejected=%u\n",
                                xfer_len, mdev->pixel_bytes, rejected_frames);
                        spin_lock_irqsave(&mdev->buf_lock, flags);
                        list_add(&mbuf->list, &mdev->buf_list);
                        spin_unlock_irqrestore(&mdev->buf_lock, flags);
                        continue;
                }
                delivered_frames++;

                /* 3. Frame data is already in vb2 buffer - just fill metadata */
                mbuf->vb.vb2_buf.timestamp = ktime_get_ns();
                mbuf->vb.sequence = mdev->sequence++;
                mbuf->vb.field = V4L2_FIELD_NONE;
                vb2_set_plane_payload(&mbuf->vb.vb2_buf, 0,
                                      mdev->pixel_bytes);

                /* 4. Return buffer to userspace */
                vb2_buffer_done(&mbuf->vb.vb2_buf, VB2_BUF_STATE_DONE);
        }

        pr_info(DRIVER_NAME ": DMA thread stopped: delivered=%u rejected=%u dma_errors=%u\n",
                delivered_frames, rejected_frames, dma_errors);
        return 0;
}

/* ------------------------------------------------------------------ */
/* vb2 queue operations                                               */
/* ------------------------------------------------------------------ */

static int milianke_queue_setup(struct vb2_queue *vq,
                                unsigned int *nbuffers,
                                unsigned int *nplanes,
                                unsigned int sizes[],
                                struct device *alloc_devs[])
{
        struct milianke_v4l2_dev *mdev = vb2_get_drv_priv(vq);
        u32 buf_size = max(mdev->pixel_bytes, mdev->read_size);

        if (*nplanes) {
                if (sizes[0] < buf_size)
                        return -EINVAL;
                return 0;
        }

        *nplanes = 1;
        sizes[0] = buf_size;

        if (*nbuffers < MIN_BUFFERS)
                *nbuffers = MIN_BUFFERS;
        if (*nbuffers > MAX_BUFFERS)
                *nbuffers = MAX_BUFFERS;

        pr_info(DRIVER_NAME ": queue_setup: %u buffers, %u bytes each\n",
                *nbuffers, sizes[0]);
        return 0;
}

static int milianke_buf_init(struct vb2_buffer *vb)
{
        struct milianke_v4l2_dev *mdev = vb2_get_drv_priv(vb->vb2_queue);
        struct vb2_v4l2_buffer *vbuf = to_vb2_v4l2_buffer(vb);
        struct milianke_v4l2_buffer *mbuf = to_milianke_buf(vbuf);
        struct scatterlist *sg;
        dma_addr_t dma_addr;
        int ret;

        /* Build SG table pointing to this vb2 buffer's DMA address */
        ret = sg_alloc_table(&mbuf->sgt, 1, GFP_KERNEL);
        if (ret)
                return ret;

        dma_addr = vb2_dma_contig_plane_dma_addr(vb, 0);
        sg = mbuf->sgt.sgl;
        sg_dma_address(sg) = dma_addr;
        sg_dma_len(sg) = mdev->read_size;
        mbuf->sgt.nents = 1;
        mbuf->sgt_valid = true;

        pr_info(DRIVER_NAME ": buf_init[%d]: DMA addr=0x%llx, size=%u\n",
                vb->index, (u64)dma_addr, mdev->read_size);
        return 0;
}

static void milianke_buf_cleanup(struct vb2_buffer *vb)
{
        struct vb2_v4l2_buffer *vbuf = to_vb2_v4l2_buffer(vb);
        struct milianke_v4l2_buffer *mbuf = to_milianke_buf(vbuf);

        if (mbuf->sgt_valid) {
                sg_free_table(&mbuf->sgt);
                mbuf->sgt_valid = false;
        }
}

static int milianke_buf_prepare(struct vb2_buffer *vb)
{
        struct milianke_v4l2_dev *mdev = vb2_get_drv_priv(vb->vb2_queue);
        u32 buf_size = max(mdev->pixel_bytes, mdev->read_size);

        if (vb2_plane_size(vb, 0) < buf_size) {
                pr_err(DRIVER_NAME ": buffer too small (%lu < %u)\n",
                       vb2_plane_size(vb, 0), buf_size);
                return -EINVAL;
        }
        return 0;
}

static void milianke_buf_queue(struct vb2_buffer *vb)
{
        struct milianke_v4l2_dev *mdev = vb2_get_drv_priv(vb->vb2_queue);
        struct vb2_v4l2_buffer *vbuf = to_vb2_v4l2_buffer(vb);
        struct milianke_v4l2_buffer *mbuf = to_milianke_buf(vbuf);
        unsigned long flags;

        spin_lock_irqsave(&mdev->buf_lock, flags);
        list_add_tail(&mbuf->list, &mdev->buf_list);
        spin_unlock_irqrestore(&mdev->buf_lock, flags);
}

static int milianke_start_streaming(struct vb2_queue *vq, unsigned int count)
{
        struct milianke_v4l2_dev *mdev = vb2_get_drv_priv(vq);
        int ret;

        u32 hw_width, hw_height, hw_padded, hw_mode;

        /* Buffers and SG DMA lengths were fixed during REQBUFS/buf_init.
         * Never resize this stream from a direct BAR mode write afterwards. */
        hw_mode = ioread32(mdev->user_bar + REG_CAM_MODE) & 0x3;
        hw_width = ioread32(mdev->user_bar + REG_WIDTH);
        hw_height = ioread32(mdev->user_bar + REG_HEIGHT);
        hw_padded = ioread32(mdev->user_bar + REG_PADDED_BYTES);
        if (hw_mode != mdev->cam_mode || hw_width != mdev->width ||
            hw_height != mdev->height || hw_padded != mdev->read_size ||
            mdev->read_size != mdev->pixel_bytes) {
                pr_err(DRIVER_NAME
                        ": FPGA format changed after allocation: mode=%u size=%ux%u bytes=%u expected mode=%u size=%ux%u bytes=%u\n",
                        hw_mode, hw_width, hw_height, hw_padded,
                        mdev->cam_mode, mdev->width, mdev->height,
                        mdev->read_size);
                ret = -EINVAL;
                goto fail_return_bufs;
        }

        /* Claim before changing EOP policy; raw C2H opens share this lease. */
        ret = sgdma_engine_claim(mdev->sgdev, 0, false, 1);
        if (ret) {
                pr_err(DRIVER_NAME ": C2H is owned by another client: %d\n", ret);
                goto fail_return_bufs;
        }
        mdev->dma_claimed = true;

        pr_info(DRIVER_NAME ": start_streaming: %ux%u (mode=%u), read_size=%u\n",
                mdev->width, mdev->height, mdev->cam_mode, mdev->read_size);

        /* Soft-reset the FPGA video pipeline.
         * reg_enable stays 0 — the DMA thread will set it to 1 right
         * before the first DMA submission. */
        iowrite32(0x02, mdev->user_bar + REG_CTRL);  /* soft_reset, auto-clears */

        mdev->sequence = 0;
        WRITE_ONCE(mdev->streaming, true);
        mdev->pipeline_enabled = false;

        /* Start DMA worker thread */
        mdev->dma_thread = kthread_run(milianke_dma_thread, mdev,
                                       "milianke-v4l2-dma");
        if (IS_ERR(mdev->dma_thread)) {
                ret = PTR_ERR(mdev->dma_thread);
                mdev->dma_thread = NULL;
                WRITE_ONCE(mdev->streaming, false);
                goto fail_return_bufs;
        }

        return 0;

fail_return_bufs:
        if (mdev->dma_claimed) {
                iowrite32(0, mdev->user_bar + REG_CTRL);
                sgdma_engine_release(mdev->sgdev, 0, false);
                mdev->dma_claimed = false;
        }
        {
                struct milianke_v4l2_buffer *mbuf, *tmp;
                unsigned long flags;

                spin_lock_irqsave(&mdev->buf_lock, flags);
                list_for_each_entry_safe(mbuf, tmp, &mdev->buf_list, list) {
                        list_del(&mbuf->list);
                        vb2_buffer_done(&mbuf->vb.vb2_buf,
                                        VB2_BUF_STATE_QUEUED);
                }
                spin_unlock_irqrestore(&mdev->buf_lock, flags);
        }
        return ret;
}

static void milianke_stop_streaming(struct vb2_queue *vq)
{
        struct milianke_v4l2_dev *mdev = vb2_get_drv_priv(vq);
        struct milianke_v4l2_buffer *mbuf, *tmp;
        unsigned long flags;

        WRITE_ONCE(mdev->streaming, false);
        if (mdev->dma_thread) {
                kthread_stop(mdev->dma_thread);
                mdev->dma_thread = NULL;
        }

        spin_lock_irqsave(&mdev->buf_lock, flags);
        list_for_each_entry_safe(mbuf, tmp, &mdev->buf_list, list) {
                list_del(&mbuf->list);
                vb2_buffer_done(&mbuf->vb.vb2_buf, VB2_BUF_STATE_ERROR);
        }
        spin_unlock_irqrestore(&mdev->buf_lock, flags);

        /* Disable before another client can claim this C2H stream. */
        iowrite32(0, mdev->user_bar + REG_CTRL);
        if (mdev->dma_claimed) {
                sgdma_engine_release(mdev->sgdev, 0, false);
                mdev->dma_claimed = false;
        }

        pr_info(DRIVER_NAME ": stop_streaming: %u frames captured\n",
                mdev->sequence);
}

static const struct vb2_ops milianke_vb2_ops = {
        .queue_setup    = milianke_queue_setup,
        .buf_init       = milianke_buf_init,
        .buf_cleanup    = milianke_buf_cleanup,
        .buf_prepare    = milianke_buf_prepare,
        .buf_queue      = milianke_buf_queue,
        .start_streaming = milianke_start_streaming,
        .stop_streaming = milianke_stop_streaming,
        .wait_prepare   = vb2_ops_wait_prepare,
        .wait_finish    = vb2_ops_wait_finish,
};

/* ------------------------------------------------------------------ */
/* V4L2 file operations                                               */
/* ------------------------------------------------------------------ */

static const struct v4l2_file_operations milianke_fops = {
        .owner          = THIS_MODULE,
        .open           = v4l2_fh_open,
        .release        = vb2_fop_release,
        .read           = vb2_fop_read,
        .mmap           = vb2_fop_mmap,
        .poll           = vb2_fop_poll,
        .unlocked_ioctl = video_ioctl2,
};

/* ------------------------------------------------------------------ */
/* Module init / exit                                                 */
/* ------------------------------------------------------------------ */

static struct milianke_v4l2_dev *g_mdev;

static int __init milianke_v4l2_init(void)
{
        struct pci_dev *pdev = NULL;
        struct milianke_v4l2_dev *mdev;
        struct vb2_queue *q;
        int ret;

        pdev = pci_get_device(PCI_VENDOR_MILIANKE, PCI_DEVICE_MILIANKE, NULL);
        if (!pdev) {
                pr_err(DRIVER_NAME ": no Milianke PCIe device found\n");
                return -ENODEV;
        }

        mdev = kzalloc(sizeof(*mdev), GFP_KERNEL);
        if (!mdev) {
                ret = -ENOMEM;
                goto fail_put_pdev;
        }

        mdev->pdev = pdev;
        mdev->sgdev = anlogic_get_sgdev(pdev);
        if (!mdev->sgdev) {
                pr_err(DRIVER_NAME ": anlogic_get_sgdev failed\n");
                ret = -ENODEV;
                goto fail_free_mdev;
        }

        mdev->user_bar = anlogic_get_user_bar(pdev);
        if (!mdev->user_bar) {
                pr_err(DRIVER_NAME ": anlogic_get_user_bar failed\n");
                ret = -ENODEV;
                goto fail_free_mdev;
        }

        /* This driver requires the whole-frame credit protocol in FPGA34. */
        if (ioread32(mdev->user_bar + REG_VERSION) != FRAME_CREDIT_VERSION) {
                pr_err(DRIVER_NAME ": FPGA whole-frame credit version mismatch\n");
                ret = -ENODEV;
                goto fail_free_mdev;
        }

        /* Read current cam_mode from FPGA and clamp to allowed set */
        mdev->cam_mode = ioread32(mdev->user_bar + REG_CAM_MODE) & 0x3;
        if (mdev->cam_mode >= NUM_MODES)
                mdev->cam_mode = DEFAULT_MODE;
        mdev->cam_mode = milianke_clamp_mode(mdev->cam_mode);

        /* Apply clamped mode back to FPGA */
        iowrite32(mdev->cam_mode, mdev->user_bar + REG_CAM_MODE);

        mdev->width = ioread32(mdev->user_bar + REG_WIDTH);
        mdev->height = ioread32(mdev->user_bar + REG_HEIGHT);
        mdev->padded_frame_bytes = ioread32(mdev->user_bar + REG_PADDED_BYTES);
        mdev->pixel_bytes = mdev->width * mdev->height * BPP;

        if (mdev->padded_frame_bytes == 0 ||
            mdev->padded_frame_bytes < mdev->pixel_bytes) {
                u32 line_bytes = mdev->width * BPP;
                u32 beats = (line_bytes + 63) / 64;
                mdev->padded_frame_bytes = beats * mdev->height * 64;
        }
        mdev->read_size = mdev->padded_frame_bytes;

        pr_info(DRIVER_NAME ": video %ux%u (mode=%u), pixel=%u, padded=%u\n",
                mdev->width, mdev->height, mdev->cam_mode,
                mdev->pixel_bytes, mdev->padded_frame_bytes);

        mutex_init(&mdev->lock);
        spin_lock_init(&mdev->buf_lock);
        INIT_LIST_HEAD(&mdev->buf_list);

        /* V4L2 controls: expose AE_GAIN as standard V4L2_CID_GAIN */
        v4l2_ctrl_handler_init(&mdev->ctrl_handler, 1);
        v4l2_ctrl_new_std(&mdev->ctrl_handler, &milianke_ctrl_ops,
                          V4L2_CID_GAIN, 0, 1023, 1, 100);
        if (mdev->ctrl_handler.error) {
                ret = mdev->ctrl_handler.error;
                pr_err(DRIVER_NAME ": ctrl handler error: %d\n", ret);
                goto fail_ctrl_free;
        }

        ret = v4l2_device_register(&pdev->dev, &mdev->v4l2_dev);
        if (ret) {
                pr_err(DRIVER_NAME ": v4l2_device_register failed: %d\n", ret);
                goto fail_ctrl_free;
        }
        mdev->v4l2_dev.ctrl_handler = &mdev->ctrl_handler;

        q = &mdev->queue;
        q->type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        q->io_modes = VB2_MMAP | VB2_DMABUF | VB2_READ;
        q->drv_priv = mdev;
        q->ops = &milianke_vb2_ops;
        q->mem_ops = &vb2_dma_contig_memops;
        q->buf_struct_size = sizeof(struct milianke_v4l2_buffer);
        q->timestamp_flags = V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC;
        q->min_buffers_needed = MIN_BUFFERS;
        q->lock = &mdev->lock;
        q->dev = &pdev->dev;

        ret = vb2_queue_init(q);
        if (ret) {
                pr_err(DRIVER_NAME ": vb2_queue_init failed: %d\n", ret);
                goto fail_v4l2_unreg;
        }

        strscpy(mdev->vdev.name, CARD_NAME, sizeof(mdev->vdev.name));
        mdev->vdev.v4l2_dev = &mdev->v4l2_dev;
        mdev->vdev.fops = &milianke_fops;
        mdev->vdev.ioctl_ops = &milianke_ioctl_ops;
        mdev->vdev.queue = &mdev->queue;
        mdev->vdev.release = video_device_release_empty;
        mdev->vdev.lock = &mdev->lock;
        mdev->vdev.device_caps = V4L2_CAP_VIDEO_CAPTURE | V4L2_CAP_STREAMING |
                                 V4L2_CAP_READWRITE;
        video_set_drvdata(&mdev->vdev, mdev);

        ret = video_register_device(&mdev->vdev, VFL_TYPE_VIDEO, -1);
        if (ret) {
                pr_err(DRIVER_NAME ": video_register_device failed: %d\n", ret);
                goto fail_v4l2_unreg;
        }

        g_mdev = mdev;

        pr_info(DRIVER_NAME ": registered as /dev/video%d (%ux%u RGB24, zero-copy, max=1080p)\n",
                mdev->vdev.num, mdev->width, mdev->height);
        return 0;

fail_v4l2_unreg:
        v4l2_device_unregister(&mdev->v4l2_dev);
fail_ctrl_free:
        v4l2_ctrl_handler_free(&mdev->ctrl_handler);
fail_free_mdev:
        kfree(mdev);
fail_put_pdev:
        pci_dev_put(pdev);
        return ret;
}

static void __exit milianke_v4l2_exit(void)
{
        struct milianke_v4l2_dev *mdev = g_mdev;

        if (!mdev)
                return;

        video_unregister_device(&mdev->vdev);
        v4l2_device_unregister(&mdev->v4l2_dev);
        v4l2_ctrl_handler_free(&mdev->ctrl_handler);
        pci_dev_put(mdev->pdev);
        kfree(mdev);
        g_mdev = NULL;

        pr_info(DRIVER_NAME ": removed\n");
}

module_init(milianke_v4l2_init);
module_exit(milianke_v4l2_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Milianke PCIe Video");
MODULE_DESCRIPTION("V4L2 zero-copy capture for Milianke SGDMA PCIe FPGA (max 1080p)");
MODULE_VERSION("0.3");
