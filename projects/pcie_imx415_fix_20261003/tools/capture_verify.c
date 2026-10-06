/* gcc -O2 -Wall -Wextra -o capture_verify capture_verify.c
 * ./capture_verify /dev/videoX 1280 720 60 prefix
 * MMAP capture verifies actual V4L2 bytesused, logs RGB means/sequence,
 * and saves first/last frames without a display pipeline. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <poll.h>
#include <linux/videodev2.h>

struct buffer { void *p; size_t size; };
static void die(const char *s) { perror(s); exit(1); }
static void xio(int fd, unsigned long cmd, void *arg) {
    int rc;
    do { rc=ioctl(fd,cmd,arg); } while(rc<0&&errno==EINTR);
    if(rc<0) die("ioctl");
}
static double now(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);
    return t.tv_sec+t.tv_nsec/1e9;
}
int main(int argc,char **argv) {
    if(argc!=7) { fprintf(stderr,"usage: %s device width height count prefix timeout_s\n",argv[0]); return 1; }
    unsigned w=atoi(argv[2]),h=atoi(argv[3]),count=atoi(argv[4]);
    unsigned expected=w*h*3,bad=0,done=0;
    const char *save_mode=getenv("CAPTURE_SAVE_MODE");
    if(!save_mode) save_mode="bounded";
    int save=strcmp(save_mode,"none")!=0;
    int all_anomalies=strcmp(save_mode,"all")==0;
    unsigned anomaly_saved=0;
    if(strcmp(save_mode,"none")&&strcmp(save_mode,"bounded")&&strcmp(save_mode,"all")) {
        fprintf(stderr,"CAPTURE_SAVE_MODE must be none, bounded or all\n");return 2;
    }
    double started=now(),deadline=started+atof(argv[6]);
    int fd=open(argv[1],O_RDWR|O_NONBLOCK); if(fd<0) die("open");
    struct v4l2_format fmt={.type=V4L2_BUF_TYPE_VIDEO_CAPTURE};
    fmt.fmt.pix.width=w;fmt.fmt.pix.height=h;fmt.fmt.pix.pixelformat=V4L2_PIX_FMT_RGB24;
    fmt.fmt.pix.field=V4L2_FIELD_NONE;
    xio(fd,VIDIOC_S_FMT,&fmt);
    if(fmt.fmt.pix.width!=w||fmt.fmt.pix.height!=h||fmt.fmt.pix.pixelformat!=V4L2_PIX_FMT_RGB24) {
        fprintf(stderr,"unexpected negotiated format\n");return 1;
    }
    struct v4l2_requestbuffers req={.count=4,.type=V4L2_BUF_TYPE_VIDEO_CAPTURE,.memory=V4L2_MEMORY_MMAP};
    xio(fd,VIDIOC_REQBUFS,&req); if(req.count>8||req.count<2) return 1;
    struct buffer buffers[8]={0};
    for(unsigned i=0;i<req.count;i++) {
        struct v4l2_buffer b={.type=req.type,.memory=req.memory,.index=i};
        xio(fd,VIDIOC_QUERYBUF,&b);buffers[i].size=b.length;
        buffers[i].p=mmap(NULL,b.length,PROT_READ|PROT_WRITE,MAP_SHARED,fd,b.m.offset);
        if(buffers[i].p==MAP_FAILED) die("mmap");
        xio(fd,VIDIOC_QBUF,&b);
    }
    enum v4l2_buf_type type=req.type; xio(fd,VIDIOC_STREAMON,&type);
    while(done<count&&now()<deadline) {
        struct pollfd p={.fd=fd,.events=POLLIN};
        int rc=poll(&p,1,1000); if(rc<0&&errno==EINTR) continue;
        if(rc<0) die("poll");
        if(!rc) continue;
        struct v4l2_buffer b={.type=req.type,.memory=req.memory};
        if(ioctl(fd,VIDIOC_DQBUF,&b)<0) { if(errno==EAGAIN) continue;die("DQBUF"); }
        if(b.index>=req.count) return 1;
        if(b.bytesused>buffers[b.index].size) {
            fprintf(stderr,"driver bytesused exceeds mapped buffer\n");
            xio(fd,VIDIOC_STREAMOFF,&type);
            close(fd);return 2;
        }
        unsigned char *data=buffers[b.index].p;
        uint64_t sum[3]={0},n=0,green=0,purple=0;
        for(unsigned at=0;at+2<b.bytesused&&at+2<buffers[b.index].size;at+=192) {
            for(unsigned c=0;c<3;c++) sum[c]+=data[at+c];
            n++;
            if(data[at+1] > data[at]+60 && data[at+1] > data[at+2]+60) green++;
            if(data[at] > data[at+1]+60 && data[at+2] > data[at+1]+60) purple++;
        }
        if(b.bytesused!=expected || (b.flags&V4L2_BUF_FLAG_ERROR)) bad++;
        printf("{\"frame\":%u,\"sequence\":%u,\"bytesused\":%u,\"expected\":%u,\"error\":%s,\"seconds\":%.6f,\"rgb_mean\":[%.3f,%.3f,%.3f],\"green_fraction\":%.6f,\"purple_fraction\":%.6f}\n",
               done,b.sequence,b.bytesused,expected,(b.flags&V4L2_BUF_FLAG_ERROR)?"true":"false",now()-started,
               n?(double)sum[0]/n:0,n?(double)sum[1]/n:0,n?(double)sum[2]/n:0,
               n?(double)green/n:0,n?(double)purple/n:0);
        fflush(stdout);
        if(save && (done==0||done+1==count)) {
            char path[512];snprintf(path,sizeof(path),"%s_%s.rgb",argv[5],done?"last":"first");
            FILE *out=fopen(path,"wb");if(!out) die("fopen");
            if(fwrite(data,1,b.bytesused,out)!=b.bytesused) die("fwrite");
            fclose(out);
        }
        int anomaly=green > n/20 || purple > n/20;
        if(save && (done<6 || done%250==0 || (anomaly && (all_anomalies||anomaly_saved<8)))) {
            if(anomaly) anomaly_saved++;
            char path[512];snprintf(path,sizeof(path),"%s_frame%04u.rgb",argv[5],done);
            FILE *out=fopen(path,"wb");if(!out) die("fopen");
            if(fwrite(data,1,b.bytesused,out)!=b.bytesused) die("fwrite");
            fclose(out);
        }
        done++;xio(fd,VIDIOC_QBUF,&b);
    }
    xio(fd,VIDIOC_STREAMOFF,&type);
    for(unsigned i=0;i<req.count;i++) munmap(buffers[i].p,buffers[i].size);
    close(fd);
    fprintf(stderr,"CAPTURE_RESULT done=%u expected=%u bad=%u seconds=%.3f save_mode=%s\n",done,count,bad,now()-started,save_mode);
    return done==count&&bad==0?0:2;
}
