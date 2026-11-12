// Optional display-only resize. No model pixels, coordinates or state are changed.
#include <cstddef>
#include <cstdio>
#include <rga/im2d.h>
#include <cstdlib>
#include <cstring>
#include <algorithm>
struct Buffers { void *src=nullptr,*dst=nullptr; int sw=0,sh=0,dw=0,dh=0; rga_buffer_handle_t s=0,d=0; };
static void release(Buffers *b){if(b->s)releasebuffer_handle(b->s);if(b->d)releasebuffer_handle(b->d);free(b->src);free(b->dst);*b=Buffers();}
extern "C" void *hmi_rga_create(){return new Buffers();}
extern "C" void hmi_rga_destroy(void *handle){auto b=(Buffers*)handle;if(b){release(b);delete b;}}
extern "C" int hmi_rga_resize(void *handle,const void *src,int sw,int sh,void *dst,int dw,int dh){
 auto b=(Buffers*)handle;
 if(!b||!src||!dst||sw<2||sh<2||dw<2||dh<2||sw>8192||sh>8192||dw>8192||dh>8192)return -100;
 if(b->sw!=sw||b->sh!=sh||b->dw!=dw||b->dh!=dh){
  release(b);if(posix_memalign(&b->src,4096,(size_t)sw*sh*4)||posix_memalign(&b->dst,4096,(size_t)dw*dh*4)){release(b);return -101;}
  b->s=importbuffer_virtualaddr(b->src,sw*sh*4);b->d=importbuffer_virtualaddr(b->dst,dw*dh*4);
  if(!b->s||!b->d){release(b);return -102;}
  b->sw=sw;b->sh=sh;b->dw=dw;b->dh=dh;
 }
 memcpy(b->src,src,(size_t)sw*sh*4);
 auto s=wrapbuffer_handle(b->s,sw,sh,RK_FORMAT_BGRA_8888);auto d=wrapbuffer_handle(b->d,dw,dh,RK_FORMAT_BGRA_8888);
 im_rect empty={};auto status=imcheck(s,d,empty,empty);
 if(status!=IM_STATUS_NOERROR)return (int)status;
 status=imresize(s,d,0,0,1,1);
 if(status!=IM_STATUS_SUCCESS)return (int)status;
 memcpy(dst,b->dst,(size_t)dw*dh*4);return 0;
}

// RGB888 variant for the owner's HD preview. Separate caller handle; same bounded buffers.
extern "C" int hmi_rga_resize_rgb(void *handle,const void *src,int sw,int sh,void *dst,int dw,int dh){
 auto b=(Buffers*)handle;
 if(!b||!src||!dst||sw<2||sh<2||dw<2||dh<2||sw>8192||sh>8192||dw>8192||dh>8192)return -100;
 if(b->sw!=sw||b->sh!=sh||b->dw!=dw||b->dh!=dh){
  release(b);if(posix_memalign(&b->src,4096,(size_t)sw*sh*4)||posix_memalign(&b->dst,4096,(size_t)dw*dh*4)){release(b);return -101;}
  b->s=importbuffer_virtualaddr(b->src,sw*sh*4);b->d=importbuffer_virtualaddr(b->dst,dw*dh*4);
  if(!b->s||!b->d){release(b);return -102;}
  b->sw=sw;b->sh=sh;b->dw=dw;b->dh=dh;
 }
 memcpy(b->src,src,(size_t)sw*sh*3);
 auto s=wrapbuffer_handle(b->s,sw,sh,RK_FORMAT_RGB_888);auto d=wrapbuffer_handle(b->d,dw,dh,RK_FORMAT_RGB_888);
 im_rect empty={};auto status=imcheck(s,d,empty,empty);
 if(status!=IM_STATUS_NOERROR)return (int)status;
 status=imresize(s,d,0,0,1,1);
 if(status!=IM_STATUS_SUCCESS)return (int)status;
 memcpy(dst,b->dst,(size_t)dw*dh*3);return 0;
}
