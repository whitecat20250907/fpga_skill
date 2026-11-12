/* Anti-aliasing for the exact RGB3 1920x1080 -> 640x360 delivery ratio.
 * Equal 3x3 footprint in each channel, nearest rounding; no colour mask.
 * Does not change the full-resolution camera or DMA lifetime contract. */
#ifndef GAZE_RGB_AREA3_H
#define GAZE_RGB_AREA3_H
#include <stddef.h>
#include <stdint.h>
static int rgb_area3(uint8_t *dst,size_t dst_size,const uint8_t *src,
                     size_t src_size,size_t stride,unsigned width,unsigned height){
 if(!dst||!src||width!=1920||height!=1080||stride<5760||stride>67108864u/1080||src_size<stride*1080||dst_size<691200)return -1;
 for(size_t y=0;y<360;y++){
  const uint8_t *a=src+(y*3)*stride;
  const uint8_t *b=a+stride;
  const uint8_t *c=b+stride;
  uint8_t *out=dst+y*1920;
  for(size_t x=0;x<640;x++){
   size_t j=x*9;
   for(size_t k=0;k<3;k++){
    unsigned sum=a[j+k]+a[j+k+3]+a[j+k+6]
                +b[j+k]+b[j+k+3]+b[j+k+6]
                +c[j+k]+c[j+k+3]+c[j+k+6];
    out[x*3+k]=(uint8_t)((sum+4)/9);
   }
  }
 }
 return 0;
}
#endif
