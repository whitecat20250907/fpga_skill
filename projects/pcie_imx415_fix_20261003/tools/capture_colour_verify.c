/* gcc -O2 -std=c11 -Wall -Wextra -Werror -o capture_colour_verify capture_colour_verify.c -lm
 * ./capture_colour_verify /dev/videoX 1280 720 1000 fresh/prefix 90 manual_roi.txt
 * Windows measurement self-test: gcc -DCOLOUR_SELFTEST_ONLY ... ; exe --self-test
 * Every dequeued RGB24 frame is measured without software colour correction.
 * Exit 0 means complete acquisition/measurements, NEVER colour/link PASS.
 * Thresholds create suspicion flags, not automatic physical diagnoses.
 */
#define _POSIX_C_SOURCE 200809L
#define __USE_MINGW_ANSI_STDIO 1
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <math.h>
#include <limits.h>
#ifndef COLOUR_SELFTEST_ONLY
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <poll.h>
#include <signal.h>
#include <linux/videodev2.h>
#endif

#define MAX_ROIS 9
static const char *names[MAX_ROIS] = {"RED","GREEN","BLUE","WHITE","GRAY","BLACK","ORANGE","CYAN","MAGENTA"};
struct roi { int kind; unsigned x0,y0,x1,y1; };
struct config {
    double margin, min_brightness, min_chroma, row_jump, temporal_jump;
    unsigned stable_frames, min_bad_rows, periodic, allow_partial;
};
struct row_stat { double rgb[3], score, jump; char dominant, order; };
struct roi_stat {
    double mean[3], temporal_max;
    uint64_t pixels, clipped0[3], clipped255[3];
    unsigned wrong_rows, inconclusive_rows, jump_rows;
    int suspicious;
    struct row_stat *rows;
};
struct measured_frame { struct roi_stat rois[MAX_ROIS]; unsigned suspicious_rois, inconclusive_rois; };
static struct config defaults(void) {
    struct config c = {5.0, 8.0, 8.0, 40.0, 40.0, 30, 1, 250, 0};
    return c;
}
static double max3(double a,double b,double c) { return fmax(a,fmax(b,c)); }
static double min3(double a,double b,double c) { return fmin(a,fmin(b,c)); }
static double order_score(int kind, const double rgb[3]) {
    double r=rgb[0],g=rgb[1],b=rgb[2];
    switch(kind) {
        case 0: return fmin(r-g,r-b);
        case 1: return fmin(g-r,g-b);
        case 2: return fmin(b-r,b-g);
        case 6: return fmin(r-g,g-b);
        case 7: return fmin(g-r,b-r);
        case 8: return fmin(r-g,b-g);
        default:return 0;
    }
}
static char dominant(const double rgb[3],double margin) {
    double r=rgb[0],g=rgb[1],b=rgb[2];
    if(r-g>margin&&r-b>margin) return 'R';
    if(g-r>margin&&g-b>margin) return 'G';
    if(b-r>margin&&b-g>margin) return 'B';
    if(fabs(r-g)<=margin&&r-b>margin&&g-b>margin) return 'Y';
    if(fabs(g-b)<=margin&&g-r>margin&&b-r>margin) return 'C';
    if(fabs(r-b)<=margin&&r-g>margin&&b-g>margin) return 'M';
    if(max3(r,g,b)-min3(r,g,b)<=margin) return 'N';
    return '?';
}
static int parse_rois(FILE *in,unsigned w,unsigned h,struct roi rois[MAX_ROIS],unsigned *n,
                      unsigned allow_partial,char *error,size_t error_size) {
    char line[512]; unsigned seen=0,number=0;
    *n=0;
    while(fgets(line,sizeof(line),in)) {
        char name[32],extra,coordinate[4][32]; long points[4]; int fields,kind=-1;
        number++;
        if(!strchr(line,'\n')&&!feof(in)) {snprintf(error,error_size,"ROI line %u is too long",number);return -1;}
        char *comment=strchr(line,'#'); if(comment) *comment=0;
        fields=sscanf(line," %31s %31s %31s %31s %31s %c",name,coordinate[0],coordinate[1],coordinate[2],coordinate[3],&extra);
        if(fields==EOF) continue;
        if(fields!=5) {snprintf(error,error_size,"ROI line %u requires NAME x0 y0 x1 y1",number);return -1;}
        for(unsigned k=0;k<4;k++) {
            char *end;
            errno=0;points[k]=strtol(coordinate[k],&end,10);
            if(errno||!*coordinate[k]||*end) {
                snprintf(error,error_size,"Invalid coordinate on ROI line %u",number);return -1;
            }
        }
        long x0=points[0],y0=points[1],x1=points[2],y1=points[3];
        for(int i=0;i<MAX_ROIS;i++) if(!strcmp(name,names[i])) kind=i;
        if(kind<0||(seen&(1u<<kind))||*n>=MAX_ROIS) {
            snprintf(error,error_size,"Unknown/duplicate ROI on line %u",number);return -1;
        }
        if(x0<0||y0<0||x1<=x0||y1<=y0||x1>(long)w||y1>(long)h||
           (x1-x0)*(y1-y0)<16||y1-y0<3) {
            snprintf(error,error_size,"Invalid/out-of-bounds/tiny ROI on line %u",number);return -1;
        }
        struct roi r={kind,(unsigned)x0,(unsigned)y0,(unsigned)x1,(unsigned)y1};
        for(unsigned i=0;i<*n;i++) {
            const struct roi *a=&rois[i];
            if(r.x0<a->x1&&r.x1>a->x0&&r.y0<a->y1&&r.y1>a->y0) {
                snprintf(error,error_size,"Overlapping ROIs on line %u",number);return -1;
            }
        }
        rois[(*n)++]=r;seen|=1u<<kind;
    }
    if(ferror(in)||!*n||(!allow_partial&&seen!=((1u<<MAX_ROIS)-1))) {
        snprintf(error,error_size,"ROI read failure/empty set/missing nine chart patches (partial requires explicit COLOUR_ALLOW_PARTIAL=1)");return -1;
    }
    return 0;
}
static int allocate_measurements(const struct roi rois[MAX_ROIS],unsigned n,struct measured_frame *m) {
    memset(m,0,sizeof(*m));
    for(unsigned i=0;i<n;i++) {
        m->rois[i].rows=calloc(rois[i].y1-rois[i].y0,sizeof(struct row_stat));
        if(!m->rois[i].rows) {
            for(unsigned j=0;j<i;j++) free(m->rois[j].rows);
            memset(m,0,sizeof(*m));return -1;
        }
    }
    return 0;
}
static void free_measurements(unsigned n,struct measured_frame *m) {
    for(unsigned i=0;i<n;i++) free(m->rois[i].rows);
    memset(m,0,sizeof(*m));
}
static void measure(const unsigned char *rgb,unsigned w,const struct roi rois[MAX_ROIS],unsigned n,
                    const struct config *c,const double previous[MAX_ROIS][3],int have_previous,
                    struct measured_frame *m) {
    m->suspicious_rois=m->inconclusive_rois=0;
    for(unsigned i=0;i<n;i++) {
        const struct roi *r=&rois[i]; struct roi_stat *s=&m->rois[i];
        struct row_stat *row_memory=s->rows;
        memset(s,0,sizeof(*s));s->rows=row_memory;
        for(unsigned y=r->y0;y<r->y1;y++) {
            struct row_stat *row=&s->rows[y-r->y0]; uint64_t sum[3]={0};
            memset(row,0,sizeof(*row));
            for(unsigned x=r->x0;x<r->x1;x++) {
                const unsigned char *p=rgb+((size_t)y*w+x)*3;
                for(unsigned k=0;k<3;k++) {
                    sum[k]+=p[k];s->clipped0[k]+=p[k]==0;s->clipped255[k]+=p[k]==255;
                }
            }
            for(unsigned k=0;k<3;k++) {row->rgb[k]=(double)sum[k]/(r->x1-r->x0);s->mean[k]+=sum[k];}
            s->pixels+=r->x1-r->x0;
            row->dominant=dominant(row->rgb,c->margin);
            row->score=order_score(r->kind,row->rgb);
            if(r->kind>=3&&r->kind<=5) row->order='N';
            else if(max3(row->rgb[0],row->rgb[1],row->rgb[2])<c->min_brightness||
                    max3(row->rgb[0],row->rgb[1],row->rgb[2])-min3(row->rgb[0],row->rgb[1],row->rgb[2])<c->min_chroma||
                    fabs(row->score)<=c->margin) {row->order='I';s->inconclusive_rows++;}
            else if(row->score>c->margin) row->order='E';
            else {row->order='W';s->wrong_rows++;}
            if(y>r->y0) {
                const struct row_stat *before=&s->rows[y-r->y0-1];
                row->jump=max3(fabs(row->rgb[0]-before->rgb[0]),fabs(row->rgb[1]-before->rgb[1]),fabs(row->rgb[2]-before->rgb[2]));
                if(row->jump>=c->row_jump) s->jump_rows++;
            }
        }
        for(unsigned k=0;k<3;k++) s->mean[k]/=(double)s->pixels;
        if(have_previous) s->temporal_max=max3(fabs(s->mean[0]-previous[i][0]),fabs(s->mean[1]-previous[i][1]),fabs(s->mean[2]-previous[i][2]));
        s->suspicious=s->wrong_rows>=c->min_bad_rows||s->jump_rows>0||
                      (have_previous&&s->temporal_max>=c->temporal_jump);
        m->suspicious_rois+=s->suspicious;
        m->inconclusive_rois+=s->inconclusive_rows>0;
    }
}
static int expect(int cond,const char *test,unsigned *total) {
    (*total)++;
    if(!cond) {fprintf(stderr,"SELFTEST_FAILED %s\n",test);return -1;}
    return 0;
}
static void fill_roi(unsigned char *rgb,unsigned w,const struct roi *r,const unsigned char color[3]) {
    for(unsigned y=r->y0;y<r->y1;y++) for(unsigned x=r->x0;x<r->x1;x++)
        memcpy(rgb+((size_t)y*w+x)*3,color,3);
}
static int self_test(void) {
    enum { W=96,H=96 }; unsigned char rgb[W*H*3],golden[W*H*3];
    const unsigned char colors[MAX_ROIS][3]={{255,0,0},{0,255,0},{0,0,255},{255,255,255},{128,128,128},{0,0,0},{255,128,0},{0,255,255},{255,0,255}};
    struct roi rois[MAX_ROIS]; struct measured_frame m; struct config c=defaults();
    double previous[MAX_ROIS][3]={{0}}; unsigned tests=0; char error[256];
    memset(rgb,25,sizeof(rgb));
    for(unsigned i=0;i<MAX_ROIS;i++) {
        unsigned x=(i%3)*32,y=(i/3)*32;
        rois[i]=(struct roi){(int)i,x+4,y+4,x+28,y+28};fill_roi(rgb,W,&rois[i],colors[i]);
    }
    if(allocate_measurements(rois,MAX_ROIS,&m)) return 1;
    memcpy(golden,rgb,sizeof(rgb));
#define CHECK(cond,label) do {if(expect((cond),(label),&tests)) goto fail;} while(0)
    measure(rgb,W,rois,MAX_ROIS,&c,previous,0,&m);
    CHECK(m.suspicious_rois==0&&m.inconclusive_rois==0,"nominal nine chart: natural green/magenta/cyan do not flag");
    CHECK(m.rois[6].mean[0]==255&&m.rois[6].mean[1]==128&&m.rois[6].mean[2]==0,"orange exact RGB order");
    CHECK(m.rois[3].clipped255[0]==m.rois[3].pixels,"white clipping recorded without arbitrary failure");
    for(unsigned i=0;i<MAX_ROIS;i++) memcpy(previous[i],m.rois[i].mean,sizeof(previous[i]));
    const unsigned char bad_orange[3]={30,160,20};fill_roi(rgb,W,&rois[6],bad_orange);
    measure(rgb,W,rois,MAX_ROIS,&c,previous,1,&m);
    CHECK(m.rois[6].wrong_rows==24&&m.rois[6].suspicious,"orange green-dominant frame detected");
    CHECK(m.rois[6].temporal_max>=c.temporal_jump,"ROI temporal colour flash measured");
    memcpy(rgb,golden,sizeof(rgb));
    struct roi stripe=rois[0];stripe.y0+=9;stripe.y1=stripe.y0+1;fill_roi(rgb,W,&stripe,colors[1]);
    measure(rgb,W,rois,MAX_ROIS,&c,previous,0,&m);
    CHECK(m.rois[0].wrong_rows==1&&m.rois[0].jump_rows==2&&m.rois[0].suspicious,"one-line green stripe in red ROI");
    stripe.y1++;fill_roi(rgb,W,&stripe,colors[1]);
    measure(rgb,W,rois,MAX_ROIS,&c,previous,0,&m);
    CHECK(m.rois[0].wrong_rows==2&&m.rois[0].jump_rows==2,"two-line green stripe");
    memset(rgb,1,sizeof(rgb));measure(rgb,W,rois,MAX_ROIS,&c,previous,0,&m);
    CHECK(m.inconclusive_rois==6&&m.suspicious_rois==0,"dark scene inconclusive, never colour established");
    memset(rgb,255,sizeof(rgb));measure(rgb,W,rois,MAX_ROIS,&c,previous,0,&m);
    CHECK(m.inconclusive_rois==6&&m.rois[0].clipped255[0]==m.rois[0].pixels,"all-channel saturation inconclusive");
    memcpy(rgb,golden,sizeof(rgb));
    for(unsigned i=0;i<MAX_ROIS;i++) for(unsigned y=rois[i].y0;y<rois[i].y1;y++) {
        struct roi line=rois[i];line.y0=y;line.y1=y+1;
        double gain=0.45+0.4*(double)(y-rois[i].y0)/(rois[i].y1-rois[i].y0-1);
        unsigned char shade[3];for(unsigned k=0;k<3;k++) shade[k]=(unsigned char)(gain*colors[i][k]);
        fill_roi(rgb,W,&line,shade);
    }
    measure(rgb,W,rois,MAX_ROIS,&c,previous,0,&m);
    CHECK(m.suspicious_rois==0&&m.inconclusive_rois==0,"tilted/illumination gradient inside manual centre ROIs");
    /* Colour borders/other patches outside selected ROIs never enter measurements. */
    for(unsigned y=0;y<H;y++) for(unsigned x=0;x<W;x++) if(x%32<3) memcpy(rgb+((size_t)y*W+x)*3,colors[8],3);
    measure(rgb,W,rois,MAX_ROIS,&c,previous,0,&m);
    CHECK(m.suspicious_rois==0,"scene geometry excluded by explicit centre boxes");
    FILE *f=tmpfile();CHECK(f!=NULL,"ROI parser fixture opened");
    for(unsigned i=0;i<MAX_ROIS;i++) fprintf(f,"%s %u %u %u %u # manual centre\n",names[i],rois[i].x0,rois[i].y0,rois[i].x1,rois[i].y1);
    rewind(f);struct roi parsed[MAX_ROIS];unsigned n=0;
    int rc=parse_rois(f,W,H,parsed,&n,0,error,sizeof(error));fclose(f);
    CHECK(rc==0&&n==9,"nine-name parser accepts valid manual boxes");
    const char *invalid[]={"RED 4 4 28 28\n", "RED -1 0 24 24\n", "RED 4 4 28 28\nRED 40 4 60 24\n", "RED 0 0 30 30\nGREEN 4 4 28 28\n", "UNKNOWN 4 4 28 28\n", "RED 4 4 28 28 junk\n", "RED 4 4 28 5\n"};
    for(unsigned i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++) {
        f=tmpfile();CHECK(f!=NULL,"negative ROI fixture opened");fputs(invalid[i],f);rewind(f);
        rc=parse_rois(f,W,H,parsed,&n,i!=0,error,sizeof(error));fclose(f);
        CHECK(rc<0,"malformed/empty/missing/overlap ROI rejected");
    }
    CHECK(((uint32_t)(0u-UINT32_MAX))==1u,"normal V4L2 sequence uint32 wrap delta");
    free_measurements(MAX_ROIS,&m);
    printf("{\"record\":\"selftest\",\"status\":\"PASS_SOFTWARE_FIXTURES_ONLY\",\"checks\":%u}\n",tests);
    return 0;
fail:
    free_measurements(MAX_ROIS,&m);return 1;
#undef CHECK
}

