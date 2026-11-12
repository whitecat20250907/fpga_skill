/* Hardware ownership remains within this process, including inherited capture.
 * Python sidecar only converts msgpack to bounded local UI messages: no BAR fd.
 */
#include <sys/socket.h>
#include <sys/un.h>
#include <dirent.h>
#include <limits.h>
#include "twb_core.h"
#include "ui_transaction.h"
#include "device_open.h"
#include "roi_stats.h"
#include "input_viewer.h"
#include "ae_example_gain.h"
#include "ae_example_exposure.h"
static volatile uint32_t *owner_bar;
static atomic_int owner_quit;
static int owner_gain_enabled,owner_exposure_enabled;
static int owner_socket=-1;
static void owner_barrier(void){
#ifdef __aarch64__
 __asm__ __volatile__("dsb sy":::"memory");
#else
 atomic_thread_fence(memory_order_seq_cst);
#endif
}
static int owner_read(void *ctx,uint32_t off,uint32_t *out){(void)ctx;if(off>=4096||off%4)return -1;owner_barrier();*out=owner_bar[off/4];owner_barrier();return 0;}
static int owner_write(void *ctx,uint32_t off,uint32_t value){(void)ctx;if(off>=4096||off%4)return -1;owner_barrier();owner_bar[off/4]=value;owner_barrier();return 0;}
#include "panel.h"
static uint64_t owner_time(void *ctx){(void)ctx;return mono();}
static int owner_flush(struct twb_session *session){
 int r=twb_flush_begin(session);uint64_t end=mono()+200000000u;
 while(r==TWB_PENDING&&mono()<end){struct timespec t={0,1000000};nanosleep(&t,NULL);r=twb_flush_poll(session);}
 return r;
}
static void *owner_ui(void *unused){
 struct hmi_roi_state roi={0};
 struct hmi_example_gain gain={0};
 (void)unused;struct twb_session session;struct twb_io io={NULL,owner_read,owner_write,owner_time};twb_init(&session,io);
 struct twb_probe probe;if(twb_probe(&session,&probe)!=TWB_OK||owner_flush(&session)!=TWB_OK){atomic_store(&owner_quit,1);return NULL;}
 while(!atomic_load(&owner_quit)){
  int wait_ms=100;
  if(owner_gain_enabled){
   uint64_t now=mono();struct hmi_ring_header *h=hmi_ring_map;
   (void)(owner_exposure_enabled?hmi_example_exposure_step:hmi_example_gain_step)(&gain,&roi,h->epoch,1,now,NULL,owner_read,owner_write);
   uint64_t delay=gain.next_poll_ns>now?(gain.next_poll_ns-now+999999u)/1000000u:1;
   if(delay<(uint64_t)wait_ms)wait_ms=(int)delay;
  }
  struct pollfd pf={owner_socket,POLLIN,0};if(poll(&pf,1,wait_ms)<=0)continue;
  int fd=accept4(owner_socket,NULL,NULL,SOCK_CLOEXEC);if(fd<0)continue;
  struct timeval timeout={0,200000};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
  unsigned char msg[4096];ssize_t n=recv(fd,msg,sizeof(msg),0);int result=-1;
  if((n==52&&!memcmp(msg,"ROI1",4))||(n==56&&!memcmp(msg,"ROI2",4))){
   struct hmi_ring_header *h=hmi_ring_map;
   int prior_enabled=roi.enabled;uint32_t prior_track=roi.active_track;
   result=hmi_roi_command(&roi,msg,(size_t)n,h->epoch,mono(),NULL,owner_read,owner_write);
   if(!result&&(prior_enabled!=roi.enabled||prior_track!=roi.active_track))gain.next_poll_ns=0;
   (void)send(fd,&result,sizeof(result),MSG_NOSIGNAL);close(fd);continue;
  }
  if(n==4&&(!memcmp(msg,"ROIR",4)||!memcmp(msg,"ROIS",4))){
   struct hmi_ring_header *h=hmi_ring_map;
   unsigned char reply[120];size_t bytes=hmi_roi_reply(&roi,h->epoch,mono(),NULL,owner_read,!memcmp(msg,"ROIS",4),reply);
   (void)send(fd,reply,bytes,MSG_NOSIGNAL);close(fd);continue;
  }
  if(n==4&&!memcmp(msg,"STAT",4)){
   char reply[3072],viewer[256],gain_json[768];struct hmi_ring_header *h=hmi_ring_map;
   snprintf(gain_json,sizeof(gain_json),"{\"enabled\":%s,\"backend\":\"%s\",\"initialized\":%s,\"pending\":%s,\"fault\":%s,\"result\":%d,\"baseline\":%u,\"current\":%u,\"mean_linear_rgb10\":%u,\"submitted\":%u,\"completed\":%u,\"sensor_readback_supported\":%s,\"optical_applied_frame_verified\":false,\"shutter_control\":%s,\"vmax\":%u,\"baseline_shr\":%u,\"current_shr\":%u}",owner_gain_enabled?"true":"false",owner_exposure_enabled?"example_exposure":"example_gain",gain.initialized?"true":"false",gain.pending?"true":"false",gain.fault?"true":"false",gain.result,gain.baseline,gain.current,gain.mean,gain.submitted,gain.completed,owner_exposure_enabled?"true":"false",owner_exposure_enabled?"true":"false",gain.vmax,gain.baseline_shr,gain.current_shr);
   int vn=hmi_viewer_json(viewer,sizeof(viewer),NULL,owner_read);
   if(vn<0||(size_t)vn>=sizeof(viewer))strcpy(viewer,"null");
   /* Read only, by the existing owner. These sequential samples are not an
    * atomic snapshot and do not establish physical panel visibility. */
   const uint32_t offsets[]={0x19c,0xcf0,0xcf4,0xcf8,0xcfc,0xc40,0xc44,
    0xc48,0xc4c,0xc50,0xc54,0xc58,0xc5c,0xd00,0xd04,0xd08,0xd0c,
    0x1c4,0x1c8,0x1ac,0x1b0,0x1b4,0x1b8,0x1bc,0x1c0,0x1cc};
   uint32_t v[sizeof(offsets)/sizeof(offsets[0])];
   for(size_t i=0;i<sizeof(v)/sizeof(v[0]);i++)owner_read(NULL,offsets[i],&v[i]);
   int len=snprintf(reply,sizeof(reply),"{\"epoch\":%" PRIu64 ",\"serial\":%" PRIu64 ",\"model_control\":%u,\"ok\":true,"
    "\"display\":{\"ui_abi\":%u,\"csr_rejected\":%u,\"csr_generation\":%u,\"csr_state\":%u,"
    "\"snapshot_status\":%u,\"snapshot_features\":%u,\"published_scenes\":%u,\"accepted_packets\":%u,"
    "\"crc_errors\":%u,\"format_errors\":%u,\"sequence_errors\":%u,\"clock_delta\":%u,"
    "\"panel_abi\":%u,\"panel_clock_abi\":%u,\"panel_control\":%u,\"panel_clock_window\":%u,"
    "\"atomic_snapshot\":false,\"physical_visibility_verified\":false},"
    "\"capture\":{\"preview_blocked_valid_cycles\":%u,\"preview_fifo_highwater_words\":%u,"
    "\"model_source_frames\":%u,\"model_complete_frames\":%u,\"model_abort_frames\":%u,"
    "\"model_overflows\":%u,\"model_packet_aborts\":%u,\"model_drops\":%u,\"tdm_abi\":%u,"
    "\"atomic_snapshot\":false},\"input_viewer\":%s,\"auto_exposure\":%s}",
    h->epoch,atomic_load(&h->write_seq),v[0],v[1],v[2],v[3],v[4],v[5],v[6],v[7],v[8],v[9],v[10],v[11],v[12],v[13],v[14],v[15],v[16],
    v[17],v[18],v[19],v[20],v[21],v[22],v[23],v[24],v[25],viewer,gain_json);
   if(len>0&&(size_t)len<sizeof(reply)){(void)send(fd,reply,(size_t)len,MSG_NOSIGNAL);}
   close(fd);continue;
  }
  /* UI01: epoch u64, source_ns u64, CSR flag u32, length u32,
   * 31 shadow CSR values (0xC80..0xCF8), followed by HFT2 packet. */
  if(n>=152&&!memcmp(msg,"UI01",4)){
   uint64_t epoch,stamp;uint32_t csr,length;memcpy(&epoch,msg+4,8);memcpy(&stamp,msg+12,8);memcpy(&csr,msg+20,4);memcpy(&length,msg+24,4);
   struct hmi_ring_header *h=hmi_ring_map;uint64_t now=mono();
   uint64_t packet_epoch=0;if(n>=152+116)memcpy(&packet_epoch,msg+152+24,8);
   if(epoch==h->epoch&&packet_epoch==epoch&&stamp&&stamp<=now&&now-stamp<=150000000u&&csr<=2&&length>=116&&length<=TWB_MAX_PACKET&&n==(ssize_t)(152+length)){
    uint32_t values[31];memcpy(values,msg+28,sizeof(values));
    result=hmi_ui_submit(&session,msg+152,length,(int)csr,values);
   }
  }
  (void)send(fd,&result,sizeof(result),MSG_NOSIGNAL);close(fd);
 }
 if(owner_gain_enabled&&gain.initialized){
  uint64_t until=mono()+1200000000u;gain.next_poll_ns=0;
  while(!gain.fault&&(gain.pending||gain.current!=gain.baseline||(owner_exposure_enabled&&gain.current_shr!=gain.baseline_shr))&&mono()<until){
   struct hmi_ring_header *h=hmi_ring_map;
   (void)(owner_exposure_enabled?hmi_example_exposure_step:hmi_example_gain_step)(&gain,&roi,h->epoch,0,mono(),NULL,owner_read,owner_write);
   struct timespec pause={0,10000000};nanosleep(&pause,NULL);
  }
  fprintf(stderr,"{\"kind\":\"gain_shutdown\",\"baseline\":%u,\"current\":%u,\"pending\":%d,\"fault\":%d}\n",gain.baseline,gain.current,gain.pending,gain.fault);
 }
 (void)owner_flush(&session);return NULL;
}
static int owner_video(char *out,size_t size){
 DIR *dir=opendir("/sys/class/video4linux");if(!dir)return -1;struct dirent *ent;int found=0;
 while((ent=readdir(dir))){
  if(strncmp(ent->d_name,"video",5))continue;
  char path[PATH_MAX],name[128]={0};snprintf(path,sizeof(path),"/sys/class/video4linux/%s/name",ent->d_name);
  FILE *f=fopen(path,"r");if(!f)continue;char *read=fgets(name,sizeof(name),f);fclose(f);if(!read)continue;
  name[strcspn(name,"\r\n")]=0;if(strcmp(name,"Milianke PCIe Capture"))continue;
  snprintf(out,size,"/dev/%s",ent->d_name);found++;
 }closedir(dir);return found==1?0:-1;
}
int main(int argc,char **argv){
 int start_panel=0,enable_preview=0;
 const char *gain_mode=getenv("HMI_EXAMPLE_GAIN_ENABLED");
 if(gain_mode&&strcmp(gain_mode,"0")&&strcmp(gain_mode,"1"))return 2;
 owner_gain_enabled=gain_mode&&!strcmp(gain_mode,"1");
 const char *ae_backend=getenv("HMI_AE_BACKEND");if(!ae_backend)ae_backend="example_gain";
 if(strcmp(ae_backend,"example_gain")&&strcmp(ae_backend,"example_exposure"))return 2;
 owner_exposure_enabled=!strcmp(ae_backend,"example_exposure");
 if(argc<4||argc>6)return 2;
 for(int i=4;i<argc;i++){
  if(!strcmp(argv[i],"--start-panel")&&!start_panel)start_panel=1;
  else if(!strcmp(argv[i],"--preview")&&!enable_preview)enable_preview=1;
  else return 2;
 }
 char lockpath[PATH_MAX],ringpath[PATH_MAX],compatpath[PATH_MAX],previewpath[PATH_MAX],sockpath[PATH_MAX],video[PATH_MAX];
 if(strlen(argv[1])>70)return 2;
 snprintf(lockpath,sizeof(lockpath),"%s/hardware.lock",argv[1]);snprintf(ringpath,sizeof(ringpath),"%s/frames.memfd",argv[1]);
 snprintf(compatpath,sizeof(compatpath),"%s/model_compat.memfd",argv[1]);snprintf(sockpath,sizeof(sockpath),"%s/fpga_io.sock",argv[1]);
 snprintf(previewpath,sizeof(previewpath),"%s/preview.memfd",argv[1]);
 int lock=open(lockpath,O_CREAT|O_RDWR|O_CLOEXEC,0600);if(lock<0||flock(lock,LOCK_EX|LOCK_NB)<0){perror("hardware lock");return 1;}
 const char *shared_path=getenv("HMI_SHARED_HARDWARE_LOCK");
 if(!shared_path)shared_path="/home/linaro/pcie_fix_20261003/twb_hardware_trial.lock";
 int shared_lock=open(shared_path,O_RDWR|O_CLOEXEC|O_NOFOLLOW);
 struct stat shared_stat;
 if(shared_lock<0||fstat(shared_lock,&shared_stat)<0||!S_ISREG(shared_stat.st_mode)||flock(shared_lock,LOCK_EX|LOCK_NB)<0){perror("shared hardware lease");return 1;}
 int dma=owner_open_model_dma(argv[2]),bar=open(argv[3],O_RDWR|O_CLOEXEC);if(dma<0||bar<0||flock(bar,LOCK_EX|LOCK_NB)<0){perror("device open/lock");return 1;}
 owner_bar=mmap(NULL,4096,PROT_READ|PROT_WRITE,MAP_SHARED,bar,0);
 if(owner_bar==MAP_FAILED)return 1;
 if(start_panel && panel_start()){fprintf(stderr,"Panel ABI/readback/clock activity gate failed\n");return 1;}
 if(owner_bar[0x198/4]!=0x31444e42u||owner_bar[0x1cc/4]!=0x314d4454u||owner_bar[0xc00/4]!=0x32544648u||owner_bar[0xc38/4]!=0x32425754u){fprintf(stderr,"BND1/TDM1/HFT2/TWB2 mismatch\n");return 1;}
 const char *ui_mode=getenv("HMI_UI_MODE");uint32_t ui_abi=owner_bar[0xcf0/4];
 if(!ui_mode)ui_mode="0";
 if((strcmp(ui_mode,"0")&&strcmp(ui_mode,"1")&&strcmp(ui_mode,"2"))||
    (!strcmp(ui_mode,"0")&&ui_abi==0x55493131u)||
    (!strcmp(ui_mode,"1")&&ui_abi!=0x55493130u)||
    (!strcmp(ui_mode,"2")&&ui_abi!=0x55493131u)){
  fprintf(stderr,"UI layout/bitstream ABI mismatch before capture startup\n");return 1;
 }
 if(owner_video(video,sizeof(video))){fprintf(stderr,"Expected exactly one Milianke PCIe Capture\n");return 1;}
 int ring=memfd_create("hmi_frames",MFD_CLOEXEC|MFD_ALLOW_SEALING);if(ring<0||ftruncate(ring,HMI_RING_BYTES)<0)return 1;
 if(fcntl(ring,F_ADD_SEALS,F_SEAL_GROW|F_SEAL_SHRINK)<0)return 1;
 hmi_ring_map=mmap(NULL,HMI_RING_BYTES,PROT_READ|PROT_WRITE,MAP_SHARED,ring,0);if(hmi_ring_map==MAP_FAILED)return 1;hmi_ring_init(hmi_ring_map,0);
 int compat=memfd_create("hmi_legacy",MFD_CLOEXEC|MFD_ALLOW_SEALING);if(compat<0||ftruncate(compat,MODEL_EXPORT_HEADER+MODEL_EXPORT_BYTES)<0)return 1;
 if(fcntl(compat,F_ADD_SEALS,F_SEAL_GROW|F_SEAL_SHRINK)<0)return 1;
 if(pwrite(compat,"GZMDL002",8,0)!=8)return 1;
 int preview=-1;
 if(enable_preview){
  preview=memfd_create("hmi_preview1080",MFD_CLOEXEC|MFD_ALLOW_SEALING);
  if(preview<0||ftruncate(preview,PREVIEW_SIZE)<0)return 1;
  unsigned char header[PREVIEW_HEADER]={0};memcpy(header,"GZPRV001",8);
  preview_le32(header+8,1);preview_le32(header+12,PREVIEW_WIDTH);
  preview_le32(header+16,PREVIEW_HEIGHT);preview_le32(header+20,PREVIEW_STRIDE);
  if(pwrite(preview,header,sizeof(header),0)!=(ssize_t)sizeof(header)||
     fcntl(preview,F_ADD_SEALS,F_SEAL_GROW|F_SEAL_SHRINK|F_SEAL_SEAL)<0)return 1;
 }
 char target[128];snprintf(target,sizeof(target),"/proc/%ld/fd/%d",(long)getpid(),ring);unlink(ringpath);if(symlink(target,ringpath)<0)return 1;
 snprintf(target,sizeof(target),"/proc/%ld/fd/%d",(long)getpid(),compat);unlink(compatpath);if(symlink(target,compatpath)<0)return 1;
 unlink(previewpath);
 if(enable_preview){snprintf(target,sizeof(target),"/proc/%ld/fd/%d",(long)getpid(),preview);if(symlink(target,previewpath)<0)return 1;}
 owner_socket=socket(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0);struct sockaddr_un addr={.sun_family=AF_UNIX};strcpy(addr.sun_path,sockpath);unlink(sockpath);
 if(owner_socket<0||bind(owner_socket,(struct sockaddr*)&addr,sizeof(addr))<0||chmod(sockpath,0600)<0||listen(owner_socket,4)<0)return 1;
 atomic_init(&owner_quit,0);pthread_t ui;if(pthread_create(&ui,NULL,owner_ui,NULL))return 1;
 char fds[80],store[80];snprintf(fds,sizeof(fds),"--fpga-model-fds=%d,%d",dma,bar);snprintf(store,sizeof(store),"--model-store-fd=%d",compat);
 char *capture_argv[]={"fpga_io",video,"1920","1080","RGB3","0","--fpga-model-only",fds,store,NULL};
 char preview_arg[80];snprintf(preview_arg,sizeof(preview_arg),"--preview-fd=%d",preview);
 char *preview_argv[]={"fpga_io",video,"1920","1080","RGB3","0",fds,store,preview_arg,"--preview-fps=0",NULL};
 int result=enable_preview?capture_main(10,preview_argv):capture_main(9,capture_argv);
 atomic_store(&owner_quit,1);pthread_join(ui,NULL);
 if(owner_bar[0x19c/4]&7u){fprintf(stderr,"Model channel not idle on close\n");result=1;}
 close(owner_socket);unlink(sockpath);unlink(ringpath);unlink(compatpath);unlink(previewpath);
 munmap(hmi_ring_map,HMI_RING_BYTES);munmap((void*)owner_bar,4096);close(ring);close(compat);close(dma);close(bar);close(shared_lock);close(lock);return result;
}
