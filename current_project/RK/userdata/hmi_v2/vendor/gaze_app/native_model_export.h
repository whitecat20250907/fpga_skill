#ifndef NATIVE_MODEL_EXPORT_H
#define NATIVE_MODEL_EXPORT_H
#include <sys/stat.h>
/* The Python owner creates and retains this sealed memfd. The native decoder
 * is its sole publisher; existing readers retain the same GZMDL002 ABI. */
struct native_model_export {int fd;unsigned char *map;uint64_t serial,busy,last_stamp;};
static struct native_model_export model_export={.fd=-1};
enum { MODEL_EXPORT_HEADER=96, MODEL_EXPORT_BYTES=850944 };
static void export_u32(unsigned char *p,uint32_t v){memcpy(p,&v,4);}
static void export_u64(unsigned char *p,uint64_t v){memcpy(p,&v,8);}
static int model_export_attach(int fd){
 struct stat st;int seals=fcntl(fd,F_GET_SEALS);
 if(fstat(fd,&st)<0)return -1;
 if(!S_ISREG(st.st_mode)||st.st_size!=MODEL_EXPORT_HEADER+MODEL_EXPORT_BYTES||seals<0||(seals&(F_SEAL_GROW|F_SEAL_SHRINK))!=(F_SEAL_GROW|F_SEAL_SHRINK)){errno=EINVAL;return -1;}
 unsigned char *p=mmap(NULL,st.st_size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
 if(p==MAP_FAILED)return -1;
 if(memcmp(p,"GZMDL002",8)){munmap(p,st.st_size);errno=EPROTO;return -1;}
 model_export.fd=fd;model_export.map=p;return 0;
}
static int model_export_publish(const unsigned char *pixels,uint32_t sequence,uint64_t stamp,uint64_t epoch,uint64_t tick){
 if(!model_export.map)return 0;
 if(stamp<=model_export.last_stamp||!epoch){errno=EPROTO;return -1;}
 struct flock lock={.l_type=F_WRLCK,.l_whence=SEEK_SET,.l_start=0,.l_len=1};
 if(fcntl(model_export.fd,F_SETLK,&lock)<0){
  if(errno==EAGAIN||errno==EACCES||errno==EINTR){model_export.busy++;return 0;}
  return -1;
 }
 unsigned char h[MODEL_EXPORT_HEADER]={0};memcpy(h,"GZMDL002",8);
 export_u32(h+8,2);export_u32(h+12,640);export_u32(h+16,360);export_u32(h+20,1920);export_u32(h+24,MODEL_EXPORT_BYTES);export_u32(h+28,sequence);
 export_u64(h+32,stamp);export_u64(h+40,stamp);export_u64(h+48,++model_export.serial);export_u64(h+64,epoch);export_u64(h+72,tick);export_u32(h+80,125000000);
 export_u32(model_export.map+24,0);
 memcpy(model_export.map+MODEL_EXPORT_HEADER,pixels,MODEL_EXPORT_BYTES);
 export_u64(h+56,mono());memcpy(model_export.map,h,sizeof(h));model_export.last_stamp=stamp;
 lock.l_type=F_UNLCK;return fcntl(model_export.fd,F_SETLK,&lock);
}
static void model_export_close(void){
 if(model_export.map){
  fprintf(stderr,"{\"kind\":\"native_model_export_summary\",\"published\":%" PRIu64 ",\"busy_drops\":%" PRIu64 "}\n",model_export.serial,model_export.busy);
  munmap(model_export.map,MODEL_EXPORT_HEADER+MODEL_EXPORT_BYTES);model_export.map=NULL;
 }
}
#endif
