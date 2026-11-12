#ifndef FPGA_MODEL_INPUT_H
#define FPGA_MODEL_INPUT_H
#include <sys/file.h>
#include <sched.h>
#include <sys/random.h>
#include "fpga_model_packet.h"
#include "finish_diagnostics.h"
#include "receive_diagnostics.h"
struct fpga_model_input {
 struct async_output *out;int dma,bar_fd,started;volatile uint32_t *bar;
 atomic_uint_fast64_t last_published_ns;
 pthread_t worker;atomic_int stop_requested,error;uint64_t frames,epoch;
 /* Worker-owned diagnostics: read only after model_finish joins. */
 uint64_t dma_read_calls,dma_error_ns;int dma_errno;
 uint64_t worker_error_ns;const char *worker_error_origin;int worker_join_errno;
 uint64_t sealed_packets,dropped_status_2,dropped_status_4,dropped_status_8,suppressed_drop_logs;
 uint32_t last_sealed_id,last_sealed_status,last_published_id;
 uint64_t last_sealed_tick,last_published_tick;int have_sealed,have_published;
};
static void model_write(struct fpga_model_input *m,unsigned off,uint32_t v){
 atomic_thread_fence(memory_order_seq_cst);m->bar[off/4]=v;
 atomic_thread_fence(memory_order_seq_cst);(void)m->bar[0x19c/4];
}
static int model_resync_retired_error(struct fpga_model_input *m){
 /* Called only after a CRC/epoch-verified error packet has completed an
  * EOP-mode read. This worker issued exactly one credit, consumed by that
  * packet, and has NOT submitted the next credit/read. No DMA is in flight.
  * Reject pending/busy instead of racing an old SOF or aborting a descriptor.
  * 0x19c enable resets only the model pixels/bundle; preview/CSI stay running.
  */
 if(atomic_load(&m->stop_requested))return 0;
 if((m->bar[0x19c/4]&7u)!=1u)return EBUSY;
 model_write(m,0x19c,0);
 if(m->bar[0x19c/4]&7u)return EBUSY;
 unsigned tries=0;
 while((m->bar[0x19c/4]&8u)&&++tries<1000)atomic_thread_fence(memory_order_seq_cst);
 if(m->bar[0x19c/4]&15u)return EIO;
 if(atomic_load(&m->stop_requested))return 0;
 model_write(m,0x19c,1);
 return (m->bar[0x19c/4]&15u)==1u?0:EIO;
}
/* Three bounded raw slots: one DMA-owned, one decoder-owned, one latest.
 * Only this receiver posts credit/reads DMA. It never waits for FPGA busy
 * before arming read(), and never has more than one outstanding credit.
 * CRC and tensor checks remain mandatory in the decoder before publication.
 * Error packets are CRC-checked and retired/reset here before another credit.
 */
