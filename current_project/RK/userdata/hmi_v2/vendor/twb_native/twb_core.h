#ifndef TWB_CORE_H
#define TWB_CORE_H
#include <stddef.h>
#include <stdint.h>

enum { TWB_OK=0, TWB_AGAIN=1, TWB_PENDING=2, TWB_UNSUPPORTED=-1,
       TWB_IO=-2, TWB_STATE=-3, TWB_PACKET=-4, TWB_CHANGED=-5, TWB_ARGUMENT=-6 };
enum { TWB_CAP=0xc00, TWB_STATUS=0xc04, TWB_FREE=0xc08, TWB_ACCEPTED=0xc0c,
       TWB_DATA=0xc10, TWB_CONTROL=0xc14, TWB_REJECTED=0xc18, TWB_GENERATION=0xc1c,
       TWB_ANCHOR=0xc28, TWB_ABI=0xc38, TWB_LIMITS=0xc3c, TWB_SNAPSHOT=0xc40 };
#define TWB_MAX_PACKET 1916u
struct twb_io {
    void *context;
    int (*read32)(void *,uint32_t,uint32_t *);
    int (*write32)(void *,uint32_t,uint32_t);
    uint64_t (*monotonic_ns)(void *);
};
struct twb_probe { uint32_t cap,abi,limits,status; };
struct twb_snapshot { uint32_t generation,flags,scenes,accepted,crc_errors,format_errors,sequence_errors,clock_delta; };
struct twb_session {
    struct twb_io io;
    uint32_t depth,maximum,flush_generation,generation,accepted_before,rejected_before,reserve;
    uint64_t token,prepared_ns;
    unsigned bound,needs_flush,flush_pending,prepared;
};
void twb_init(struct twb_session *,struct twb_io);
int twb_probe(struct twb_session *,struct twb_probe *);
int twb_flush_begin(struct twb_session *);
int twb_flush_poll(struct twb_session *);
int twb_prepare(struct twb_session *,uint32_t,uint64_t *,uint64_t *);
int twb_cancel(struct twb_session *,uint64_t);
int twb_commit(struct twb_session *,uint64_t,const uint8_t *,size_t);
int twb_read_snapshot(struct twb_session *,struct twb_snapshot *);
const char *twb_error(int);
#endif
