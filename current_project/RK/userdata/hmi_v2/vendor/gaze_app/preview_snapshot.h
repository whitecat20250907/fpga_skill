/* Optional raw RGB preview. POSIX record locks are process-owned, unlike
 * inherited flock open-file-description locks. Neither side waits for a lock.
 * The model's area3/MCF1 path and DMA ownership are independent of this slot. */
#ifndef GAZE_PREVIEW_SNAPSHOT_H
#define GAZE_PREVIEW_SNAPSHOT_H
#include <errno.h>
#include <fcntl.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#ifndef F_GET_SEALS
#define F_GET_SEALS 1034
#define F_SEAL_SEAL 0x0001
#define F_SEAL_SHRINK 0x0002
#define F_SEAL_GROW 0x0004
#endif
/* valid_bytes is a separate aligned, lock-free commit word in the 64B ABI.
 * A dead writer releases its POSIX lock: invalidation must precede any payload
 * mutation, and full validity must be the last publication store. */
_Static_assert(sizeof(_Atomic uint32_t)==4,"Preview commit must be atomic32");
_Static_assert(ATOMIC_INT_LOCK_FREE==2,"Preview commit requires lock-free atomics");
_Static_assert(__BYTE_ORDER__==__ORDER_LITTLE_ENDIAN__,"Preview ABI is little endian");
#define PREVIEW_HEADER 64u
#define PREVIEW_WIDTH 1920u
#define PREVIEW_HEIGHT 1080u
#define PREVIEW_STRIDE 5760u
#define PREVIEW_BYTES (PREVIEW_STRIDE*PREVIEW_HEIGHT)
#define PREVIEW_SIZE (PREVIEW_HEADER+PREVIEW_BYTES)
struct preview_snapshot {
 int fd,disabled;
 unsigned char *map;
 uint64_t serial,last_attempt_ns,interval_ns;
};
static void preview_le32(unsigned char *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(v>>(i*8));}
static void preview_le64(unsigned char *p,uint64_t v){for(unsigned i=0;i<8;i++)p[i]=(unsigned char)(v>>(i*8));}
static uint32_t preview_u32(const unsigned char *p){uint32_t v=0;for(unsigned i=0;i<4;i++)v|=(uint32_t)p[i]<<(i*8);return v;}
static int preview_lock(int fd,short type){
 struct flock lock;memset(&lock,0,sizeof(lock));lock.l_type=type;lock.l_whence=SEEK_SET;lock.l_start=0;lock.l_len=1;
 return fcntl(fd,F_SETLK,&lock); /* NONBLOCK: never F_SETLKW. */
}
static int preview_attach(struct preview_snapshot *p,int fd,unsigned fps){
 struct stat st;memset(p,0,sizeof(*p));p->fd=-1;
 if(fd<3||fps>120||fstat(fd,&st)<0||!S_ISREG(st.st_mode)||st.st_size!=(off_t)PREVIEW_SIZE){errno=EINVAL;return -1;}
 int seals=fcntl(fd,F_GET_SEALS);
 if(seals<0||(seals&(F_SEAL_SHRINK|F_SEAL_GROW))!=(F_SEAL_SHRINK|F_SEAL_GROW)){errno=EINVAL;return -1;}
 p->map=mmap(NULL,PREVIEW_SIZE,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
 if(p->map==MAP_FAILED){p->map=NULL;return -1;}
 if(memcmp(p->map,"GZPRV001",8)||preview_u32(p->map+8)!=1||preview_u32(p->map+12)!=PREVIEW_WIDTH||
    preview_u32(p->map+16)!=PREVIEW_HEIGHT||preview_u32(p->map+20)!=PREVIEW_STRIDE||preview_u32(p->map+24)!=0){
  munmap(p->map,PREVIEW_SIZE);p->map=NULL;errno=EINVAL;return -1;
 }
 p->fd=fd;p->interval_ns=fps?(1000000000ull+fps-1)/fps:0;
 return 0;
}
/* Returns 1=new snapshot, 0=rate/busy/invalid-frame skip, -1=disable preview.
 * Caller always continues the unchanged model capture on a preview failure. */
static int preview_publish(struct preview_snapshot *p,const unsigned char *src,size_t available,size_t stride,
                           uint32_t sequence,uint64_t stamp,uint64_t dequeue,uint64_t now,unsigned flags,unsigned field){
 if(p->fd<0||p->disabled)return 0;
 if((flags&0x40)||(flags&0xe000)!=0x2000||field!=1||!stamp||stamp>dequeue||dequeue>now||!src||stride<PREVIEW_STRIDE||
    stride>SIZE_MAX/PREVIEW_HEIGHT||available<stride*PREVIEW_HEIGHT)return 0;
 if(p->last_attempt_ns&&now-p->last_attempt_ns<p->interval_ns)return 0;
 p->last_attempt_ns=now;
 if(preview_lock(p->fd,F_WRLCK)<0){
  if(errno==EACCES||errno==EAGAIN||errno==EINTR)return 0;
  p->disabled=1;return -1;
 }
 atomic_thread_fence(memory_order_acquire);
 _Atomic uint32_t *valid=(_Atomic uint32_t *)(void *)(p->map+24);
 atomic_store_explicit(valid,0,memory_order_seq_cst);
 atomic_thread_fence(memory_order_seq_cst); /* invalidate before the first RGB write */
 for(size_t y=0;y<PREVIEW_HEIGHT;y++)memcpy(p->map+PREVIEW_HEADER+y*PREVIEW_STRIDE,src+y*stride,PREVIEW_STRIDE);
 unsigned char h[PREVIEW_HEADER]={0};memcpy(h,"GZPRV001",8);
 preview_le32(h+8,1);preview_le32(h+12,PREVIEW_WIDTH);preview_le32(h+16,PREVIEW_HEIGHT);
 preview_le32(h+20,PREVIEW_STRIDE);preview_le32(h+24,0);preview_le32(h+28,sequence);
 preview_le64(h+32,stamp);preview_le64(h+40,dequeue);preview_le64(h+48,++p->serial);preview_le64(h+56,now);
 memcpy(p->map,h,sizeof(h)); /* metadata remains invalid until the final store */
 atomic_store_explicit(valid,PREVIEW_BYTES,memory_order_release);
 if(preview_lock(p->fd,F_UNLCK)<0){p->disabled=1;return -1;}
 return 1;
}
static void preview_close(struct preview_snapshot *p){
 if(p->map){munmap(p->map,PREVIEW_SIZE);p->map=NULL;}
 if(p->fd>=0){close(p->fd);p->fd=-1;}
}
#endif