struct model_raw_slot {unsigned char *packet;ssize_t length;uint64_t received;int state;};
struct model_receive_queue {
 struct fpga_model_input *m;pthread_mutex_t lock;pthread_cond_t ready;
 struct model_raw_slot slots[3];int latest,done,error;
 const char *origin;uint64_t error_ns,dropped,recoveries;
};
static void *model_receive_main(void *arg){
 struct model_receive_queue *q=arg;struct fpga_model_input *m=q->m;
 uint64_t fault_events=0;
 pthread_setname_np(pthread_self(),"model_dma_rx");
 cpu_set_t cpus;CPU_ZERO(&cpus);CPU_SET(4,&cpus);
 int affinity=pthread_setaffinity_np(pthread_self(),sizeof(cpus),&cpus);
 struct sched_param priority={.sched_priority=10};
 int scheduling=pthread_setschedparam(pthread_self(),SCHED_FIFO,&priority);
 fprintf(stderr,"{\"kind\":\"dma_receiver_scheduling\",\"affinity_errno\":%d,\"scheduler_errno\":%d,\"requested_cpu\":4,\"requested_priority\":10}\n",affinity,scheduling);
 while(!atomic_load(&m->stop_requested)&&!atomic_load(&m->out->error)){
  int i=-1;
  pthread_mutex_lock(&q->lock);
  for(int k=0;k<3;k++)if(q->slots[k].state==0){i=k;break;}
  if(i<0&&q->latest>=0){i=q->latest;q->latest=-1;q->dropped++;}
  if(i>=0)q->slots[i].state=1;
  pthread_mutex_unlock(&q->lock);
  if(i<0){q->error=EPROTO;q->origin="raw_queue_invariant";break;}
  if(atomic_load(&m->stop_requested)||atomic_load(&m->out->error))break;
  struct model_raw_slot *s=&q->slots[i];
  uint64_t credit_ns=mono();
  model_write(m,0x1a0,1);m->dma_read_calls++;
  uint64_t before_read_ns=mono();
  s->length=read(m->dma,s->packet,FPGA_MODEL_PACKET);int saved=errno;s->received=mono();
  if(s->length<0){hmi_receive_fault(m->bar,++fault_events,s->length,saved?saved:EIO,0,0,credit_ns,before_read_ns,s->received);q->error=saved?saved:EIO;q->origin="dma_read";m->dma_errno=q->error;m->dma_error_ns=s->received;break;}
  /* Fast path is only a scheduling hint, never permission to publish data.
   * All bytes stay private until the decoder performs the full validation. */
  int normal_hint=s->length==FPGA_MODEL_PACKET&&model_u32(s->packet+FPGA_MODEL_PACKET-12)==1u;
  if(!normal_hint){
   struct model_packet_info info;uint32_t status=0;
   int c=model_packet_classify_sealed(s->packet,(size_t)s->length,m->epoch,&info,&status);
   if(c==1){
    hmi_receive_fault(m->bar,++fault_events,s->length,0,status,info.frame_id,credit_ns,before_read_ns,s->received);
    int r=model_resync_retired_error(m);
    if(r){q->error=r;q->origin="retired_packet_resync";break;}
    q->recoveries++;
   }
  }
  pthread_mutex_lock(&q->lock);
  if(q->latest>=0){q->slots[q->latest].state=0;q->dropped++;}
  s->state=2;q->latest=i;pthread_cond_signal(&q->ready);
  pthread_mutex_unlock(&q->lock);
 }
 if(q->error)q->error_ns=mono();
 pthread_mutex_lock(&q->lock);q->done=1;pthread_cond_broadcast(&q->ready);pthread_mutex_unlock(&q->lock);
 return NULL;
}
static void *model_worker(void *arg){
 struct fpga_model_input *m=arg;
 struct model_receive_queue q;memset(&q,0,sizeof(q));q.m=m;q.latest=-1;
 uint64_t invalid_packets=0;int err=0,current=-1,created=0;
 err=pthread_mutex_init(&q.lock,NULL);if(err)goto initialization_failed;
 err=pthread_cond_init(&q.ready,NULL);if(err){pthread_mutex_destroy(&q.lock);goto initialization_failed;}
 for(int i=0;i<3&&!err;i++)err=posix_memalign((void**)&q.slots[i].packet,4096,FPGA_MODEL_PACKET);
 pthread_t receiver;
 if(!err){err=pthread_create(&receiver,NULL,model_receive_main,&q);created=!err;}
 if(err){m->worker_error_origin="receive_queue_initialization";m->worker_error_ns=mono();}
 while(!err&&!atomic_load(&m->stop_requested)&&!atomic_load(&m->out->error)){
  pthread_mutex_lock(&q.lock);
  if(current>=0){q.slots[current].state=0;current=-1;}
  while(q.latest<0&&!q.done)pthread_cond_wait(&q.ready,&q.lock);
  if(q.latest<0){pthread_mutex_unlock(&q.lock);break;}
  current=q.latest;q.latest=-1;q.slots[current].state=3;
  pthread_mutex_unlock(&q.lock);
  unsigned char *packet=q.slots[current].packet;
  ssize_t n=q.slots[current].length;uint64_t received=q.slots[current].received;
  struct model_packet_info info;uint32_t status=0;
  int classification=model_packet_classify_sealed(packet,(size_t)n,m->epoch,&info,&status);
  if(classification<0){
   /* read() completed at EOP: this packet is bounded but not trusted. Do not
    * unpack, publish or advance trusted sequence state; request the next one. */
   if(++invalid_packets==1)fprintf(stderr,"{\"kind\":\"model_invalid_eop_packet_drop\",\"validation\":%d,\"bytes\":%zd}\n",classification,n);
   continue;
  }
  /* Same original sequence policy, now against ALL sealed packets, including drops. */
  if(m->have_sealed&&(info.frame_id==m->last_sealed_id||info.tick<=m->last_sealed_tick)){
   if(++invalid_packets==1)fprintf(stderr,"{\"kind\":\"model_duplicate_eop_packet_drop\"}\n");
   continue;
  }
  m->last_sealed_id=info.frame_id;m->last_sealed_tick=info.tick;m->last_sealed_status=status;m->have_sealed=1;m->sealed_packets++;
  if(classification==1){
   uint64_t status_count=status==2u?++m->dropped_status_2:status==4u?++m->dropped_status_4:++m->dropped_status_8;
   /* stderr is undrained during capture: at most THREE drop records per worker. */
   if(status_count==1){
   fprintf(stderr,"{\"kind\":\"model_sealed_bad_frame_drop\",\"reason\":\"%s\",\"status\":%u,\"frame_id\":%u,\"fpga_tick\":%" PRIu64 ",\"epoch\":%" PRIu64 ",\"received_ns\":%" PRIu64 ",\"status_count\":%" PRIu64 ",\"sealed_packets\":%" PRIu64 ",\"published_frames\":%" PRIu64 "}\n",model_sealed_drop_reason(status),status,info.frame_id,info.tick,info.epoch,received,status_count,m->sealed_packets,m->frames);
   }else m->suppressed_drop_logs++;
   /* Receiver already recovered this sealed error before issuing another credit. */
   continue;
  }
  if(atomic_load(&m->stop_requested))break;
  struct output_slot *slot=output_reserve(m->out);if(!slot){err=errno?errno:EIO;m->worker_error_origin="output_reserve_inherited_or_local";m->worker_error_ns=mono();break;}
  int z=snprintf(slot->json,sizeof(slot->json),"{\"kind\":\"frame\",\"sequence\":%u,\"flags\":8192,\"field\":1,\"timestamp_ns\":%" PRIu64 ",\"dequeue_ns\":%" PRIu64 ",\"index\":0,\"timestamp_origin\":\"linux_model_dma_complete\",\"fpga_source_tick\":%" PRIu64 ",\"fpga_tick_hz\":125000000,\"fpga_epoch\":%" PRIu64 ",\"fpga_crc_verified\":true,\"detector_contract\":\"square640_warp_linear5_zero\",\"planes\":[{\"bytesused\":691200,\"data_offset\":0,\"payload\":691200},{\"bytesused\":49152,\"data_offset\":691200,\"payload\":49152},{\"bytesused\":110592,\"data_offset\":740352,\"payload\":110592}]}",info.frame_id,received,received,info.tick,info.epoch);
  if(z<0||(size_t)z>=sizeof(slot->json)){err=EOVERFLOW;m->worker_error_origin="metadata_overflow";m->worker_error_ns=mono();break;}
  int unpack=model_unpack_tensor(packet,slot->payload,m->out->capacity);
  if(unpack){
   if(output_discard(m->out,slot)){err=errno?errno:EIO;m->worker_error_origin="output_discard";m->worker_error_ns=mono();break;}
   if(unpack==-1){err=EOVERFLOW;m->worker_error_origin="tensor_output_capacity";m->worker_error_ns=mono();break;}
   if(++invalid_packets==1)fprintf(stderr,"{\"kind\":\"model_invalid_tensor_drop\",\"validation\":%d}\n",unpack);
   continue;
  }
  slot->length=FPGA_MODEL_OUTPUT;
  if(model_export_publish(slot->payload,info.frame_id,received,info.epoch,info.tick)){err=errno?errno:EIO;m->worker_error_origin="native_model_export";m->worker_error_ns=mono();break;}
  if(output_publish(m->out,slot)){err=errno?errno:EIO;m->worker_error_origin="output_publish";m->worker_error_ns=mono();break;}m->frames++;atomic_store(&m->last_published_ns,received);
  m->last_published_id=info.frame_id;m->last_published_tick=info.tick;m->have_published=1;
 }

 atomic_store(&m->stop_requested,1);
 if(created){int j=pthread_join(receiver,NULL);if(j&&!err)err=j;}
 /* No producer can still access slots, BAR or diagnostics after the join. */
 if(q.error){err=q.error;m->worker_error_origin=q.origin;m->worker_error_ns=q.error_ns;}
 if(invalid_packets)fprintf(stderr,"{\"kind\":\"model_invalid_eop_packet_summary\",\"dropped\":%" PRIu64 "}\n",invalid_packets);
 fprintf(stderr,"{\"kind\":\"model_receive_pipeline_summary\",\"raw_queue_drops\":%" PRIu64 ",\"retired_error_recoveries\":%" PRIu64 "}\n",q.dropped,q.recoveries);
 for(int i=0;i<3;i++)free(q.slots[i].packet);
 pthread_cond_destroy(&q.ready);pthread_mutex_destroy(&q.lock);
initialization_failed:
 if(m->bar[0x19c/4]&4u){if(!err){err=EBUSY;m->worker_error_origin="channel_busy_on_exit";m->worker_error_ns=mono();}}else model_write(m,0x19c,0);
 if(err){atomic_store(&m->error,err);atomic_store(&m->out->error,err);}
 return NULL;
}
static int model_start(struct fpga_model_input *m,struct async_output *out,int dma,int bar_fd){
 memset(m,0,sizeof(*m));m->out=out;m->dma=dma;m->bar_fd=bar_fd;atomic_init(&m->stop_requested,0);atomic_init(&m->error,0);
 atomic_init(&m->last_published_ns,mono());
 if(flock(dma,LOCK_EX|LOCK_NB)<0)return -1;
 m->bar=mmap(NULL,4096,PROT_READ|PROT_WRITE,MAP_SHARED,bar_fd,0);
 if(m->bar==MAP_FAILED){m->bar=NULL;flock(dma,LOCK_UN);return -1;}
 if(m->bar[0x198/4]!=0x31444e42u||(m->bar[0x19c/4]&7u)){errno=EBUSY;goto bad;}
 if(getrandom(&m->epoch,sizeof(m->epoch),0)!=(ssize_t)sizeof(m->epoch)){errno=EIO;goto bad;}
 model_write(m,0x1a4,(uint32_t)m->epoch);model_write(m,0x1a8,(uint32_t)(m->epoch>>32));model_write(m,0x19c,1);
 if(!(m->bar[0x19c/4]&1u)){errno=EIO;goto bad;}
 sigset_t blocked,previous;sigemptyset(&blocked);sigaddset(&blocked,SIGINT);sigaddset(&blocked,SIGTERM);sigaddset(&blocked,SIGHUP);
 int r=pthread_sigmask(SIG_BLOCK,&blocked,&previous);if(r){errno=r;goto disable;}
 r=pthread_create(&m->worker,NULL,model_worker,m);pthread_sigmask(SIG_SETMASK,&previous,NULL);
 if(r){errno=r;goto disable;}m->started=1;return 0;
disable:model_write(m,0x19c,0);
bad:{int saved=errno;munmap((void*)m->bar,4096);m->bar=NULL;flock(dma,LOCK_UN);errno=saved;return -1;}
}
static int model_finish(struct fpga_model_input *m){
 if(!m->started)return 0;
 atomic_store(&m->stop_requested,1);int r=pthread_join(m->worker,NULL);m->worker_join_errno=r;m->started=0;
 int worker_error=atomic_load(&m->error);
 uint32_t control=m->bar[0x19c/4];
 int unmap_error=munmap((void*)m->bar,4096)<0?errno:0;
 m->bar=NULL;
 int unlock_error=flock(m->dma,LOCK_UN)<0?errno:0;
 return hmi_finish_result(worker_error,r,unmap_error,unlock_error,control);
}
#endif
