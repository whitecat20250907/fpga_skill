/* Passive ROI statistics only. All BAR access stays in the existing owner.
 * ROI1 wire: epoch/source_ns u64, frame/en/x0/y0/x1/y1/model_w/model_h u32.
 * ROI2 adds track_id u32; ROIS replies include epoch/source_ns/track_id.
 * New command IDs are allocated here; callers cannot extend a stale lease.
 */
#ifndef HMI_ROI_STATS_H
#define HMI_ROI_STATS_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>
typedef int (*hmi_roi_read)(void *,uint32_t,uint32_t *);
typedef int (*hmi_roi_write)(void *,uint32_t,uint32_t);
#define HMI_ROI_HISTORY 16
struct hmi_roi_observation {uint32_t command,frame,track,area;uint64_t stamp,epoch;};
struct hmi_roi_state {
 uint32_t generation,active_track;uint64_t stamp,epoch;int enabled;
 struct hmi_roi_observation observations[HMI_ROI_HISTORY];
};
static int hmi_roi_command(struct hmi_roi_state *s,const unsigned char *msg,size_t n,
 uint64_t epoch,uint64_t now,void *ctx,hmi_roi_read rd,hmi_roi_write wr){
 uint64_t source_epoch,stamp;uint32_t p[8],magic,w,h,track=0,area=0;
 if(!((n==52&&!memcmp(msg,"ROI1",4))||(n==56&&!memcmp(msg,"ROI2",4))))return -1;
 memcpy(&source_epoch,msg+4,8);memcpy(&stamp,msg+12,8);memcpy(p,msg+20,32);
 if(n==56)memcpy(&track,msg+52,4);
 if(source_epoch!=epoch||!epoch||p[1]>1)return -1;
 if(rd(ctx,0xe00,&magic)||magic!=0x53494f52u)return -2;
 if(s->epoch!=epoch){
  /* The FPGA may survive an owner restart. Start after its last submitted
   * ID so an old published frame cannot alias the first new observation. */
  uint32_t prior;if(rd(ctx,0xe10,&prior))return -6;
  memset(s,0,sizeof(*s));s->epoch=epoch;s->generation=prior&0x7fffffffu;
 }
 if(p[1]){
  if(!stamp||stamp>now||now-stamp>250000000u||stamp<=s->stamp)return -3;
  if(!p[6]||!p[7]||p[6]>8191||p[7]>8191||p[2]>=p[4]||p[3]>=p[5]||p[4]>p[6]||p[5]>p[7])return -4;
  if(rd(ctx,0x44,&w)||rd(ctx,0x48,&h)||!w||!h||w>8191||h>8191)return -5;
  /* Floor start, ceil end: all coordinates are on this source frame plane. */
  uint32_t xy0=(p[2]*w/p[6])|((p[3]*h/p[7])<<16);
  uint32_t xy1=((p[4]*w+p[6]-1)/p[6])|(((p[5]*h+p[7]-1)/p[7])<<16);
  area=((xy1&8191u)-(xy0&8191u))*((xy1>>16)-(xy0>>16));
  if(wr(ctx,0xe04,xy0)||wr(ctx,0xe08,xy1)||wr(ctx,0xe0c,p[0]))return -6;
 }
 uint32_t next=(s->generation+1)&0x7fffffffu;if(!next)next=1;
 if(wr(ctx,0xe10,(p[1]<<31)|next))return -6;
 s->generation=next;s->enabled=(int)p[1];s->active_track=track;
 if(p[1]){
  s->stamp=stamp;
  s->observations[next%HMI_ROI_HISTORY]=(struct hmi_roi_observation){next,p[0],track,area,stamp,epoch};
 }
 return 0;
}
/* Return a coherent published frame or refuse it. No retry loop on BAR. */
static int hmi_roi_snapshot(void *ctx,hmi_roi_read rd,uint32_t out[24]){
 uint32_t magic,seq,valid;
 if(rd(ctx,0xe00,&magic)||magic!=0x53494f52u)return -2;
 if(rd(ctx,0xe14,&seq)||rd(ctx,0xe18,&valid))return -6;
 out[0]=seq;out[1]=valid;
 for(unsigned i=2;i<8;i++)if(rd(ctx,0xe1c+(i-2)*4,&out[i]))return -6;
 for(unsigned i=0;i<16;i++)if(rd(ctx,0xe40+i*4,&out[8+i]))return -6;
 uint32_t after,still_valid;
 if(rd(ctx,0xe14,&after)||rd(ctx,0xe18,&still_valid))return -6;
 if(seq!=after||valid!=still_valid)return -7;
 return 0;
}
/* Hardware stats can lag the most recently submitted command by a frame.
 * Match the actual completed command in a bounded history, rather than reject
 * every result that is not the newest submission. Identity changes and loss
 * take effect immediately, before the next FPGA SOF clears its valid bit.
 */
static int hmi_roi_readout(struct hmi_roi_state *s,uint64_t epoch,uint64_t now,
 void *ctx,hmi_roi_read rd,uint32_t out[24],uint64_t *source_ns,uint32_t *track){
 *source_ns=0;*track=0;
 int result=hmi_roi_snapshot(ctx,rd,out);if(result)return result;
 if(!out[1])return 0;
 if(!s->enabled||!epoch||s->epoch!=epoch){out[1]=0;return -8;}
 struct hmi_roi_observation *old=&s->observations[out[3]%HMI_ROI_HISTORY];
 if(old->command!=out[3]||old->frame!=out[4]||old->epoch!=epoch||old->track!=s->active_track){out[1]=0;return -9;}
 if(!old->stamp||old->stamp>now||now-old->stamp>250000000u){out[1]=0;return -10;}
 uint64_t count=0,total=(uint64_t)out[6]|((uint64_t)out[7]<<32);
 for(unsigned i=8;i<24;i++)count+=out[i];
 if(out[1]!=1||out[5]!=old->area||!count||count!=out[5]||total>1023u*count){out[1]=0;return -11;}
 *source_ns=old->stamp;*track=old->track;return 0;
}
static size_t hmi_roi_reply(struct hmi_roi_state *s,uint64_t epoch,uint64_t now,
 void *ctx,hmi_roi_read rd,int modern,unsigned char reply[120]){
 uint32_t values[24]={0},track=0;uint64_t stamp=0;
 int result=hmi_roi_readout(s,epoch,now,ctx,rd,values,&stamp,&track);
 memcpy(reply,&result,4);
 if(modern){
  memcpy(reply+4,&epoch,8);memcpy(reply+12,&stamp,8);memcpy(reply+20,&track,4);
  memcpy(reply+24,values,96);return 120;
 }
 memcpy(reply+4,values,96);return 100;
}
#endif
