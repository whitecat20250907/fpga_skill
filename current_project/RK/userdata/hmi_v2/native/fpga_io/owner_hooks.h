#include "ring.h"
static void *hmi_ring_map;
static int hmi_publish(const unsigned char *pixels,uint32_t seq,uint64_t stamp,uint64_t epoch,uint64_t tick){
 struct hmi_ring_header *h=hmi_ring_map;
 if(!h)return -1;
 if(!h->epoch)h->epoch=epoch;
 if(h->epoch!=epoch){errno=EPROTO;return -1;}
 if(hmi_ring_publish(h,pixels,seq,stamp,mono(),tick))return -1;
 return model_export_publish(pixels,seq,stamp,epoch,tick);
}
