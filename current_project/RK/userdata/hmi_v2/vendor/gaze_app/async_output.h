#ifndef HCI_ASYNC_OUTPUT_H
#define HCI_ASYNC_OUTPUT_H
#include <pthread.h>
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>

/* Two private copies: one writer-owned and at most one pending. Camera DMA
 * mappings are never referenced by the output thread. Drops remain observable. */
struct output_slot { unsigned char *payload; uint32_t length; char json[4096]; int state; };
struct output_stats { uint64_t published, sent, dropped; int error; };
struct async_output {
    pthread_mutex_t lock;
    pthread_cond_t ready;
    pthread_t writer;
    struct output_slot slots[2];
    atomic_int error;
    atomic_uint_fast64_t finish_deadline_ns;
    size_t capacity;
    int latest, done, started, stdout_flags;
    unsigned timeout_ms;
    char start_json[4096], stage[96];
    int capture_error, cleanup_error;
    uint64_t captured, elapsed_ns, published, sent, dropped;
    /* Writer-owned until pthread_join succeeds; capture only reads afterward. */
    int writer_errno, writer_first_syscall_errno;
    uint64_t writer_error_ns, writer_first_syscall_error_ns;
    const char *writer_error_origin, *writer_first_syscall_origin;
    uint64_t write_calls, write_error_calls, write_eagain_calls, write_eintr_calls;
    uint64_t poll_calls, poll_error_calls, poll_eintr_calls, writer_bytes, writer_records;
    int writer_join_errno; /* output_finish owner, not the writer */
};
int output_init(struct async_output *, size_t, const char *, unsigned);
struct output_slot *output_reserve(struct async_output *);
int output_publish(struct async_output *, struct output_slot *);
int output_discard(struct async_output *, struct output_slot *);
uint64_t output_dropped(struct async_output *);
struct output_stats output_finish(struct async_output *, uint64_t, int, int, const char *, uint64_t);
#endif
