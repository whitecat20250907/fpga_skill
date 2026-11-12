#ifndef HMI_RING_H
#define HMI_RING_H
#include <stdint.h>
#include <stddef.h>
#include <stdatomic.h>
#define HMI_PAYLOAD 850944u
#define HMI_SLOTS 3u
#define HMI_SLOT_BYTES (64u+HMI_PAYLOAD)
#define HMI_RING_BYTES (64u+HMI_SLOTS*HMI_SLOT_BYTES)
struct hmi_ring_header {char magic[8];uint32_t version,slots,slot_bytes,payload_bytes;uint64_t epoch;_Atomic uint64_t write_seq;uint64_t reserved[3];};
struct hmi_slot_header {_Atomic uint64_t lock;uint64_t serial;uint32_t frame_id,flags;uint64_t src_ns,dequeue_ns,pub_ns,tick;uint32_t crc,valid;};
_Static_assert(sizeof(struct hmi_ring_header)==64,"ring ABI");
_Static_assert(sizeof(struct hmi_slot_header)==64,"slot ABI");
void hmi_ring_init(void *,uint64_t);
int hmi_ring_publish(void *,const void *,uint32_t,uint64_t,uint64_t,uint64_t);
int hmi_ring_snapshot(const void *,void *,size_t,uint64_t);
#endif