#ifndef COLOUR_SELFTEST_ONLY
struct buffer { void *p; size_t size; };
static volatile sig_atomic_t stop_requested=0;
static void stop_signal(int signo) { (void)signo;stop_requested=1; }
static double now_seconds(void) {
    struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t)) return -1;
    return (double)t.tv_sec+t.tv_nsec/1e9;
}
static int xio(int fd,unsigned long cmd,void *arg) {
    int rc;do {rc=ioctl(fd,cmd,arg);} while(rc<0&&errno==EINTR);return rc;
}
static int parse_uint(const char *s,unsigned *out) {
    char *end;errno=0;unsigned long v=strtoul(s,&end,10);
    if(errno||!*s||*s=='-'||*end||v>UINT_MAX) return -1;
    *out=(unsigned)v;return 0;
}
static int env_double(const char *name,double *value,double lo,double hi) {
    const char *s=getenv(name);if(!s) return 0;char *end;errno=0;
    double v=strtod(s,&end);
    if(errno||!*s||*end||!isfinite(v)||v<lo||v>hi) {fprintf(stderr,"Invalid %s\n",name);return -1;}
    *value=v;return 0;
}
static int env_uint(const char *name,unsigned *value,unsigned lo,unsigned hi) {
    const char *s=getenv(name);if(!s) return 0;unsigned v;
    if(parse_uint(s,&v)||v<lo||v>hi) {fprintf(stderr,"Invalid %s\n",name);return -1;}
    *value=v;return 0;
}
static void json_string(const char *s) {
    putchar('"');for(const unsigned char *p=(const unsigned char *)s;*p;p++) {
        if(*p=='"'||*p=='\\') {putchar('\\');putchar(*p);}
        else if(*p<32) printf("\\u%04x",*p);else putchar(*p);
    }putchar('"');
}
static int save_frame(const char *prefix,const char *suffix,const void *data,size_t bytes) {
    char path[1024];int written=snprintf(path,sizeof(path),"%s_%s.rgb",prefix,suffix);
    if(written<0||(size_t)written>=sizeof(path)) {errno=ENAMETOOLONG;return -1;}
    /* Evidence is never silently overwritten. Root must use a fresh prefix. */
    int fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0644);if(fd<0) return -1;
    size_t done=0;
    while(done<bytes) {
        ssize_t n=write(fd,(const unsigned char *)data+done,bytes-done);
        if(n<0&&errno==EINTR) continue;
        if(n<=0) {int e=n<0?errno:EIO;close(fd);errno=e;return -1;}done+=(size_t)n;
    }
    return close(fd);
}
static void print_rois(const struct roi rois[MAX_ROIS],unsigned n,const struct measured_frame *m) {
    printf("\"rois\":[");
    for(unsigned i=0;i<n;i++) {
        const struct roi *r=&rois[i];const struct roi_stat *s=&m->rois[i];
        if(i) putchar(',');
        printf("{\"name\":\"%s\",\"box\":[%u,%u,%u,%u],\"pixels\":%llu,\"rgb_mean\":[%.5f,%.5f,%.5f],\"clip0\":[%llu,%llu,%llu],\"clip255\":[%llu,%llu,%llu],\"wrong_rows\":%u,\"inconclusive_rows\":%u,\"jump_rows\":%u,\"temporal_max_delta\":%.5f,\"suspicious\":%s,\"rows\":[",
            names[r->kind],r->x0,r->y0,r->x1,r->y1,(unsigned long long)s->pixels,
            s->mean[0],s->mean[1],s->mean[2],(unsigned long long)s->clipped0[0],(unsigned long long)s->clipped0[1],(unsigned long long)s->clipped0[2],
            (unsigned long long)s->clipped255[0],(unsigned long long)s->clipped255[1],(unsigned long long)s->clipped255[2],
            s->wrong_rows,s->inconclusive_rows,s->jump_rows,s->temporal_max,s->suspicious?"true":"false");
        for(unsigned y=r->y0;y<r->y1;y++) {
            const struct row_stat *row=&s->rows[y-r->y0];if(y>r->y0) putchar(',');
            printf("[%u,%.5f,%.5f,%.5f,%.5f,%.5f,\"%c\",\"%c\"]",y,row->rgb[0],row->rgb[1],row->rgb[2],row->score,row->jump,row->dominant,row->order);
        }
        printf("]}");
    }
    putchar(']');
}
static int capture_main(int argc,char **argv) {
    struct config c=defaults();struct roi rois[MAX_ROIS];struct measured_frame measured;
    struct buffer buffers[8]={{0}};unsigned w,h,target,nrois=0,done=0,bad=0,suspicious=0,inconclusive=0;
    unsigned stable_measured=0,stable_suspicious=0,stable_inconclusive=0,saved_suspicious=0;
    int fd=-1,streaming=0,allocated=0,measurements_allocated=0,failed=0,have_previous=0;
    uint32_t previous_sequence=0;int have_sequence=0;size_t expected=0;
    unsigned char *last_copy=NULL;size_t last_bytes=0;double previous[MAX_ROIS][3]={{0}};
    const char *failure="none";double started=now_seconds(),elapsed=0,timeout;char *end;
    const char *save_mode=getenv("CAPTURE_SAVE_MODE");if(!save_mode) save_mode="bounded";
    if(argc!=8) {
        fprintf(stderr,"usage: %s device width height count fresh_prefix timeout_s ROI.txt\n",argv[0]);return 2;
    }
    errno=0;timeout=strtod(argv[6],&end);
    if(parse_uint(argv[2],&w)||parse_uint(argv[3],&h)||parse_uint(argv[4],&target)||!w||!h||!target||w>16384||h>16384||
       errno||!*argv[6]||*end||!isfinite(timeout)||timeout<=0||started<0) {fprintf(stderr,"Invalid dimensions/count/deadline\n");return 2;}
    if(strcmp(save_mode,"none")&&strcmp(save_mode,"bounded")&&strcmp(save_mode,"all")) {fprintf(stderr,"Invalid CAPTURE_SAVE_MODE\n");return 2;}
    int save=strcmp(save_mode,"none")!=0,all_suspicious=!strcmp(save_mode,"all");
    if(env_double("COLOUR_ORDER_MARGIN",&c.margin,0.001,255)||
       env_double("COLOUR_MIN_BRIGHTNESS",&c.min_brightness,0,255)||
       env_double("COLOUR_MIN_CHROMA",&c.min_chroma,0,255)||
       env_double("COLOUR_ROW_JUMP",&c.row_jump,0.001,255)||
       env_double("COLOUR_TEMPORAL_JUMP",&c.temporal_jump,0.001,255)||
       env_uint("COLOUR_STABLE_FRAMES",&c.stable_frames,0,UINT_MAX)||
       env_uint("COLOUR_MIN_BAD_ROWS",&c.min_bad_rows,1,16384)||
       env_uint("COLOUR_SAVE_EVERY",&c.periodic,0,UINT_MAX)||
       env_uint("COLOUR_ALLOW_PARTIAL",&c.allow_partial,0,1)) return 2;
    FILE *roi_file=fopen(argv[7],"rb");char roi_error[256];
    if(!roi_file) {perror("ROI fopen");return 2;}
    int parsed=parse_rois(roi_file,w,h,rois,&nrois,c.allow_partial,roi_error,sizeof(roi_error));
    int roi_close=fclose(roi_file);
    if(parsed||roi_close) {fprintf(stderr,"ROI rejected: %s\n",parsed?roi_error:"fclose failure");return 2;}
    expected=(size_t)w*h*3;
    if(allocate_measurements(rois,nrois,&measured)) {perror("measurements allocate");return 2;}
    measurements_allocated=1;
    struct sigaction sa;memset(&sa,0,sizeof(sa));sa.sa_handler=stop_signal;sigemptyset(&sa.sa_mask);
    sigaction(SIGINT,&sa,NULL);sigaction(SIGTERM,&sa,NULL);
    struct v4l2_requestbuffers req;memset(&req,0,sizeof(req));
    req.count=4;req.type=V4L2_BUF_TYPE_VIDEO_CAPTURE;req.memory=V4L2_MEMORY_MMAP;
    enum v4l2_buf_type type=req.type;
#define IO_FAIL(label) do {failure=(label);perror(label);failed=1;goto cleanup;} while(0)
    fd=open(argv[1],O_RDWR|O_NONBLOCK);if(fd<0) IO_FAIL("open");
    struct v4l2_format fmt;memset(&fmt,0,sizeof(fmt));fmt.type=req.type;
    fmt.fmt.pix.width=w;fmt.fmt.pix.height=h;fmt.fmt.pix.pixelformat=V4L2_PIX_FMT_RGB24;fmt.fmt.pix.field=V4L2_FIELD_NONE;
    if(xio(fd,VIDIOC_S_FMT,&fmt)<0) IO_FAIL("S_FMT");
    if(fmt.fmt.pix.width!=w||fmt.fmt.pix.height!=h||fmt.fmt.pix.pixelformat!=V4L2_PIX_FMT_RGB24||
       fmt.fmt.pix.bytesperline!=w*3||fmt.fmt.pix.sizeimage!=expected) {errno=EINVAL;IO_FAIL("unsupported negotiated RGB24 stride/size");}
    if(xio(fd,VIDIOC_REQBUFS,&req)<0) IO_FAIL("REQBUFS");
    allocated=1;
    if(req.count<2||req.count>8) {errno=EINVAL;IO_FAIL("unexpected buffer count");}
    size_t biggest=0;
    for(unsigned i=0;i<req.count;i++) {
        struct v4l2_buffer b;memset(&b,0,sizeof(b));b.type=req.type;b.memory=req.memory;b.index=i;
        if(xio(fd,VIDIOC_QUERYBUF,&b)<0) IO_FAIL("QUERYBUF");
        if(b.length<expected) {errno=EINVAL;IO_FAIL("short buffer allocation");}
        buffers[i].size=b.length;
        buffers[i].p=mmap(NULL,b.length,PROT_READ|PROT_WRITE,MAP_SHARED,fd,b.m.offset);
        if(buffers[i].p==MAP_FAILED) {buffers[i].p=NULL;IO_FAIL("mmap");}
        if(b.length>biggest) biggest=b.length;
        if(xio(fd,VIDIOC_QBUF,&b)<0) IO_FAIL("QBUF setup");
    }
    if(save) {last_copy=malloc(biggest);if(!last_copy) IO_FAIL("last frame allocate");}
    printf("{\"record\":\"metadata\",\"device\":");json_string(argv[1]);
    printf(",\"roi_file\":");json_string(argv[7]);
    printf(",\"width\":%u,\"height\":%u,\"target_frames\":%u,\"scope\":\"%s\",\"rgb_byte_order\":\"R,G,B\",\"row_fields\":[\"y\",\"R_mean\",\"G_mean\",\"B_mean\",\"expected_order_score\",\"adjacent_max_channel_jump\",\"dominant\",\"order_status\"],\"thresholds\":{\"order_margin\":%.5f,\"min_brightness\":%.5f,\"min_chroma\":%.5f,\"row_jump\":%.5f,\"temporal_jump\":%.5f,\"min_bad_rows\":%u,\"stable_frames\":%u},\"save_mode\":\"%s\",\"save_every\":%u}\n",
        w,h,target,nrois==9?"nine_manual_chart_rois":"EXPLICIT_PARTIAL_ROIS",c.margin,c.min_brightness,c.min_chroma,c.row_jump,c.temporal_jump,c.min_bad_rows,c.stable_frames,save_mode,c.periodic);
    fflush(stdout);
    if(xio(fd,VIDIOC_STREAMON,&type)<0) IO_FAIL("STREAMON");
    streaming=1;
    while(done<target&&!stop_requested&&now_seconds()-started<timeout) {
        struct pollfd p={fd,POLLIN,0};int rc=poll(&p,1,1000);
        if(rc<0&&errno==EINTR) continue;
        if(rc<0) IO_FAIL("poll");
        if(!rc) continue;
        if(!(p.revents&POLLIN)&&(p.revents&(POLLERR|POLLHUP|POLLNVAL))) {errno=EIO;IO_FAIL("poll device error");}
        struct v4l2_buffer b;memset(&b,0,sizeof(b));b.type=req.type;b.memory=req.memory;
        if(xio(fd,VIDIOC_DQBUF,&b)<0) {if(errno==EAGAIN) continue;IO_FAIL("DQBUF");}
        if(b.index>=req.count||b.bytesused>buffers[b.index].size) {errno=EOVERFLOW;IO_FAIL("invalid DQBUF index/bytesused");}
        int transport_bad=b.bytesused!=expected||(b.flags&V4L2_BUF_FLAG_ERROR);
        uint32_t seq_delta=have_sequence?(uint32_t)(b.sequence-previous_sequence):1;
        int seq_gap=have_sequence&&seq_delta!=1;
        previous_sequence=b.sequence;have_sequence=1;bad+=transport_bad||seq_gap;
        int warmup=done<c.stable_frames,flag=transport_bad||seq_gap,unknown=transport_bad;
        unsigned char *data=buffers[b.index].p;
        if(!transport_bad) {
            measure(data,w,rois,nrois,&c,previous,have_previous,&measured);
            flag|=measured.suspicious_rois>0;unknown|=measured.inconclusive_rois>0;
            for(unsigned i=0;i<nrois;i++) memcpy(previous[i],measured.rois[i].mean,sizeof(previous[i]));
            have_previous=1;
        } else have_previous=0;
        suspicious+=flag;inconclusive+=unknown;
        if(!warmup) {stable_measured+=!transport_bad;stable_suspicious+=flag;stable_inconclusive+=unknown;}
        printf("{\"record\":\"frame\",\"frame\":%u,\"sequence\":%u,\"sequence_delta\":%u,\"sequence_gap\":%s,\"bytesused\":%u,\"expected_bytes\":%zu,\"v4l2_error\":%s,\"seconds\":%.6f,\"warmup\":%s,\"transport_bad\":%s,\"suspicious\":%s,\"inconclusive\":%s,",
            done,b.sequence,seq_delta,seq_gap?"true":"false",b.bytesused,expected,(b.flags&V4L2_BUF_FLAG_ERROR)?"true":"false",now_seconds()-started,warmup?"true":"false",transport_bad?"true":"false",flag?"true":"false",unknown?"true":"false");
        if(!transport_bad) print_rois(rois,nrois,&measured);else printf("\"rois\":null");
        printf("}\n");fflush(stdout);
        if(ferror(stdout)) {errno=EIO;IO_FAIL("stdout JSON write");}
        if(save) {
            char suffix[64];memcpy(last_copy,data,b.bytesused);last_bytes=b.bytesused;
            if(done==0&&save_frame(argv[5],"first",data,b.bytesused)) IO_FAIL("save first");
            if(c.periodic&&done%c.periodic==0) {
                snprintf(suffix,sizeof(suffix),"periodic%06u",done);
                if(save_frame(argv[5],suffix,data,b.bytesused)) IO_FAIL("save periodic");
            }
            if(flag&&(all_suspicious||saved_suspicious<8)) {
                snprintf(suffix,sizeof(suffix),"suspect%06u",done);
                if(save_frame(argv[5],suffix,data,b.bytesused)) IO_FAIL("save suspect");
                saved_suspicious++;
            }
        }
        done++;
        if(xio(fd,VIDIOC_QBUF,&b)<0) IO_FAIL("QBUF running");
    }
cleanup:
    if(streaming&&xio(fd,VIDIOC_STREAMOFF,&type)<0) {perror("STREAMOFF");failed=1;failure="STREAMOFF";}
    for(unsigned i=0;i<8;i++) if(buffers[i].p&&munmap(buffers[i].p,buffers[i].size)) {perror("munmap");failed=1;failure="munmap";}
    if(allocated&&fd>=0) {
        req.count=0;
        if(xio(fd,VIDIOC_REQBUFS,&req)<0) {perror("REQBUFS release");failed=1;failure="REQBUFS release";}
    }
    if(fd>=0&&close(fd)) {perror("close");failed=1;failure="close";}
    if(save&&last_copy&&done>0&&save_frame(argv[5],"last",last_copy,last_bytes)) {perror("save last");failed=1;failure="save last";}
    free(last_copy);if(measurements_allocated) free_measurements(nrois,&measured);
    elapsed=now_seconds()-started;
    const char *status=failed?"INPUT_OR_IO_ERROR":(done!=target||bad?"CAPTURE_INCOMPLETE_OR_TRANSPORT_ERROR":"CAPTURE_COMPLETE_MEASUREMENTS_ONLY");
    printf("{\"record\":\"summary\",\"status\":\"%s\",\"colour_acceptance\":\"REQUIRES_REVIEW_OF_EVERY_FRAME\",\"failure\":",status);json_string(failure);
    printf(",\"done\":%u,\"target\":%u,\"transport_or_sequence_bad_frames\":%u,\"suspicious_frames\":%u,\"inconclusive_frames\":%u,\"stable_measured_frames\":%u,\"stable_suspicious_frames\":%u,\"stable_inconclusive_frames\":%u,\"saved_suspicious_frames\":%u,\"interrupted\":%s,\"seconds\":%.6f}\n",
        done,target,bad,suspicious,inconclusive,stable_measured,stable_suspicious,stable_inconclusive,saved_suspicious,stop_requested?"true":"false",elapsed);
    fflush(stdout);
    fprintf(stderr,"COLOUR_CAPTURE_RESULT status=%s done=%u/%u bad=%u suspicious=%u inconclusive=%u stable_measured=%u seconds=%.3f (measurement only, no colour PASS)\n",status,done,target,bad,suspicious,inconclusive,stable_measured,elapsed);
    return failed||done!=target||bad?2:0;
#undef IO_FAIL
}
#endif
int main(int argc,char **argv) {
    if(argc==2&&!strcmp(argv[1],"--self-test")) return self_test();
#ifdef COLOUR_SELFTEST_ONLY
    fprintf(stderr,"This binary contains only shared measurement self-tests; Linux V4L2 backend was not compiled.\n");
    return 2;
#else
    return capture_main(argc,argv);
#endif
}
