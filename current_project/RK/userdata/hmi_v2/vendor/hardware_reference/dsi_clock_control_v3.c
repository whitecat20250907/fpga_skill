/* Bounded diagnostic of the existing user BAR. No /dev/mem, guessed PCI
 * resources, driver changes, or writes to camera/PHY/DMA state. A write is
 * admitted only by the exact clock-control ABI, disabled capture and quiet
 * DSI pads, except one disabled-to-enabled PLL start with pads already exposed. The board action separately owns the shared trial lock and proves
 * there are no camera FDs/processes. Monitoring is independent of requests.
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
#include <time.h>
#if !defined(__aarch64__) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error Build for little-endian RK AArch64
#endif
static volatile uint32_t *bar;
static uint32_t rd(unsigned offset){
 uint32_t v;__asm__ __volatile__("dsb sy":::"memory");v=bar[offset/4];
 __asm__ __volatile__("dsb sy":::"memory");return v;
}
static void request_store(uint32_t value){
 __asm__ __volatile__("dsb sy":::"memory");bar[0xd04/4]=value;
 __asm__ __volatile__("dsb sy":::"memory");
}
static int pause_ms(unsigned ms){
 struct timespec delay={(time_t)(ms/1000),(long)(ms%1000)*1000000L};
 return nanosleep(&delay,NULL);
}
int main(int argc,char **argv){
 int write=0,enable=0,fd,rc=0;unsigned stores=0,n=0;struct stat st;
 uint32_t before,after,ctrl,pads,abi,twb,monitor,status[4]={0},window[4]={0};
 const char *why="OBSERVED_ONLY";
 if(argc==2&&!strcmp(argv[1],"off")){write=1;enable=0;}
 else if(argc==2&&!strcmp(argv[1],"on")){write=1;enable=1;}
 else if(argc!=1)return 64;
 fd=open("/dev/ANLOGIC-PCI0_user",(write?O_RDWR:O_RDONLY)|O_CLOEXEC|O_NOFOLLOW|O_SYNC);
 if(fd<0){perror("existing user BAR");return 2;}
 if(fstat(fd,&st)||!S_ISCHR(st.st_mode)||(write&&flock(fd,LOCK_EX|LOCK_NB))){close(fd);return 2;}
 void *p=mmap(NULL,4096,PROT_READ|(write?PROT_WRITE:0),MAP_SHARED,fd,0);
 if(p==MAP_FAILED){perror("existing BAR mmap");close(fd);return 2;}
 bar=p;before=rd(0xd04);after=before;ctrl=rd(0x60);pads=rd(0xd00);abi=rd(0x5c);twb=rd(0xc38);monitor=rd(0xd08);
 /* TWB is held in UI reset while this PLL is off. It is observed, not
  * a prerequisite for the independent clock-control/status ABI. */
 if(abi!=0x56442501u ||
    (before&~1u)!=0x44534300u || (monitor>>24)!=0xd5u ||
    (pads&~1u)!=0x44534900u){rc=3;why="UNSUPPORTED_BEFORE_STORE";goto done;}
 if(write&&(ctrl&1u)){rc=4;why="CAPTURE_ENABLED_BEFORE_STORE";goto done;}
 /* Only a disabled -> enabled request may follow enabling LP pads.
  * Reset/disable still requires quiet pads; repeated on while driving rejects. */
 if(write&&(pads&1u)&&(!enable || before!=0x44534300u)){rc=4;why="DSI_PADS_DRIVING_BEFORE_STORE";goto done;}
 if(write){
  request_store(0x44534300u|(unsigned)enable);stores=1;after=rd(0xd04);
  if(after!=(0x44534300u|(unsigned)enable)){rc=5;why="REQUEST_READBACK_FAILED";goto done;}
 }
 if(pause_ms(10)){rc=5;why="SETTLE_INTERRUPTED";goto done;}
 for(n=0;n<4;n++){
  window[n]=rd(0xd0c);status[n]=rd(0xd08);
  if((status[n]>>24)!=0xd5u || !(status[n]&8u) ||
     (n&&window[n]==window[n-1])){rc=5;why="MISSING_OR_STALE_ACTIVITY_WINDOW";n++;goto done;}
  if(n!=3&&pause_ms(2)){rc=5;why="MONITOR_INTERRUPTED";n++;goto done;}
 }
 if(write){
  for(unsigned k=0;k<n;k++){
   unsigned ui=(status[k]>>8)&255u,hs=(status[k]>>16)&255u,flags=status[k]&15u;
   if(enable?(ui<38u||ui>40u||hs<155u||hs>157u||flags!=11u):
             (ui||hs||flags!=12u)){
    rc=6;why="ACTUAL_CLOCK_ACTIVITY_DOES_NOT_MATCH_REQUEST";goto done;
   }
  }
  why="REQUEST_AND_INDEPENDENT_CLOCK_ACTIVITY_VERIFIED";
 }
done:
 printf("{\"camera_ABI\":%u,\"UI_TWB_ID_before\":%u,\"UI_TWB_ID_after\":%u,\"clock_status_before\":%u,",abi,twb,rd(0xc38),monitor);
 printf("\"status\":\"%s\",\"returncode\":%d,\"before\":%u,\"after\":%u,\"capture_CTRL\":%u,\"DSI_PAD_gate\":%u,\"MMIO_writes\":%u,\"camera_PHY_DMA_control_writes\":0,\"samples\":[",why,rc,before,after,ctrl,pads,stores);
 for(unsigned k=0;k<n;k++)printf("%s{\"window\":%u,\"status_word\":%u,\"UI_divided_bit_edges\":%u,\"HS_divided_bit_edges\":%u,\"flags\":%u}",k?",":"",window[k],status[k],(status[k]>>8)&255u,(status[k]>>16)&255u,status[k]&15u);
 printf("],\"scope\":\"Internal activity only; not external pin or panel acceptance\"}\n");
 munmap(p,4096);close(fd);return rc;
}
