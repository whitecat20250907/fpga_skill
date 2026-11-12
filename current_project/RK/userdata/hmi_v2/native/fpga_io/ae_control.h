/* ROI-driven AE policy, called only by the existing C hardware owner.
 * IMX415 master/linear, fixed HMAX: integration = VMAX - SHR0 (lines),
 * SHR0 in [8, VMAX-4]; GAIN_PCG_0 in 0..240, each code 0.3 dB.
 * No BAR/I2C write occurs here. A request must pass through the single
 * readback/REGHOLD/rollback transaction owner; acceptance is not completion.
 * A two-source-frame settling fence is a scheduling rule, not a claim of
 * measured sensor frame-applied timing or successful optical exposure.
 */
#ifndef HMI_AE_CONTROL_H
#define HMI_AE_CONTROL_H
#include <stdint.h>
#include <string.h>

struct hmi_ae_tuple {uint32_t vmax,shr,gain;};
struct hmi_ae_sensor {
 uint64_t epoch;uint32_t base_epoch,frame;
 int qualified,readback_verified,master_linear;
 struct hmi_ae_tuple value;
};
struct hmi_ae_sample {
 uint64_t epoch,source_ns,sum;uint32_t frame,sequence,track,count,histogram[16];
 int valid;
};
struct hmi_ae_config {
 uint32_t target,deadband,min_lines,max_lines,max_gain;
 int32_t kp_q16,ki_q16,max_step_q16,integral_limit_q16;
 uint64_t period_ns,source_ttl_ns,completion_ns;
};
struct hmi_ae_request {
 uint64_t epoch;uint32_t sequence,base_epoch,source_frame,track;
 struct hmi_ae_tuple observed,desired;
 uint32_t integration_lines;int restore;
};
struct hmi_ae_state {
 struct hmi_ae_config config;struct hmi_ae_tuple baseline,current;
 struct hmi_ae_request request;
 uint64_t epoch,next_ns,issued_ns,last_source_ns;
 uint32_t base_epoch,sequence,track,last_sample,settle_frame;
 int initialized,fault,pending,restore,settling,have_sample,have_track;
 int32_t integral_q16,proposed_integral_q16;
};
enum {HMI_AE_IDLE=0,HMI_AE_REQUEST=1,HMI_AE_WAIT=2,HMI_AE_INVALID=-1,HMI_AE_UNKNOWN=-2};
/* Consume the existing hmi_roi_readout result, including its source identity.
 * v[2] is the completed hardware statistics frame; v[4] is the older face
 * command's source frame and must not be substituted for the measured frame. */
