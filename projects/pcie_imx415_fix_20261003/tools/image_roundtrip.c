/* Full RGB frame bytes: RK H2C -> FPGA FIFO -> RK C2H.
 * gcc -O2 -Wall -Wextra -pthread -o image_roundtrip image_roundtrip.c
 * Requires repaired stream-ownership driver and loop-FIFO soft reset.
 * Run with V4L2 unloaded. SIGINT/SIGTERM restore the camera mux after
 * outstanding DMA calls finish/timeout; SIGKILL cannot perform cleanup. */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <pthread.h>
#include <signal.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>

struct test {
    int rx, out;
    unsigned char *source;
    size_t size, chunk;
    unsigned frames;
    size_t read_bytes, mismatches;
    atomic_bool failed, stop;
};
static volatile sig_atomic_t interrupted;
static void interrupt_test(int signo) { (void)signo; interrupted = 1; }
static bool stopping(struct test *t) { return interrupted || atomic_load(&t->stop); }
static void fail_test(struct test *t) {
    atomic_store(&t->failed, true);
    atomic_store(&t->stop, true);
}
static double clock_s(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}
static int save_all(int fd, const unsigned char *data, size_t size) {
    size_t offset = 0;
    while (offset < size) {
        ssize_t written = write(fd, data + offset, size - offset);
        if (written < 0 && errno == EINTR) continue;
        if (written <= 0) return -1;
        offset += (size_t)written;
    }
    return 0;
}
static void *receive(void *arg) {
    struct test *t = arg;
    unsigned char *buf = NULL;
    if (posix_memalign((void **)&buf, 4096, t->chunk)) {
        fprintf(stderr, "C2H buffer allocation failed\n");
        fail_test(t);
        return NULL;
    }
    for (unsigned f = 0; f < t->frames && !stopping(t); f++) {
        size_t offset = 0;
        while (offset < t->size && !stopping(t)) {
            size_t wanted = t->size - offset;
            if (wanted > t->chunk) wanted = t->chunk;
            ssize_t got = read(t->rx, buf, wanted);
            if (got != (ssize_t)wanted) {
                if (got < 0) perror("C2H read");
                fprintf(stderr, "short C2H frame=%u offset=%zu got=%zd expected=%zu\n",
                        f, offset, got, wanted);
                fail_test(t);
                free(buf);
                return NULL;
            }
            for (size_t k = 0; k < wanted; k++) {
                if (buf[k] == t->source[offset + k]) continue;
                if (t->mismatches < 8)
                    fprintf(stderr, "byte mismatch frame=%u offset=%zu got=%02x expected=%02x\n",
                            f, offset + k, buf[k], t->source[offset + k]);
                t->mismatches++;
            }
            if (f == 0 && save_all(t->out, buf, wanted)) {
                perror("save echo");
                fail_test(t);
                free(buf);
                return NULL;
            }
            offset += wanted;
            t->read_bytes += wanted;
        }
    }
    free(buf);
    return NULL;
}
static int number(const char *text, size_t *value) {
    char *end;
    errno = 0;
    unsigned long long n = strtoull(text, &end, 0);
    if (errno || *end || text == end || text[0] == '-' || n > SIZE_MAX) return -1;
    *value = (size_t)n;
    return 0;
}
int main(int argc, char **argv) {
    if (argc != 7) {
        fprintf(stderr, "usage: %s device_prefix input.rgb echo.rgb frames chunk_bytes bar_path\n", argv[0]);
        return 2;
    }
    struct test t = {.rx = -1, .out = -1};
    atomic_init(&t.failed, false);
    atomic_init(&t.stop, false);
    size_t frames;
    if (number(argv[4], &frames) || number(argv[5], &t.chunk) ||
        !frames || frames > UINT32_MAX || !t.chunk || t.chunk % 16) return 2;
    t.frames = (unsigned)frames;
    /* Kernel ownership is the final gate; preflight also avoids modifying
     * a camera controlled by a loaded, currently idle V4L2 driver. */
    if (access("/sys/module/milianke_v4l2", F_OK) == 0) {
        fprintf(stderr, "Unload milianke_v4l2 before a full image roundtrip\n");
        return 2;
    }
    struct sigaction sa = {.sa_handler = interrupt_test};
    sigemptyset(&sa.sa_mask);
    if (sigaction(SIGINT, &sa, NULL) || sigaction(SIGTERM, &sa, NULL)) {
        perror("sigaction");
        return 2;
    }
    char path[512];
    int input = -1, barfd = -1, tx = -1, result = 2;
    volatile uint32_t *regs = MAP_FAILED;
    bool armed = false, thread_started = false;
    pthread_t thread;
    size_t sent = 0;
    double started = clock_s();
    struct stat st;
    input = open(argv[2], O_RDONLY);
    if (input < 0 || fstat(input, &st)) { perror("input"); goto cleanup; }
    if (st.st_size <= 0 || (uintmax_t)st.st_size > SIZE_MAX || st.st_size % 16)
        goto cleanup;
    struct stat output_st;
    if (stat(argv[3], &output_st) == 0 && output_st.st_dev == st.st_dev &&
        output_st.st_ino == st.st_ino) {
        fprintf(stderr, "Input image and echo output must be different files\n");
        goto cleanup;
    }
    t.size = (size_t)st.st_size;
    if (t.frames > SIZE_MAX / t.size) goto cleanup;
    if (posix_memalign((void **)&t.source, 4096, t.size)) goto cleanup;
    for (size_t offset = 0; offset < t.size;) {
        ssize_t got = read(input, t.source + offset, t.size - offset);
        if (got < 0 && errno == EINTR && !interrupted) continue;
        if (got <= 0 || interrupted) goto cleanup;
        offset += (size_t)got;
    }
    close(input); input = -1;
    /* Acquire both stream devices before touching mux or app control. */
    if (snprintf(path, sizeof(path), "%s_c2h_0", argv[1]) >= (int)sizeof(path)) goto cleanup;
    t.rx = open(path, O_RDONLY | O_TRUNC);
    if (snprintf(path, sizeof(path), "%s_h2c_0", argv[1]) >= (int)sizeof(path)) goto cleanup;
    tx = open(path, O_WRONLY);
    if (t.rx < 0 || tx < 0) { perror("DMA open"); goto cleanup; }
    t.out = open(argv[3], O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (t.out < 0) { perror("echo open"); goto cleanup; }
    barfd = open(argv[6], O_RDWR | O_SYNC);
    if (barfd < 0) { perror("BAR open"); goto cleanup; }
    regs = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, barfd, 0);
    if (regs == MAP_FAILED) { perror("BAR mmap"); goto cleanup; }
    armed = true;
    regs[0x60 / 4] = 2; /* camera and loop FIFO reset, enable remains off */
    (void)regs[0x60 / 4]; /* complete posted MMIO before enabling the route */
    regs[0x20 / 4] = 3;
    regs[0xA4 / 4] = 1;
    if (regs[0xA4 / 4] != 1) {
        fprintf(stderr, "FPGA image loopback register missing\n");
        goto cleanup;
    }
    int thread_error = pthread_create(&thread, NULL, receive, &t);
    if (thread_error) {
        fprintf(stderr, "pthread_create: %s\n", strerror(thread_error));
        goto cleanup;
    }
    thread_started = true;
    struct timespec arm = {.tv_nsec = 100000000};
    nanosleep(&arm, NULL);
    for (unsigned f = 0; f < t.frames && !stopping(&t); f++) {
        for (size_t offset = 0; offset < t.size && !stopping(&t);) {
            size_t wanted = t.size - offset;
            if (wanted > t.chunk) wanted = t.chunk;
            ssize_t wrote = write(tx, t.source + offset, wanted);
            if (wrote != (ssize_t)wanted) {
                if (wrote < 0) perror("H2C write");
                fprintf(stderr, "short H2C got=%zd expected=%zu\n", wrote, wanted);
                fail_test(&t);
                break;
            }
            offset += wanted;
            sent += wanted;
        }
    }
    if (interrupted) fail_test(&t);
    pthread_join(thread, NULL);
    thread_started = false;
    result = atomic_load(&t.failed) || interrupted || t.mismatches ||
             sent != t.size * t.frames || t.read_bytes != sent ? 1 : 0;
    printf("{\"frames\":%u,\"frame_bytes\":%zu,\"chunk_bytes\":%zu,\"sent\":%zu,\"received\":%zu,\"byte_mismatches\":%zu,\"failed\":%s,\"interrupted\":%s,\"seconds\":%.6f}\n",
           t.frames, t.size, t.chunk, sent, t.read_bytes, t.mismatches,
           result ? "true" : "false", interrupted ? "true" : "false", clock_s() - started);
cleanup:
    if (thread_started) {
        fail_test(&t);
        pthread_join(thread, NULL);
    }
    if (armed) {
        regs[0xA4 / 4] = 0;
        regs[0x20 / 4] = 0;
        regs[0x60 / 4] = 2;
        (void)regs[0x60 / 4];
    }
    if (tx >= 0) close(tx);
    if (t.rx >= 0) close(t.rx);
    if (t.out >= 0) close(t.out);
    if (regs != MAP_FAILED) munmap((void *)regs, 4096);
    if (barfd >= 0) close(barfd);
    if (input >= 0) close(input);
    free(t.source);
    return result;
}
