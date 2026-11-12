#ifndef HMI_FINISH_DIAGNOSTICS_H
#define HMI_FINISH_DIAGNOSTICS_H
#include <stdint.h>
#include <stdio.h>
/* Preserve inherited failure precedence. Do not call a receiver error a
 * second cleanup failure, or infer DMA-engine quiescence from the BAR bit. */
static int hmi_finish_result(int worker,int join,int unmap,int unlock,uint32_t control){
 int cleanup=join?join:(unmap?unmap:unlock);
 fprintf(stderr,"{\"kind\":\"model_finish_diagnostics\",\"worker_errno\":%d,"
  "\"join_errno\":%d,\"munmap_errno\":%d,\"unlock_errno\":%d,"
  "\"local_cleanup_errno\":%d,\"model_control_before_unmap\":%u,"
  "\"dma_engine_quiescence_verified\":false}\n",worker,join,unmap,unlock,cleanup,control);
 return worker?worker:cleanup;
}
#endif
