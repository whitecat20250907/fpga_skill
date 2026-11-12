#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "ae_example_exposure.h"
static unsigned checks;
#define CHECK(x) do {checks++;if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
struct board {uint32_t status,gain,mode,frame,stats[24],writes,shr,desired_shr,vmax;int no_cap;int read_error,write_error,emit;};
static int rd(void *v,uint32_t a,uint32_t *out){
 struct board *b=v;if(b->read_error)return -1;
 switch(a){
 case 0x84:*out=b->status;break;case 0x98:*out=b->gain;break;
 case 0x90:*out=b->mode;break;
 case 0x1d0:*out=b->no_cap?0:0x32454153u;break;case 0x1d4:*out=b->shr;break;case 0x1d8:*out=b->vmax;break;
 // Independent capture branch counter intentionally has a different origin.
 case 0x88:*out=b->frame+100000;break;
 case 0xe00:*out=0x53494f52;break;
 case 0xe14:*out=b->stats[0];break;case 0xe18:*out=b->stats[1];break;
 default:
  if(a>=0xe1c&&a<=0xe30)*out=b->stats[2+(a-0xe1c)/4];
  else if(a>=0xe40&&a<=0xe7c)*out=b->stats[8+(a-0xe40)/4];
  else return -1;
 }
 return 0;
}
static int wr(void *v,uint32_t a,uint32_t value){
 struct board *b=v;CHECK(a==0x98);CHECK(value&0x80000000u);CHECK((value&255)<=240);b->gain=value&255;b->desired_shr=(value>>8)&0xfffff;CHECK(b->desired_shr>=8&&b->desired_shr<=b->vmax-4);b->writes++;
 if(b->emit)printf("GAIN_REQUEST %u\n",value);
 return b->write_error?-1:0;
}
static void sample(struct board *b,struct hmi_roi_state *r,uint64_t now,uint32_t mean){
 b->frame++;memset(b->stats,0,sizeof(b->stats));
 b->stats[0]=b->frame;b->stats[1]=1;b->stats[2]=b->frame;
 b->stats[3]=b->frame;b->stats[4]=b->frame;b->stats[5]=100;b->stats[6]=mean*100;
 b->stats[8+(mean>>6)]=100;
 r->stamp=now;r->enabled=1;r->epoch=0x100000001ull;r->active_track=7;
 r->observations[b->frame%16]=(struct hmi_roi_observation){b->frame,b->frame,7,100,now,r->epoch};
}
static int step(struct hmi_example_gain *s,struct hmi_roi_state *r,struct board *b,uint64_t now,int enabled){
 return hmi_example_exposure_step(s,r,0x100000001ull,enabled,now,b,rd,wr);
}
static void done(struct board *b){b->shr=b->desired_shr;b->status=((b->status+0x01000000u)&0xff000000u)|0x2001;}

static void plant(double light){
 struct hmi_example_gain s={0};struct hmi_roi_state r={0};
 struct board b={.status=0x2001,.gain=32,.shr=8,.desired_shr=8,.vmax=2283};
 uint64_t now=1000000000ull;unsigned full_changes=0,gain_changes=0;
 for(unsigned i=0;i<650;i++){
  now+=20000000ull;
  if(s.pending){if(b.desired_shr!=b.shr)full_changes++;done(&b);}
  uint32_t mean=(uint32_t)(light*(b.vmax-b.shr)/(b.vmax-8)*pow(10.0,b.gain*0.3/10.0));
  if(mean>1023)mean=1023;sample(&b,&r,now,mean);
  unsigned prior=b.gain;step(&s,&r,&b,now,1);if(prior!=b.gain)gain_changes++;
  CHECK(!s.fault);CHECK(b.shr>=8&&b.shr<=b.vmax-4);
 }
 CHECK(s.completed>0&&!s.bootstrap);
 printf("FINAL light=%.1f mean=%u gain=%u shr=%u fault=%d writes=%u\n",light,s.mean,b.gain,b.shr,s.fault,b.writes);CHECK(s.mean>=415&&s.mean<=481);
 if(light>1000)CHECK(full_changes>0&&b.shr>8);
 if(light<10)CHECK(gain_changes>0&&b.gain>32);
 printf("PLANT light=%.1f mean=%u gain=%u shr=%u writes=%u\n",light,s.mean,b.gain,b.shr,b.writes);
 // A brief invalid snapshot must not force baseline while the face lease is live.
 now+=20000000;sample(&b,&r,now,448);b.stats[1]=0;unsigned before=b.writes;
 if(s.pending)done(&b);step(&s,&r,&b,now,1);CHECK(b.writes==before);
 for(unsigned i=0;i<20&&(s.pending||s.current!=32||s.current_shr!=8);i++){
  now+=20000000;if(s.pending)done(&b);r.enabled=0;step(&s,&r,&b,now,0);
 }
 CHECK(!s.fault&&!s.pending&&s.current==32&&s.current_shr==8);
}
int main(void){
 (void)&hmi_example_gain_step;(void)&hmi_roi_command;(void)&hmi_roi_reply;
 plant(5);plant(50);plant(5000);
 struct hmi_example_gain s={0};struct hmi_roi_state r={0};
 struct board b={.status=0x2001,.gain=32,.shr=8,.desired_shr=8,.vmax=2283,.no_cap=1};
 sample(&b,&r,1000000000ull,128);
 CHECK(step(&s,&r,&b,1000000000ull,1)==HMI_AE_INVALID&&b.writes==0);
 b.no_cap=0;CHECK(step(&s,&r,&b,1020000000ull,1)==HMI_AE_REQUEST&&b.writes==1);
 done(&b);b.shr++;CHECK(step(&s,&r,&b,1040000000ull,1)==HMI_GAIN_CHANGED&&s.fault);
 printf("PASS EXPOSURE685 checks=%u\n",checks);return 0;
}
