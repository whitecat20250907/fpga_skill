#ifndef HMI_PREVIEW_BUDGET_H
#define HMI_PREVIEW_BUDGET_H
#include <stdint.h>
#include <errno.h>
/* Only dequeued, CPU-owned V4L2 buffers may be held. No in-flight DMA is
 * cancelled. At most one buffer is requeued per interval; missed deadlines
 * never accumulate a burst. Model C2H1 has no admission cap. */
struct hmi_preview_budget { unsigned index[32],head,count; uint64_t held,next_ns; };
static int hmi_preview_hold(struct hmi_preview_budget *q,unsigned index){
 if(index>=32||q->count>=32||(q->held&(UINT64_C(1)<<index))){errno=EINVAL;return -1;}
 q->index[(q->head+q->count)%32]=index;q->count++;q->held|=UINT64_C(1)<<index;return 0;
}
static int hmi_preview_due(struct hmi_preview_budget *q,uint64_t now,unsigned *index){
 if(!q->count||now<q->next_ns)return 0;
 *index=q->index[q->head];return 1;
}
static void hmi_preview_requeued(struct hmi_preview_budget *q,uint64_t now){
 q->held&=~(UINT64_C(1)<<q->index[q->head]);q->head=(q->head+1)%32;q->count--;
 q->next_ns=now+50000000u; /* 20 full-resolution preview transfers / second. */
}
#endif
