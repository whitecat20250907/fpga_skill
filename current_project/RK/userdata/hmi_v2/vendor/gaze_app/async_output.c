#define _POSIX_C_SOURCE 200809L
#include "async_output.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

enum { FREE, FILLING, READY, WRITING };
static uint64_t now_ns(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);
    return (uint64_t)t.tv_sec*1000000000u+(uint64_t)t.tv_nsec;
}
static int writer_fail(struct async_output *q,int error,const char *origin,int syscall_failure) {
    /* Writer-owned diagnostics; never infer these from the shared q->error.
     * EAGAIN/EINTR retries are counted separately, not called the first fault. */
    int saved=error?error:EIO;
    q->writer_error_origin=origin;
    if(syscall_failure&&!q->writer_first_syscall_errno) {
        q->writer_first_syscall_errno=saved;
        q->writer_first_syscall_error_ns=now_ns();
        q->writer_first_syscall_origin=origin;
    }
    errno=saved;return -1;
}
static int write_all(struct async_output *q,const void *data,size_t size) {
    const unsigned char *p=data; uint64_t progress=now_ns();
    while(size) {
        uint_fast64_t deadline=atomic_load(&q->finish_deadline_ns);
        if(deadline&&now_ns()>=deadline)return writer_fail(q,ETIMEDOUT,"finish_deadline",0);
        q->write_calls++;ssize_t n=write(STDOUT_FILENO,p,size);
        if(n<0)q->write_error_calls++;
        if(n>0) {q->writer_bytes+=(uint64_t)n;p+=n;size-=(size_t)n;progress=now_ns();continue;}
        if(n<0&&errno==EINTR){q->write_eintr_calls++;continue;}
        if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK)) {
            q->write_eagain_calls++;
            if(now_ns()-progress>=(uint64_t)q->timeout_ms*1000000u)return writer_fail(q,ETIMEDOUT,"write_progress_timeout",0);
            struct pollfd fd={.fd=STDOUT_FILENO,.events=POLLOUT};
            q->poll_calls++;int r=poll(&fd,1,50);
            if(r<0)q->poll_error_calls++;
            if(r<0&&errno==EINTR){q->poll_eintr_calls++;continue;}
            if(r<0)return writer_fail(q,errno,"poll_syscall",1);
            if(r>0&&(fd.revents&(POLLERR|POLLHUP|POLLNVAL)))return writer_fail(q,EPIPE,"poll_revents",0);
            continue;
        }
        return writer_fail(q,n==0?EPIPE:errno,n==0?"write_zero":"write_syscall",n<0);
    }
    return 0;
}
static void le32(unsigned char *p,uint32_t n) {for(int i=0;i<4;i++)p[i]=(unsigned char)(n>>(8*i));}
static int record(struct async_output *q,const char *json,const void *payload,uint32_t length) {
    unsigned char h[12]={'M','C','F','1'};size_t n=strlen(json);
    if(n>4095)return writer_fail(q,EOVERFLOW,"record_metadata_bounds",0);
    le32(h+4,(uint32_t)n);le32(h+8,length);
    if(write_all(q,h,sizeof(h))||write_all(q,json,n))return -1;
    if(length&&write_all(q,payload,length))return -1;
    q->writer_records++;return 0;
}
static void *writer_main(void *arg) {
    struct async_output *q=arg;
    if(record(q,q->start_json,NULL,0))goto fail;
    for(;;) {
        pthread_mutex_lock(&q->lock);
        while(q->latest<0&&!q->done)pthread_cond_wait(&q->ready,&q->lock);
        if(q->latest<0&&q->done) {pthread_mutex_unlock(&q->lock);break;}
        struct output_slot *slot=&q->slots[q->latest];
        slot->state=WRITING;q->latest=-1;
        pthread_mutex_unlock(&q->lock);
        if(record(q,slot->json,slot->payload,slot->length))goto fail;
        pthread_mutex_lock(&q->lock);q->sent++;slot->state=FREE;pthread_mutex_unlock(&q->lock);
    }
    char end[1024];
    snprintf(end,sizeof(end),"{\"kind\":\"end\",\"frames\":%" PRIu64 ",\"captured_frames\":%" PRIu64 ",\"software_dropped_frames\":%" PRIu64 ",\"errno\":%d,\"cleanup_errno\":%d,\"stage\":\"%s\",\"elapsed_ns\":%" PRIu64 "}",q->sent,q->captured,q->dropped,q->capture_error,q->cleanup_error,q->stage,q->elapsed_ns);
    if(record(q,end,NULL,0))goto fail;
    return NULL;
fail:
    q->writer_errno=errno?errno:EIO;q->writer_error_ns=now_ns();
    atomic_store(&q->error,q->writer_errno);
    fprintf(stderr,"{\"kind\":\"writer_terminal_error_v1\",\"errno\":%d,\"timestamp_ns\":%" PRIu64 ",\"origin\":\"%s\"}\n",
            q->writer_errno,q->writer_error_ns,q->writer_error_origin?q->writer_error_origin:"unrecorded");
    return NULL;
}
int output_init(struct async_output *q,size_t capacity,const char *start,unsigned timeout_ms) {
    memset(q,0,sizeof(*q));q->latest=-1;q->stdout_flags=-1;atomic_init(&q->error,0);atomic_init(&q->finish_deadline_ns,0);
    if(!capacity||capacity>67108864||strlen(start)>=sizeof(q->start_json)||timeout_ms<100||timeout_ms>30000) {errno=EINVAL;return -1;}
    q->capacity=capacity;q->timeout_ms=timeout_ms;strcpy(q->start_json,start);
    int err=pthread_mutex_init(&q->lock,NULL);
    if(err) {errno=err;return -1;}
    err=pthread_cond_init(&q->ready,NULL);
    if(err) {pthread_mutex_destroy(&q->lock);errno=err;return -1;}
    for(int i=0;i<2;i++) {
        q->slots[i].payload=malloc(capacity);
        if(!q->slots[i].payload)goto fail;
    }
    q->stdout_flags=fcntl(STDOUT_FILENO,F_GETFL);
    if(q->stdout_flags<0||fcntl(STDOUT_FILENO,F_SETFL,q->stdout_flags|O_NONBLOCK)<0)goto fail;
    err=pthread_create(&q->writer,NULL,writer_main,q);
    if(err) {errno=err;goto fail;}
    q->started=1;return 0;
fail: {
    int saved=errno;
    if(q->stdout_flags>=0)(void)fcntl(STDOUT_FILENO,F_SETFL,q->stdout_flags);
    for(int i=0;i<2;i++)free(q->slots[i].payload);
    pthread_cond_destroy(&q->ready);pthread_mutex_destroy(&q->lock);errno=saved;return -1;
    }
}
struct output_slot *output_reserve(struct async_output *q) {
    int failure=atomic_load(&q->error);
    if(failure) {errno=failure;return NULL;}
    pthread_mutex_lock(&q->lock);
    int index=-1;
    for(int i=0;i<2;i++)if(q->slots[i].state==FREE) {index=i;break;}
    if(index<0&&q->latest>=0) {index=q->latest;q->latest=-1;q->dropped++;}
    if(index>=0)q->slots[index].state=FILLING;
    pthread_mutex_unlock(&q->lock);
    if(index<0)errno=EPROTO; /* single producer + one writer must always leave a slot */
    return index<0?NULL:&q->slots[index];
}
int output_discard(struct async_output *q,struct output_slot *slot) {
    if(slot!=&q->slots[0]&&slot!=&q->slots[1]) {errno=EINVAL;return -1;}
    pthread_mutex_lock(&q->lock);
    if(slot->state!=FILLING) {pthread_mutex_unlock(&q->lock);errno=EPROTO;return -1;}
    slot->length=0;slot->state=FREE;
    pthread_mutex_unlock(&q->lock);return 0;
}
int output_publish(struct async_output *q,struct output_slot *slot) {
    int index=slot==&q->slots[0]?0:slot==&q->slots[1]?1:-1;
    if(index<0||slot->length>q->capacity) {errno=EINVAL;return -1;}
    pthread_mutex_lock(&q->lock);
    if(slot->state!=FILLING) {pthread_mutex_unlock(&q->lock);errno=EPROTO;return -1;}
    if(q->latest>=0) {q->slots[q->latest].state=FREE;q->dropped++;}
    slot->state=READY;q->latest=index;q->published++;
    pthread_cond_signal(&q->ready);pthread_mutex_unlock(&q->lock);return 0;
}
uint64_t output_dropped(struct async_output *q) {
    pthread_mutex_lock(&q->lock);uint64_t result=q->dropped;pthread_mutex_unlock(&q->lock);return result;
}
struct output_stats output_finish(struct async_output *q,uint64_t captured,int error,int cleanup,const char *stage,uint64_t elapsed) {
    /* A continuously trickling reader also cannot prolong teardown forever. */
    atomic_store(&q->finish_deadline_ns,now_ns()+(uint64_t)q->timeout_ms*1000000u);
    pthread_mutex_lock(&q->lock);
    q->captured=captured;q->capture_error=error;q->cleanup_error=cleanup;q->elapsed_ns=elapsed;
    snprintf(q->stage,sizeof(q->stage),"%s",stage);q->done=1;pthread_cond_signal(&q->ready);
    pthread_mutex_unlock(&q->lock);
    int err=pthread_join(q->writer,NULL);q->writer_join_errno=err;
    struct output_stats result={q->published,q->sent,q->dropped,err?err:atomic_load(&q->error)};
    for(int i=0;i<2;i++)free(q->slots[i].payload);
    if(fcntl(STDOUT_FILENO,F_SETFL,q->stdout_flags)<0&&!result.error)result.error=errno;
    pthread_cond_destroy(&q->ready);pthread_mutex_destroy(&q->lock);
    return result;
}
