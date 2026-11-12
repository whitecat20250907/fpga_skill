/* Model latest-copy v18 V4L2 capture. No FPGA/kernel/trigger changes.
 * gcc -O2 -std=c11 -Wall -Wextra -Werror -pthread capture_native.c async_output.c -o capture_native
 * Binary stdout: MCF1 + little-endian JSON length + payload length + JSON + planes.
 */
#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include "async_output.h"
#include "rgb_area3.h"
#include "preview_snapshot.h"
#include "preview_budget.h"
#define MAXBUF 16
struct map {void *p;size_t n;};
static volatile sig_atomic_t stopped;
static void stop(int sig){(void)sig;stopped=1;}
static int install_stop_handlers(void){
 struct sigaction action;
 memset(&action,0,sizeof(action));
 if(sigemptyset(&action.sa_mask)<0)return -1;
 action.sa_handler=stop;
 /* Explicit persistent POSIX disposition: no SA_RESETHAND/SA_NODEFER.
  * poll/ioctl/write keep their existing EINTR and cleanup decisions. */
 if(sigaction(SIGINT,&action,NULL)<0 || sigaction(SIGTERM,&action,NULL)<0 ||
    sigaction(SIGHUP,&action,NULL)<0)return -1;
 action.sa_handler=SIG_IGN;
 return sigaction(SIGPIPE,&action,NULL);
}
static uint64_t mono(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000u+t.tv_nsec;}
static int call(int fd,unsigned long op,void *p){int r;do{r=ioctl(fd,op,p);}while(r<0&&errno==EINTR&&!stopped);return r;}
static void buf(struct v4l2_buffer *b,struct v4l2_plane *p,unsigned type,unsigned planes,unsigned index){memset(b,0,sizeof(*b));memset(p,0,VIDEO_MAX_PLANES*sizeof(*p));b->type=type;b->memory=V4L2_MEMORY_MMAP;b->index=index;if(type==V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE){b->length=planes;b->m.planes=p;}}
#include "native_model_export.h"
#include "owner_hooks.h"
#define model_export_publish hmi_publish

