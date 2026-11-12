/* Time-weighted semantic target selection. GPL-2.0-or-later.
 * Header-only, no GTK/model dependency; parity-tested against semantic_selection.py. */
#ifndef FREECIV_DEMO_SELECTION_H
#define FREECIV_DEMO_SELECTION_H
#include <math.h>
#include <string.h>
#define DS_MAX 64
struct ds_target { int kind,id,arg; double x,y; };
struct ds_state {
  struct ds_target targets[DS_MAX];
  double scores[DS_MAX],mass,stamp,since,x,y,confidence,margin;
  int n,pick,hover,candidate,count,have_stamp,ready;
};
static void ds_reset(struct ds_state *s) {
  memset(s->scores,0,sizeof(s->scores));s->mass=0;s->have_stamp=0;
  s->pick=s->hover=s->candidate=-1;s->count=s->ready=0;s->confidence=s->margin=0;
}
static int ds_key(struct ds_target a,struct ds_target b) {
  return a.kind==b.kind && a.id==b.id && a.arg==b.arg;
}
static void ds_sync(struct ds_state *s,const struct ds_target *targets,int n) {
  int indices[DS_MAX],changed=n!=s->n,oldpick=s->pick,oldcandidate=s->candidate,oldhover=s->hover;
  double scores[DS_MAX];
  if(n<0 || n>DS_MAX) {s->n=0;ds_reset(s);return;}
  for(int i=0;i<n;i++) {
    indices[i]=-1;
    for(int j=0;j<s->n;j++) if(ds_key(targets[i],s->targets[j])) {indices[i]=j;break;}
    if(indices[i]<0 || fabs(targets[i].x-s->targets[indices[i]].x)>2 ||
       fabs(targets[i].y-s->targets[indices[i]].y)>2) changed=1;
    scores[i]=indices[i]<0?0:s->scores[indices[i]];
  }
  if(changed) ds_reset(s);
  else {
    s->pick=s->candidate=s->hover=-1;
    for(int i=0;i<n;i++) {
      if(indices[i]==oldpick) s->pick=i;
      if(indices[i]==oldcandidate) s->candidate=i;
      if(indices[i]==oldhover) s->hover=i;
    }
    memcpy(s->scores,scores,n*sizeof(double));
  }
  memcpy(s->targets,targets,n*sizeof(*targets));s->n=n;
}
static void ds_sample(struct ds_state *s,double x,double y,double stamp,double now,int filtered) {
  if(!isfinite(x)||!isfinite(y)||!isfinite(stamp)||!isfinite(now)||now<stamp||now-stamp>.25) {ds_reset(s);return;}
  if(s->have_stamp && stamp<=s->stamp) return;
  if(s->have_stamp && stamp-s->stamp>.25) ds_reset(s);
  double dt=s->have_stamp?stamp-s->stamp:0;
  if(!s->have_stamp || filtered) {s->x=x;s->y=y;}
  else {double a=-expm1(-dt/.045);s->x+=a*(x-s->x);s->y+=a*(y-s->y);}
  s->stamp=stamp;s->have_stamp=1;s->ready=0;
  double best=1e30,second=1e30;int winner=-1;
  for(int i=0;i<s->n;i++) {
    double dx=s->targets[i].x-s->x,dy=s->targets[i].y-s->y,d=dx*dx+dy*dy;
    if(d<best) {second=best;best=d;winner=i;} else if(d<second) second=d;
  }
  if(winner<0) {ds_reset(s);return;}
  double spacing=1e30;
  for(int i=0;i<s->n;i++) if(i!=winner) {
    double d=hypot(s->targets[i].x-s->targets[winner].x,s->targets[i].y-s->targets[winner].y);
    if(d<spacing) spacing=d;
  }
  if(s->n==1) spacing=200.;
  double radius=fmax(36.,fmin(180.,spacing*.9));
  int usable=(second-best)/(second+1.)>=.08 && best<=radius*radius;
  s->hover=usable?winner:-1;
  double decay=exp(-dt/.18),weight=-expm1(-(dt>0?dt:1./30)/.18);
  for(int i=0;i<s->n;i++) s->scores[i]*=decay;
  s->mass=s->mass*decay+weight;
  if(usable) s->scores[winner]+=weight;
  double runner=0;
  for(int i=0;i<s->n;i++) if(i!=winner && s->scores[i]>runner) runner=s->scores[i];
  s->confidence=s->mass>0?s->scores[winner]/s->mass:0;
  s->margin=s->mass>0?(s->scores[winner]-runner)/s->mass:0;
  if(!usable || s->confidence<.60 || s->margin<.12) {s->candidate=-1;s->count=0;return;}
  if(s->candidate!=winner) {s->candidate=winner;s->since=stamp;s->count=1;} else s->count++;
  if(s->count>=3 && stamp-s->since>=.12-1e-9) {s->pick=winner;s->ready=1;}
}
static int ds_confirmable(const struct ds_state *s,double now) {
  return s->ready && s->pick>=0 && s->have_stamp && now>=s->stamp && now-s->stamp<=.25;
}
static int ds_preview(const struct ds_state *s,double now) {
  return s->have_stamp && now>=s->stamp && now-s->stamp<=.25?s->hover:-1;
}
#endif
