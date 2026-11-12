#include <stddef.h>
#include <assert.h>
#include "roi_stats.h"
static uint32_t bar[1024];static int writes,change;
static int rd(void *ctx,uint32_t a,uint32_t *v){(void)ctx;*v=bar[a/4];if(change&&a==0xe7c)bar[0xe14/4]++;return 0;}
static int wr(void *ctx,uint32_t a,uint32_t v){(void)ctx;bar[a/4]=v;writes++;return 0;}
int main(void){
 struct hmi_roi_state state={0};unsigned char msg[52]="ROI1";
 uint64_t epoch=7,stamp=900000000;uint32_t p[8]={31,1,10,20,111,101,640,360},out[24];
 memcpy(msg+4,&epoch,8);memcpy(msg+12,&stamp,8);memcpy(msg+20,p,32);
 bar[0xe00/4]=0x53494f52;bar[0x44/4]=1920;bar[0x48/4]=1080;
 assert(hmi_roi_command(&state,msg,52,7,1000000000,NULL,rd,wr)==0);
 assert(writes==4&&bar[0xe04/4]==(30u|(60u<<16))&&bar[0xe08/4]==(333u|(303u<<16)));
 assert(bar[0xe10/4]==0x80000001&&bar[0xe0c/4]==31);
 assert(hmi_roi_command(&state,msg,52,7,1000000000,NULL,rd,wr)==-3); /* repeat source */
 assert(hmi_roi_command(&state,msg,52,8,1000000000,NULL,rd,wr)==-1); /* wrong epoch */
 assert(writes==4);
 p[1]=0;memcpy(msg+20,p,32);assert(hmi_roi_command(&state,msg,52,7,2000000000,NULL,rd,wr)==0);
 assert(writes==5&&bar[0xe10/4]==2); /* disable need not wait for a fresh face */
 bar[0xe00/4]=0;assert(hmi_roi_command(&state,msg,52,7,2000000000,NULL,rd,wr)==-2);assert(writes==5);
 bar[0xe00/4]=0x53494f52;bar[0xe14/4]=8;bar[0xe18/4]=1;bar[0xe28/4]=100;
 assert(hmi_roi_snapshot(NULL,rd,out)==0&&out[0]==8&&out[5]==100);
 uint64_t source_ns;uint32_t track;
 assert(hmi_roi_readout(&state,7,2000000000,NULL,rd,out,&source_ns,&track)==-8&&!out[1]);
 unsigned char reply[120];assert(hmi_roi_reply(&state,7,2000000000,NULL,rd,0,reply)==100);
 change=1;assert(hmi_roi_snapshot(NULL,rd,out)==-7);
 return 0;
}