#include "fpga_model_input.h"
/* Error labels describe the observation boundary, not a guessed DMA/pipe cause. */
static void retain_model_error_after_join(int worker_error,int *error,const char **stage){
 if(worker_error&&!*error){*error=worker_error;*stage="model_worker_error";}
}
static void retain_output_error_after_finish(int output_error,int *error,const char **stage){
 if(output_error&&!*error){*error=output_error;*stage="async_output_or_model_error";}
}
static void report_error_origins(const struct async_output *q,const struct fpga_model_input *m,
                                int model_joined,int error,int cleanup,const char *stage){
 /* Only successful joins permit reading the corresponding owner's plain fields.
  * These timestamps are observations, not proof of causality between threads. */
 int wvalid=q->writer_join_errno==0;
 int mvalid=model_joined&&m->worker_join_errno==0;
 fprintf(stderr,"{\"kind\":\"capture_error_origins_v1\",\"clock\":\"CLOCK_MONOTONIC\","
  "\"error\":%d,\"cleanup_errno\":%d,\"stage\":\"%s\","
  "\"writer_diagnostics_valid\":%s,\"writer_join_errno\":%d,"
  "\"writer_errno\":%d,\"writer_error_ns\":%" PRIu64 ",\"writer_error_origin\":\"%s\","
  "\"write_calls\":%" PRIu64 ",\"write_error_calls\":%" PRIu64 ","
  "\"write_eagain_calls\":%" PRIu64 ",\"write_eintr_calls\":%" PRIu64 ","
  "\"poll_calls\":%" PRIu64 ",\"poll_error_calls\":%" PRIu64 ",\"poll_eintr_calls\":%" PRIu64 ","
  "\"writer_bytes\":%" PRIu64 ",\"writer_records\":%" PRIu64 ","
  "\"writer_first_syscall_errno\":%d,\"writer_first_syscall_error_ns\":%" PRIu64 ","
  "\"writer_first_syscall_origin\":\"%s\","
  "\"model_diagnostics_valid\":%s,\"worker_join_errno\":%d,"
  "\"dma_read_calls\":%" PRIu64 ",\"dma_errno\":%d,\"dma_error_ns\":%" PRIu64 ","
  "\"worker_error_ns\":%" PRIu64 ",\"worker_error_origin\":\"%s\","
  "\"sealed_packets\":%" PRIu64 ",\"dropped_status_2\":%" PRIu64 ","
  "\"dropped_status_4\":%" PRIu64 ",\"dropped_status_8\":%" PRIu64 ","
  "\"suppressed_drop_logs\":%" PRIu64 "}\n",
  error,cleanup,stage,wvalid?"true":"false",q->writer_join_errno,
  wvalid?q->writer_errno:0,wvalid?q->writer_error_ns:0,
  wvalid&&q->writer_error_origin?q->writer_error_origin:"unrecorded",
  wvalid?q->write_calls:0,wvalid?q->write_error_calls:0,
  wvalid?q->write_eagain_calls:0,wvalid?q->write_eintr_calls:0,
  wvalid?q->poll_calls:0,wvalid?q->poll_error_calls:0,wvalid?q->poll_eintr_calls:0,
  wvalid?q->writer_bytes:0,wvalid?q->writer_records:0,
  wvalid?q->writer_first_syscall_errno:0,wvalid?q->writer_first_syscall_error_ns:0,
  wvalid&&q->writer_first_syscall_origin?q->writer_first_syscall_origin:"unrecorded",
  mvalid?"true":"false",model_joined?m->worker_join_errno:0,
  mvalid?m->dma_read_calls:0,mvalid?m->dma_errno:0,mvalid?m->dma_error_ns:0,
  mvalid?m->worker_error_ns:0,
  mvalid&&m->worker_error_origin?m->worker_error_origin:"unrecorded",
  mvalid?m->sealed_packets:0,mvalid?m->dropped_status_2:0,
  mvalid?m->dropped_status_4:0,mvalid?m->dropped_status_8:0,
  mvalid?m->suppressed_drop_logs:0);
}
static int capture_main(int argc,char **argv){
 if(argc==2&&!strcmp(argv[1],"--help")){fprintf(stderr,"capture_native /dev/videoN width height FOURCC seconds\n");return 0;}
 if(argc<6||argc>10||strncmp(argv[1],"/dev/video",10)||strlen(argv[4])!=4)return 2;
 unsigned w=(unsigned)strtoul(argv[2],NULL,10),h=(unsigned)strtoul(argv[3],NULL,10),seconds=(unsigned)strtoul(argv[5],NULL,10);
 if(!w||!h||w>8192||h>8192||seconds>600)return 2;
 int model_dma_fd=-1,model_bar_fd=-1,fpga_model=0;
 int export_fd=-1;
 int area3=0,preview_fd=-1,fps_given=0,model_only=0;unsigned preview_fps=20;
 for(int i=6;i<argc;i++){
  if(!strcmp(argv[i],"--fpga-model-only")){if(model_only)return 2;model_only=1;}
  else if(!strncmp(argv[i],"--model-store-fd=",17)){
   char *end=NULL;long n=strtol(argv[i]+17,&end,10);if(export_fd>=0||!end||*end||n<3||n>1048576)return 2;export_fd=(int)n;
  }
  else if(!strcmp(argv[i],"--rgb-area3")){if(area3)return 2;area3=1;}
  else if(!strncmp(argv[i],"--fpga-model-fds=",17)){
   char extra; if(area3||sscanf(argv[i]+17,"%d,%d%c",&model_dma_fd,&model_bar_fd,&extra)!=2||model_dma_fd<3||model_bar_fd<3||model_dma_fd==model_bar_fd)return 2;
   fpga_model=1;area3=1;
  }
  else if(!strncmp(argv[i],"--preview-fd=",13)){
   char *end=NULL;long n=strtol(argv[i]+13,&end,10);if(preview_fd>=0||!end||*end||n<3||n>1048576)return 2;preview_fd=(int)n;
  }else if(!strncmp(argv[i],"--preview-fps=",14)){
   char *end=NULL;long n=strtol(argv[i]+14,&end,10);if(fps_given||!end||*end||n<0||n>120)return 2;preview_fps=(unsigned)n;fps_given=1;
  }else return 2;
 }
 if((area3||preview_fd>=0)&&(w!=1920||h!=1080||strcmp(argv[4],"RGB3")))return 2;
 if((preview_fd>=0&&!area3)||(fps_given&&preview_fd<0))return 2;
 if(model_only&&(!fpga_model||preview_fd>=0))return 2;
 if(export_fd>=0&&(!fpga_model||export_fd==model_dma_fd||export_fd==model_bar_fd||export_fd==preview_fd))return 2;
 uint32_t fourcc=v4l2_fourcc(argv[4][0],argv[4][1],argv[4][2],argv[4][3]);
 struct map maps[MAXBUF][VIDEO_MAX_PLANES]={{{0}}};unsigned mapped[MAXBUF]={0};
 struct v4l2_format before={0},fmt={0};struct v4l2_requestbuffers req={0};struct v4l2_capability cap={0};
 int fd=-1,streaming=0,allocated=0,changed=0,error=0,cleanup=0;unsigned type=0,planes=0;uint64_t frames=0,start=0,last=0,wait_since=0;
 const char *stage="open";char json[4096];
 struct async_output output;int output_started=0;struct output_stats stats={0};
 struct fpga_model_input model={0};int model_joined=0;
 struct preview_snapshot preview={.fd=-1};
 struct hmi_preview_budget preview_budget={0};
 if(install_stop_handlers()<0){perror("sigaction");return 1;}
#define NEED(ok,label) do{if(!(ok)){stage=label;error=errno?errno:EINVAL;goto done;}}while(0)
 if(preview_fd>=0)NEED(preview_attach(&preview,preview_fd,preview_fps)==0,"preview_attach");
 if(export_fd>=0)NEED(model_export_attach(export_fd)==0,"model_export_attach");
 fd=open(argv[1],O_RDWR|O_NONBLOCK);NEED(fd>=0,"open");NEED(call(fd,VIDIOC_QUERYCAP,&cap)==0,"querycap");
 uint32_t caps=cap.capabilities&V4L2_CAP_DEVICE_CAPS?cap.device_caps:cap.capabilities;
 NEED(caps&V4L2_CAP_STREAMING,"streaming_capability");
 type=caps&V4L2_CAP_VIDEO_CAPTURE_MPLANE?V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE:V4L2_BUF_TYPE_VIDEO_CAPTURE;
 NEED(caps&(V4L2_CAP_VIDEO_CAPTURE|V4L2_CAP_VIDEO_CAPTURE_MPLANE),"capture_capability");
 before.type=type;NEED(call(fd,VIDIOC_G_FMT,&before)==0,"get_before");fmt.type=type;
 if(type==V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE){fmt.fmt.pix_mp.width=w;fmt.fmt.pix_mp.height=h;fmt.fmt.pix_mp.pixelformat=fourcc;fmt.fmt.pix_mp.field=V4L2_FIELD_NONE;}
 else{fmt.fmt.pix.width=w;fmt.fmt.pix.height=h;fmt.fmt.pix.pixelformat=fourcc;fmt.fmt.pix.field=V4L2_FIELD_NONE;}
 NEED(call(fd,VIDIOC_S_FMT,&fmt)==0,"set_format");changed=1;
 unsigned width=type==9?fmt.fmt.pix_mp.width:fmt.fmt.pix.width,height=type==9?fmt.fmt.pix_mp.height:fmt.fmt.pix.height;
 uint32_t returned=type==9?fmt.fmt.pix_mp.pixelformat:fmt.fmt.pix.pixelformat;
 unsigned field=type==9?fmt.fmt.pix_mp.field:fmt.fmt.pix.field;
 planes=type==9?fmt.fmt.pix_mp.num_planes:1;
 NEED(width==w&&height==h&&returned==fourcc&&field==V4L2_FIELD_NONE&&planes>0&&planes<=VIDEO_MAX_PLANES,"exact_format");
 if(area3){unsigned stride=type==9?fmt.fmt.pix_mp.plane_fmt[0].bytesperline:fmt.fmt.pix.bytesperline;NEED(planes==1&&stride>=5760,"area3_source_format");}
 req.type=type;req.memory=V4L2_MEMORY_MMAP;req.count=8;NEED(call(fd,VIDIOC_REQBUFS,&req)==0,"reqbufs");allocated=1;
 NEED(req.count>=2&&req.count<=MAXBUF,"buffer_count");
 for(unsigned i=0;i<req.count;i++){
  struct v4l2_buffer b;struct v4l2_plane p[VIDEO_MAX_PLANES];buf(&b,p,type,planes,i);NEED(call(fd,VIDIOC_QUERYBUF,&b)==0,"querybuf");
  NEED(type!=9||b.length==planes,"query_plane_count");
  for(unsigned j=0;j<planes;j++){size_t n=type==9?p[j].length:b.length;unsigned offset=type==9?p[j].m.mem_offset:b.m.offset;
   NEED(n>0&&n<=67108864,"mapping_bounds");maps[i][j].n=n;maps[i][j].p=mmap(NULL,n,PROT_READ|PROT_WRITE,MAP_SHARED,fd,offset);
   NEED(maps[i][j].p!=MAP_FAILED,"mmap");mapped[i]++;}
  buf(&b,p,type,planes,i);NEED(call(fd,VIDIOC_QBUF,&b)==0,"initial_qbuf");
 }
 char plane_json[2048]={0};size_t at=0;
 for(unsigned j=0;j<planes;j++){unsigned stride=type==9?fmt.fmt.pix_mp.plane_fmt[j].bytesperline:fmt.fmt.pix.bytesperline;
  unsigned size=type==9?fmt.fmt.pix_mp.plane_fmt[j].sizeimage:fmt.fmt.pix.sizeimage;
  int z=snprintf(plane_json+at,sizeof(plane_json)-at,"%s{\"stride\":%u,\"sizeimage\":%u}",j?",":"",stride,size);NEED(z>0&&(size_t)z<sizeof(plane_json)-at,"plane_json");at+=(size_t)z;}
 snprintf(json,sizeof(json),"{\"kind\":\"start\",\"hardware_capture\":true,\"output_policy\":\"bounded_latest_copy\",\"copy_slots\":2,\"output_stall_timeout_ms\":2000,\"pid\":%ld,\"driver\":\"%.16s\",\"bus_info\":\"%.32s\",\"width\":%u,\"height\":%u,\"fourcc\":\"%.4s\",\"type\":%u,\"planes\":[%s],\"buffers\":%u,\"colorspace\":%u,\"ycbcr_enc\":%u,\"quantization\":%u,\"xfer_func\":%u}",
  (long)getpid(),cap.driver,cap.bus_info,w,h,argv[4],type,plane_json,req.count,type==9?fmt.fmt.pix_mp.colorspace:fmt.fmt.pix.colorspace,
  type==9?fmt.fmt.pix_mp.ycbcr_enc:fmt.fmt.pix.ycbcr_enc,type==9?fmt.fmt.pix_mp.quantization:fmt.fmt.pix.quantization,type==9?fmt.fmt.pix_mp.xfer_func:fmt.fmt.pix.xfer_func);
 if(area3){
  size_t z=strlen(json);NEED(z>0&&json[z-1]=='}',"start_json_bounds");
  int added=snprintf(json+z-1,sizeof(json)-z+1,",\"output_transform\":\"rgb_area3_1920x1080_to_640x360\",\"output_width\":640,\"output_height\":360,\"output_stride\":1920}");
  NEED(added>0&&(size_t)added<sizeof(json)-z+1,"area3_start_metadata");
 }
 if(fpga_model){
  size_t z=strlen(json);int added=snprintf(json+z-1,sizeof(json)-z+1,",\"transform_executor\":\"fpga\",\"model_channel\":1,\"fpga_tensor_bundle\":\"BND1\",\"preview_width\":1920,\"preview_height\":1080}");
  NEED(added>0&&(size_t)added<sizeof(json)-z+1,"fpga_start_metadata");
 }
 if(model_only){
  size_t z=strlen(json);int added=snprintf(json+z-1,sizeof(json)-z+1,",\"preview_dma_policy\":\"drain_initial_buffers_no_requeue\",\"full_resolution_preview\":false}");
  NEED(added>0&&(size_t)added<sizeof(json)-z+1,"model_only_start_metadata");
 }
 size_t capacity=0;
 for(unsigned i=0;i<req.count;i++){size_t bytes=0;for(unsigned j=0;j<planes;j++)bytes+=maps[i][j].n;if(bytes>capacity)capacity=bytes;}
 if(area3)capacity=691200;
 if(fpga_model)capacity=FPGA_MODEL_OUTPUT;
 NEED(output_init(&output,capacity,json,2000)==0,"output_init");output_started=1;
 NEED(call(fd,VIDIOC_STREAMON,&type)==0,"streamon");streaming=1;start=last=wait_since=mono();
 if(fpga_model)NEED(model_start(&model,&output,model_dma_fd,model_bar_fd)==0,"fpga_model_start");
 while(!stopped&&!atomic_load(&output.error)&&(!seconds||mono()-start<(uint64_t)seconds*1000000000u)){
  if(fpga_model && preview.fd>=0){
   unsigned index;uint64_t now=mono();
   if(hmi_preview_due(&preview_budget,now,&index)){
    struct v4l2_buffer queued;struct v4l2_plane qp[VIDEO_MAX_PLANES];buf(&queued,qp,type,planes,index);
    NEED(call(fd,VIDIOC_QBUF,&queued)==0,"preview_budget_requeue");hmi_preview_requeued(&preview_budget,now);
   }
  }
  struct pollfd pollfd={.fd=fd,.events=POLLIN};int r=poll(&pollfd,1,(fpga_model && preview.fd>=0)?5:100);if(r<0&&errno==EINTR)continue;
  NEED(r>=0&&!(pollfd.revents&(POLLHUP|POLLERR|POLLNVAL)),"poll_error");
  if(atomic_load(&output.error))break;
  if(!r){
   uint64_t progress=model_only?atomic_load(&model.last_published_ns):wait_since;
   if(mono()-progress>=5000000000u){errno=ETIMEDOUT;NEED(0,model_only?"five_second_model_timeout":"five_second_camera_timeout");}
   continue;
  }
  struct v4l2_buffer b;struct v4l2_plane p[VIDEO_MAX_PLANES];buf(&b,p,type,planes,0);r=call(fd,VIDIOC_DQBUF,&b);
  if(r<0&&errno==EAGAIN){
   uint64_t progress=model_only?atomic_load(&model.last_published_ns):wait_since;
   if(mono()-progress>=5000000000u){errno=ETIMEDOUT;NEED(0,model_only?"five_second_model_timeout":"five_second_camera_timeout");}
   if(model_only){struct timespec pause={0,1000000};nanosleep(&pause,NULL);}
   continue;
  }
  NEED(r==0&&b.index<req.count&&(type!=9||b.length==planes),"dqbuf");last=mono();frames++;
  if(model_only){
   /* Retire the initial, already submitted preview buffers. Do not return
    * them with QBUF: the unchanged driver then submits no further C2H0
    * credits, while keeping the source pipeline enabled for C2H1. Every
    * dequeued mapping remains owned here until the original STREAMOFF. */
   wait_since=mono();continue;
  }
  uint32_t total=0;at=0;
  for(unsigned j=0;j<planes;j++){unsigned used=type==9?p[j].bytesused:b.bytesused,offset=type==9?p[j].data_offset:0;
   NEED(offset<=used&&used<=maps[b.index][j].n&&total<=67108864-(used-offset),"payload_bounds");total+=used-offset;
   int z=snprintf(plane_json+at,sizeof(plane_json)-at,"%s{\"bytesused\":%u,\"data_offset\":%u,\"payload\":%u}",j?",":"",used,offset,used-offset);
   NEED(z>0&&(size_t)z<sizeof(plane_json)-at,"record_planes");at+=(size_t)z;}
  struct output_slot *slot=NULL;
  if(!fpga_model){
  if(area3){
   unsigned used=type==9?p[0].bytesused:b.bytesused,offset=type==9?p[0].data_offset:0;
   snprintf(plane_json,sizeof(plane_json),"{\"bytesused\":691200,\"data_offset\":0,\"payload\":691200,\"source_bytesused\":%u,\"source_data_offset\":%u}",used,offset);
   total=691200;
  }
  snprintf(json,sizeof(json),"{\"kind\":\"frame\",\"sequence\":%u,\"flags\":%u,\"field\":%u,\"timestamp_ns\":%" PRIu64 ",\"dequeue_ns\":%" PRIu64 ",\"index\":%u,\"planes\":[%s]}",b.sequence,b.flags,b.field,(uint64_t)b.timestamp.tv_sec*1000000000u+(uint64_t)b.timestamp.tv_usec*1000u,last,b.index,plane_json);
  slot=output_reserve(&output);
  if(!slot){
   int output_failure=errno;
   /* The writer can fail while poll/DQBUF is in progress. Return that dequeued
    * DMA buffer too; output failure must not retain it until STREAMOFF. */
   buf(&b,p,type,planes,b.index);NEED(call(fd,VIDIOC_QBUF,&b)==0,"requeue_after_output_error");
   wait_since=mono();error=output_failure;stage="async_output_or_model_error";goto done;
  }
  NEED(strlen(json)<sizeof(slot->json)&&total<=output.capacity,"output_copy_bounds");
  strcpy(slot->json,json);slot->length=total;size_t copied=0;
  if(area3){
   unsigned used=type==9?p[0].bytesused:b.bytesused,offset=type==9?p[0].data_offset:0;
   unsigned stride=type==9?fmt.fmt.pix_mp.plane_fmt[0].bytesperline:fmt.fmt.pix.bytesperline;
   NEED(rgb_area3(slot->payload,output.capacity,(unsigned char*)maps[b.index][0].p+offset,used-offset,stride,width,height)==0,"area3_copy_bounds");
  }else{
  for(unsigned j=0;j<planes;j++){unsigned used=type==9?p[j].bytesused:b.bytesused,offset=type==9?p[j].data_offset:0;
   memcpy(slot->payload+copied,(unsigned char*)maps[b.index][j].p+offset,used-offset);copied+=used-offset;}
  }
  } // CPU model path; FPGA mode publishes from its independent C2H1 worker.
  if(preview.fd>=0){
   unsigned used=type==9?p[0].bytesused:b.bytesused,offset=type==9?p[0].data_offset:0;
   unsigned stride=type==9?fmt.fmt.pix_mp.plane_fmt[0].bytesperline:fmt.fmt.pix.bytesperline;
   uint64_t stamp=(uint64_t)b.timestamp.tv_sec*1000000000u+(uint64_t)b.timestamp.tv_usec*1000u;
   if(preview_publish(&preview,(unsigned char*)maps[b.index][0].p+offset,used-offset,stride,b.sequence,stamp,last,mono(),b.flags,b.field)<0)
    fprintf(stderr,"preview disabled errno=%d; model capture continues\n",errno);
  }
  /* No writer can see this slot until QBUF has returned. The writer holds only
   * the copied bytes, never a DMA mapping, even when stdout blocks. */
  if(fpga_model && preview.fd>=0){NEED(hmi_preview_hold(&preview_budget,b.index)==0,"preview_budget_hold");}
  else {buf(&b,p,type,planes,b.index);NEED(call(fd,VIDIOC_QBUF,&b)==0,"requeue");}
  wait_since=mono();if(!fpga_model)NEED(output_publish(&output,slot)==0,"output_publish");
 }
 stage=stopped?"signal_stop":"duration_complete";
 if(atomic_load(&output.error)){error=atomic_load(&output.error);stage="async_output_or_model_error";}
done:
 if(model.started){int q=model_finish(&model);model_joined=1;if(q&&!cleanup)cleanup=q;
  retain_model_error_after_join(atomic_load(&model.error),&error,&stage);}
 if(streaming&&call(fd,VIDIOC_STREAMOFF,&type)<0)cleanup=errno;
 for(unsigned i=0;i<MAXBUF;i++)for(unsigned j=0;j<mapped[i];j++)if(munmap(maps[i][j].p,maps[i][j].n)<0&&!cleanup)cleanup=errno;
 if(allocated){req.count=0;if(call(fd,VIDIOC_REQBUFS,&req)<0&&!cleanup)cleanup=errno;}
 if(changed&&call(fd,VIDIOC_S_FMT,&before)<0&&!cleanup)cleanup=errno;
 if(fd>=0)close(fd);
 preview_close(&preview);
 model_export_close();
 if(output_started){
  stats=output_finish(&output,fpga_model?model.frames:frames,error,cleanup,stage,start?mono()-start:0);
  retain_output_error_after_finish(stats.error,&error,&stage);
  report_error_origins(&output,&model,model_joined,error,cleanup,stage);
 }
 fprintf(stderr,"capture end captured=%" PRIu64 " published=%" PRIu64 " sent=%" PRIu64 " software_dropped=%" PRIu64 " error=%d cleanup=%d stage=%s\n",frames,stats.published,stats.sent,stats.dropped,error,cleanup,stage);
 return error||cleanup?1:0;
}

#undef model_export_publish
#include "owner_main.h"