static inline struct hmi_ae_sample hmi_ae_roi_sample(int result,uint64_t epoch,
 uint64_t source_ns,uint32_t track,const uint32_t v[24]){
 struct hmi_ae_sample m={0};
 if(result||!v||v[1]!=1)return m;
 m.epoch=epoch;m.source_ns=source_ns;m.track=track;m.valid=1;
 m.sequence=v[0];m.frame=v[2];m.count=v[5];m.sum=(uint64_t)v[6]|((uint64_t)v[7]<<32);
 memcpy(m.histogram,v+8,sizeof(m.histogram));return m;
}
static inline struct hmi_ae_config hmi_ae_defaults(void){
 /* Starting tuning only; backlit/dark physical measurements are still required. */
 return (struct hmi_ae_config){448,16,4,0xfffffu,96,22938,5243,13107,13107,
  200000000u,250000000u,500000000u};
}
static inline int hmi_ae_tuple_valid(struct hmi_ae_tuple v){
 return v.vmax>=1222&&v.vmax<=0xfffffu&&v.shr>=8&&v.shr<=v.vmax-4&&v.gain<=240;
}
static inline int hmi_ae_equal(struct hmi_ae_tuple a,struct hmi_ae_tuple b){
 return a.vmax==b.vmax&&a.shr==b.shr&&a.gain==b.gain;
}
static inline int32_t hmi_ae_clip(int64_t n,int32_t lo,int32_t hi){return n<lo?lo:n>hi?hi:(int32_t)n;}
static inline int hmi_ae_forward(uint32_t a,uint32_t b){uint32_t d=a-b;return d&&d<0x80000000u;}
static inline int hmi_ae_init(struct hmi_ae_state *s,struct hmi_ae_config c,
 const struct hmi_ae_sensor *sensor){
 if(!sensor||!sensor->epoch||!sensor->base_epoch||!sensor->qualified||!sensor->readback_verified||!sensor->master_linear||!hmi_ae_tuple_valid(sensor->value)||
  c.target<1||c.target>1023||c.deadband>=c.target||c.min_lines<4||c.min_lines>sensor->value.vmax-8||c.max_lines<c.min_lines||c.max_lines>0xfffffu||c.max_gain>240||
  c.kp_q16<0||c.kp_q16>65536||c.ki_q16<0||c.ki_q16>65536||c.max_step_q16<1||c.max_step_q16>32768||
  c.integral_limit_q16<0||c.integral_limit_q16>65536||c.period_ns<100000000u||c.period_ns>1000000000u||
  !c.source_ttl_ns||c.source_ttl_ns>250000000u||c.completion_ns<100000000u||c.completion_ns>1000000000u)return HMI_AE_INVALID;
 memset(s,0,sizeof(*s));s->config=c;s->epoch=sensor->epoch;s->base_epoch=sensor->base_epoch;
 s->baseline=s->current=sensor->value;s->initialized=1;return 0;
}
static inline int hmi_ae_sample_valid(const struct hmi_ae_sample *m,uint64_t epoch,uint64_t now,uint64_t ttl){
 if(!m||!m->valid||m->epoch!=epoch||!m->source_ns||m->source_ns>now||now-m->source_ns>ttl||!m->count||m->sum>1023ull*m->count)return 0;
 uint64_t count=0;for(unsigned i=0;i<16;i++)count+=m->histogram[i];return count==m->count;
}
static inline int hmi_ae_step(struct hmi_ae_state *s,const struct hmi_ae_sensor *sensor,
 const struct hmi_ae_sample *sample,int enabled,uint64_t now,struct hmi_ae_request *out){
 if(!s->initialized||s->fault)return HMI_AE_UNKNOWN;
 if(!sensor||sensor->epoch!=s->epoch||sensor->base_epoch!=s->base_epoch||!sensor->master_linear){s->fault=1;return HMI_AE_UNKNOWN;}
 int valid=enabled&&hmi_ae_sample_valid(sample,s->epoch,now,s->config.source_ttl_ns)&&sensor->frame-sample->frame<=2;
 if(!valid||(s->have_track&&s->track!=sample->track)){
  s->restore=1;s->track=0;s->have_track=0;s->integral_q16=0;s->have_sample=0;
 }
 if(s->pending){
  if(now<s->issued_ns||now-s->issued_ns>s->config.completion_ns){s->fault=1;return HMI_AE_UNKNOWN;}
  return HMI_AE_WAIT;
 }
 if(!sensor->qualified||!sensor->readback_verified)return HMI_AE_WAIT;
 if(!hmi_ae_tuple_valid(sensor->value))return HMI_AE_INVALID;
 /* A different register tuple needs reconciliation, never blind overwrite. */
 if(!hmi_ae_equal(sensor->value,s->current)){s->fault=1;return HMI_AE_UNKNOWN;}
 struct hmi_ae_tuple desired=s->current;int32_t next_integral=s->integral_q16;
 if(s->restore){
  if(hmi_ae_equal(s->current,s->baseline)){s->restore=0;if(!valid)return HMI_AE_IDLE;}
  else desired=s->baseline;
 }
 if(!s->restore){
  if(!valid)return HMI_AE_IDLE;
  if(s->settling&&!hmi_ae_forward(sample->frame,s->settle_frame-1))return HMI_AE_WAIT;
  if(s->settling)s->settling=0;
  if(now<s->next_ns)return HMI_AE_WAIT;
  if(s->have_sample&&(!hmi_ae_forward(sample->sequence,s->last_sample)||sample->source_ns<=s->last_source_ns))return HMI_AE_IDLE;
  s->track=sample->track;s->have_track=1;s->have_sample=1;s->last_sample=sample->sequence;s->last_source_ns=sample->source_ns;
  s->next_ns=now+s->config.period_ns;
  uint32_t mean=(uint32_t)((sample->sum+sample->count/2)/sample->count);
  int32_t raw_error=(int32_t)s->config.target-(int32_t)mean;
  int clipped=10ull*sample->histogram[15]>sample->count;
  if(raw_error<=((int32_t)s->config.deadband)&&raw_error>=-((int32_t)s->config.deadband)&&!clipped){s->integral_q16=0;return HMI_AE_IDLE;}
  int32_t error=(int32_t)((int64_t)raw_error*65536/s->config.target);
  if(clipped&&error>-16384)error=-16384;
  next_integral=hmi_ae_clip((int64_t)s->integral_q16+(int64_t)error*s->config.ki_q16*(int64_t)(s->config.period_ns/1000000u)/65536/1000,
   -s->config.integral_limit_q16,s->config.integral_limit_q16);
  int32_t drive=hmi_ae_clip((int64_t)error*s->config.kp_q16/65536+next_integral,-s->config.max_step_q16,s->config.max_step_q16);
  uint32_t lines=s->current.vmax-s->current.shr;
  uint32_t maximum=s->config.max_lines<s->current.vmax-8?s->config.max_lines:s->current.vmax-8;
  uint32_t magnitude=drive<0?(uint32_t)-drive:(uint32_t)drive;
  uint32_t delta=(uint32_t)(((uint64_t)lines*magnitude+65535)/65536);
  uint32_t gain_delta=(magnitude*20+65535)/65536;
  if(drive>0){
   if(lines<maximum){lines=maximum-lines<delta?maximum:lines+delta;desired.shr=desired.vmax-lines;}
   else if(desired.gain<s->config.max_gain)desired.gain+=s->config.max_gain-desired.gain<gain_delta?s->config.max_gain-desired.gain:gain_delta;
  }else if(drive<0){
   if(desired.gain)desired.gain-=desired.gain<gain_delta?desired.gain:gain_delta;
   else if(lines>s->config.min_lines){lines=lines-s->config.min_lines<delta?s->config.min_lines:lines-delta;desired.shr=desired.vmax-lines;}
  }
  if(hmi_ae_equal(desired,s->current)){s->integral_q16=0;return HMI_AE_IDLE;}
 }
 s->sequence++;if(!s->sequence)s->sequence=1;
 s->request=(struct hmi_ae_request){s->epoch,s->sequence,s->base_epoch,
  s->restore?sensor->frame:sample->frame,s->restore?0:s->track,s->current,desired,desired.vmax-desired.shr,s->restore};
 s->pending=1;s->issued_ns=now;s->proposed_integral_q16=s->restore?0:next_integral;*out=s->request;
 return HMI_AE_REQUEST;
}
/* Called only for the matching held transaction DONE, after readback/UNHOLD.
 * restored means the transaction restored its previous tuple, not baseline.
 * Fatal/unknown is cleared only by a verified new startup (hmi_ae_init).
 */
static inline int hmi_ae_complete(struct hmi_ae_state *s,uint64_t epoch,uint32_t base_epoch,
 uint32_t sequence,int committed,int restored,int known,struct hmi_ae_tuple value,
 uint32_t completed_frame,uint64_t now){
 if(!s->pending||epoch!=s->epoch||base_epoch!=s->base_epoch||sequence!=s->request.sequence)return HMI_AE_INVALID;
 if(s->fault||now<s->issued_ns||now-s->issued_ns>s->config.completion_ns||!known||(committed&&restored)||!hmi_ae_tuple_valid(value)){
  s->fault=1;return HMI_AE_UNKNOWN;
 }
 if((committed&&!hmi_ae_equal(value,s->request.desired))||(!committed&&!hmi_ae_equal(value,s->request.observed))){s->fault=1;return HMI_AE_UNKNOWN;}
 s->current=value;s->pending=0;s->next_ns=now+s->config.period_ns;
 if(committed){
  s->integral_q16=s->proposed_integral_q16;s->settling=1;s->settle_frame=completed_frame+2;
  if(s->request.restore)s->restore=0;
 }else s->integral_q16=0;
 return 0;
}
#endif
