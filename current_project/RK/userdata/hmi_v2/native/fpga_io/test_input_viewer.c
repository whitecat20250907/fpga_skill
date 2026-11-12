#include "input_viewer.h"
#include <assert.h>
#include <string.h>
struct mock{int calls,fail;uint32_t magic;};
static int rd(void *ctx,uint32_t off,uint32_t *out){
 struct mock *m=ctx;int index=m->calls++;assert(off==(uint32_t)(0xf00+index*4));
 if(index==m->fail)return -1;
 *out=index==0?m->magic:((uint32_t[]){0,0xffffffffu,17,2,5})[index];return 0;
}
int main(void){
 char s[256];struct mock m={0,-1,0};
 assert(hmi_viewer_json(s,sizeof(s),&m,rd)>0);assert(m.calls==1&&strstr(s,"\"supported\":false")&&strstr(s,"\"counters\":null"));
 for(int i=0;i<5;i++){
  m=(struct mock){0,i,0x31574956u};assert(hmi_viewer_json(s,sizeof(s),&m,rd)>0);
  assert(m.calls==i+1&&strstr(s,"\"read_ok\":false")&&strstr(s,"\"counters\":null"));
 }
 m=(struct mock){0,-1,0x31574956u};assert(hmi_viewer_json(s,sizeof(s),&m,rd)>0);
 assert(m.calls==5&&strstr(s,"\"completed\":4294967295")&&strstr(s,"\"control\":5"));puts(s);
 /* The owner detects truncation; the helper still reports snprintf's length. */
 m=(struct mock){0,-1,0x31574956u};assert(hmi_viewer_json(s,8,&m,rd)>=8);
 puts("PASS viewer telemetry: unsupported, each read failure, full counters, truncation");return 0;
}
