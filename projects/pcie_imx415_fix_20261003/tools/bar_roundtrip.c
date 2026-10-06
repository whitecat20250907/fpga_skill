/* RK -> FPGA register RAM -> RK, preserving the tested RAM contents. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <time.h>
int main(int argc, char **argv) {
    if(argc != 3) return 2;
    int fd = open(argv[1], O_RDWR | O_SYNC);
    if(fd < 0) { perror("open"); return 2; }
    volatile uint32_t *regs = mmap(NULL,4096,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    if(regs == MAP_FAILED) { perror("mmap"); return 2; }
    uint32_t saved[64], values[64], state=0x12345678, errors=0;
    unsigned rounds=atoi(argv[2]);
    /* Vendor axil_anal aliases every low byte 0x28 to IRQ status. */
    for(unsigned i=0;i<64;i++) if(i!=10) saved[i]=regs[0x300/4+i];
    for(unsigned j=0;j<rounds;j++) {
        for(unsigned i=0;i<64;i++) {
            if(i==10) continue;
            state ^= state<<13; state ^= state>>17; state ^= state<<5;
            values[i]=state; regs[0x300/4+i]=state;
        }
        for(unsigned i=0;i<64;i++) {
            if(i==10) continue;
            uint32_t actual=regs[0x300/4+i];
            if(actual!=values[i]) {
                if(errors<8) fprintf(stderr,"round=%u address=%x expected=%08x actual=%08x\n",j,0x300+i*4,values[i],actual);
                errors++;
            }
        }
    }
    for(unsigned i=0;i<64;i++) if(i!=10) regs[0x300/4+i]=saved[i];
    (void)regs[0x300/4];
    munmap((void *)regs,4096);close(fd);
    printf("{\"test\":\"BAR_register_roundtrip\",\"rounds\":%u,\"words\":%u,\"errors\":%u}\n",rounds,rounds*63,errors);
    return errors?1:0;
}
