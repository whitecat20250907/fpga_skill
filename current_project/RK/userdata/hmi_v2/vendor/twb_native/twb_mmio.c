#define _GNU_SOURCE
#include "twb_mmio.h"
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/file.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

/* Device mapping comes from the existing SGDMA user node. Never map a guessed
 * physical address or write through Python byte slices. All DATA are a single
 * aligned volatile uint32_t store. Device readback drains posted PCIe writes.
 * kernel.org/doc/html/latest/driver-api/io_ordering.html
 * support.arm.com/documentation/102336/0100/Limiting-the-scope-of-memory-barriers
 */
struct native {int fd,writable;volatile uint32_t *bar;struct twb_session session;};
_Static_assert(sizeof(uint32_t)==4,"32-bit MMIO required");
uint32_t twb_native_library_abi(void){return UINT32_C(0x32535754);}
static void io_barrier(void){
#if defined(__aarch64__)
    __asm__ __volatile__("dsb sy":::"memory");
#elif defined(__x86_64__) || defined(__i386__)
    __sync_synchronize();
#else
#error Unsupported MMIO architecture; implement and verify native barriers.
#endif
}
static int read32(void *opaque,uint32_t offset,uint32_t *out){
    struct native *n=opaque;
    if((offset&3u)||offset>=4096u||!out)return -1;
    io_barrier();*out=n->bar[offset/4u];io_barrier();return 0;
}
static int write32(void *opaque,uint32_t offset,uint32_t value){
    struct native *n=opaque;
    if(!n->writable||(offset!=TWB_DATA&&offset!=TWB_CONTROL&&offset!=TWB_ANCHOR))return -1;
    io_barrier();n->bar[offset/4u]=value;io_barrier();return 0;
}
static uint64_t monotonic_ns(void *opaque){
    (void)opaque;struct timespec t;
    if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;
    return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;
}
static int open_native(const char *device,int writable,struct native **out){
#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
    (void)device;(void)writable;(void)out;return TWB_ARGUMENT;
#else
    if(!device||!out)return TWB_ARGUMENT;
    *out=0;struct native *n=calloc(1,sizeof(*n));if(!n)return TWB_IO;
    n->fd=open(device,(writable?O_RDWR:O_RDONLY)|O_SYNC|O_CLOEXEC|O_NOFOLLOW);
    if(n->fd<0){free(n);return TWB_IO;}
    struct stat st;
    if(fstat(n->fd,&st)||!S_ISCHR(st.st_mode)||(writable&&flock(n->fd,LOCK_EX|LOCK_NB))){close(n->fd);free(n);return TWB_IO;}
    void *mapping=mmap(0,4096,PROT_READ|(writable?PROT_WRITE:0),MAP_SHARED,n->fd,0);
    if(mapping==MAP_FAILED){close(n->fd);free(n);return TWB_IO;}
    n->bar=mapping;n->writable=writable;
    twb_init(&n->session,(struct twb_io){n,read32,write32,monotonic_ns});
    *out=n;return TWB_OK;
#endif
}
void twb_native_close(void *handle){
    struct native *n=handle;if(!n)return;
    munmap((void *)n->bar,4096);close(n->fd);free(n);
}
int twb_native_probe(const char *device,struct twb_probe *out){
    struct native *n=0;int rc=open_native(device,0,&n);if(rc)return rc;
    rc=twb_probe(&n->session,out);twb_native_close(n);return rc;
}
int twb_native_open(const char *device,void **out){
    if(!out)return TWB_ARGUMENT;
    *out=0;
    struct native *n=0;int rc=open_native(device,1,&n);if(rc)return rc;
    rc=twb_probe(&n->session,0);
    if(rc){twb_native_close(n);return rc;}
    *out=n;return TWB_OK;
}
int twb_native_flush_begin(void *p){return p?twb_flush_begin(&((struct native *)p)->session):TWB_ARGUMENT;}
int twb_native_flush_poll(void *p){return p?twb_flush_poll(&((struct native *)p)->session):TWB_ARGUMENT;}
int twb_native_prepare(void *p,uint32_t reserve,uint64_t *now,uint64_t *token){return p?twb_prepare(&((struct native *)p)->session,reserve,now,token):TWB_ARGUMENT;}
int twb_native_cancel(void *p,uint64_t token){return p?twb_cancel(&((struct native *)p)->session,token):TWB_ARGUMENT;}
int twb_native_commit(void *p,uint64_t token,const uint8_t *data,size_t size){return p?twb_commit(&((struct native *)p)->session,token,data,size):TWB_ARGUMENT;}
int twb_native_snapshot(void *p,struct twb_snapshot *s){return p?twb_read_snapshot(&((struct native *)p)->session,s):TWB_ARGUMENT;}
