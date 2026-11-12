/* Exact 1920x1080 RGB3 -> 640x360 integer-centred bilinear sample.
 * This matches OpenCV INTER_LINEAR at this exact 3:1 ratio; other sizes reject.
 * Private destination ownership must be established before calling it. */
#ifndef GAZE_RGB_CENTER3_H
#define GAZE_RGB_CENTER3_H
#include <stddef.h>
#include <stdint.h>
static int rgb_center3(uint8_t *dst,size_t dst_size,const uint8_t *src,
                       size_t src_size,size_t stride,unsigned width,unsigned height){
 if(!dst||!src||width!=1920||height!=1080||stride<5760||stride>67108864u/1080||src_size<stride*1080||dst_size<691200)return -1;
 for(size_t y=0;y<360;y++){
  const uint8_t *row=src+(y*3+1)*stride+3;
  uint8_t *out=dst+y*1920;
  for(size_t x=0;x<640;x++){
   out[x*3]=row[x*9];out[x*3+1]=row[x*9+1];out[x*3+2]=row[x*9+2];
  }
 }
 return 0;
}
#endif
