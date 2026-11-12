#ifndef HMI_RECEIVE_DIAGNOSTICS_H
#define HMI_RECEIVE_DIAGNOSTICS_H
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdatomic.h>
/* Existing BND1 read-only counters, sampled by the sole DMA receiver BEFORE
 * its model-branch reset. Sequential reads are not an atomic FPGA snapshot.
 * At most the first eight events and powers of two are logged per session. */
static int hmi_receive_log_due(uint64_t count){
 return count && (count<=8 || !(count&(count-1)));
}
static void hmi_receive_fault(volatile uint32_t *bar,uint64_t event,
 int64_t length,int error,uint32_t status,uint32_t frame_id,
 uint64_t credit_ns,uint64_t before_read_ns,uint64_t received_ns){
 if(!hmi_receive_log_due(event))return;
 atomic_thread_fence(memory_order_seq_cst);
 uint32_t control=bar[0x19c/4],packets=bar[0x1a0/4];
 uint32_t source=bar[0x1ac/4],complete=bar[0x1b0/4],abort=bar[0x1b4/4];
 uint32_t overflow=bar[0x1b8/4],packet_abort=bar[0x1bc/4],drops=bar[0x1c0/4];
 atomic_thread_fence(memory_order_seq_cst);
 fprintf(stderr,"{\"kind\":\"model_fault_before_reset\",\"event\":%" PRIu64
  ",\"read_bytes\":%" PRId64 ",\"read_errno\":%d,\"sealed_status\":%u,\"frame_id\":%u,"
  "\"credit_ns\":%" PRIu64 ",\"before_read_ns\":%" PRIu64 ",\"received_ns\":%" PRIu64
  ",\"control\":%u,\"packets\":%u,\"source_frames\":%u,\"complete_frames\":%u,"
  "\"abort_frames\":%u,\"overflows\":%u,\"packet_aborts\":%u,\"packet_drops\":%u,"
  "\"atomic_hardware_snapshot\":false,\"dma_engine_quiescence_verified\":false}\n",
  event,length,error,status,frame_id,credit_ns,before_read_ns,received_ns,
  control,packets,source,complete,abort,overflow,packet_abort,drops);
}
#endif
