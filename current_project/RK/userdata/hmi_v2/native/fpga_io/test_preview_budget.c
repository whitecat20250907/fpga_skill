#include <assert.h>
#include <stdio.h>
#include "preview_budget.h"
int main(void){
 struct hmi_preview_budget q={0};unsigned index=99;
 assert(!hmi_preview_due(&q,0,&index));
 for(unsigned i=0;i<32;i++)assert(!hmi_preview_hold(&q,i));
 assert(hmi_preview_hold(&q,0)==-1&&hmi_preview_hold(&q,32)==-1);
 for(unsigned i=0;i<32;i++){
  uint64_t now=(uint64_t)i*50000000u;
  if(i)assert(!hmi_preview_due(&q,now-1,&index));
  assert(hmi_preview_due(&q,now,&index)&&index==i);
  assert(hmi_preview_due(&q,now,&index)&&index==i); /* failed QBUF retains ownership */
  hmi_preview_requeued(&q,now);
 }
 assert(!q.count&&!q.held);
 assert(!hmi_preview_hold(&q,7));assert(hmi_preview_due(&q,10000000000ull,&index)&&index==7);
 hmi_preview_requeued(&q,10000000000ull);assert(!hmi_preview_hold(&q,8));
 assert(!hmi_preview_due(&q,10000000001ull,&index));
 puts("PASS preview budget: ownership, wrap, no burst, failed requeue retained");return 0;
}
