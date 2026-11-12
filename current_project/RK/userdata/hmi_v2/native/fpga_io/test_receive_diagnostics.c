#include <assert.h>
#include <string.h>
#include "receive_diagnostics.h"
int main(void){
 uint32_t bar[1024]={0},original[1024];
 bar[0x19c/4]=1;bar[0x1a0/4]=100;bar[0x1ac/4]=101;bar[0x1b0/4]=99;
 bar[0x1b4/4]=2;bar[0x1b8/4]=3;bar[0x1bc/4]=4;bar[0x1c0/4]=5;
 memcpy(original,bar,sizeof(bar));unsigned logs=0;
 for(uint64_t i=1;i<=1024;i++){
  if(hmi_receive_log_due(i))logs++;
  hmi_receive_fault(bar,i,176,0,8,42,1000,1100,2000);
 }
 assert(logs==15);assert(!hmi_receive_log_due(0));
 hmi_receive_fault(bar,1,-1,110,0,0,3000,3100,4000);
 assert(!memcmp(bar,original,sizeof(bar)));return 0;
}
