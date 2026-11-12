/* Gain-only feedback through the working example's BAR 0x98 interface.
 * Called by the unique C owner, mutually exclusive with AE01 exposure control.
 * Completion means ONE additional successful I2C write, not sensor readback
 * or a measured optical applied-frame. No XVS or AE01 capability is invented.
 * The 8-bit completion counter requires exclusive commands and no camera reset
 * during a transaction. A mode/reset/error observation stops this backend.
 */
#ifndef HMI_AE_EXAMPLE_GAIN_H
#define HMI_AE_EXAMPLE_GAIN_H
#include "ae_control.h"
#include "roi_stats.h"
struct hmi_example_gain {
 uint64_t epoch,next_poll_ns,next_adjust_ns,issued_ns,last_source_ns;
 uint32_t mode,baseline,current,desired,track,last_sample,settle_frame;
 uint32_t submitted,completed,mean;
 uint32_t vmax,baseline_shr,current_shr,desired_shr;int bootstrap;
 uint8_t counter;
 int initialized,pending,fault,restore,have_track,have_sample,settling,result;
 int32_t integral_q16,proposed_integral_q16;
};
enum {HMI_GAIN_IO=-10,HMI_GAIN_CHANGED=-11,HMI_GAIN_TIMEOUT=-12};
static int hmi_example_gain_step(struct hmi_example_gain *s,
 struct hmi_roi_state *roi,uint64_t epoch,int enabled,uint64_t now,
 void *ctx,hmi_roi_read rd,hmi_roi_write wr){
 if(now<s->next_poll_ns)return s->result;
 s->next_poll_ns=now+(s->fault?1000000000u:20000000u);
 if(s->fault)return s->result;
 if(s->pending&&(now<s->issued_ns||now-s->issued_ns>500000000u)){
  s->fault=1;return s->result=HMI_GAIN_TIMEOUT;
 }
 uint32_t status,after,gain,mode;
 if(rd(ctx,0x84,&status)||rd(ctx,0x98,&gain)||rd(ctx,0x90,&mode)||
    rd(ctx,0x84,&after))return s->result=HMI_GAIN_IO;
 /* Low bits are live diagnostic levels; only compare the gain snapshot and
  * configuration bit. A moving camera must not prevent taking a snapshot. */
 if((status^after)&0xff006009u)return s->result=HMI_AE_WAIT;
 if(!(status&1u)||(status&8u)){
  if(s->initialized){s->fault=1;return s->result=HMI_GAIN_CHANGED;}
  return s->result=HMI_AE_WAIT;
 }
 if(!epoch||gain>240||mode>2)return s->result=HMI_AE_INVALID;
 uint8_t count=(uint8_t)(status>>24);
 int idle=(status&0x6000u)==0x2000u;
 if(!s->initialized){
  if(!enabled||!idle)return s->result=HMI_AE_IDLE;
  s->initialized=1;s->epoch=epoch;s->mode=mode;
  s->baseline=s->current=gain;s->counter=count;
 }
 if(s->epoch!=epoch||s->mode!=mode||gain!=(s->pending?s->desired:s->current)){
  s->fault=1;return s->result=HMI_GAIN_CHANGED;
 }
 uint32_t values[24]={0},track=0;uint64_t source_ns=0;
 int rc=roi?hmi_roi_readout(roi,epoch,now,ctx,rd,values,&source_ns,&track):-1;
 struct hmi_ae_sample sample=hmi_ae_roi_sample(rc,epoch,source_ns,track,values);
 /* ROI statistics have their own accepted-SOF counter. BAR 0x88 counts a
  * different capture branch: subtracting those counters can reject all valid
  * samples after a dropped frame. Freshness comes from ROI command identity,
  * its hardware lease, and the original source timestamp in roi_readout. */
 int valid=enabled&&hmi_ae_sample_valid(&sample,epoch,now,250000000u);
 /* A frame-boundary snapshot can be briefly unavailable while the ROI
  * lease remains current. Hold gain in that gap; only actual loss, expiry or
  * identity change restores baseline. A missing histogram never drives PI. */
 int source_live=enabled&&roi&&roi->enabled&&roi->epoch==epoch&&roi->stamp&&
   roi->stamp<=now&&now-roi->stamp<=250000000u;
 if(!source_live||(s->have_track&&s->track!=roi->active_track)){
  s->restore=1;s->have_track=0;s->have_sample=0;s->integral_q16=0;
 }
 if(s->pending){
  uint8_t delta=(uint8_t)(count-s->counter);
  if(delta>1){s->fault=1;return s->result=HMI_GAIN_CHANGED;}
  if(delta==1&&idle){
   s->counter=count;s->current=s->desired;s->pending=0;s->completed++;
   s->integral_q16=s->restore?0:s->proposed_integral_q16;
   s->settling=valid;s->settle_frame=sample.frame+2;s->next_adjust_ns=now+200000000u;
  }else{
   if(now<s->issued_ns||now-s->issued_ns>500000000u){s->fault=1;return s->result=HMI_GAIN_TIMEOUT;}
   return s->result=HMI_AE_WAIT;
  }
 }else if(count!=s->counter){s->fault=1;return s->result=HMI_GAIN_CHANGED;}
 if(!idle)return s->result=HMI_AE_WAIT;
 uint32_t desired=s->current;int32_t next_integral=0;
 if(s->restore){
  desired=s->baseline;
  if(desired==s->current)s->restore=0;
 }
 if(!s->restore){
  if(!valid)return s->result=HMI_AE_IDLE;
  if(now<s->next_adjust_ns||(s->settling&&!hmi_ae_forward(sample.frame,s->settle_frame-1)))return s->result=HMI_AE_WAIT;
  if(s->have_sample&&(!hmi_ae_forward(sample.sequence,s->last_sample)||sample.source_ns<=s->last_source_ns))return s->result=HMI_AE_IDLE;
  s->settling=0;s->have_track=1;s->track=sample.track;s->have_sample=1;
  s->last_sample=sample.sequence;s->last_source_ns=sample.source_ns;s->next_adjust_ns=now+200000000u;
  s->mean=(uint32_t)((sample.sum+sample.count/2)/sample.count);
  int32_t error=448-(int32_t)s->mean;
  int clipped=10ull*sample.histogram[15]>sample.count;
  if(error>=-16&&error<=16&&!clipped){s->integral_q16=0;return s->result=HMI_AE_IDLE;}
  int32_t normalized=(int32_t)((int64_t)error*65536/448);
  if(clipped&&normalized>-16384)normalized=-16384;
  next_integral=hmi_ae_clip((int64_t)s->integral_q16+(int64_t)normalized*5243/65536/5,-13107,13107);
  int32_t drive=hmi_ae_clip((int64_t)normalized*22938/65536+next_integral,-13107,13107);
  uint32_t delta=(uint32_t)(((int64_t)(drive<0?-drive:drive)*20+65535)/65536);
  if(drive>0&&desired<96)desired+=96-desired<delta?96-desired:delta;
  if(drive<0)desired-=desired<delta?desired:delta;
  if(desired==s->current){s->integral_q16=0;return s->result=HMI_AE_IDLE;}
 }
 s->desired=desired;s->issued_ns=now;s->proposed_integral_q16=next_integral;
 /* Set pending before writing. A failing transport may have committed: never
  * replay it. Stop and require explicit reinitialization after inspection. */
 s->pending=1;
 if(wr(ctx,0x98,desired)){s->fault=1;return s->result=HMI_GAIN_IO;}
 s->submitted++;return s->result=HMI_AE_REQUEST;
}
#endif
