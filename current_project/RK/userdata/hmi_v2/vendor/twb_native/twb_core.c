#include "twb_core.h"
#include <string.h>

#define CAP_VALUE UINT32_C(0x32544648)
#define ABI_VALUE UINT32_C(0x32425754)
#define FLUSH_VALUE UINT32_C(0x48534c46)
#define ANCHOR_VALUE UINT32_C(0x48434e41)
#define ST_BUSY 2u
#define ST_FAULT 4u
#define ST_UP 16u
#define ST_ANCHOR 32u
static int rd(struct twb_session *s,uint32_t off,uint32_t *v){return s->io.read32(s->io.context,off,v)?TWB_IO:TWB_OK;}
static int wr(struct twb_session *s,uint32_t off,uint32_t v){return s->io.write32(s->io.context,off,v)?TWB_IO:TWB_OK;}
static uint16_t le16(const uint8_t *p){return (uint16_t)((uint16_t)p[0]|((uint16_t)p[1]<<8));}
static uint32_t le32(const uint8_t *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static uint64_t le64(const uint8_t *p){return (uint64_t)le32(p)|((uint64_t)le32(p+4)<<32);}
static uint32_t crc32(const uint8_t *p,size_t n){
    uint32_t c=UINT32_MAX;
    for(size_t j=0;j<n;j++){
        c^=p[j];
        for(unsigned k=0;k<8;k++)c=(c>>1)^(UINT32_C(0xedb88320)&(0u-(c&1u)));
    }
    return ~c;
}
void twb_init(struct twb_session *s,struct twb_io io){memset(s,0,sizeof(*s));s->io=io;s->needs_flush=1;}
static int identify(struct twb_session *s,struct twb_probe *out){
    struct twb_probe p={0};
    if(!s||!s->io.read32||!s->io.write32||!s->io.monotonic_ns)return TWB_ARGUMENT;
    if(rd(s,TWB_CAP,&p.cap)||rd(s,TWB_ABI,&p.abi)||rd(s,TWB_LIMITS,&p.limits)||rd(s,TWB_STATUS,&p.status))return TWB_IO;
    if(out)*out=p;
    uint32_t depth=p.limits>>16,maximum=p.limits&65535u;
    if(p.cap!=CAP_VALUE||p.abi!=ABI_VALUE||(maximum!=1908u&&maximum!=TWB_MAX_PACKET)||depth<(maximum+3u)/4u||depth>32768u||(depth&(depth-1u)))return TWB_UNSUPPORTED;
    s->depth=depth;s->maximum=maximum;return TWB_OK;
}
int twb_probe(struct twb_session *s,struct twb_probe *out){
    int rc=identify(s,out);if(s)s->bound=rc==TWB_OK;return rc;
}
static int check(struct twb_session *s){
    if(!s||!s->bound)return TWB_STATE;
    int rc=identify(s,0);if(rc!=TWB_OK){s->bound=0;s->needs_flush=1;s->prepared=0;}return rc;
}
int twb_flush_poll(struct twb_session *s){
    int rc=check(s);if(rc)return rc;
    if(!s->flush_pending)return TWB_STATE;
    uint32_t status,generation;
    if(rd(s,TWB_STATUS,&status)||rd(s,TWB_GENERATION,&generation))return TWB_IO;
    if(generation!=s->flush_generation){s->flush_pending=0;s->needs_flush=1;return TWB_CHANGED;}
    if(status&ST_BUSY)return TWB_PENDING;
    s->flush_pending=0;
    if((status&(ST_FAULT|ST_ANCHOR))||!(status&ST_UP)){s->needs_flush=1;return TWB_CHANGED;}
    s->needs_flush=0;return TWB_OK;
}
int twb_flush_begin(struct twb_session *s){
    int rc=check(s);if(rc)return rc;
    if(s->flush_pending)return TWB_STATE;
    uint32_t status,generation,after;
    if(rd(s,TWB_STATUS,&status)||rd(s,TWB_GENERATION,&generation))return TWB_IO;
    if((status&ST_BUSY)||!(status&ST_UP))return TWB_AGAIN;
    s->needs_flush=1;s->prepared=0;
    if(wr(s,TWB_CONTROL,FLUSH_VALUE)||rd(s,TWB_GENERATION,&after))return TWB_IO;
    if((uint32_t)(after-generation)!=1u)return TWB_CHANGED;
    s->flush_generation=after;s->flush_pending=1;
    return twb_flush_poll(s);
}
int twb_prepare(struct twb_session *s,uint32_t reserve,uint64_t *now,uint64_t *token){
    int rc=check(s);if(rc)return rc;
    if(!now||!token||reserve<116u||reserve>s->maximum||(reserve&3u))return TWB_ARGUMENT;
    if(s->needs_flush||s->flush_pending||s->prepared)return TWB_STATE;
    uint32_t status,free_words,g0,g1,accepted,rejected,anchor;
    if(rd(s,TWB_GENERATION,&g0)||rd(s,TWB_STATUS,&status)||rd(s,TWB_FREE,&free_words))return TWB_IO;
    if((status&(ST_BUSY|ST_FAULT))||!(status&ST_UP)||free_words<reserve/4u)return TWB_AGAIN;
    if(free_words>s->depth)return TWB_CHANGED;
    if(rd(s,TWB_ACCEPTED,&accepted)||rd(s,TWB_REJECTED,&rejected)||rd(s,TWB_GENERATION,&g1))return TWB_IO;
    if(g0!=g1)return TWB_AGAIN;
    if(wr(s,TWB_ANCHOR,ANCHOR_VALUE)||rd(s,TWB_ANCHOR,&anchor))return TWB_IO;
    (void)anchor; /* Same-device read drains the posted ANCH before timing. */
    if(rd(s,TWB_STATUS,&status)||rd(s,TWB_GENERATION,&g1))return TWB_IO;
    if(g1!=g0||(status&(ST_BUSY|ST_FAULT))||!(status&ST_UP)||!(status&ST_ANCHOR)){
        s->needs_flush=1;return TWB_CHANGED;
    }
    s->prepared_ns=s->io.monotonic_ns(s->io.context);
    if(!s->prepared_ns)return TWB_IO;
    s->token++;if(!s->token)s->token++;
    s->generation=g0;s->accepted_before=accepted;s->rejected_before=rejected;
    s->reserve=reserve;s->prepared=1;*now=s->prepared_ns;*token=s->token;return TWB_OK;
}
int twb_cancel(struct twb_session *s,uint64_t token){
    if(!s||!s->prepared||token!=s->token)return TWB_STATE;
    s->prepared=0;return TWB_OK;
}
/* HFT3 adds only an independent trace source time. HFT2 remains accepted. */
static unsigned packet_header_bytes(const uint8_t *p,size_t n){
    if(!p||n<116)return 0;
    unsigned header=(p[4]==2&&p[6]==112)?112u:(p[4]==3&&p[6]==120)?120u:0u;
    return header && n>=header+4u ? header:0u;
}
static uint64_t packet_source_ns(const uint8_t *p,unsigned group){
    return le64(p+(group==4&&p[4]==3?112:group<2||group==4?40:48));
}
static int packet_valid(struct twb_session *s,const uint8_t *p,size_t n){
    unsigned header=packet_header_bytes(p,n);
    if(!header||n>s->reserve||(n&3u)||memcmp(p,"HFT1",4)||(p[5]&~3u)||(p[11]!=1&&p[11]!=2)||le32(p+92))return 0;
    unsigned vc=p[7],ec=p[8],tc=p[9],mask=p[10];
    if(vc>128||ec>128||tc>64||(mask&~31u)||le16(p+12)!=vc*8u+ec*4u+tc*4u||n!=header+4u+le16(p+12)||!le64(p+24))return 0;
    if(crc32(p,n-4)!=le32(p+n-4))return 0;
    uint32_t state=le32(p+100);unsigned draw=state&15u,gesture=(state>>4)&15u,label=(state>>8)&15u;
    unsigned mode=(state>>16)&3u,assoc=p[110];
    if(p[111]||state>>18||mode>2u||p[109]>48u||(assoc&~7u))return 0;
    if(!((draw<=5u)||draw==15u)||!((gesture<=6u)||gesture==15u)||!((label<=7u)||label==15u))return 0;
    if(((mask&1u)&&!(assoc&2u))||((mask&2u)&&!(assoc&4u)))return 0;
    if(((mask&12u)||(assoc&6u))&&!(assoc&1u))return 0;
    if((assoc&1u)&&le32(p+96)==UINT32_MAX)return 0;
    if((mask&16u)&&(mode!=1u||!(assoc&6u)||!p[109]))return 0;
    if((state&32768u)&&(!(state&16384u)||!(state&8192u)||!(assoc&1u)))return 0;
    if((state&16384u)&&(!(state&8192u)||!(assoc&1u)))return 0;
    if((state&4096u)&&(draw!=3u||label>7u))return 0;
    unsigned trace_vertices=0;
    for(unsigned group=0;group<5;group++){
        if(!(mask&(1u<<group)))continue;
        uint64_t source=packet_source_ns(p,group);
        if(!source||source>s->prepared_ns)return 0;
        uint64_t delta=s->prepared_ns-source,age=delta/1000000u+(delta%1000000u!=0);
        if(age>65535u)age=65535u;
        if(le16(p+14+2u*group)<age)return 0;
    }
    size_t pos=header;
    for(unsigned j=0;j<vc;j++,pos+=8){if(p[pos]>4||p[pos+1])return 0;if(p[pos]==4)trace_vertices++;}
    if((mask&16u)&&trace_vertices!=p[109])return 0;
    for(unsigned j=0;j<ec;j++,pos+=4){
        unsigned a=p[pos],b=p[pos+1];
        if(a>=vc||b>=vc||p[pos+2]>3||p[pos+3]||p[header+8*a]!=p[header+8*b])return 0;
    }
    for(unsigned j=0;j<tc;j++,pos+=4){
        unsigned a=p[pos],b=p[pos+1],c=p[pos+2];
        if(a>=vc||b>=vc||c>=vc||p[pos+3]>3||p[header+8*a]!=p[header+8*b]||p[header+8*a]!=p[header+8*c])return 0;
    }
    return 1;
}
int twb_commit(struct twb_session *s,uint64_t token,const uint8_t *packet,size_t n){
    if(!s||!s->prepared||token!=s->token)return TWB_STATE;
    int rc=check(s);if(rc)return rc;
    if(!packet_valid(s,packet,n)){s->prepared=0;return TWB_PACKET;}
    uint32_t gen,status,free_words,accepted,rejected;
    if(rd(s,TWB_GENERATION,&gen)||rd(s,TWB_STATUS,&status)||rd(s,TWB_FREE,&free_words))return TWB_IO;
    s->prepared=0;
    if(gen!=s->generation||(status&(ST_BUSY|ST_FAULT))||!(status&ST_UP)||!(status&ST_ANCHOR)||free_words<n/4u){
        s->needs_flush=1;return TWB_CHANGED;
    }
    for(size_t off=0;off<n;off+=4){
        if(wr(s,TWB_DATA,le32(packet+off))){s->needs_flush=1;return TWB_IO;}
    }
    /* Accepted read both drains posted DATA and verifies real commit count. */
    if(rd(s,TWB_ACCEPTED,&accepted)||rd(s,TWB_REJECTED,&rejected)||rd(s,TWB_GENERATION,&gen)||rd(s,TWB_STATUS,&status)){
        s->needs_flush=1;return TWB_IO;
    }
    if((uint32_t)(accepted-s->accepted_before)!=n/4u||rejected!=s->rejected_before||gen!=s->generation||(status&(ST_BUSY|ST_FAULT))){
        s->needs_flush=1;return TWB_CHANGED;
    }
    return TWB_OK; /* Enqueued only; use coherent UI snapshot for HFT acceptance. */
}
int twb_read_snapshot(struct twb_session *s,struct twb_snapshot *out){
    int rc=check(s);if(rc)return rc;if(!out)return TWB_ARGUMENT;
    for(unsigned tries=0;tries<8;tries++){
        uint32_t a,b,v[7];
        if(rd(s,TWB_SNAPSHOT,&a))return TWB_IO;
        if(a&1u)continue;
        for(unsigned k=0;k<7;k++)if(rd(s,TWB_SNAPSHOT+4+4*k,&v[k]))return TWB_IO;
        if(rd(s,TWB_SNAPSHOT,&b))return TWB_IO;
        if(a==b&&!(b&1u)){
            *out=(struct twb_snapshot){b,v[0],v[1],v[2],v[3],v[4],v[5],v[6]};return TWB_OK;
        }
    }
    return TWB_AGAIN;
}
const char *twb_error(int rc){
    switch(rc){case TWB_OK:return "ok";case TWB_AGAIN:return "busy_or_no_credit";
    case TWB_PENDING:return "flush_pending";case TWB_UNSUPPORTED:return "unsupported_TWB2";
    case TWB_IO:return "io_failure";case TWB_STATE:return "invalid_session_state";
    case TWB_PACKET:return "invalid_HFT2_or_source_age";case TWB_CHANGED:return "device_or_counters_changed";
    default:return "invalid_argument";}
}
