/* Compile the reviewed HFT2/HFT3 protocol and ownership glue together so
 * the actual packet validator and exact per-source age calculation agree. */
#include "../../vendor/twb_native/twb_core.c"
#include "ui_transaction.h"
static void hmi_le32(uint8_t *p,uint32_t x){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(x>>(8*i));}
int hmi_ui_submit(struct twb_session *s,const uint8_t *input,size_t n,int csr,const uint32_t *values){
 if(!s||!input||n<116||n>TWB_MAX_PACKET||(n&3u)||csr<0||csr>2)return TWB_ARGUMENT;
 if(!packet_header_bytes(input,n))return TWB_PACKET;
 if(input[4]==3 && s->maximum<1916u)return TWB_UNSUPPORTED;
 /* Never repair an incoming bad CRC when updating transport-age fields. */
 if(crc32(input,n-4)!=le32(input+n-4))return TWB_PACKET;
 if(csr&&(!values||values[30]!=le32(input+104)))return TWB_ARGUMENT;
 if(csr){uint32_t abi,busy;if(rd(s,0xcf0,&abi)||rd(s,0xcfc,&busy))return TWB_IO;
  if(abi!=(csr==2?0x55493131u:0x55493130u)){return TWB_UNSUPPORTED;}
  if(busy&1u){return TWB_AGAIN;}}
 else {uint32_t abi;if(rd(s,0xcf0,&abi))return TWB_IO;
  if(abi==0x55493131u)return TWB_UNSUPPORTED;}
 uint64_t prepared_ns,token;int result=twb_prepare(s,(uint32_t)n,&prepared_ns,&token);
 if(result!=TWB_OK)return result;
 uint8_t packet[TWB_MAX_PACKET];memcpy(packet,input,n);
 /* The hardware owner allocates transport identity. A restarted composer
  * may begin at sequence 1 again; it must not replay old FPGA sequence IDs. */
 for(unsigned i=0;i<8;i++)packet[32+i]=(uint8_t)(token>>(8*i));
 hmi_le32(packet+104,(uint32_t)token);
 for(unsigned group=0;group<5;group++)if(packet[10]&(1u<<group)){
  uint64_t source=packet_source_ns(packet,group);
  if(!source||source>prepared_ns){twb_cancel(s,token);return TWB_PACKET;}
  uint64_t delta=prepared_ns-source,age=delta/1000000u+(delta%1000000u!=0);
  if(age>65535u)age=65535u;
  if(age<le16(packet+14+2*group))age=le16(packet+14+2*group);
  packet[14+2*group]=(uint8_t)age;packet[15+2*group]=(uint8_t)(age>>8);
 }
 hmi_le32(packet+n-4,crc32(packet,n-4));
 if(!packet_valid(s,packet,n)){twb_cancel(s,token);return TWB_PACKET;}
 if(csr){
  for(unsigned i=0;i<31;i++)if(wr(s,0xc80+4*i,i==30?(uint32_t)token:values[i])){twb_cancel(s,token);return TWB_IO;}
  /* Arm the held mailbox BEFORE starting the HFT2 packet. Its CDC handshake
   * then precedes packet parsing/raster completion, even at a blank boundary. */
  if(wr(s,0xcfc,0x55490001u)){twb_cancel(s,token);return TWB_IO;}
  uint32_t drain;if(rd(s,0xcfc,&drain)){twb_cancel(s,token);return TWB_IO;}
 }
 return twb_commit(s,token,packet,n);
}
