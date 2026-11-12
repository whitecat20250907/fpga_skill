#include <stdlib.h>
#include "demo_selection.h"
#include "demo_input_parse.h"
void *selection_new(void) {struct ds_state *s=calloc(1,sizeof(*s));ds_reset(s);return s;}
void selection_free(void *s) {free(s);}
void selection_reset(void *s) {ds_reset(s);}
void selection_sync(void *s,double *rows,int n) {
  struct ds_target t[64];
  for(int i=0;i<n;i++) t[i]=(struct ds_target){(int)rows[i*5],(int)rows[i*5+1],(int)rows[i*5+2],rows[i*5+3],rows[i*5+4]};
  ds_sync(s,t,n);
}
void selection_sample(void *s,double x,double y,double stamp,double now,int filtered) {ds_sample(s,x,y,stamp,now,filtered);}
int selection_confirm(void *s,double now) {return ds_confirmable(s,now);}
int selection_preview(void *s,double now) {return ds_preview(s,now);}
void selection_read(void *ptr,double *v) {
  struct ds_state *s=ptr;v[0]=s->pick;v[1]=s->ready;v[2]=s->confidence;v[3]=s->margin;v[4]=s->x;v[5]=s->y;
}
int parse_source(const char *text,long long now) {gint64 stamp;double x,y;return demo_parse_gaze2(text,now,&stamp,&x,&y);}
