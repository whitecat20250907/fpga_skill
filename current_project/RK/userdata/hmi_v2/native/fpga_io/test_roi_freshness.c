#include <stddef.h>
#include <assert.h>
#include <stdio.h>
#include "roi_stats.h"
static uint32_t bar[1024];static int unstable,failed_write;
static int rd(void *ctx,uint32_t off,uint32_t *v){(void)ctx;*v=bar[off/4];if(unstable&&off==0xe7c)bar[0xe14/4]++;return 0;}
static int wr(void *ctx,uint32_t off,uint32_t v){(void)ctx;if((int)off==failed_write)return -1;bar[off/4]=v;return 0;}
static int command(struct hmi_roi_state *s,uint64_t epoch,uint64_t stamp,uint32_t frame,uint32_t track,int enable){
 unsigned char msg[56]="ROI2";uint32_t p[9]={frame,(uint32_t)enable,10,20,30,40,640,360,track};
 memcpy(msg+4,&epoch,8);memcpy(msg+12,&stamp,8);memcpy(msg+20,p,36);
 return hmi_roi_command(s,msg,sizeof(msg),epoch,stamp+1000000,NULL,rd,wr);
}
static void publish(uint32_t cmd,uint32_t frame){
 bar[0xe14/4]++;bar[0xe18/4]=1;bar[0xe1c/4]=101;bar[0xe20/4]=cmd;bar[0xe24/4]=frame;
 bar[0xe28/4]=3600;bar[0xe2c/4]=3600*100;bar[0xe30/4]=0;
 for(unsigned i=0;i<16;i++)bar[(0xe40+4*i)/4]=(i==1?3600:0);
}
static int readout(struct hmi_roi_state *s,uint64_t epoch,uint64_t now){
 uint32_t out[24],track;uint64_t stamp;int v=hmi_roi_readout(s,epoch,now,NULL,rd,out,&stamp,&track);
 if(!v&&out[1]){assert(stamp&&track==s->active_track);assert(out[5]==3600);}
 if(v)assert(!stamp&&!track);
 return v;
}
int main(void){
 struct hmi_roi_state s={0};uint64_t t=1000000000;
 bar[0xe00/4]=0x53494f52;bar[0x44/4]=1920;bar[0x48/4]=1080;
 assert(command(&s,7,t,40,11,1)==0);publish(1,40);assert(readout(&s,7,t+10000000)==0);
 /* A new observation must not invalidate the previous complete FPGA frame. */
 assert(command(&s,7,t+30000000,41,11,1)==0);assert(readout(&s,7,t+40000000)==0);
 assert(readout(&s,7,t+250000001)==-10); /* frozen valid bit is not fresh */
 assert(command(&s,7,t+60000000,42,22,1)==0);assert(readout(&s,7,t+70000000)==-9);
 publish(3,42);assert(readout(&s,7,t+70000000)==0);
 assert(command(&s,7,t+80000000,43,22,0)==0);
 uint32_t raw[24];assert(hmi_roi_snapshot(NULL,rd,raw)==0&&raw[1]==1); /* old raw API would show valid */
 assert(readout(&s,7,t+90000000)==-8); /* loss disables immediately, no next SOF needed */
 assert(command(&s,7,t+100000000,44,22,1)==0);publish(5,44);
 assert(readout(&s,8,t+110000000)==-8);
 assert(command(&s,8,t+120000000,45,33,1)==0);assert(readout(&s,8,t+130000000)==-9);
 assert(s.generation==6);publish(6,45);assert(readout(&s,8,t+130000000)==0);
 bar[0xe24/4]=46;assert(readout(&s,8,t+130000000)==-9);bar[0xe24/4]=45;
 bar[0xe28/4]++;assert(readout(&s,8,t+130000000)==-11);bar[0xe28/4]--;
 bar[0xe2c/4]=3600*1024;assert(readout(&s,8,t+130000000)==-11);bar[0xe2c/4]=3600*100;
 unstable=1;assert(readout(&s,8,t+130000000)==-7);unstable=0;
 failed_write=0xe10;assert(command(&s,8,t+150000000,46,44,1)==-6);
 assert(s.active_track==33&&s.generation==6);assert(readout(&s,8,t+160000000)==0);failed_write=0;
 for(unsigned i=0;i<16;i++)assert(command(&s,8,t+170000000+i*1000000,47+i,33,1)==0);
 assert(readout(&s,8,t+190000000)==-9); /* bounded history does not alias a wrapped slot */
 s.generation=0x7fffffff;assert(command(&s,8,t+200000000,70,33,1)==0&&s.generation==1);
 publish(1,70);assert(readout(&s,8,t+210000000)==0);
 unsigned char reply[120];assert(hmi_roi_reply(&s,8,t+210000000,NULL,rd,1,reply)==120);
 FILE *out=fopen("roi_reply.bin","wb");assert(out);assert(fwrite(reply,1,120,out)==120);assert(!fclose(out));
 puts("PASS_ROI_FRESHNESS_HISTORY_IDENTITY_DISABLE_EPOCH_AND_WRAP");return 0;
}
