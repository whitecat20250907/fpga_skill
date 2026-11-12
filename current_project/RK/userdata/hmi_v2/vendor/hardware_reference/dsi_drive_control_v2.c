/* Diagnostic-only DSI pad gate. Never map /dev/mem or guessed addresses.
 * Build for RK AArch64. An unsupported gate signature returns before a store.
 * Writes require capture CTRL disabled; the board action additionally proves
 * no model/capture process and no open V4L2 FD before invoking this binary.
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/file.h>
#include <sys/mman.h>
#include <sys/stat.h>
#if !defined(__aarch64__) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error Build for little-endian RK AArch64
#endif
static volatile uint32_t *bar;
static uint32_t rd(unsigned offset){
    uint32_t v;
    __asm__ __volatile__("dsb sy":::"memory");
    v=bar[offset/4];
    __asm__ __volatile__("dsb sy":::"memory");
    return v;
}
static void gate_store(uint32_t value){
    __asm__ __volatile__("dsb sy":::"memory");
    bar[0xd00/4]=value;
    __asm__ __volatile__("dsb sy":::"memory");
}
int main(int argc,char **argv){
    int write=0,enable=0,fd,rc=0;struct stat st;uint32_t before,after,ctrl;
    if(argc==2 && !strcmp(argv[1],"quiet")){write=1;enable=0;}
    else if(argc==2 && !strcmp(argv[1],"drive")){write=1;enable=1;}
    else if(argc!=1)return 64;
    fd=open("/dev/ANLOGIC-PCI0_user",(write?O_RDWR:O_RDONLY)|O_CLOEXEC|O_NOFOLLOW|O_SYNC);
    if(fd<0){perror("existing user BAR");return 2;}
    if(fstat(fd,&st)||!S_ISCHR(st.st_mode)||(write&&flock(fd,LOCK_EX|LOCK_NB))){close(fd);return 2;}
    void *p=mmap(NULL,4096,PROT_READ|(write?PROT_WRITE:0),MAP_SHARED,fd,0);
    if(p==MAP_FAILED){perror("existing BAR mmap");close(fd);return 2;}
    bar=p;before=rd(0xd00);ctrl=rd(0x60);after=before;
    /* UI domain may be in PLL reset. Validate independent camera/clock ABI. */
    if(rd(0x5c)!=0x56442501u || (rd(0xd04)&~1u)!=0x44534300u ||
       (rd(0xd08)>>24)!=0xd5u || (before&~1u)!=0x44534900u)rc=3;
    else if(write && (ctrl&1u))rc=4;
    else if(write){
        gate_store(0x44534900u|(unsigned)enable);after=rd(0xd00);
        if(after!=(0x44534900u|(unsigned)enable))rc=5;
    }
    printf("{\"status\":\"%s\",\"before\":%u,\"after\":%u,\"capture_CTRL\":%u,\"MMIO_writes\":%u,\"diagnostic_only\":true}\n",
           rc==0?"GATE_REGISTER_OBSERVED":rc==3?"UNSUPPORTED_BEFORE_STORE":rc==4?"CAPTURE_ENABLED_BEFORE_STORE":"READBACK_FAILED",before,after,ctrl,(unsigned)(write&&rc!=3&&rc!=4));
    munmap(p,4096);close(fd);return rc;
}
