#ifndef TWB_MMIO_H
#define TWB_MMIO_H
#include "twb_core.h"
uint32_t twb_native_library_abi(void);
int twb_native_probe(const char *,struct twb_probe *);
int twb_native_open(const char *,void **);
void twb_native_close(void *);
int twb_native_flush_begin(void *);
int twb_native_flush_poll(void *);
int twb_native_prepare(void *,uint32_t,uint64_t *,uint64_t *);
int twb_native_cancel(void *,uint64_t);
int twb_native_commit(void *,uint64_t,const uint8_t *,size_t);
int twb_native_snapshot(void *,struct twb_snapshot *);
#endif
