/* Local register-model test only; no device nodes or physical I/O. */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <time.h>
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <string.h>
static uint32_t regs[1024],addresses[8],values[8];static unsigned stores;
static int owner_read(void *ctx,uint32_t address,uint32_t *value){
 (void)ctx;
 if(address==0xd0c)regs[address/4]++;
 if(address==0xd08)regs[address/4]=0xd5000000u|((regs[0xd04/4]&1u)?(156u<<16)|(39u<<8)|11u:12u);
 *value=regs[address/4];return 0;
}
static int owner_write(void *ctx,uint32_t address,uint32_t value){
 (void)ctx;assert(stores<8);addresses[stores]=address;values[stores++]=value;regs[address/4]=value;return 0;
}
#include "panel.h"
static void init(void){memset(regs,0,sizeof(regs));stores=0;regs[0x5c/4]=0x56442501u;regs[0xd00/4]=0x44534901u;regs[0xd04/4]=0x44534301u;}
int main(void){
 init();assert(panel_start()==0);assert(stores==4);
 assert(addresses[0]==0xd00 && values[0]==0x44534900u);
 assert(addresses[1]==0xd04 && values[1]==0x44534300u);
 assert(addresses[2]==0xd00 && values[2]==0x44534901u);
 assert(addresses[3]==0xd04 && values[3]==0x44534301u);
 init();regs[0x5c/4]=0;assert(panel_start()<0 && stores==0);
 init();regs[0x60/4]=1;assert(panel_start()<0 && stores==0);
 init();regs[0x19c/4]=4;assert(panel_start()<0 && stores==0);
 init();assert(panel_step(1,0)<0 && stores==0);
 init();assert(panel_step(1,1)<0 && stores==0);
 puts("PASS panel sequence, unsupported ABI, capture/model busy, driven-clock guards (register model only)");return 0;
}
