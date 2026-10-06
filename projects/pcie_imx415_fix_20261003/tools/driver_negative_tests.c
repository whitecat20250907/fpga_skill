/* Real RK3576 negative tests for repaired PH1A90 SGDMA/V4L2 drivers.
 * gcc -std=gnu11 -O2 -Wall -Wextra -o driver_negative_tests driver_negative_tests.c
 * usage: driver_negative_tests /dev/videoX /dev/ANLOGIC-PCI0 BAR_resource0
 * Run with camera applications stopped and the V4L2 driver loaded.
 * Each verdict is JSON. No image read/write DMA is performed by this tool. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define MAX_BUFFERS 8
#define REG_CTRL 0x60
#define REG_CAM_MODE 0x90
#define REG_IMAGE_LOOPBACK 0xA4
struct mapping { void *address; size_t size; };
struct video {
    int fd;
    bool streaming;
    unsigned count;
    struct mapping buffers[MAX_BUFFERS];
};
static volatile sig_atomic_t interrupted;
static unsigned passed, failed;
static int cleanup_error;
static void stop_tests(int signo) { (void)signo; interrupted = 1; }
static int xio(int fd, unsigned long cmd, void *arg) {
    int ret;
    do { ret = ioctl(fd, cmd, arg); }
    while (ret < 0 && errno == EINTR && !interrupted);
    return ret;
}
static void remember_cleanup_error(void) {
    if (!cleanup_error) cleanup_error = errno ? errno : EIO;
}
static void close_fd(int *fd) {
    if (*fd >= 0) {
        if (close(*fd) < 0) remember_cleanup_error();
        *fd = -1; /* Linux close(EINTR) must not be retried on a reused fd. */
    }
}
static void verdict(const char *name, bool pass, int observed_errno,
                    int expected_errno, const char *stage) {
    pass = pass && !interrupted;
    if (pass) passed++; else failed++;
    printf("{\"test\":\"%s\",\"pass\":%s,\"errno\":%d,\"expected_errno\":%d,\"stage\":\"%s\"}\n",
           name, pass ? "true" : "false", observed_errno, expected_errno, stage);
    fflush(stdout);
}
static void video_init(struct video *v) {
    memset(v, 0, sizeof(*v));
    v->fd = -1;
}
static int video_cleanup(struct video *v) {
    int first_error = 0;
    if (v->fd >= 0 && v->streaming) {
        enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        if (xio(v->fd, VIDIOC_STREAMOFF, &type) < 0) first_error = errno;
        else v->streaming = false;
    }
    for (unsigned i = 0; i < v->count; i++) {
        if (v->buffers[i].address && v->buffers[i].address != MAP_FAILED) {
            if (munmap(v->buffers[i].address, v->buffers[i].size) < 0 && !first_error)
                first_error = errno;
            v->buffers[i].address = NULL;
        }
    }
    if (v->fd >= 0) {
        /* Explicitly release allocated vb2 buffers; close is still required
         * if REQBUFS(0) fails or STREAMOFF was interrupted. */
        struct v4l2_requestbuffers free_bufs = {
            .count = 0, .type = V4L2_BUF_TYPE_VIDEO_CAPTURE,
            .memory = V4L2_MEMORY_MMAP
        };
        if (v->count && xio(v->fd, VIDIOC_REQBUFS, &free_bufs) < 0 && !first_error)
            first_error = errno;
        if (close(v->fd) < 0 && !first_error) first_error = errno;
    }
    video_init(v);
    if (first_error && !cleanup_error) cleanup_error = first_error;
    return first_error;
}
static int set_format(int fd, unsigned width, unsigned height) {
    struct v4l2_format fmt = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE};
    fmt.fmt.pix.width = width;
    fmt.fmt.pix.height = height;
    fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_RGB24;
    fmt.fmt.pix.field = V4L2_FIELD_NONE;
    if (xio(fd, VIDIOC_S_FMT, &fmt) < 0) return -1;
    if (fmt.fmt.pix.width != width || fmt.fmt.pix.height != height ||
        fmt.fmt.pix.pixelformat != V4L2_PIX_FMT_RGB24) {
        errno = EPROTO;
        return -1;
    }
    return 0;
}
static int video_open(struct video *v, const char *node) {
    struct v4l2_capability cap;
    v->fd = open(node, O_RDWR | O_NONBLOCK);
    if (v->fd < 0) return -1;
    memset(&cap, 0, sizeof(cap));
    if (xio(v->fd, VIDIOC_QUERYCAP, &cap) < 0) return -1;
    if (!strstr((const char *)cap.card, "Milianke PCIe Capture")) {
        errno = ENODEV;
        return -1;
    }
    return 0;
}
static int video_allocate_720(struct video *v, const char *node) {
    if (video_open(v, node) < 0 || set_format(v->fd, 1280, 720) < 0) return -1;
    struct v4l2_requestbuffers req = {
        .count = 4, .type = V4L2_BUF_TYPE_VIDEO_CAPTURE,
        .memory = V4L2_MEMORY_MMAP
    };
    if (xio(v->fd, VIDIOC_REQBUFS, &req) < 0) return -1;
    if (req.count < 4 || req.count > MAX_BUFFERS) {
        errno = ENOBUFS;
        return -1;
    }
    v->count = req.count;
    for (unsigned i = 0; i < v->count; i++) {
        struct v4l2_buffer b = {
            .type = req.type, .memory = req.memory, .index = i
        };
        if (xio(v->fd, VIDIOC_QUERYBUF, &b) < 0) return -1;
        v->buffers[i].size = b.length;
        v->buffers[i].address = mmap(NULL, b.length, PROT_READ | PROT_WRITE,
                                    MAP_SHARED, v->fd, b.m.offset);
        if (v->buffers[i].address == MAP_FAILED) return -1;
        if (xio(v->fd, VIDIOC_QBUF, &b) < 0) return -1;
    }
    return 0;
}
static int stream_on(struct video *v) {
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (xio(v->fd, VIDIOC_STREAMON, &type) < 0) return -1;
    v->streaming = true;
    return 0;
}
static void test_double_open(const char *name, const char *path, int flags) {
    int first = -1, second = -1, observed = 0;
    const char *stage = "second_open";
    bool pass = false;
    first = open(path, flags);
    if (first < 0) {
        observed = errno;
        stage = "first_open_failed";
    } else {
        errno = 0;
        second = open(path, flags);
        observed = second < 0 ? errno : 0;
        pass = second < 0 && observed == EBUSY;
    }
    close_fd(&second);
    close_fd(&first);
    verdict(name, pass, observed, EBUSY, stage);
}
static void test_raw_blocks_video(const char *video_node, const char *c2h) {
    struct video v;
    video_init(&v);
    int raw = -1, observed = 0;
    const char *stage = "streamon";
    bool pass = false;
    raw = open(c2h, O_RDONLY | O_TRUNC);
    if (raw < 0) {
        observed = errno;
        stage = "raw_open_failed";
    } else if (video_allocate_720(&v, video_node) < 0) {
        observed = errno;
        stage = "allocate_failed";
    } else {
        errno = 0;
        int ret = stream_on(&v);
        observed = ret < 0 ? errno : 0;
        pass = ret < 0 && observed == EBUSY;
    }
    if (video_cleanup(&v)) pass = false;
    close_fd(&raw);
    verdict("raw_c2h_blocks_streamon", pass, observed, EBUSY, stage);
}
static void test_allocated_blocks_format(const char *video_node) {
    struct video v;
    video_init(&v);
    int observed = 0;
    const char *stage = "s_fmt_1080";
    bool pass = false;
    if (video_allocate_720(&v, video_node) < 0) {
        observed = errno;
        stage = "allocate_failed";
    } else {
        errno = 0;
        int ret = set_format(v.fd, 1920, 1080);
        observed = ret < 0 ? errno : 0;
        pass = ret < 0 && observed == EBUSY;
    }
    if (video_cleanup(&v)) pass = false;
    verdict("allocated_buffers_block_s_fmt", pass, observed, EBUSY, stage);
}
static bool mode_720_restored(volatile uint32_t *regs) {
    for (unsigned n = 0; n < 50 && !interrupted; n++) {
        if ((regs[REG_CAM_MODE / 4] & 3) == 2 &&
            regs[0x44 / 4] == 1280 && regs[0x48 / 4] == 720) return true;
        struct timespec delay = {.tv_nsec = 1000000};
        nanosleep(&delay, NULL);
    }
    return false;
}
static void test_mode_guard_and_restore(const char *video_node,
                                       volatile uint32_t *regs) {
    struct video v;
    video_init(&v);
    int observed = 0;
    const char *stage = "streamon_after_bar_mode0";
    bool pass = false;
    if (video_allocate_720(&v, video_node) < 0) {
        observed = errno;
        stage = "allocate_failed";
    } else {
        regs[REG_CAM_MODE / 4] = 0;
        (void)regs[REG_CAM_MODE / 4];
        errno = 0;
        int ret = stream_on(&v);
        observed = ret < 0 ? errno : 0;
        pass = ret < 0 && observed == EINVAL;
    }
    if (video_cleanup(&v)) pass = false;
    verdict("bar_mode_mismatch_blocks_streamon", pass, observed, EINVAL, stage);

    /* A new file, same driver-cached 720p mode; S_FMT must also repair the
     * externally modified BAR, even if the requested software mode matches. */
    video_init(&v);
    observed = 0;
    stage = "s_fmt_720_restores_bar";
    pass = false;
    if (video_open(&v, video_node) < 0 || set_format(v.fd, 1280, 720) < 0) {
        observed = errno;
        stage = "s_fmt_failed";
    } else {
        pass = mode_720_restored(regs);
        if (!pass) observed = EPROTO;
    }
    if (video_cleanup(&v)) pass = false;
    verdict("s_fmt_resynchronizes_hardware", pass, observed, 0, stage);
}
static void test_stream_ownership(const char *video_node, const char *c2h) {
    struct video v;
    video_init(&v);
    int raw = -1, observed = 0;
    const char *stage = "raw_open_during_streamon";
    bool pass = false;
    if (video_allocate_720(&v, video_node) < 0) {
        observed = errno;
        stage = "allocate_failed";
    } else if (stream_on(&v) < 0) {
        observed = errno;
        stage = "streamon_failed";
    } else {
        errno = 0;
        raw = open(c2h, O_RDONLY | O_TRUNC);
        observed = raw < 0 ? errno : 0;
        pass = raw < 0 && observed == EBUSY;
    }
    close_fd(&raw);
    verdict("streamon_blocks_raw_c2h_open", pass, observed, EBUSY, stage);

    observed = 0;
    stage = "raw_open_after_streamoff";
    pass = false;
    if (!v.streaming) {
        observed = EPROTO;
        stage = "preceding_streamon_not_active";
    } else {
        enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        if (xio(v.fd, VIDIOC_STREAMOFF, &type) < 0) {
            observed = errno;
            stage = "streamoff_failed";
        } else {
            v.streaming = false;
            raw = open(c2h, O_RDONLY | O_TRUNC);
            observed = raw < 0 ? errno : 0;
            pass = raw >= 0;
        }
    }
    close_fd(&raw);
    if (video_cleanup(&v)) pass = false;
    verdict("streamoff_releases_raw_c2h", pass, observed, 0, stage);
}
int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: %s video_node device_prefix bar_path\n", argv[0]);
        return 2;
    }
    struct sigaction sa = {.sa_handler = stop_tests};
    sigemptyset(&sa.sa_mask);
    if (sigaction(SIGINT, &sa, NULL) || sigaction(SIGTERM, &sa, NULL)) {
        perror("sigaction");
        return 2;
    }
    char c2h[512], h2c[512];
    if (snprintf(c2h, sizeof(c2h), "%s_c2h_0", argv[2]) >= (int)sizeof(c2h) ||
        snprintf(h2c, sizeof(h2c), "%s_h2c_0", argv[2]) >= (int)sizeof(h2c)) return 2;
    int barfd = open(argv[3], O_RDWR | O_SYNC);
    if (barfd < 0) {
        verdict("preflight", false, errno, 0, "bar_open_failed");
        return 2;
    }
    volatile uint32_t *regs = mmap(NULL, 4096, PROT_READ | PROT_WRITE,
                                   MAP_SHARED, barfd, 0);
    if (regs == MAP_FAILED) {
        verdict("preflight", false, errno, 0, "bar_mmap_failed");
        close(barfd);
        return 2;
    }
    /* Refuse to mutate another active camera/loopback session. */
    if ((regs[REG_CTRL / 4] & 1) || (regs[REG_IMAGE_LOOPBACK / 4] & 1)) {
        verdict("preflight", false, EBUSY, 0, "stop_existing_camera_or_loopback");
        munmap((void *)regs, 4096);
        close(barfd);
        return 2;
    }
    test_double_open("c2h_double_open", c2h, O_RDONLY | O_TRUNC);
    if (!interrupted) test_double_open("h2c_double_open", h2c, O_WRONLY);
    if (!interrupted) test_raw_blocks_video(argv[1], c2h);
    if (!interrupted) test_allocated_blocks_format(argv[1]);
    if (!interrupted) test_mode_guard_and_restore(argv[1], regs);
    if (!interrupted) test_stream_ownership(argv[1], c2h);
    /* All test-owned mappings/filehandles have been closed before reset. */
    struct video restore;
    video_init(&restore);
    if (video_open(&restore, argv[1]) < 0 ||
        set_format(restore.fd, 1920, 1080) < 0) remember_cleanup_error();
    video_cleanup(&restore); /* keep V4L2 cached format consistent with mode0 */
    regs[REG_CTRL / 4] = 0;
    regs[REG_CAM_MODE / 4] = 0;
    regs[REG_IMAGE_LOOPBACK / 4] = 0;
    regs[0x20 / 4] = 0;
    regs[REG_CTRL / 4] = 2;
    unsigned final_mode = regs[REG_CAM_MODE / 4] & 3;
    unsigned final_control = regs[REG_CTRL / 4];
    if (munmap((void *)regs, 4096) < 0) remember_cleanup_error();
    close_fd(&barfd);
    bool all_passed = passed == 8 && !failed && !cleanup_error && !interrupted &&
                      final_mode == 0 && !(final_control & 1);
    printf("{\"summary\":\"driver_negative_tests\",\"passed\":%u,\"failed\":%u,\"total\":%u,\"cleanup_errno\":%d,\"final_mode\":%u,\"final_ctrl\":%u,\"interrupted\":%s,\"all_passed\":%s}\n",
           passed, failed, passed + failed, cleanup_error, final_mode,
           final_control, interrupted ? "true" : "false", all_passed ? "true" : "false");
    return all_passed ? 0 : 1;
}
