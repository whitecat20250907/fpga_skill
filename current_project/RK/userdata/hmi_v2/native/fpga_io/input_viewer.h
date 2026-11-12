#ifndef HMI_INPUT_VIEWER_H
#define HMI_INPUT_VIEWER_H
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
/* Sequential read-only samples by the existing C owner. No second BAR fd,
 * no frame copy, no atomic-snapshot or panel-visibility claim. */
typedef int (*hmi_viewer_read)(void *,uint32_t,uint32_t *);
static int hmi_viewer_json(char *out,size_t size,void *ctx,hmi_viewer_read read){
 uint32_t magic=0,v[4]={0};int n;
 if(read(ctx,0xf00,&magic))return snprintf(out,size,"{\"supported\":null,\"read_ok\":false,\"counters\":null}");
 if(magic!=0x31574956u)return snprintf(out,size,"{\"supported\":false,\"read_ok\":true,\"counters\":null}");
 for(n=0;n<4;n++)if(read(ctx,0xf04+4*(uint32_t)n,&v[n]))return snprintf(out,size,"{\"supported\":true,\"read_ok\":false,\"counters\":null}");
 return snprintf(out,size,"{\"supported\":true,\"read_ok\":true,\"control\":%u,\"counters\":{\"completed\":%u,\"dropped\":%u,\"malformed\":%u},\"atomic_snapshot\":false}",v[3],v[0],v[1],v[2]);
}
#endif
