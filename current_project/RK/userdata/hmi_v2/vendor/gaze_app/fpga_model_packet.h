#ifndef FPGA_MODEL_PACKET_H
#define FPGA_MODEL_PACKET_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#if defined(__aarch64__) && defined(__ARM_FEATURE_CRC32)
#include <arm_acle.h>
#endif
#define FPGA_MODEL_PAYLOAD 861824u
#define FPGA_MODEL_OUTPUT 850944u
#define FPGA_MODEL_PACKET (FPGA_MODEL_PAYLOAD+80u)
static uint32_t model_u32(const unsigned char *p){uint32_t v;memcpy(&v,p,4);return v;}
static uint64_t model_u64(const unsigned char *p){uint64_t v;memcpy(&v,p,8);return v;}
static uint32_t model_crc32(const unsigned char *p,size_t n){
 uint32_t c=0xffffffffu;
#if defined(__aarch64__) && defined(__ARM_FEATURE_CRC32)
 while(n>=8){uint64_t v;memcpy(&v,p,8);c=__crc32d(c,v);p+=8;n-=8;}
 while(n--)c=__crc32b(c,*p++);
#else
 while(n--){c^=*p++;for(unsigned i=0;i<8;i++)c=(c>>1)^((c&1)?0xedb88320u:0u);}
#endif
 return ~c;
}
struct model_packet_info {uint32_t frame_id;uint64_t tick,epoch;};
static int model_packet_validate(const unsigned char *p,size_t n,uint64_t epoch,struct model_packet_info *info){
 if(n!=FPGA_MODEL_PACKET)return -1;
 if(model_u32(p)!=0x31463341u||model_u32(p+4)!=0x00010040u||model_u32(p+8)!=FPGA_MODEL_PAYLOAD)return -2;
 if(model_u32(p+16)!=0x31444e42u||model_u32(p+20)!=(360u<<16|640u)||model_u32(p+24)!=1920||model_u32(p+28)!=0)return -3;
 if(model_u64(p+40)!=epoch||model_u64(p+48)!=0||model_u32(p+56)!=125000000||model_u32(p+60)!=0)return -4;
 const unsigned char *f=p+n-16;
 if(model_u32(f+4)!=1||model_u32(f+8)!=FPGA_MODEL_PAYLOAD||model_u32(f+12)!=0x31444e45u)return -5;
 if(model_u32(f)!=model_crc32(p+64,FPGA_MODEL_PAYLOAD))return -6;
 info->frame_id=model_u32(p+12);info->tick=model_u64(p+32);info->epoch=model_u64(p+40);return 0;
}
static int model_unpack_tensor(const unsigned char *packet,unsigned char *output,size_t capacity){
 static const unsigned widths[3]={640,128,192},heights[3]={360,128,192};
 static const size_t offsets[3]={0,691200,740352};
 unsigned char seen[3][360]={{0}};unsigned rows=0;size_t pos=0;
 if(capacity<FPGA_MODEL_OUTPUT)return -1;
 const unsigned char *p=packet+64;
 while(pos<FPGA_MODEL_PAYLOAD){
  if(FPGA_MODEL_PAYLOAD-pos<16)return -2;
  unsigned magic=model_u32(p+pos),kind=model_u32(p+pos+4),row=model_u32(p+pos+8),n=model_u32(p+pos+12);pos+=16;
  if(magic!=0x31574f52u||kind>=3||row>=heights[kind]||seen[kind][row]||n!=widths[kind]*3u||n>FPGA_MODEL_PAYLOAD-pos)return -3;
  seen[kind][row]=1;rows++;memcpy(output+offsets[kind]+row*n,p+pos,n);pos+=n;
 }
 return pos==FPGA_MODEL_PAYLOAD&&rows==680?0:-4;
}


/* Independent sealed-error classifier. Original validator/unpacker above unchanged.
 * 0: normal packet; 1: integrity-checked framing, explicitly bad and droppable;
 * negative: fail closed. CRC is integrity, not cryptographic authentication.
 */
static int model_packet_classify_sealed(const unsigned char *p,size_t n,uint64_t epoch,
                                      struct model_packet_info *info,uint32_t *status){
 /* EOP may retire a CRC-sealed bad frame before its advertised maximum.
  * Validate bounds before reading any field; a truncated/unsealed read is
  * never treated as a droppable frame. Normal inference still requires the
  * exact original full-size packet and tensor layout. */
 if(n<80u||n>FPGA_MODEL_PACKET||(n&15u))return -1;
 if(model_u32(p)!=0x31463341u||model_u32(p+4)!=0x00010040u||model_u32(p+8)!=FPGA_MODEL_PAYLOAD)return -2;
 if(model_u32(p+16)!=0x31444e42u||model_u32(p+20)!=(360u<<16|640u)||model_u32(p+24)!=1920||model_u32(p+28)!=0)return -3;
 if(model_u64(p+40)!=epoch||model_u64(p+48)!=0||model_u32(p+56)!=125000000||model_u32(p+60)!=0)return -4;
 const unsigned char *f=p+n-16;
 uint32_t s=model_u32(f+4);
 size_t payload_size=n-80u;
 if(model_u32(f+8)!=payload_size||model_u32(f+12)!=0x31444e45u)return -5;
 if(s==1u){
  int r=model_packet_validate(p,n,epoch,info);
  if(r)return r;
  *status=1;return 0;
 }
 if(s!=2u&&s!=4u&&s!=8u)return -7;
 if(model_u32(f)!=model_crc32(p+64,payload_size))return -6;
 struct model_packet_info candidate;
 candidate.frame_id=model_u32(p+12);candidate.tick=model_u64(p+32);candidate.epoch=model_u64(p+40);
 *info=candidate;*status=s;return 1;
}
static const char *model_sealed_drop_reason(uint32_t status){
 return status==2u?"payload_boundary_error":status==4u?"source_identity_changed":status==8u?"source_idle_timeout":"invalid_status";
}
#endif
