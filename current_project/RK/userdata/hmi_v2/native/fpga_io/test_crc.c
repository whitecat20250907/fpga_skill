#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include "ring.c"
#include "../../vendor/gaze_app/fpga_model_packet.h"
int main(void){
 (void)model_packet_validate;(void)model_unpack_tensor;
 (void)model_packet_classify_sealed;(void)model_sealed_drop_reason;
 unsigned char *p=malloc(FPGA_MODEL_PAYLOAD+8);if(!p)return 2;
 for(size_t i=0;i<FPGA_MODEL_PAYLOAD+8;i++)p[i]=(unsigned char)((i*37u+(i>>7)*19u)^0xa5u);
 const size_t lengths[]={0,1,7,8,9,15,16,17,63,64,65,4095,4096,4097,HMI_PAYLOAD,FPGA_MODEL_PAYLOAD};
 for(unsigned a=0;a<8;a++)for(unsigned i=0;i<sizeof(lengths)/sizeof(lengths[0]);i++){
  size_t n=lengths[i];printf("%u %zu %u %u\n",a,n,crc32(p+a,n),model_crc32(p+a,n));
 }
 volatile uint32_t sink=0;clock_t start=clock();
 for(unsigned i=0;i<64;i++)sink^=model_crc32(p,FPGA_MODEL_PAYLOAD);
 double model_ms=1000.*(clock()-start)/CLOCKS_PER_SEC/64.;start=clock();
 for(unsigned i=0;i<64;i++)sink^=crc32(p,HMI_PAYLOAD);
 double ring_ms=1000.*(clock()-start)/CLOCKS_PER_SEC/64.;
 printf("BENCH %.6f %.6f %u\n",model_ms,ring_ms,sink);free(p);return 0;
}
